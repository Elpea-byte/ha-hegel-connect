"""Client for the local API of Hegel streaming amplifiers (H150, H200, H400, H600).

This module has no Home Assistant dependencies so it can later move to its own
package on PyPI. It talks to the same HTTP API the amplifier's built-in web app
uses:

* ``GET  /api/getData?path=...``   read a value
* ``GET  /api/getRows?path=...``   read a list (inputs, radio favorites, ...)
* ``POST /api/setData``            write a value or trigger an action
* ``POST /api/event/modifyQueue``  subscribe to paths, returns a queue id
* ``GET  /api/event/pollQueue``    long-poll: returns as soon as something changes
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import ipaddress
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

PATH_POWER = "powermanager:target"
PATH_GO_ONLINE = "powermanager:goOnline"
PATH_GO_STANDBY = "powermanager:goNetworkStandby"
PATH_VOLUME = "player:volume"
PATH_MUTE = "settings:/mediaPlayer/mute"
PATH_SOURCE = "hegel:activePhysicalSource"
PATH_SOURCES = "hegel:listPhysicalSources"
PATH_VOLUME_TYPE = "settings:/hegel/volumeType"
PATH_PLAYER = "player:player/data"
# Position in ms. Not subscribed (changes several times a second); read after player events.
PATH_PLAY_TIME = "player:player/data/playTime"
PATH_PLAY_MODE = "player:player/data/playMode"
PATH_CONTROL = "player:player/control"
# Resume a paused Spotify Connect session. A bare "play" control breaks it
# ("Directory is empty"); this is the "Resume Playback" action of the Spotify UI.
PATH_SPOTIFY_RESUME = "spotify:/ui/resume"
PATH_PRODUCT_NAME = "settings:/system/productName"
PATH_DEVICE_NAME = "settings:/deviceName"
PATH_MEMBER = "systemmanager:systemMember"
PATH_FIRMWARE = "settings:/version"
PATH_AIRABLE_ROOT = "airable:"
PATH_PLAY_HISTORY = "ui:/playHistory"
PATH_MEDIA_SERVERS = "ui:/upnp"
PATH_USB = "musiclibrary:/usbFolder"

EVENT_PATHS: tuple[str, ...] = (
    PATH_POWER,
    PATH_VOLUME,
    PATH_MUTE,
    PATH_SOURCE,
    PATH_VOLUME_TYPE,
    PATH_PLAYER,
    PATH_PLAY_MODE,
)

# Play modes as the amplifier names them (shuffle x repeat).
PLAY_MODES: dict[tuple[bool, str], str] = {
    (False, "off"): "normal",
    (True, "off"): "shuffle",
    (False, "one"): "repeatOne",
    (True, "one"): "shuffleRepeatOne",
    (False, "all"): "repeatAll",
    (True, "all"): "shuffleRepeatAll",
}


def play_mode_parts(mode: str | None) -> tuple[bool, str]:
    """(shuffle, repeat) of a play mode; repeat is "off", "one" or "all"."""
    for parts, name in PLAY_MODES.items():
        if name == mode:
            return parts
    return False, "off"


LOSSY_CODECS = ("mp3", "mpeg", "aac", "ogg", "vorbis", "opus", "wma")
LOSSLESS_CODECS = ("flac", "alac", "wav", "pcm", "aiff", "lpcm", "mqa")

POWER_ONLINE = "online"
POWER_STANDBY = "networkStandby"
NETWORK_SOURCE_NAME = "Network"


class HegelError(Exception):
    """Generic error returned by the amplifier."""


class HegelConnectionError(HegelError):
    """The amplifier could not be reached."""


class HegelQueueLost(HegelError):
    """The event queue no longer exists on the amplifier (e.g. after a reboot)."""


def unwrap(value: Any) -> Any:
    """Turn a typed API value into a plain Python value.

    ``{"type": "i32_", "i32_": 5}`` -> ``5``; ``{"type": "bool_", "bool_": True}``
    -> ``True``; ``{"type": "powerTarget", "powerTarget": {...}}`` -> ``{...}``.
    Values without a type marker (player data) are returned unchanged.
    """
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        kind = value.get("type")
        if isinstance(kind, str) and kind in value:
            return value[kind]
    return value


@dataclass(slots=True)
class HegelSource:
    """A physical input of the amplifier."""

    index: int
    name: str


def _dig(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


@dataclass(slots=True)
class PlayerData:
    """What the streamer is doing (parsed from ``player:player/data``)."""

    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def state(self) -> str | None:
        """playing, paused, stopped, transitioning or buffering."""
        return self.raw.get("state")

    @property
    def _meta(self) -> dict[str, Any]:
        return (
            _dig(self.raw, "trackRoles", "mediaData", "metaData")
            or _dig(self.raw, "mediaRoles", "mediaData", "metaData")
            or {}
        )

    @property
    def title(self) -> str | None:
        return _dig(self.raw, "trackRoles", "title") or _dig(self.raw, "mediaRoles", "title") or None

    @property
    def artist(self) -> str | None:
        return self._meta.get("artist") or None

    @property
    def album(self) -> str | None:
        return self._meta.get("album") or None

    @property
    def service(self) -> str | None:
        return self._meta.get("serviceName") or None

    @property
    def playback_source(self) -> str | None:
        """What the track plays from: a playlist or album (e.g. "New Dance 2026")."""
        value = self._meta.get("playbackSource")
        return value if isinstance(value, str) and value else None

    @property
    def media_id(self) -> str | None:
        """Id of what is playing (e.g. a radio station); matches the id of a favorites row."""
        media_id = _dig(self.raw, "mediaRoles", "id")
        return str(media_id) if media_id else None

    @property
    def is_radio(self) -> bool:
        return bool(self._meta.get("radioStation"))

    @property
    def image_url(self) -> str | None:
        for icon in (_dig(self.raw, "trackRoles", "icon"), _dig(self.raw, "mediaRoles", "icon")):
            if isinstance(icon, str) and icon.startswith(("http://", "https://")):
                return icon
        return None

    def play_mode_allowed(self, mode: str) -> bool:
        """Whether the current source allows a play mode (controls.playMode), e.g. "shuffle"."""
        controls = self.raw.get("controls")
        modes = controls.get("playMode") if isinstance(controls, dict) else None
        return mode == "normal" or (isinstance(modes, dict) and bool(modes.get(mode)))

    def control_allowed(self, name: str) -> bool:
        """Whether the current service allows a control (e.g. "next_", "previous").

        A missing flag means not allowed, like the amplifier's own web client:
        Spotify Connect only reports {"pause": true} and answers next/previous
        with "Control is not supported".
        """
        controls = self.raw.get("controls")
        return isinstance(controls, dict) and bool(controls.get(name))

    @property
    def _resource(self) -> dict[str, Any]:
        return _dig(self.raw, "trackRoles", "mediaData", "activeResource") or {}

    @property
    def duration(self) -> int | None:
        """Track length in seconds; None for radio and unknown."""
        ms = _dig(self.raw, "status", "duration")
        return round(ms / 1000) if isinstance(ms, (int, float)) and ms > 0 else None

    @property
    def short_codec(self) -> str | None:
        """Codec name only (e.g. "FLAC", or the AirPlay badge), for the codec sensor."""
        res = self._resource
        return res.get("shortCodec") or res.get("codec") or _dig(res, "quality", "airplayBadging") or None

    @property
    def sample_rate(self) -> float | None:
        """kHz."""
        rate = self._resource.get("sampleFrequency")
        return rate / 1000 if isinstance(rate, (int, float)) and rate > 0 else None

    @property
    def bit_depth(self) -> int | None:
        bits = self._resource.get("bitsPerSample")
        return int(bits) if isinstance(bits, (int, float)) and bits > 0 else None

    @property
    def bitrate(self) -> int | None:
        """kbit/s."""
        rate = self._resource.get("bitRate") or self._resource.get("nominalBitRate")
        return round(rate / 1000) if isinstance(rate, (int, float)) and rate > 0 else None

    @property
    def quality(self) -> str | None:
        """hi_res, cd, lossless, lossy or dsd.

        The codec decides first: internet radio (MP3 16-bit/48 kHz) is lossy, not
        CD quality. Spotify reports no format, only whether it streams lossless.
        """
        res = self._resource
        if not res:
            return None
        spotify = _dig(res, "quality", "spotifyHifi")
        if spotify is not None and not res.get("shortCodec") and not res.get("codec"):
            return "lossless" if spotify else "lossy"
        # AirPlay (e.g. Apple Music) labels the stream itself, like the web client shows.
        badge = str(_dig(res, "quality", "airplayBadging") or "").lower()
        if "hi-res" in badge or "hires" in badge:
            return "hi_res"
        if "lossless" in badge:
            return "lossless"
        codec = str(res.get("shortCodec") or res.get("codec") or res.get("mimeType") or "").lower()
        if "dsd" in codec or "dsf" in codec or "dff" in codec:
            return "dsd"
        if any(tag in codec for tag in LOSSY_CODECS):
            return "lossy"
        if _dig(res, "quality", "qobuzHiRes"):
            return "hi_res"
        bits, rate = self.bit_depth, res.get("sampleFrequency") or 0
        if any(tag in codec for tag in LOSSLESS_CODECS):
            if (bits and bits > 16) or rate > 48000:
                return "hi_res"
            if bits == 16:
                return "cd"
            return "lossless"
        return None

    @property
    def codec(self) -> str | None:
        """Display label with codec and format, e.g. "FLAC · 24-bit/96kHz" (audio_format attribute)."""
        resource = self._resource
        parts = []
        codec = resource.get("shortCodec")
        if _dig(resource, "quality", "spotifyHifi"):
            codec = "Lossless"
        elif _dig(resource, "quality", "airplayBadging"):
            codec = _dig(resource, "quality", "airplayBadging")
        if codec:
            parts.append(str(codec))
        if resource.get("bitsPerSample") and resource.get("sampleFrequency"):
            khz = float(resource["sampleFrequency"]) / 1000
            parts.append(f"{resource['bitsPerSample']}-bit/{khz:g}kHz")
        return " · ".join(parts) or None


@dataclass(slots=True)
class HegelState:
    """Current state of the amplifier."""

    power: str | None = None
    volume: int | None = None
    muted: bool | None = None
    source_index: int | None = None
    volume_fixed: bool | None = None
    player: PlayerData = field(default_factory=PlayerData)
    # normal, shuffle, repeatOne, repeatAll, shuffleRepeatOne, shuffleRepeatAll
    play_mode: str | None = None
    # Last streaming service seen (player data can lose it while paused).
    last_service: str | None = None
    # Playback position (seconds) and when it was read.
    position: int | None = None
    position_at: datetime | None = None

    def set_play_time(self, value: Any) -> None:
        ms = unwrap(value)
        if isinstance(ms, (int, float)) and ms >= 0 and self.player.duration:
            self.position = round(ms / 1000)
            self.position_at = datetime.now(UTC)
        else:
            self.position = None
            self.position_at = None

    @property
    def is_on(self) -> bool:
        return self.power == POWER_ONLINE

    def apply_event(self, path: str, value: Any) -> bool:
        """Apply a push event. Returns True if something we track changed."""
        if path == PATH_POWER:
            data = unwrap(value)
            target = data.get("target") if isinstance(data, dict) else None
            if target:
                self.power = target
            return True
        if path == PATH_VOLUME:
            self.volume = int(unwrap(value))
            return True
        if path == PATH_MUTE:
            self.muted = bool(unwrap(value))
            return True
        if path == PATH_SOURCE:
            self.source_index = int(unwrap(value))
            return True
        if path == PATH_VOLUME_TYPE:
            self.volume_fixed = int(unwrap(value)) == 1
            return True
        if path == PATH_PLAY_MODE:
            mode = unwrap(value)
            self.play_mode = mode if isinstance(mode, str) else None
            return True
        if path == PATH_PLAYER:
            data = unwrap(value)
            if isinstance(data, dict) and "playLogicData" in data:
                data = data["playLogicData"]
            self.player = PlayerData(data if isinstance(data, dict) else {})
            if self.player.service:
                self.last_service = self.player.service
            return True
        return False


def play_request(track: dict[str, Any], parent: dict[str, Any] | None, index: int) -> dict[str, Any]:
    """The play command of the Hegel web client (player:player/control).

    Inside a playable folder (album, playlist, play history) the folder goes along
    as mediaRoles with type "itemInContainer", so the amplifier keeps playing the
    next items. Radio stations (audioBroadcast) are always played on their own.
    """
    media: dict[str, Any] = track
    kind: str | None = None
    if (
        parent
        and track.get("audioType") != "audioBroadcast"
        and parent.get("type") == "container"
        and parent.get("containerPlayable")
    ):
        media, kind = parent, "itemInContainer"
    return {"control": "play", "mediaRoles": media, "trackRoles": track, "type": kind, "index": index}


def url_host(host: str) -> str:
    """Host as it goes into a URL: IPv6 addresses need square brackets."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    return f"[{host.replace('%', '%25')}]" if address.version == 6 else host


class HegelClient:
    """Async client for one amplifier."""

    def __init__(self, host: str, session: aiohttp.ClientSession, request_timeout: float = 10) -> None:
        self.host = host
        self.base_url = f"http://{url_host(host)}"
        self._session = session
        self._timeout = request_timeout

    # ---------------------------------------------------------------- basics

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self.base_url}/api/{endpoint}"
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout or self._timeout),
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    if endpoint == "event/pollQueue":
                        raise HegelQueueLost(text[:200])
                    raise HegelError(f"{endpoint} {resp.status}: {text[:200]}")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HegelConnectionError(f"{self.host}: {err!r}") from err
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError as err:
            raise HegelError(f"{endpoint}: invalid JSON") from err

    async def get_raw(self, path: str, roles: str = "@all") -> Any:
        """Full getData answer (value, title, edit range, ...)."""
        return await self._request("GET", "getData", params={"path": path, "roles": roles})

    async def get_value(self, path: str) -> Any:
        """Plain value of a path."""
        data = await self._request("GET", "getData", params={"path": path, "roles": "value"})
        if isinstance(data, dict) and "value" in data:
            data = data["value"]
        return unwrap(data)

    async def get_rows(self, path: str, start: int = 0, count: int = 50) -> dict[str, Any]:
        """A list on the amplifier (inputs, favorites, browse folders)."""
        data = await self._request(
            "GET",
            "getRows",
            params={"path": path, "roles": "@all", "from": str(start), "to": str(start + count)},
        )
        return data if isinstance(data, dict) else {}

    async def set_value(self, path: str, value: dict[str, Any]) -> None:
        """Write a typed value (e.g. {"type": "i32_", "i32_": 20}) to a path."""
        await self._request("POST", "setData", payload={"path": path, "role": "value", "value": value})

    async def activate(self, path: str, value: dict[str, Any] | None = None, **extra: Any) -> None:
        """Trigger an action path (power, play, ...); ``extra`` adds keys to the request like the web client."""
        payload = {"path": path, "role": "activate", "value": value or {}, **extra}
        await self._request("POST", "setData", payload=payload)

    # ------------------------------------------------------------ device info

    async def product_name(self) -> str:
        """Model as reported by the amplifier, e.g. "H150"."""
        name = await self.get_value(PATH_PRODUCT_NAME)
        if not isinstance(name, str) or not name.strip():
            raise HegelError("No product name reported")
        return name.strip()

    async def device_name(self) -> str | None:
        """Name given to the amplifier in the Hegel app (None if not set)."""
        try:
            name = await self.get_value(PATH_DEVICE_NAME)
        except HegelError:
            return None
        return str(name) if name else None

    async def unique_id(self) -> str | None:
        """Stable id of the amplifier, e.g. "hegelh600-<uuid>".

        The StreamSDK system member id. The same id is announced as the "uuid" TXT
        record of the _sues800device mDNS service, so discovery can match it before
        connecting. Falls back to the id in the player data.
        """
        try:
            member = await self.get_value(PATH_MEMBER)
        except HegelConnectionError:
            raise
        except HegelError:
            member = None
        if isinstance(member, dict) and isinstance(member.get("systemMember"), dict):
            member = member["systemMember"]
        member_id = member.get("id") if isinstance(member, dict) else None
        if isinstance(member_id, str) and member_id:
            return member_id
        try:
            data = await self.get_value(PATH_PLAYER)
        except HegelError:
            return None
        player_id = _dig(data, "playId", "systemMemberId")
        return player_id if isinstance(player_id, str) and player_id else None

    async def firmware(self) -> str | None:
        """Firmware version for the device info (None if not readable)."""
        try:
            version = await self.get_value(PATH_FIRMWARE)
        except HegelError:
            return None
        return str(version) if version else None

    async def sources(self) -> list[HegelSource]:
        """The inputs as (index, name), in the amplifier's order."""
        data = await self.get_rows(PATH_SOURCES)
        result: list[HegelSource] = []
        for row in data.get("rows", []):
            if isinstance(row, dict):
                name, value = row.get("title"), row.get("value")
            elif isinstance(row, list) and len(row) >= 2:
                name, value = row[0], row[1]
            else:
                continue
            index = unwrap(value)
            if isinstance(name, str) and isinstance(index, int):
                result.append(HegelSource(index, name))
        return result

    async def volume_max(self) -> int:
        """Upper end of the volume range as reported by the amplifier."""
        try:
            data = await self.get_raw(PATH_VOLUME)
            return int(_dig(data, "edit", "max") or 100)
        except (HegelError, ValueError, TypeError):
            return 100

    async def play_time(self) -> Any:
        """Position in the current track (typed value, milliseconds); not pushed, read on demand."""
        return await self.get_value(PATH_PLAY_TIME)

    async def fetch_state(self) -> HegelState:
        """Read everything once (used at start-up and after reconnecting)."""
        state = HegelState()
        state.apply_event(PATH_POWER, await self.get_value(PATH_POWER))
        for path in (PATH_VOLUME, PATH_MUTE, PATH_SOURCE, PATH_VOLUME_TYPE):
            try:
                state.apply_event(path, await self.get_value(path))
            except HegelConnectionError:
                raise
            except (HegelError, ValueError, TypeError) as err:
                _LOGGER.debug("Path %s not available: %s", path, err)
        if state.is_on:
            # In network standby this path does not return valid data.
            try:
                state.apply_event(PATH_PLAYER, await self.get_value(PATH_PLAYER))
                if state.player.duration:
                    state.set_play_time(await self.get_value(PATH_PLAY_TIME))
            except HegelConnectionError:
                raise
            except HegelError as err:
                _LOGGER.debug("Player data not available: %s", err)
            try:
                state.apply_event(PATH_PLAY_MODE, await self.get_value(PATH_PLAY_MODE))
            except HegelConnectionError:
                raise
            except HegelError as err:
                _LOGGER.debug("Play mode not available: %s", err)
        return state

    # --------------------------------------------------------------- commands

    async def power_on(self) -> None:
        """Wake the amplifier from network standby."""
        await self.activate(PATH_GO_ONLINE)

    async def power_off(self) -> None:
        """Put the amplifier in network standby (it stays reachable)."""
        await self.activate(PATH_GO_STANDBY)

    async def set_volume(self, volume: int) -> None:
        """Set the volume in the amplifier's own steps (0..volume_max)."""
        await self.set_value(PATH_VOLUME, {"type": "i32_", "i32_": int(volume)})

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        await self.set_value(PATH_MUTE, {"type": "bool_", "bool_": bool(mute)})

    async def set_source(self, index: int) -> None:
        """Select an input by its index (see sources()); no retry, see the coordinator."""
        await self.set_value(PATH_SOURCE, {"type": "i32_", "i32_": int(index)})

    async def control(self, command: str) -> None:
        """play, pause, next or previous."""
        await self.activate(PATH_CONTROL, {"control": command})

    async def seek(self, position_ms: int) -> None:
        """Jump to a position in the current track, in milliseconds (like the web client's progress bar)."""
        await self.activate(PATH_CONTROL, {"control": "seekTime", "time": max(0, int(position_ms))})

    async def set_play_mode(self, mode: str) -> None:
        """Shuffle/repeat, as the web client does: one of the PLAY_MODES names."""
        await self.activate(PATH_CONTROL, {"control": "changePlayMode", "playMode": mode})

    async def resume_spotify(self) -> None:
        """Resume a paused Spotify Connect session."""
        await self.activate(PATH_SPOTIFY_RESUME, {})

    async def play_path(self, path: str) -> None:
        """Play a browse item by its path.

        A track plays directly. A folder (radio favorite, album, playlist, USB
        folder) plays from its first item; albums and folders then continue
        with the next tracks.
        """
        try:
            item = await self.get_raw(path)
        except HegelError:
            item = None
        if isinstance(item, dict) and item.get("type") not in (None, "container"):
            await self._play(item, None, 0)
            return
        await self.play_in_container(path, 0, item if isinstance(item, dict) else None)

    async def play_in_container(self, path: str, index: int, parent: dict[str, Any] | None = None) -> None:
        """Play item number `index` of a folder, and continue with the rest."""
        detail = await self.get_rows(path, index, 1)
        rows = [row for row in detail.get("rows", []) if isinstance(row, dict)]
        if not rows:
            raise HegelError(f"Nothing playable at {path}")
        if parent is None:
            roles = detail.get("roles")
            if isinstance(roles, dict) and roles.get("containerPlayable"):
                parent = roles
            else:
                try:
                    raw = await self.get_raw(path)
                except HegelError:
                    raw = None
                parent = raw if isinstance(raw, dict) else None
        await self._play(rows[0], parent, index)

    async def _play(self, track: dict[str, Any], parent: dict[str, Any] | None, index: int) -> None:
        """Send the play command (see play_request)."""
        # Same request as the Hegel web client (including "platform"), live-tested
        # with radio favorites and media server albums.
        await self.activate(PATH_CONTROL, play_request(track, parent, index), platform="windows")

    async def favorites_path(self) -> str:
        """The radio favorites folder (its path contains a per-device Airable id)."""
        root = await self.get_rows(PATH_AIRABLE_ROOT, 0, 10)
        rows = [r for r in root.get("rows", []) if isinstance(r, dict)]
        radios = next((r.get("path") for r in rows if str(r.get("path", "")).endswith("/radios")), None)
        if radios is None:
            raise HegelError("No radio section found")
        return f"{radios}/favorites"

    async def favorites(self) -> list[dict[str, Any]]:
        """Radio favorites as saved in the Hegel Control app: title, icon, path, id."""
        data = await self.get_rows(await self.favorites_path(), 0, 50)
        result = []
        for row in data.get("rows", []):
            if not isinstance(row, dict) or not row.get("path") or not row.get("title"):
                continue
            icon = row.get("icon")
            result.append(
                {
                    "title": row["title"],
                    "path": row["path"],
                    "id": row.get("id"),
                    "icon": icon if isinstance(icon, str) and icon.startswith(("http://", "https://")) else None,
                }
            )
        return result

    # ------------------------------------------------------------------ push

    async def subscribe(self, paths: tuple[str, ...] = EVENT_PATHS) -> str:
        """Create an event queue for the given paths."""
        queue_id = await self._request(
            "POST",
            "event/modifyQueue",
            payload={
                "queueId": "",
                "subscribe": [{"path": p, "type": "itemWithValue"} for p in paths],
                "unsubscribe": [],
            },
        )
        if not isinstance(queue_id, str) or not queue_id:
            raise HegelError(f"Unexpected modifyQueue answer: {queue_id!r}")
        return queue_id

    async def poll(self, queue_id: str, timeout: int = 30) -> list[dict[str, Any]]:
        """Wait up to ``timeout`` seconds for events."""
        data = await self._request(
            "GET",
            "event/pollQueue",
            params={"queueId": queue_id, "timeout": str(timeout)},
            timeout=timeout + 15,
        )
        return [event for event in data or [] if isinstance(event, dict)]


# Older Hegel amplifiers (H95, H120, H190(V), H390, H590, Röst) have no web API but
# speak Hegel's IP control protocol on TCP 50001. They belong in Home Assistant's
# built-in "hegel" integration; recognising them lets setup say so.
IP_CONTROL_PORT = 50001


async def async_has_ip_control(host: str, timeout: float = 3) -> bool:
    """True if the device answers an IP control power query ("-p.?") on port 50001.

    Read-only: the query only asks for the power state. Older models reply
    "-p.0"/"-p.1" (or "-e.x" on an error). Anything else, or no reply, is False.
    """
    writer = None
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, IP_CONTROL_PORT)
            writer.write(b"-p.?\r")
            await writer.drain()
            reply = await reader.readuntil(b"\r")
    except Exception:  # noqa: BLE001 - any failure simply means "not an older Hegel"
        return False
    finally:
        if writer is not None:
            writer.close()
    return reply.startswith((b"-p.", b"-e."))

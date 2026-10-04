"""Client for the local API of Hegel streaming amplifiers (H150, H400, H600).

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

from dataclasses import dataclass, field
from datetime import UTC, datetime
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

EVENT_PATHS: tuple[str, ...] = (
    PATH_POWER,
    PATH_VOLUME,
    PATH_MUTE,
    PATH_SOURCE,
    PATH_VOLUME_TYPE,
    PATH_PLAYER,
)

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
        res = self._resource
        return res.get("shortCodec") or res.get("codec") or None

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
        resource = _dig(self.raw, "trackRoles", "mediaData", "activeResource") or {}
        parts = []
        codec = resource.get("shortCodec")
        if _dig(resource, "quality", "spotifyHifi"):
            codec = "Lossless"
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
            target = (unwrap(value) or {}).get("target")
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
        if path == PATH_PLAYER:
            data = unwrap(value)
            if isinstance(data, dict) and "playLogicData" in data:
                data = data["playLogicData"]
            self.player = PlayerData(data if isinstance(data, dict) else {})
            return True
        return False


class HegelClient:
    """Async client for one amplifier."""

    def __init__(self, host: str, session: aiohttp.ClientSession, request_timeout: float = 10) -> None:
        self.host = host
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
        url = f"http://{self.host}/api/{endpoint}"
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
        await self._request("POST", "setData", payload={"path": path, "role": "value", "value": value})

    async def activate(self, path: str, value: dict[str, Any] | None = None) -> None:
        await self._request("POST", "setData", payload={"path": path, "role": "activate", "value": value or {}})

    # ------------------------------------------------------------ device info

    async def product_name(self) -> str:
        return str(await self.get_value(PATH_PRODUCT_NAME))

    async def device_name(self) -> str | None:
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
        if isinstance(member, dict) and isinstance(member.get("id"), str) and member["id"]:
            return member["id"]
        try:
            data = await self.get_value(PATH_PLAYER)
        except HegelError:
            return None
        player_id = _dig(data, "playId", "systemMemberId")
        return player_id if isinstance(player_id, str) and player_id else None

    async def firmware(self) -> str | None:
        try:
            version = await self.get_value(PATH_FIRMWARE)
        except HegelError:
            return None
        return str(version) if version else None

    async def sources(self) -> list[HegelSource]:
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
        return state

    # --------------------------------------------------------------- commands

    async def power_on(self) -> None:
        await self.activate(PATH_GO_ONLINE)

    async def power_off(self) -> None:
        await self.activate(PATH_GO_STANDBY)

    async def set_volume(self, volume: int) -> None:
        await self.set_value(PATH_VOLUME, {"type": "i32_", "i32_": int(volume)})

    async def set_mute(self, mute: bool) -> None:
        await self.set_value(PATH_MUTE, {"type": "bool_", "bool_": bool(mute)})

    async def set_source(self, index: int) -> None:
        await self.set_value(PATH_SOURCE, {"type": "i32_", "i32_": int(index)})

    async def control(self, command: str) -> None:
        """play, pause, next or previous."""
        await self.activate(PATH_CONTROL, {"control": command})

    async def resume_spotify(self) -> None:
        """Resume a paused Spotify Connect session."""
        await self.activate(PATH_SPOTIFY_RESUME, {})

    async def play_path(self, path: str) -> None:
        """Play a browse item (e.g. a radio favorite) by its path.

        Favorites are containers; the playable item is the first row inside.
        """
        detail = await self.get_rows(path, 0, 5)
        rows = [row for row in detail.get("rows", []) if isinstance(row, dict)]
        if not rows:
            raise HegelError(f"Nothing playable at {path}")
        row = rows[0]
        await self.activate(
            PATH_CONTROL,
            {"control": "play", "mediaRoles": row, "trackRoles": row, "type": None, "index": 0},
        )

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

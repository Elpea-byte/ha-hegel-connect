"""Media player entity for Hegel Connect."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime
import ipaddress
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .api import (
    NETWORK_SOURCE_NAME,
    PATH_AIRABLE_ROOT,
    PATH_MEDIA_SERVERS,
    PATH_PLAY_HISTORY,
    PATH_USB,
    PLAY_MODES,
    HegelError,
    play_mode_parts,
)
from .const import DOMAIN
from .coordinator import HegelCoordinator
from .entity import HegelEntity

if TYPE_CHECKING:
    from homeassistant.components.media_player.browse_media import SearchMedia, SearchMediaQuery

# Commands go one at a time to the amplifier; state comes from the coordinator (push).
PARALLEL_UPDATES = 1

MEDIA_TYPE_HEGEL = "hegel_path"
ROOT_ID = "root"
FAVORITES_ID = "favorites"
# A track inside a folder: "track:<index>:<folder path>", so it plays with the rest of the folder
TRACK_PREFIX = "track:"
BROWSE_PAGE = 100
BROWSE_MAX = 1000
# Media server folders that hold no music (the amplifier only plays audio)
_NON_AUDIO_TITLES = {
    "photo",
    "photos",
    "pictures",
    "picture",
    "video",
    "videos",
    "movies",
    "foto",
    "fotos",
    "foto's",
    "video's",
    "films",
    "bilder",
    "filme",
}

# Titles of the top-level browse folders
_ROOT_TITLES = {
    FAVORITES_ID: "Radio favorites",
    PATH_AIRABLE_ROOT: "Internet radio",
    PATH_MEDIA_SERVERS: "Media servers",
    PATH_USB: "USB",
    PATH_PLAY_HISTORY: "Recently played",
}

# Search filters: these mean podcasts, these internet radio (no filter searches radio too).
_PODCAST_CLASSES = {MediaClass.PODCAST, MediaClass.EPISODE}
_RADIO_CLASSES = {MediaClass.CHANNEL, MediaClass.MUSIC}
# Airable marks podcasts, their episode lists and episodes with this service id.
_PODCAST_SERVICE = "airablePodcasts"
# Airable paths of a podcast (".../feed/<id>"), its episode list and its episodes (".../feed.episode/<id>").
_FEED = re.compile(r"/feed/[^/]+$")


def _is_podcast_path(path: str) -> bool:
    return "/feed/" in path or "/feed.episode/" in path


def _service(row: Any) -> Any:
    media_data = row.get("mediaData") if isinstance(row, dict) else None
    meta = media_data.get("metaData") if isinstance(media_data, dict) else None
    return meta.get("serviceID") if isinstance(meta, dict) else None


def _is_podcast_folder(folder: dict[str, Any], rows: list[Any]) -> bool:
    """A podcast or its episode list (the folder says so, or else its rows do)."""
    return _service(folder) == _PODCAST_SERVICE or any(_service(row) == _PODCAST_SERVICE for row in rows)


# Search in the media browser exists from a newer Home Assistant on; older ones simply do not offer it.
_SEARCH = getattr(MediaPlayerEntityFeature, "SEARCH_MEDIA", MediaPlayerEntityFeature(0))

_PLAYER_STATES = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "buffering": MediaPlayerState.BUFFERING,
    "transitioning": MediaPlayerState.BUFFERING,
}


def _is_public_https(url: str | None) -> bool:
    """True for an https picture on a public host (not an IP on the local network, not a local name)."""
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    if parts.scheme.lower() != "https" or not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host and not host.endswith((".local", ".lan", ".home", ".internal", ".localdomain"))
    return address.is_global


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelMediaPlayer(entry.runtime_data)])


class HegelMediaPlayer(HegelEntity, MediaPlayerEntity):
    """The amplifier and its built-in streamer."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    # Static or double (the volume is also the volume_level) and changing often: not worth a row in the recorder.
    _unrecorded_attributes = frozenset({"input_names", "fixed_volume", "max_volume", "can_pause", "volume_raw"})
    _attr_volume_step = 0.02
    _BASE_FEATURES = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "media_player")

    # ------------------------------------------------------------------ state

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Next/previous only when the current service allows it (not Spotify, not radio)."""
        features = self._BASE_FEATURES | _SEARCH
        data = self.coordinator.data
        if self._playing_network():
            if data.player.control_allowed("next_"):
                features |= MediaPlayerEntityFeature.NEXT_TRACK
            if data.player.control_allowed("previous"):
                features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
            # Seeking only where the amplifier allows it (media server, USB; not Spotify or radio)
            if data.player.control_allowed("seekTime"):
                features |= MediaPlayerEntityFeature.SEEK
            # Shuffle / repeat only where the source offers them (media server, USB)
            if data.player.play_mode_allowed("shuffle"):
                features |= MediaPlayerEntityFeature.SHUFFLE_SET
            if data.player.play_mode_allowed("repeatOne") or data.player.play_mode_allowed("repeatAll"):
                features |= MediaPlayerEntityFeature.REPEAT_SET
            # Stop ends the stream (radio). Not for Spotify Connect: like a bare
            # "play" it would drop the session with the phone.
            if (data.player.service or data.last_service) != "Spotify" and data.player.state in (
                "playing",
                "paused",
                "buffering",
                "transitioning",
            ):
                features |= MediaPlayerEntityFeature.STOP
        return features

    @property
    def _max_volume(self) -> int:
        """User ceiling (number entity) within the amplifier's own range."""
        ceiling = int(self.coordinator.max_volume)
        return max(1, min(ceiling, self.coordinator.volume_max))

    @property
    def state(self) -> MediaPlayerState | None:
        data = self.coordinator.data
        if not data.is_on or not self.coordinator.connected:
            return MediaPlayerState.OFF
        if self.coordinator.source_name(data.source_index) == NETWORK_SOURCE_NAME:
            return _PLAYER_STATES.get(data.player.state or "", MediaPlayerState.IDLE)
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        volume = self.coordinator.data.volume
        return None if volume is None else volume / self.coordinator.volume_max

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.muted

    @property
    def source(self) -> str | None:
        return self.coordinator.source_label(self.coordinator.data.source_index)

    @property
    def source_list(self) -> list[str]:
        return [self.coordinator.source_label(s.index) or s.name for s in self.coordinator.visible_sources]

    def _pause_stops(self) -> bool:
        """Live radio has no pause; there pause stops the stream, like the web client.

        Only for radio: a service that reports no pause flag (AirPlay, Google Cast)
        keeps a real pause, so its session is not ended.
        """
        player = self.coordinator.data.player
        return self._playing_network() and player.is_radio and not player.control_allowed("pause")

    def _playing_network(self) -> bool:
        data = self.coordinator.data
        return (
            data.is_on
            and self.coordinator.connected
            and self.coordinator.source_name(data.source_index) == NETWORK_SOURCE_NAME
        )

    @property
    def media_title(self) -> str | None:
        return self.coordinator.data.player.title if self._playing_network() else None

    @property
    def media_artist(self) -> str | None:
        return self.coordinator.data.player.artist if self._playing_network() else None

    @property
    def media_album_name(self) -> str | None:
        return self.coordinator.data.player.album if self._playing_network() else None

    @property
    def media_content_id(self) -> str | None:
        """The Spotify URI of the track (spotify:track:...) while Spotify plays, so it can be started again."""
        return self.coordinator.data.player.spotify_track_uri if self._playing_network() else None

    @property
    def media_playlist(self) -> str | None:
        """The playlist or album the track plays from, as the service reports it."""
        return self.coordinator.data.player.playback_source if self._playing_network() else None

    @property
    def media_image_url(self) -> str | None:
        return self.coordinator.data.player.image_url if self._playing_network() else None

    @property
    def media_duration(self) -> int | None:
        return self.coordinator.data.player.duration if self._playing_network() else None

    @property
    def media_position(self) -> int | None:
        return self.coordinator.data.position if self._playing_network() else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        return self.coordinator.data.position_at if self._playing_network() else None

    @property
    def app_name(self) -> str | None:
        return self.coordinator.data.player.service if self._playing_network() else None

    @property
    def media_content_type(self) -> MediaType | str | None:
        if not self._playing_network():
            return None
        return MediaType.CHANNEL if self.coordinator.data.player.is_radio else MediaType.MUSIC

    @property
    def media_channel(self) -> str | None:
        player = self.coordinator.data.player
        return player.station if self._playing_network() and player.is_radio else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Only public https pictures go to the browser directly.

        Radio logos come over plain http and a NAS picture sits on the local network: Home Assistant fetches
        those itself, so they also show over https (Nabu Casa, a certificate) and outside the house. That
        includes https on a local address, which the browser would not reach from outside either.
        """
        return _is_public_https(self.media_image_url)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "fixed_volume": data.volume_fixed,
            # Live radio has no pause: media_pause stops it instead (Home Assistant
            # needs PAUSE for media_play_pause, so the feature stays on).
            "can_pause": not self._pause_stops(),
            "service": data.player.service if self._playing_network() else None,
            "media_id": data.player.media_id if self._playing_network() else None,
            "audio_format": data.player.codec if self._playing_network() else None,
            "volume_raw": data.volume,
            "max_volume": self._max_volume,
            # Shown name -> amplifier name, so cards can keep icons for renamed inputs.
            "input_names": {
                self.coordinator.source_label(s.index) or s.name: s.name for s in self.coordinator.visible_sources
            },
        }

    # --------------------------------------------------------------- commands

    async def _run(self, coro: Awaitable[Any]) -> None:
        """Run a command; turn amplifier errors into a (translated) Home Assistant error."""
        try:
            await coro
        except HegelError as err:
            raise _command_failed(err) from err

    async def async_turn_on(self) -> None:
        await self._run(self.coordinator.client.power_on())

    async def async_turn_off(self) -> None:
        await self._run(self.coordinator.client.power_off())

    async def async_set_volume_level(self, volume: float) -> None:
        if self.coordinator.data.volume_fixed:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="fixed_volume")
        raw = round(volume * self.coordinator.volume_max)
        target = max(0, min(raw, self._max_volume))
        current = self.coordinator.data.volume
        # The limit keeps Home Assistant from making it louder. The knob and the remote are not limited, so the
        # amplifier can already be above it: then "louder" must do nothing, not turn it down to the limit.
        if current is not None and raw > current and target <= current:
            return
        await self._run(self.coordinator.client.set_volume(target))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.coordinator.client.set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        name = self.coordinator.source_name_for(source)
        if name is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_source",
                translation_placeholders={"source": source},
            )
        await self._run(self.coordinator.async_select_source(name))

    async def async_media_play(self) -> None:
        """Resume, the way the Hegel web client does it.

        A bare "play" without a track answers "Directory is empty" and stops the
        session (seen with Spotify Connect, Qobuz Connect and media servers, #17).
        The web client resumes a paused stream by sending "pause" again (it is a
        toggle) and offers nothing to resume when the player is stopped. Spotify
        Connect keeps its own resume action. After live radio (which stops instead
        of pausing) play starts the same favorite again. Only on the network input: on any other input
        there is nothing to resume.
        """
        data = self.coordinator.data
        client = self.coordinator.client
        if not self._playing_network():
            # Another input (the TV, a turntable) or standby: resuming would switch the amplifier away from it,
            # or pull a Spotify session over from another device. Start music on purpose instead.
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nothing_to_resume")
        if (data.player.service or data.last_service) == "Spotify":
            await self._run(client.resume_spotify())
            return
        if data.player.state == "paused":
            await self._run(client.control("pause"))
            return
        if data.player.state in ("playing", "buffering", "transitioning"):
            return  # already playing
        if radio_path := self.coordinator.last_radio_path():
            # Live radio cannot pause, so stopping it left nothing to resume: start the same station again
            # (a favorite, or a station Home Assistant started from search or the media browser).
            await self._run(client.play_path(radio_path))
            return
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nothing_to_resume")

    async def async_media_stop(self) -> None:
        await self._run(self.coordinator.client.control("stop"))

    async def async_media_pause(self) -> None:
        """Pause; where the service has no pause (live radio) stop, like the web client."""
        if self._pause_stops():
            await self._run(self.coordinator.client.control("stop"))
            return
        await self._run(self.coordinator.client.control("pause"))

    async def async_media_next_track(self) -> None:
        await self._run(self.coordinator.client.control("next"))

    async def async_media_previous_track(self) -> None:
        await self._run(self.coordinator.client.control("previous"))

    @property
    def shuffle(self) -> bool | None:
        if not self._playing_network():
            return None
        return play_mode_parts(self.coordinator.data.play_mode)[0]

    @property
    def repeat(self) -> RepeatMode | None:
        if not self._playing_network():
            return None
        return RepeatMode(play_mode_parts(self.coordinator.data.play_mode)[1])

    async def async_set_shuffle(self, shuffle: bool) -> None:
        repeat = play_mode_parts(self.coordinator.data.play_mode)[1]
        await self._set_play_mode(shuffle, repeat)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        shuffle = play_mode_parts(self.coordinator.data.play_mode)[0]
        await self._set_play_mode(shuffle, str(repeat.value))

    async def _set_play_mode(self, shuffle: bool, repeat: str) -> None:
        """Send a shuffle/repeat combination, if the current source allows exactly that one."""
        mode = PLAY_MODES[(shuffle, repeat)]
        if not self.coordinator.data.player.play_mode_allowed(mode):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="play_mode_not_allowed",
                translation_placeholders={"mode": mode},
            )
        await self._run(self.coordinator.client.set_play_mode(mode))

    async def async_media_seek(self, position: float) -> None:
        """Jump to a position in seconds; show it at once, check it shortly after."""
        position_ms = round(position * 1000)
        await self._run(self.coordinator.client.seek(position_ms))
        self.coordinator.position_seeked(position_ms)

    async def async_search_media(self, query: SearchMediaQuery) -> SearchMedia:
        """Search internet radio and podcasts on the amplifier.

        Without a filter, or with a filter for stations (channel, music), internet radio is searched (Assist
        plays the first result, so "play Qmusic" keeps starting the station). Podcasts are searched when the
        filter asks for podcasts or episodes; with both in the filter, radio comes first. Other filters (album,
        artist, track) find nothing: the amplifier cannot search those. A podcast is a folder: open it to pick
        an episode, or play its episode list.
        """
        from homeassistant.components.media_player.browse_media import SearchMedia

        classes = set(query.media_filter_classes or [])
        want_podcasts = bool(classes & _PODCAST_CLASSES)
        want_radio = not classes or bool(classes & _RADIO_CLASSES)
        results: list[BrowseMedia] = []
        errors: list[HegelError] = []
        if want_radio:
            try:
                results.extend(await self._search_radio(query.search_query))
            except _SearchPartial as partial:
                results.extend(partial.found)
                errors.append(partial.error)
        if want_podcasts:
            try:
                rows = await self.coordinator.client.search_airable("podcast", query.search_query)
            except HegelError as err:
                errors.append(err)
            else:
                items = (_child(row, PATH_AIRABLE_ROOT, index, {}) for index, row in enumerate(rows))
                results.extend(item for item in items if item is not None)
        if errors and not results:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="search_failed",
                translation_placeholders={"error": str(errors[0])},
            ) from errors[0]
        return SearchMedia(result=results)

    async def _search_radio(self, text: str) -> list[BrowseMedia]:
        """Matching radio favorites first, then the stations the amplifier finds (raises _SearchPartial)."""
        # The favorites that match come first (Assist plays the first result: "play Qmusic" then starts the
        # favorite), then everything the amplifier finds in all radio, without the favorites twice.
        needle = text.strip().casefold()
        favorites = [
            fav for fav in self.coordinator.favorites if needle and fav["title"] and needle in fav["title"].casefold()
        ]
        results: list[BrowseMedia] = [
            BrowseMedia(
                media_class=MediaClass.CHANNEL,
                media_content_id=str(fav["path"]),
                media_content_type=MEDIA_TYPE_HEGEL,
                title=str(fav["title"]),
                can_play=True,
                can_expand=False,
                thumbnail=fav["icon"],
            )
            for fav in favorites
        ]
        known = {fav["id"] for fav in favorites if fav["id"]}
        try:
            rows = await self.coordinator.client.search_airable("radio", text)
        except HegelError as err:
            raise _SearchPartial(results, err) from err
        for index, row in enumerate(rows):
            if row.get("id") in known:
                continue
            if (item := _child(row, PATH_AIRABLE_ROOT, index, {})) is not None:
                results.append(item)
        return results

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        if media_id in (ROOT_ID, FAVORITES_ID, PATH_MEDIA_SERVERS, PATH_USB):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_playable")
        client = self.coordinator.client
        if media_id.startswith(TRACK_PREFIX):
            index, _, folder = media_id[len(TRACK_PREFIX) :].partition(":")
            if not index.isdecimal() or not folder:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_media",
                    translation_placeholders={"media_id": media_id},
                )
            await self._run(client.play_in_container(folder, int(index)))
            return
        if media_id.startswith(PATH_AIRABLE_ROOT) and not _is_podcast_path(media_id):
            # Noted before sending, so play after a stop can start it again: the amplifier can report the new
            # station while play_path is still waiting for its answer.
            self.coordinator.radio_started(media_id)
        try:
            await self._run(client.play_path(media_id))
        except HomeAssistantError:
            self.coordinator.radio_not_started(media_id)
            raise

    # ------------------------------------------------------------- browsing

    async def async_browse_media(
        self, media_content_type: MediaType | str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Radio favorites, internet radio, media servers, USB and recently played."""
        if media_content_id is None or media_content_id == ROOT_ID:
            return await self._browse_root()
        path = media_content_id
        try:
            if path == FAVORITES_ID:
                path = await self.coordinator.client.favorites_path()
            folder, rows = await self._rows(path)
        except HegelError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="browse_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        on_server = path.endswith("?itemType=server")
        if on_server:
            # The server calls its own top folder "Root"; show the server's name
            servers = await self._rows_safe(PATH_MEDIA_SERVERS)
            name = next((r.get("title") for r in servers if r.get("path") == path), None)
            if name:
                folder = {**folder, "title": name}
        children = []
        for index, row in enumerate(rows):
            if on_server and str(row.get("title", "")).strip().lower() in _NON_AUDIO_TITLES:
                continue
            if (child := _child(row, path, index, folder)) is not None:
                children.append(child)
        # A folder with tracks in it (album, playlist) can be played as a whole
        has_tracks = any(isinstance(r, dict) and r.get("type") == "audio" for r in rows)
        playable = has_tracks and not path.startswith(PATH_AIRABLE_ROOT) and media_content_id != FAVORITES_ID
        media_class = MediaClass.ALBUM if playable else MediaClass.DIRECTORY
        if path.startswith(PATH_AIRABLE_ROOT) and _is_podcast_folder(folder, rows):
            # An opened podcast; its episode list plays as a whole too, like it does one level up.
            playable = has_tracks or bool(folder.get("containerPlayable"))
            if _FEED.search(path):
                media_class = MediaClass.PODCAST
        return BrowseMedia(
            media_class=media_class,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_HEGEL,
            title=folder.get("title") or _ROOT_TITLES.get(media_content_id) or "Hegel",
            can_play=playable,
            can_expand=True,
            children=children,
        )

    async def _browse_root(self) -> BrowseMedia:
        children = [
            _folder(FAVORITES_ID, _ROOT_TITLES[FAVORITES_ID]),
            _folder(PATH_AIRABLE_ROOT, _ROOT_TITLES[PATH_AIRABLE_ROOT]),
        ]
        # Media servers and USB only when the amplifier sees something there
        servers, usb = await asyncio.gather(self._has_rows(PATH_MEDIA_SERVERS), self._has_rows(PATH_USB))
        if servers:
            children.append(_folder(PATH_MEDIA_SERVERS, _ROOT_TITLES[PATH_MEDIA_SERVERS]))
        if usb:
            children.append(_folder(PATH_USB, _ROOT_TITLES[PATH_USB]))
        children.append(_folder(PATH_PLAY_HISTORY, _ROOT_TITLES[PATH_PLAY_HISTORY]))
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=ROOT_ID,
            media_content_type=MEDIA_TYPE_HEGEL,
            title=self.coordinator.config_entry.title,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _has_rows(self, path: str) -> bool:
        try:
            data = await self.coordinator.client.get_rows(path, 0, 1)
        except HegelError:
            return False
        return any(isinstance(r, dict) and r.get("type") != "action" for r in data.get("rows", []))

    async def _rows_safe(self, path: str) -> list[dict[str, Any]]:
        try:
            data = await self.coordinator.client.get_rows(path, 0, BROWSE_PAGE)
        except HegelError:
            return []
        return [r for r in data.get("rows", []) if isinstance(r, dict)]

    async def _rows(self, path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """The folder itself and all its rows (large libraries are read in pages)."""
        client = self.coordinator.client
        data = await client.get_rows(path, 0, BROWSE_PAGE)
        rows = [r for r in data.get("rows", []) if isinstance(r, dict)]
        total = data.get("rowsCount")
        while isinstance(total, int) and len(rows) < min(total, BROWSE_MAX):
            more = await client.get_rows(path, len(rows), BROWSE_PAGE)
            page = [r for r in more.get("rows", []) if isinstance(r, dict)]
            if not page:
                break
            rows.extend(page)
        roles = data.get("roles")
        folder: dict[str, Any] = roles if isinstance(roles, dict) else {}
        if path.startswith(("upnp:", "musiclibrary:", "playhistory:", "ui:/playHistory")) and not folder.get("title"):
            try:
                raw = await client.get_raw(path)
            except HegelError:
                raw = None
            if isinstance(raw, dict):
                folder = {**raw, **folder} if folder else raw
        return folder, rows


class _SearchPartial(Exception):
    """A search failed on the amplifier after some results (the matching favorites) were already known."""

    def __init__(self, found: list[BrowseMedia], error: HegelError) -> None:
        super().__init__(str(error))
        self.found = found
        self.error = error


def _command_failed(err: HegelError) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="command_failed",
        translation_placeholders={"error": str(err)},
    )


def _folder(content_id: str, title: str) -> BrowseMedia:
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=content_id,
        media_content_type=MEDIA_TYPE_HEGEL,
        title=title,
        can_play=False,
        can_expand=True,
    )


def _child(row: Any, parent_path: str, index: int, parent: dict[str, Any]) -> BrowseMedia | None:
    if not isinstance(row, dict) or not row.get("path") or not row.get("title"):
        return None
    kind = row.get("type")
    if kind in ("action", "image", "video"):
        return None
    if row["path"].startswith(PATH_AIRABLE_ROOT) and row["path"].rstrip("/").endswith("/search"):
        # The search node opens a form the browser cannot show: searching is done with search_media.
        return None
    if row["path"].startswith("hegel:"):
        # Placeholders of the amplifier itself (e.g. "hegel:emptyServer" while it
        # still looks for media servers): nothing to open or play.
        return None
    media_data = row.get("mediaData")
    meta = media_data.get("metaData") if isinstance(media_data, dict) else None
    if not isinstance(meta, dict):
        meta = {}
    icon = row.get("icon") or meta.get("albumArtUri") or meta.get("albumArtURI")
    thumbnail = icon if isinstance(icon, str) and icon.startswith(("http://", "https://")) else None
    broadcast = row.get("audioType") == "audioBroadcast"
    if row["path"].startswith(PATH_AIRABLE_ROOT) and meta.get("serviceID") == _PODCAST_SERVICE:
        # Podcasts: a podcast opens to "Episodes", a list that opens (pick an episode) and also plays as a
        # whole (from the newest); an episode plays. Seen on an H150, where the whole list played.
        is_folder = kind == "container"
        row_id = str(row.get("id") or "")
        if kind == "audio":
            media_class = MediaClass.EPISODE
        elif "/feed/" in row_id:
            media_class = MediaClass.PODCAST
        else:
            media_class = MediaClass.DIRECTORY
        # An episode plays as item <index> of its episode list (the amplifier cannot open an episode on its
        # own path), and the list then goes on with the next episodes, as in the Hegel web client.
        in_list = kind == "audio" and parent_path != PATH_AIRABLE_ROOT
        return BrowseMedia(
            media_class=media_class,
            media_content_id=f"{TRACK_PREFIX}{index}:{parent_path}" if in_list else row["path"],
            media_content_type=MEDIA_TYPE_HEGEL,
            title=row["title"],
            can_play=bool(row.get("containerPlayable")) or kind == "audio",
            can_expand=is_folder,
            thumbnail=thumbnail,
        )
    if row["path"].startswith(PATH_AIRABLE_ROOT) or broadcast:
        # Internet radio and favorites: stations are containers that play directly
        is_folder = kind == "container"
        playable = bool(row.get("containerPlayable")) or kind == "audio"
        return BrowseMedia(
            media_class=MediaClass.CHANNEL if broadcast else (MediaClass.DIRECTORY if is_folder else MediaClass.MUSIC),
            media_content_id=row["path"],
            media_content_type=MEDIA_TYPE_HEGEL,
            title=row["title"],
            can_play=playable,
            can_expand=is_folder and not playable,
            thumbnail=thumbnail,
        )
    if kind not in ("container", "audio"):
        return None  # text rows and other non-media items
    if kind == "container":
        # Albums, artists, folders: open to see the tracks (and play the album there)
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=row["path"],
            media_content_type=MEDIA_TYPE_HEGEL,
            title=row["title"],
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail,
        )
    # A track: inside a playable folder it plays with the rest of that folder
    in_folder = parent.get("containerPlayable") or parent_path.startswith(("upnp:", "musiclibrary:"))
    return BrowseMedia(
        media_class=MediaClass.TRACK,
        media_content_id=f"{TRACK_PREFIX}{index}:{parent_path}" if in_folder else row["path"],
        media_content_type=MEDIA_TYPE_HEGEL,
        title=row["title"],
        can_play=True,
        can_expand=False,
        thumbnail=thumbnail,
    )

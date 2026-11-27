"""Now-playing event: fires when a new track starts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import HegelConfigEntry
from .api import ACTIVE_STATES, NETWORK_SOURCE_NAME
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 0

EVENT_TRACK_CHANGED = "track_changed"
# Seconds to wait for the rest of a new track's details (the first report of a track often lacks the
# audio quality or the album: seen in the H150 recording and with podcasts on an H150).
EVENT_SETTLE = 1.5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelNowPlaying(entry.runtime_data)])


# Some stations send these as the title around their commercials: markers, not songs.
AD_MARKERS = frozenset({"commercial-in", "commercial-out", "ad break"})
# What the amplifier shows while it plays a link from outside (an announcement through the DLNA renderer).
LINK_TITLES = frozenset({"home assistant", "upnp renderer"})
MEDIA_SERVERS = "media servers"
# Stations with a name shorter than this are not checked for jingles ("Radio" would hide "Radio Ga Ga").
JINGLE_MIN_NAME = 5
# A capitalised last part that is no artist: "Song - LIVE" stays "Artist - Title".
VERSION_WORDS = frozenset(
    {"live", "remix", "intro", "edit", "radio edit", "acoustic", "remastered", "instrumental", "extended", "version"}
)


def _track_key(player: Any) -> tuple[str | None, ...]:
    """What makes a track: Spotify has no media id, but a track URI (two versions with one title are two)."""
    return (player.title, player.artist, player.album, player.service, player.spotify_track_uri or player.media_id)


def _same_track(old: tuple[str | None, ...], new: tuple[str | None, ...]) -> bool:
    """The same track, or the same one with details that were missing before (an album, an artist)."""
    return all(before is None or before == after for before, after in zip(old, new, strict=True))


def _complete(player: Any) -> bool:
    """Everything a new track reports has arrived (Spotify never reports a codec, radio has no album)."""
    if player.service == "Spotify":
        return True
    return player.quality is not None and (player.album is not None or player.is_radio)


def _is_no_track(player: Any) -> bool:
    """The text the amplifier shows is no song: the station itself, a commercial marker, a station jingle or a link."""
    title = player.title.casefold()
    station = (player.station or "").casefold()
    if title == station or title in AD_MARKERS:
        return True
    if len(station) >= JINGLE_MIN_NAME and title.startswith(f"{station} "):
        return True  # "Qmusic nieuws"
    return (player.service or "").casefold() == MEDIA_SERVERS and title in LINK_TITLES


class HegelNowPlaying(HegelEntity, EventEntity):
    """One ``track_changed`` event per track, with the details the amplifier reports.

    For a listening log, scrobbling through another integration or a notification.
    It fires when the amplifier says "playing" for a track it has not played yet, so
    the quality details are there. Pause and resume do not fire it, and neither does
    the same track playing on (repeat). A track that played before starts a new event
    when something else, or nothing, played in between. A track that is already
    playing when Home Assistant starts or reconnects is not announced.

    Internet radio: a start only shows the station name as the title, and the song
    follows a moment later. The station name is not a track, so the event comes with
    the song title (``Artist - Title`` is split into artist and title; the station is
    in ``station``). A station that never reports a song title gives no events.

    The first report of a new track can come without its audio quality or album: the event then waits up
    to EVENT_SETTLE seconds for them and fires once, with what is known by then. Details that arrive after
    the event do not fire it again. Spotify never reports a codec, so it fires at once.

    Disabled until you enable it: each event stores the track in the recorder.
    """

    _attr_translation_key = "now_playing"
    # Every track lands in the Home Assistant database: only when you ask for it.
    _attr_entity_registry_enabled_default = False
    # Stays available while the amplifier is gone: coming back from unavailable would look like a
    # new event to a plain state trigger, every night the power strip switches off.
    _follows_connection = False

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "now_playing")
        self._attr_event_types = [EVENT_TRACK_CHANGED]
        # Which track was announced last; None while nothing plays on the network input.
        self._track: tuple[str | None, ...] | None = None
        # The first state read after the entity is added only tells what plays now.
        self._seen_state = False
        # A new track that waits for its details (cancel callback), see EVENT_SETTLE.
        self._pending: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_pending)

    def _cancel_pending(self) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._observe()
        super()._handle_coordinator_update()

    def _observe(self) -> None:
        coordinator = self.coordinator
        if not coordinator.connected:
            return  # the data is old: keep what was seen, so a reconnect does not announce the same track again
        announce, self._seen_state = self._seen_state, True
        data = coordinator.data
        player = data.player
        if (
            not data.is_on
            or coordinator.source_name(data.source_index) != NETWORK_SOURCE_NAME
            or player.state not in ACTIVE_STATES
        ):
            self._track = None
            self._cancel_pending()
            return
        if player.state != "playing" or not player.title or _is_no_track(player):
            return  # starting up, paused, or a radio station that has not reported a song yet
        track = _track_key(player)
        if self._track is not None and _same_track(self._track, track):
            # The same track, perhaps with more details: no new event (a waiting one fires once complete).
            self._track = track
            if self._pending is not None and _complete(player):
                self._fire()
            return
        self._track = track
        self._cancel_pending()
        if not announce:
            return
        if _complete(player):
            self._fire()
        else:
            self._pending = async_call_later(self.hass, EVENT_SETTLE, self._settled)

    @callback
    def _settled(self, _now: datetime) -> None:
        self._pending = None
        player = self.coordinator.data.player
        # Still that track (a skip in the meantime has its own wait): fire with what is known now.
        if (
            self._track is not None
            and player.state == "playing"
            and player.title
            and _same_track(self._track, _track_key(player))
        ):
            self._fire()

    def _fire(self) -> None:
        self._cancel_pending()
        self._trigger_event(EVENT_TRACK_CHANGED, self._event_data())
        self.async_write_ha_state()

    def _event_data(self) -> dict[str, Any]:
        coordinator = self.coordinator
        data = coordinator.data
        player = data.player
        title, artist = player.title, player.artist
        if player.is_radio and not artist and title and " - " in title:
            # Radio stations send "Artist - Title" as one text.
            first, second = (part.strip() for part in title.split(" - ", 1))
            # Most stations send "Artist - Title"; Qmusic sends "Title - ARTIST" with the artist in capitals.
            swapped = second.isupper() and not first.isupper() and second.casefold() not in VERSION_WORDS
            artist, title = (second, first) if swapped else (first, second)
        return {
            "title": title,
            "artist": artist,
            "album": player.album,
            "image_url": player.image_url,
            "service": player.service,
            "spotify_uri": player.spotify_track_uri,
            "spotify_album_uri": player.spotify_album_uri,
            "spotify_artist_uri": player.spotify_artist_uri,
            "spotify_playlist_uri": player.spotify_playlist_uri,
            "station": player.station,
            "source": coordinator.source_label(data.source_index),
            "audio_quality": player.quality,
            "codec": player.short_codec,
            "sample_rate": player.sample_rate,
            "bit_depth": player.bit_depth,
            "bitrate": player.bitrate,
            "is_radio": player.is_radio,
            "duration": player.duration,
            "playback_source": player.playback_source,
        }

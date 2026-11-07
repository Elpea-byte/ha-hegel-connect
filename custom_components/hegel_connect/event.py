"""Now-playing event: fires when a new track starts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .api import ACTIVE_STATES, NETWORK_SOURCE_NAME
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 0

EVENT_TRACK_CHANGED = "track_changed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelNowPlaying(entry.runtime_data)])


class HegelNowPlaying(HegelEntity, EventEntity):
    """One ``track_changed`` event per track, with the details the amplifier reports.

    For a listening log, scrobbling through another integration or a notification.
    It fires when the amplifier says "playing" for a track it has not played yet, so
    the quality details are there. Pause and resume do not fire it, and neither does
    the same track playing on (repeat). A track that played before starts a new event
    when something else, or nothing, played in between. A track that is already
    playing when Home Assistant starts or reconnects is not announced.
    """

    _attr_translation_key = "now_playing"

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "now_playing")
        self._attr_event_types = [EVENT_TRACK_CHANGED]
        # Which track was announced last; None while nothing plays on the network input.
        self._track: tuple[str | None, ...] | None = None
        # The first state read after the entity is added only tells what plays now.
        self._seen_state = False

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
            return
        if player.state != "playing" or not player.title:
            return  # starting up or paused: the next "playing" decides
        track = (player.title, player.artist, player.album, player.service, player.media_id)
        if track == self._track:
            return
        self._track = track
        if announce:
            self._trigger_event(EVENT_TRACK_CHANGED, self._event_data())

    def _event_data(self) -> dict[str, Any]:
        coordinator = self.coordinator
        data = coordinator.data
        player = data.player
        return {
            "title": player.title,
            "artist": player.artist,
            "album": player.album,
            "service": player.service,
            "source": coordinator.source_label(data.source_index),
            "audio_quality": player.quality,
            "codec": player.short_codec,
            "sample_rate": player.sample_rate,
            "bit_depth": player.bit_depth,
            "bitrate": player.bitrate,
            "is_radio": player.is_radio,
        }

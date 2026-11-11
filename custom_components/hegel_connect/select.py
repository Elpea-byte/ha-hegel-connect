"""Radio favorite (start a saved station) and the optional auto-standby time."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from . import HegelConfigEntry
from .api import NETWORK_SOURCE_NAME, HegelError
from .const import FAVORITES_INTERVAL
from .coordinator import HegelCoordinator
from .entity import HegelEntity
from .media_player import _command_failed

_LOGGER = logging.getLogger(__name__)

# Commands go one at a time to the amplifier (same as the media player).
PARALLEL_UPDATES = 1

# How long the chosen station stays selected while the amplifier switches (it buffers first).
PENDING_TIMEOUT = 15


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelRadioFavorite(entry.runtime_data), HegelAutoStandby(entry.runtime_data)])


class HegelRadioFavorite(HegelEntity, SelectEntity):
    """The radio favorites as options, so automations, scripts and voice can start a station.

    The options follow the favorites in the Hegel Control app. The state is the
    favorite that is playing, and empty (unknown) when something else plays.
    A station you just chose stays selected while the amplifier switches to it
    (a second or two of buffering), so the select does not flicker to unknown.
    """

    _attr_translation_key = "radio_favorite"

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "radio_favorite")
        self._pending: str | None = None
        self._cancel_pending: CALLBACK_TYPE | None = None

    async def async_will_remove_from_hass(self) -> None:
        self._clear_pending()
        await super().async_will_remove_from_hass()

    def _clear_pending(self) -> None:
        self._pending = None
        if self._cancel_pending is not None:
            self._cancel_pending()
            self._cancel_pending = None

    @callback
    def _pending_expired(self, _now: object) -> None:
        self._cancel_pending = None
        self._pending = None
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        # Like the favorites sensor: the saved list stays usable while the amplifier is off.
        return True

    def _paths(self) -> dict[str, str]:
        """Option text -> path of the station. Equal titles get a number so every option is unique."""
        paths: dict[str, str] = {}
        for favorite in self.coordinator.favorites:
            title = favorite["title"] or ""
            option, number = title, 1
            while option in paths:
                number += 1
                option = f"{title} ({number})"
            paths[option] = favorite["path"] or ""
        return paths

    @property
    def options(self) -> list[str]:
        return list(self._paths())

    def _playing_option(self) -> str | None:
        """The favorite that plays now, if any."""
        coordinator = self.coordinator
        data = coordinator.data
        media_id = data.player.media_id
        if (
            media_id is None
            or data.player.state not in ("playing", "paused")
            or coordinator.source_name(data.source_index) != NETWORK_SOURCE_NAME
        ):
            return None
        favorite_ids = [f["id"] for f in coordinator.favorites]
        options = list(self._paths())
        return options[favorite_ids.index(media_id)] if media_id in favorite_ids else None

    @property
    def current_option(self) -> str | None:
        coordinator = self.coordinator
        if not coordinator.connected or not coordinator.data.is_on:
            self._clear_pending()
            return None
        playing = self._playing_option()
        if self._pending is not None and playing == self._pending:
            self._clear_pending()
        # Still switching: keep the chosen station until it plays or the time-out ends.
        return self._pending if self._pending is not None else playing

    async def async_select_option(self, option: str) -> None:
        # Home Assistant has already checked that the option exists in options.
        # Chosen first: the amplifier reports its switching while the command is still running,
        # and that must not be written as "unknown" in between.
        self._clear_pending()
        self._pending = option
        self._cancel_pending = async_call_later(self.hass, PENDING_TIMEOUT, self._pending_expired)
        self.async_write_ha_state()
        try:
            await self.coordinator.client.play_path(self._paths()[option])
        except HegelError as err:
            self._clear_pending()
            self.async_write_ha_state()
            raise _command_failed(err) from err


def _idle_option(seconds: int) -> str:
    """Option key for an auto-standby time: "off", "5_min", "10_min" (see the translations)."""
    if seconds == 0:
        return "off"
    return f"{seconds // 60}_min" if seconds % 60 == 0 else f"{seconds}_s"


class HegelAutoStandby(HegelEntity, SelectEntity):
    """The amplifier's own auto-standby: how long it may sit idle before it goes to standby.

    Optional and disabled by default. It is a setting of the streamer inside the
    amplifier (not the standby timer in the amplifier's own menu): the amplifier
    counts the time itself, also when Home Assistant is not running. While music
    plays it does not count. The choices (off, 5, 10, 20 minutes) are read from the
    amplifier, and so is the value, when Home Assistant connects and now and then.
    """

    _attr_translation_key = "auto_standby"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "auto_standby")
        self._seconds: int | None = None
        self._choices: list[int] = []
        self._was_connected = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_interval(self.hass, self._async_tick, FAVORITES_INTERVAL))
        if self.coordinator.connected:
            self._was_connected = True
            await self._async_read()

    async def _async_tick(self, _now: object) -> None:
        if self.coordinator.connected:
            await self._async_read()

    async def _async_read(self) -> None:
        """Read the choices and the value; an amplifier without this setting leaves the entity unavailable."""
        client = self.coordinator.client
        try:
            self._choices = await client.idle_time_options()
            self._seconds = await client.idle_time()
        except HegelError as err:
            _LOGGER.debug("Auto-standby setting not available: %s", err)
            self._seconds = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        connected = self.coordinator.connected
        if connected and not self._was_connected:
            self.hass.async_create_task(self._async_read())  # back from a lost connection: read it again
        self._was_connected = connected
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return self.coordinator.connected and self._seconds is not None

    @property
    def options(self) -> list[str]:
        return [_idle_option(seconds) for seconds in self._choices]

    @property
    def current_option(self) -> str | None:
        return _idle_option(self._seconds) if self._seconds in self._choices else None

    async def async_select_option(self, option: str) -> None:
        seconds = next(s for s in self._choices if _idle_option(s) == option)
        client = self.coordinator.client
        try:
            await client.set_idle_time(seconds)
            self._seconds = await client.idle_time()  # what the amplifier says now
        except HegelError as err:
            raise _command_failed(err) from err
        self.async_write_ha_state()

"""Radio favorite: start one of the stations saved in the Hegel Control app."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import HegelConfigEntry
from .api import NETWORK_SOURCE_NAME, HegelError
from .coordinator import HegelCoordinator
from .entity import HegelEntity
from .media_player import _command_failed

# Commands go one at a time to the amplifier (same as the media player).
PARALLEL_UPDATES = 1

# How long the chosen station stays selected while the amplifier switches (it buffers first).
PENDING_TIMEOUT = 15


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelRadioFavorite(entry.runtime_data)])


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
        try:
            await self.coordinator.client.play_path(self._paths()[option])
        except HegelError as err:
            raise _command_failed(err) from err
        self._clear_pending()
        self._pending = option
        self._cancel_pending = async_call_later(self.hass, PENDING_TIMEOUT, self._pending_expired)
        self.async_write_ha_state()

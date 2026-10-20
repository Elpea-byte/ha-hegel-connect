"""Radio favorite: start one of the stations saved in the Hegel Control app."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .api import NETWORK_SOURCE_NAME, HegelError
from .coordinator import HegelCoordinator
from .entity import HegelEntity
from .media_player import _command_failed

# Commands go one at a time to the amplifier (same as the media player).
PARALLEL_UPDATES = 1


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
    """

    _attr_translation_key = "radio_favorite"

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "radio_favorite")

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

    @property
    def current_option(self) -> str | None:
        coordinator = self.coordinator
        data = coordinator.data
        media_id = data.player.media_id
        if (
            media_id is None
            or not coordinator.connected
            or not data.is_on
            or coordinator.source_name(data.source_index) != NETWORK_SOURCE_NAME
            or data.player.state not in ("playing", "paused")
        ):
            return None
        favorite_ids = [f["id"] for f in coordinator.favorites]
        paths = list(self._paths())
        return paths[favorite_ids.index(media_id)] if media_id in favorite_ids else None

    async def async_select_option(self, option: str) -> None:
        # Home Assistant has already checked that the option exists in options.
        try:
            await self.coordinator.client.play_path(self._paths()[option])
        except HegelError as err:
            raise _command_failed(err) from err

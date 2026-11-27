"""Buttons: reconnect now, and read the radio favorites again."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([HegelReconnect(coordinator), HegelRefreshFavorites(coordinator)])


class HegelReconnect(HegelEntity, ButtonEntity):
    """Try to reach the amplifier now instead of at the next retry (the same as homeassistant.update_entity).

    For after the amplifier was off at the mains; does nothing while connected but read the state once.
    Optional and disabled by default; stays available, because it is meant for when the amplifier is gone.
    """

    _attr_translation_key = "reconnect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _follows_connection = False

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "reconnect")

    async def async_press(self) -> None:
        self.coordinator.request_reconnect()
        await self.coordinator.async_request_refresh()


class HegelRefreshFavorites(HegelEntity, ButtonEntity):
    """Read the radio favorites now, so one added in the Hegel Control app shows without waiting six hours.

    Optional and disabled by default.
    """

    _attr_translation_key = "refresh_favorites"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "refresh_favorites")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_favorites(raise_errors=True)

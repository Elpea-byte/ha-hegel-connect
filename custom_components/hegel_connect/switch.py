"""Remember the volume of each input."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HegelConfigEntry
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelRememberVolume(entry.runtime_data)])


class HegelRememberVolume(HegelEntity, SwitchEntity, RestoreEntity):
    """Switching to an input (through Home Assistant) returns to the volume it had last.

    Optional and disabled by default. A start volume set for an input wins, and
    the maximum volume still applies.
    """

    _attr_translation_key = "remember_volume"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "remember_volume")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.remember_volume = last.state == STATE_ON

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.remember_volume

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.remember_volume = True
        self.coordinator.remember_current()  # start with the input that is selected now
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.remember_volume = False
        self.async_write_ha_state()

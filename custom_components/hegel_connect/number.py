"""Maximum volume: Home Assistant never sets the volume above it."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelMaxVolume(entry.runtime_data)])


class HegelMaxVolume(HegelEntity, RestoreNumber):
    """Volume ceiling for everything that goes through Home Assistant.

    A number entity instead of an option: it can change at any time (e.g. a
    "late evening" automation) without reloading the integration. The
    amplifier's own remote and knob are not limited.
    """

    _attr_translation_key = "max_volume"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "max_volume")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.max_volume = int(last.native_value)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.max_volume

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.max_volume = max(1, min(int(value), 100))
        # Also refreshes the media player (its max_volume attribute and volume limit).
        self.coordinator.async_update_listeners()

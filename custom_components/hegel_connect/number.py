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
    coordinator = entry.runtime_data
    async_add_entities([HegelMaxVolume(coordinator)])
    # Optional: one per input, switched off until you enable it in the entity settings.
    async_add_entities(HegelStartVolume(coordinator, source.index) for source in coordinator.visible_sources)


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


class HegelStartVolume(HegelEntity, RestoreNumber):
    """Volume to set when Home Assistant switches to this input (0 = leave the volume alone).

    Optional and disabled by default. The maximum volume still applies.
    """

    _attr_translation_key = "start_volume"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: HegelCoordinator, index: int) -> None:
        super().__init__(coordinator, f"start_volume_{index}")
        self._index = index
        self._attr_translation_placeholders = {"input": coordinator.source_label(index) or str(index)}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value:
            self.coordinator.start_volumes[self._index] = int(last.native_value)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.start_volumes.pop(self._index, None)
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.start_volumes.get(self._index, 0)

    async def async_set_native_value(self, value: float) -> None:
        if volume := max(0, min(int(value), 100)):
            self.coordinator.start_volumes[self._index] = volume
        else:
            self.coordinator.start_volumes.pop(self._index, None)
        self.async_write_ha_state()

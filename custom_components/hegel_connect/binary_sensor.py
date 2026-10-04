"""Fixed volume (home theater bypass) indicator."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .entity import HegelEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelFixedVolume(entry.runtime_data)])


class HegelFixedVolume(HegelEntity, BinarySensorEntity):
    """On when the current input uses fixed volume (HT bypass); volume changes are then ignored."""

    _attr_translation_key = "fixed_volume"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "fixed_volume")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.volume_fixed if self.coordinator.data else None

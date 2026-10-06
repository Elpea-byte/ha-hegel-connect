"""Fixed volume (home theater bypass) indicator."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    async_add_entities([HegelFixedVolume(entry.runtime_data), HegelNetwork(entry.runtime_data)])


class HegelFixedVolume(HegelEntity, BinarySensorEntity):
    """On when the current input uses fixed volume (HT bypass); volume changes are then ignored."""

    _attr_translation_key = "fixed_volume"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "fixed_volume")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.volume_fixed if self.coordinator.data else None


class HegelNetwork(HegelEntity, BinarySensorEntity):
    """On while the amplifier answers on the network, in standby too.

    Off: switched off at the mains, unplugged or network down. Together with the
    media player (off in standby) this tells standby and "gone" apart.
    """

    _attr_translation_key = "network"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "network")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected

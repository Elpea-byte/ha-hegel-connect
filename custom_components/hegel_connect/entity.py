"""Base entity for Hegel Connect."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HegelCoordinator


class HegelEntity(CoordinatorEntity[HegelCoordinator]):
    """Common device info and availability."""

    _attr_has_entity_name = True
    # Unavailable while the amplifier does not answer at all (off at the mains, unplugged, network
    # down). Standby still answers, so it is not affected. Entities whose value lives in Home
    # Assistant (settings, the saved favorites) or that tell "gone" themselves override this.
    _follows_connection = True

    def __init__(self, coordinator: HegelCoordinator, key: str) -> None:
        """One device per amplifier; ``key`` makes the entity's unique id."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            manufacturer=MANUFACTURER,
            model=entry.data.get("model"),
            name=entry.title,
            sw_version=coordinator.firmware,
            configuration_url=f"{coordinator.client.base_url}/webclient/",
        )

    @property
    def available(self) -> bool:
        return super().available and (self.coordinator.connected or not self._follows_connection)

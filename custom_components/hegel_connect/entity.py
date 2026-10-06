"""Base entity for Hegel Connect."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HegelCoordinator


class HegelEntity(CoordinatorEntity[HegelCoordinator]):
    """Common device info and availability."""

    _attr_has_entity_name = True

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
            configuration_url=f"http://{coordinator.client.host}/webclient/",
        )

    @property
    def available(self) -> bool:
        """Unavailable only before the first state is known (offline shows as off)."""
        return super().available and self.coordinator.data is not None

"""Stream format sensors: quality, codec, sample rate, bit depth, bitrate, service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .api import NETWORK_SOURCE_NAME, PlayerData
from .coordinator import HegelCoordinator
from .entity import HegelEntity

PARALLEL_UPDATES = 0

QUALITY_OPTIONS = ["hi_res", "cd", "lossless", "lossy", "dsd"]


@dataclass(frozen=True, kw_only=True)
class HegelSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PlayerData], Any]


SENSORS: tuple[HegelSensorDescription, ...] = (
    HegelSensorDescription(
        key="audio_quality",
        translation_key="audio_quality",
        device_class=SensorDeviceClass.ENUM,
        options=QUALITY_OPTIONS,
        value_fn=lambda p: p.quality,
    ),
    HegelSensorDescription(
        key="codec",
        translation_key="codec",
        value_fn=lambda p: p.short_codec,
    ),
    HegelSensorDescription(
        key="sample_rate",
        translation_key="sample_rate",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.KILOHERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda p: p.sample_rate,
    ),
    HegelSensorDescription(
        key="bit_depth",
        translation_key="bit_depth",
        native_unit_of_measurement="bit",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda p: p.bit_depth,
    ),
    HegelSensorDescription(
        key="bitrate",
        translation_key="bitrate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda p: p.bitrate,
    ),
    HegelSensorDescription(
        key="streaming_service",
        translation_key="streaming_service",
        value_fn=lambda p: p.service,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(HegelSensor(entry.runtime_data, description) for description in SENSORS)


class HegelSensor(HegelEntity, SensorEntity):
    """A property of the stream; empty unless the built-in streamer plays or is paused."""

    entity_description: HegelSensorDescription

    def __init__(self, coordinator: HegelCoordinator, description: HegelSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        coordinator = self.coordinator
        data = coordinator.data
        if (
            data is None
            or not coordinator.connected
            or not data.is_on
            or coordinator.source_name(data.source_index) != NETWORK_SOURCE_NAME
            or data.player.state not in ("playing", "paused")
        ):
            return None
        return self.entity_description.value_fn(data.player)

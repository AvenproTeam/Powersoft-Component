"""Sensor platform for Powersoft amplifiers."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowersoftConfigEntry, PowersoftCoordinator
from .entity import PowersoftChannelEntity, PowersoftEntity, PowersoftLiveMixin

SNAPSHOT_SENSOR = SensorEntityDescription(
    key="current_snapshot",
    translation_key="current_snapshot",
)
TEMPERATURE_SENSOR = SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)
SPEAKER_SENSOR = SensorEntityDescription(
    key="speaker",
    translation_key="speaker",
    entity_category=EntityCategory.DIAGNOSTIC,
)

# Socket.IO ``meters.output_process`` / ``slows.ampli`` readings per channel.
LIVE_CHANNEL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="impedance",
        translation_key="impedance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Ω",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="gain_reduction",
        translation_key="gain_reduction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dB",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="channel_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowersoftConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        PowersoftSnapshotSensor(coordinator, SNAPSHOT_SENSOR),
        PowersoftTemperatureSensor(coordinator, TEMPERATURE_SENSOR),
    ]
    for channel in coordinator.data["channels"]:
        entities.append(PowersoftSpeakerSensor(coordinator, channel, SPEAKER_SENSOR))
        entities.extend(
            PowersoftLiveChannelSensor(coordinator, channel, d)
            for d in LIVE_CHANNEL_SENSORS
        )
    async_add_entities(entities)


class PowersoftSnapshotSensor(PowersoftEntity, SensorEntity):
    """Snapshot (preset) currently loaded."""

    def __init__(
        self, coordinator: PowersoftCoordinator, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        return self.system.get("current_snapshot")


class PowersoftTemperatureSensor(PowersoftLiveMixin, PowersoftSnapshotSensor):
    """Hottest amplifier module temperature (live)."""

    @property
    def native_value(self) -> float | None:
        return self.system.get("temperature")


class PowersoftSpeakerSensor(PowersoftChannelEntity, SensorEntity):
    """Speaker model assigned to the output channel."""

    def __init__(
        self,
        coordinator: PowersoftCoordinator,
        channel: int,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, channel, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        return self.channel_data.get("speaker")


class PowersoftLiveChannelSensor(PowersoftLiveMixin, PowersoftSpeakerSensor):
    """Per-channel live meter."""

    @property
    def native_value(self) -> float | None:
        return self.live_data.get(self.entity_description.key)

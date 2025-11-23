"""Sensor platform for Powersoft amplifiers."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    SIGNAL_STRENGTH_DECIBELS,
    POWER_WATT,
    ELECTRICAL_VOLT_AMPERE,
    ELECTRICAL_CURRENT_AMPERE,
    ELECTRICAL_OHM,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Primera actualización para tener datos
    await coordinator.async_config_entry_first_refresh()

    entities = []

    # Sensor principal del equipo
    entities.append(PowersoftDeviceSensor(coordinator))

    # Sensores del sistema
    entities.append(PowersoftTemperatureSensor(coordinator))
    entities.append(PowersoftSnapshotSensor(coordinator))

    # Sensores por canal (creados dinámicamente)
    if coordinator.data and "channels" in coordinator.data:
        for channel in coordinator.data["channels"]:
            ch_num = channel["number"]
            entities.extend(
                [
                    PowersoftGainSensor(coordinator, ch_num),
                    PowersoftMuteSensor(coordinator, ch_num),
                    PowersoftPolaritySensor(coordinator, ch_num),
                    PowersoftDelaySensor(coordinator, ch_num),
                    PowersoftVoltageSensor(coordinator, ch_num),
                    PowersoftCurrentSensor(coordinator, ch_num),
                    PowersoftPowerSensor(coordinator, ch_num),
                    PowersoftImpedanceSensor(coordinator, ch_num),
                    PowersoftClipSensor(coordinator, ch_num),
                    PowersoftSignalSensor(coordinator, ch_num),
                ]
            )

    async_add_entities(entities, True)


class PowersoftCoordinatorEntity(CoordinatorEntity):
    """Base class for all Powersoft entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, name_suffix: str = ""):
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_name = f"Powersoft {coordinator.data['system']['model']} {name_suffix}".strip()
        self._attr_unique_id = f"{coordinator.serial}_{name_suffix.replace(' ', '_').lower()}"


# ==================== SENSORES DEL SISTEMA ====================

class PowersoftDeviceSensor(PowersoftCoordinatorEntity, SensorEntity):
    """Sensor que muestra modelo + serial del amplificador."""

    _attr_icon = "mdi:amplifier"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = []  # No es enum, pero lo usamos como descripción

    def __init__(self, coordinator):
        super().__init__(coordinator, "")
        self._attr_native_value = f"{coordinator.data['system']['model']} ({coordinator.serial})"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "firmware": self.coordinator.data["system"]["firmware"],
            "snapshot": self.coordinator.data["system"]["current_snapshot"],
        }


class PowersoftTemperatureSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_name_suffix = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_icon = "mdi:thermometer"

    @property
    def native_value(self):
        return self.coordinator.data["system"]["temperature"]


class PowersoftSnapshotSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_name_suffix = "Current Snapshot"
    _attr_icon = "mdi:bookmark-music"

    @property
    def native_value(self):
        return self.coordinator.data["system"]["current_snapshot"]


# ==================== SENSORES POR CANAL ====================

class PowersoftGainSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Gain")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return round(ch["gain"], 1) if ch else None

    @property
    def icon(self):
        return "mdi:volume-minus" if self.native_value <= -60 else "mdi:volume-high"


class PowersoftMuteSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SOUND
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Mute")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return "Muted" if ch and ch["mute"] else "Unmuted"

    @property
    def icon(self):
        return "mdi:volume-off" if self.is_muted else "mdi:volume-high"

    @property
    def is_muted(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return ch["mute"] if ch else False


class PowersoftPolaritySensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Polarity")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return "Inverted" if ch and ch["polarity_inverted"] else "Normal"


class PowersoftDelaySensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Delay")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return round(ch["delay_ms"], 1) if ch else 0.0


class PowersoftVoltageSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Voltage")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return ch["voltage"] if ch and ch["voltage"] not in (None, 0) else None


class PowersoftCurrentSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = ELECTRICAL_CURRENT_AMPERE
    _attr_icon = "mdi:current-ac"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Current")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return round(ch["current"], 3) if ch and ch["current"] not in (None, 0) else None


class PowersoftPowerSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Power")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return round(ch["power"], 1) if ch and ch["power"] not in (None, 0) else None


class PowersoftImpedanceSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.IMPEDANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = ELECTRICAL_OHM
    _attr_icon = "mdi:omega"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Impedance")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return round(ch["impedance"], 1) if ch and ch["impedance"] not in (None, 0) else None


class PowersoftClipSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Clip")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return "Clipping" if ch and ch["clip"] else "OK"

    @property
    def icon(self):
        return "mdi:alert" if self.is_clipping else "mdi:check-circle"

    @property
    def is_clipping(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return ch["clip"] if ch else False


class PowersoftSignalSensor(PowersoftCoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:waveform"

    def __init__(self, coordinator, channel: int):
        super().__init__(coordinator, f"Channel {channel} Signal")
        self.channel = channel

    @property
    def native_value(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return "Present" if ch and ch["signal_present"] else "Absent"

    @property
    def icon(self):
        return "mdi:waveform" if self.has_signal else "mdi:volume-mute"

    @property
    def has_signal(self):
        ch = next((c for c in self.coordinator.data["channels"] if c["number"] == self.channel), None)
        return ch["signal_present"] if ch else False
"""Sensor platform for Powersoft amplifiers."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft sensor entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    
    # Add system sensors
    entities.append(PowersoftTemperatureSensor(coordinator))
    
    # Add channel-specific sensors
    channels = coordinator.data.get("channels", {})
    if isinstance(channels, dict):
        channel_list = channels.get("channels", [])
        for channel in channel_list:
            channel_num = channel.get("number")
            if channel_num is not None:
                entities.extend([
                    PowersoftChannelVoltageSensor(coordinator, channel_num),
                    PowersoftChannelCurrentSensor(coordinator, channel_num),
                    PowersoftChannelPowerSensor(coordinator, channel_num),
                    PowersoftChannelImpedanceSensor(coordinator, channel_num),
                ])

    async_add_entities(entities)


class PowersoftSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Powersoft sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Return device information."""
        system_info = self.coordinator.data.get("system", {})
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": f"Powersoft {system_info.get('model', 'Amplifier')}",
            "manufacturer": "Powersoft",
            "model": system_info.get("model", "Unknown"),
            "sw_version": system_info.get("firmware", "Unknown"),
        }


class PowersoftTemperatureSensor(PowersoftSensorBase):
    """Temperature sensor for the amplifier."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_name = "Temperature"

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        system_info = self.coordinator.data.get("system", {})
        return system_info.get("temperature")


class PowersoftChannelSensorBase(PowersoftSensorBase):
    """Base class for channel-specific sensors."""

    def __init__(self, coordinator, channel: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._channel = channel

    def _get_channel_data(self) -> dict | None:
        """Get data for this channel."""
        channels = self.coordinator.data.get("channels", {})
        if isinstance(channels, dict):
            channel_list = channels.get("channels", [])
            for channel in channel_list:
                if channel.get("number") == self._channel:
                    return channel
        return None


class PowersoftChannelVoltageSensor(PowersoftChannelSensorBase):
    """Voltage sensor for a channel."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(self, coordinator, channel: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, channel)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ch{channel}_voltage"
        self._attr_name = f"Channel {channel} Voltage"

    @property
    def native_value(self) -> float | None:
        """Return the voltage value."""
        channel_data = self._get_channel_data()
        return channel_data.get("voltage") if channel_data else None


class PowersoftChannelCurrentSensor(PowersoftChannelSensorBase):
    """Current sensor for a channel."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, channel: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, channel)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ch{channel}_current"
        self._attr_name = f"Channel {channel} Current"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        channel_data = self._get_channel_data()
        return channel_data.get("current") if channel_data else None


class PowersoftChannelPowerSensor(PowersoftChannelSensorBase):
    """Power sensor for a channel."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, channel: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, channel)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ch{channel}_power"
        self._attr_name = f"Channel {channel} Power"

    @property
    def native_value(self) -> float | None:
        """Return the power value."""
        channel_data = self._get_channel_data()
        return channel_data.get("power") if channel_data else None


class PowersoftChannelImpedanceSensor(PowersoftChannelSensorBase):
    """Impedance sensor for a channel."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Ω"
    _attr_icon = "mdi:omega"

    def __init__(self, coordinator, channel: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, channel)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ch{channel}_impedance"
        self._attr_name = f"Channel {channel} Impedance"

    @property
    def native_value(self) -> float | None:
        """Return the impedance value."""
        channel_data = self._get_channel_data()
        return channel_data.get("impedance") if channel_data else None

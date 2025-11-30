"""Number platform for Powersoft amplifiers."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
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
    """Set up Powersoft number entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    
    # Add gain and delay controls for each channel
    channels = coordinator.data.get("channels", {})
    if isinstance(channels, dict):
        channel_list = channels.get("channels", [])
        for channel in channel_list:
            channel_num = channel.get("number")
            if channel_num is not None:
                entities.extend([
                    PowersoftGainNumber(coordinator, api, channel_num, config_entry.entry_id),
                    PowersoftDelayNumber(coordinator, api, channel_num, config_entry.entry_id),
                ])

    _LOGGER.info("Adding %d number entities", len(entities))
    async_add_entities(entities)


class PowersoftNumberBase(CoordinatorEntity, NumberEntity):
    """Base class for Powersoft number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, api, channel: int, entry_id: str) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._api = api
        self._channel = channel
        self._entry_id = entry_id

    @property
    def device_info(self):
        """Return device information."""
        system_info = self.coordinator.data.get("system", {})
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"Powersoft {system_info.get('model', 'Amplifier')}",
            "manufacturer": "Powersoft",
            "model": system_info.get("model", "Quattrocanali 8804 DSP"),
            "sw_version": system_info.get("firmware", "Unknown"),
        }

    def _get_channel_data(self) -> dict | None:
        """Get data for this channel."""
        channels = self.coordinator.data.get("channels", {})
        if isinstance(channels, dict):
            channel_list = channels.get("channels", [])
            for channel in channel_list:
                if channel.get("number") == self._channel:
                    return channel
        return None


class PowersoftGainNumber(PowersoftNumberBase):
    """Number entity for channel gain control."""

    _attr_native_min_value = -80.0
    _attr_native_max_value = 0.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator, api, channel: int, entry_id: str) -> None:
        """Initialize the gain control."""
        super().__init__(coordinator, api, channel, entry_id)
        self._attr_unique_id = f"{entry_id}_ch{channel}_gain"
        self._attr_name = f"Channel {channel} Gain"

    @property
    def native_value(self) -> float | None:
        """Return the current gain value."""
        channel_data = self._get_channel_data()
        return channel_data.get("gain") if channel_data else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the gain value."""
        success = await self._api.set_gain(self._channel, value)
        if success:
            await self.coordinator.async_request_refresh()


class PowersoftDelayNumber(PowersoftNumberBase):
    """Number entity for channel delay control."""

    _attr_native_min_value = 0.0
    _attr_native_max_value = 500.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator, api, channel: int, entry_id: str) -> None:
        """Initialize the delay control."""
        super().__init__(coordinator, api, channel, entry_id)
        self._attr_unique_id = f"{entry_id}_ch{channel}_delay"
        self._attr_name = f"Channel {channel} Delay"

    @property
    def native_value(self) -> float | None:
        """Return the current delay value."""
        channel_data = self._get_channel_data()
        return channel_data.get("delay") if channel_data else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the delay value."""
        success = await self._api.set_delay(self._channel, value)
        if success:
            await self.coordinator.async_request_refresh()
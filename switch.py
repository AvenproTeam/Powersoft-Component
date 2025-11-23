"""Switch platform for Powersoft amplifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Powersoft switch entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    
    # Add main power switch
    entities.append(PowersoftPowerSwitch(coordinator, api))
    
    # Add polarity switches for each channel
    channels = coordinator.data.get("channels", {})
    if isinstance(channels, dict):
        channel_list = channels.get("channels", [])
        for channel in channel_list:
            channel_num = channel.get("number")
            if channel_num is not None:
                entities.append(PowersoftPolaritySwitch(coordinator, api, channel_num))

    async_add_entities(entities)


class PowersoftSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base class for Powersoft switches."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, api) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api = api

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


class PowersoftPowerSwitch(PowersoftSwitchBase):
    """Switch to control amplifier power state."""

    _attr_icon = "mdi:power"
    _attr_name = "Power"

    def __init__(self, coordinator, api) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, api)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_power"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        system_info = self.coordinator.data.get("system", {})
        return system_info.get("power_state") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._api.power_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._api.power_off()
        await self.coordinator.async_request_refresh()


class PowersoftPolaritySwitch(PowersoftSwitchBase):
    """Switch to control channel polarity."""

    _attr_icon = "mdi:sine-wave"

    def __init__(self, coordinator, api, channel: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, api)
        self._channel = channel
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ch{channel}_polarity"
        self._attr_name = f"Channel {channel} Polarity Inverted"

    @property
    def is_on(self) -> bool:
        """Return true if polarity is inverted."""
        channel_data = self._get_channel_data()
        return channel_data.get("polarity") == "inverted" if channel_data else False

    def _get_channel_data(self) -> dict | None:
        """Get data for this channel."""
        channels = self.coordinator.data.get("channels", {})
        if isinstance(channels, dict):
            channel_list = channels.get("channels", [])
            for channel in channel_list:
                if channel.get("number") == self._channel:
                    return channel
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Invert the polarity."""
        await self._api.set_polarity(self._channel, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set polarity to normal."""
        await self._api.set_polarity(self._channel, False)
        await self.coordinator.async_request_refresh()

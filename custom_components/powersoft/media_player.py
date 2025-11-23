"""Media Player platform for Powersoft amplifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    """Set up Powersoft media player entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    
    channels = coordinator.data.get("channels", {})
    if isinstance(channels, dict):
        channel_list = channels.get("channels", [])
        for channel in channel_list:
            channel_num = channel.get("number")
            if channel_num is not None:
                entities.append(PowersoftChannel(coordinator, api, channel_num))

    async_add_entities(entities)


class PowersoftChannel(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Powersoft amplifier channel."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, api, channel: int) -> None:
        """Initialize the channel."""
        super().__init__(coordinator)
        self._api = api
        self._channel = channel
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_channel_{channel}"
        self._attr_name = f"Channel {channel}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the channel."""
        channel_data = self._get_channel_data()
        if not channel_data:
            return MediaPlayerState.OFF

        if channel_data.get("mute", False):
            return MediaPlayerState.OFF
        
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        channel_data = self._get_channel_data()
        if not channel_data:
            return None
        
        gain_db = channel_data.get("gain", -80)
        return max(0.0, min(1.0, (gain_db + 80) / 80))

    def _get_channel_data(self) -> dict | None:
        """Get data for this channel."""
        channels = self.coordinator.data.get("channels", {})
        if isinstance(channels, dict):
            channel_list = channels.get("channels", [])
            for channel in channel_list:
                if channel.get("number") == self._channel:
                    return channel
        return None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        gain_db = (volume * 80) - 80
        await self._api.set_gain(self._channel, gain_db)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self._api.set_mute(self._channel, mute)
        await self.coordinator.async_request_refresh()
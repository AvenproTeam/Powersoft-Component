"""Powersoft Amplifier Integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .powersoft_api import PowersoftAPI

OPTIONS = {
    "volume_channel": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    "mute_channel": [0, 1, 2, 3, 4, 5, 6, 7, 8],
}

async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Called when options are updated."""
    await hass.data[DOMAIN][entry.entry_id].async_request_refresh()

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Powersoft from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    api = PowersoftAPI(host, port, username, password)

    async def async_update_data():
        """Fetch data from API."""
        try:
            return await api.get_status()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"powersoft_{host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # En async_setup_entry:
    api = PowersoftAPI(host, port, username, password)
    async with api:  # Prueba conexión
        await api.get_status()  # Quick check
    coordinator = DataUpdateCoordinator(...)  # Tu coordinator existente
    coordinator.data = {"api": api}  # O usa dependency injection

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
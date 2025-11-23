"""Powersoft Amplifier integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PowersoftAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "media_player", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Powersoft from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    api = PowersoftAPI(host, port, username, password)

    async def _update_data():
        """Fetch data from Powersoft amplifier."""
        try:
            async with aiohttp.ClientTimeout(total=15):
                status = await api.get_status()
            return status
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Powersoft {host}: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Powersoft {host}",
        update_method=_update_data,
        update_interval=timedelta(seconds=10),
    )

    # Primera actualización para verificar conexión
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to connect to Powersoft %s during setup: %s", host, err)
        return False

    # Guardamos todo lo necesario
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Exponer la API para media_player y otros
    coordinator.api = api
    coordinator.serial = coordinator.data["system"].get("serial", "unknown")
    coordinator.device_info = {
        "identifiers": {(DOMAIN, coordinator.serial)},
        "name": f"Powersoft {coordinator.data['system']['model']}",
        "manufacturer": "Powersoft",
        "model": coordinator.data["system"]["model"],
        "sw_version": coordinator.data["system"]["firmware"],
    }

    # Cargar plataformas
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Soporte para opciones (volumen/mute por canal)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options (e.g. volume_channel, mute_channel)."""
    await hass.config_entries.async_reload(entry.entry_id)
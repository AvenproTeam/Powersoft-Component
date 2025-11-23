"""Powersoft Amplifier integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
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
        try:
            return await api.get_status()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Powersoft: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,  # ← Aquí está el logger que faltaba
        name=f"Powersoft {host}",
        update_method=_update_data,
        update_interval=timedelta(seconds=10),
    )

    # Primera actualización
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    coordinator.api = api
    coordinator.serial = coordinator.data["system"].get("serial", "unknown")
    coordinator.device_info = {
        "identifiers": {(DOMAIN, coordinator.serial)},
        "name": f"Powersoft {coordinator.data['system']['model']}",
        "manufacturer": "Powersoft",
        "model": coordinator.data["system"]["model"],
        "sw_version": coordinator.data["system"]["firmware"],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
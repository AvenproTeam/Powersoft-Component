"""Powersoft amplifier integration for Home Assistant."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_GAIN,
    ATTR_INPUT,
    ATTR_OUTPUT,
    ATTR_SNAPSHOT,
    CONF_NUM_CHANNELS,
    DEFAULT_NUM_CHANNELS,
    DEFAULT_PORT,
    DOMAIN,
    SERVICE_LOAD_SNAPSHOT,
    SERVICE_SET_MATRIX_GAIN,
)
from .coordinator import PowersoftConfigEntry, PowersoftCoordinator
from .powersoft_api import PowersoftAPI
from .powersoft_live import PowersoftLiveClient

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

LOAD_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_SNAPSHOT): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
SET_MATRIX_GAIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_INPUT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_OUTPUT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_GAIN): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide services."""

    def _coordinator(call: ServiceCall) -> PowersoftCoordinator:
        entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_loaded"
            )
        return entry.runtime_data

    async def _load_snapshot(call: ServiceCall) -> None:
        coordinator = _coordinator(call)
        if not await coordinator.api.load_snapshot(call.data[ATTR_SNAPSHOT]):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        await coordinator.async_request_refresh()

    async def _set_matrix_gain(call: ServiceCall) -> None:
        coordinator = _coordinator(call)
        if not await coordinator.api.set_matrix_gain(
            call.data[ATTR_INPUT], call.data[ATTR_OUTPUT], call.data[ATTR_GAIN]
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )

    hass.services.async_register(
        DOMAIN, SERVICE_LOAD_SNAPSHOT, _load_snapshot, schema=LOAD_SNAPSHOT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_MATRIX_GAIN, _set_matrix_gain, schema=SET_MATRIX_GAIN_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PowersoftConfigEntry) -> bool:
    """Set up a Powersoft amplifier from a config entry."""
    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    api = PowersoftAPI(
        host,
        port,
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        num_channels=entry.data.get(CONF_NUM_CHANNELS, DEFAULT_NUM_CHANNELS),
        session=session,
    )
    live = PowersoftLiveClient(session, host, port)
    coordinator = PowersoftCoordinator(hass, entry, api, live)
    # Live meters arrive over Socket.IO; the task is cancelled on unload.
    entry.async_create_background_task(hass, live.run(), f"{DOMAIN}_live_{host}")
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowersoftConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

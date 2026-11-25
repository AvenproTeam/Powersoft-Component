"""Data update coordinator for Powersoft amplifiers."""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_MODEL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .powersoft_api import PowersoftAPI, PowersoftAuthError, PowersoftError
from .powersoft_live import PowersoftLiveClient

_LOGGER = logging.getLogger(__name__)

type PowersoftConfigEntry = ConfigEntry[PowersoftCoordinator]


class PowersoftCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll ``/am`` for controllable state and merge Socket.IO live meters."""

    config_entry: PowersoftConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PowersoftConfigEntry,
        api: PowersoftAPI,
        live: PowersoftLiveClient | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{api.host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.live = live
        self.model = DEFAULT_MODEL
        self.firmware: str | None = None
        self.serial: str | None = None

    async def _async_setup(self) -> None:
        """Read the amplifier identity once and size the channel list."""
        try:
            info = await self.api.get_device_info()
        except PowersoftAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PowersoftError as err:
            raise UpdateFailed(str(err)) from err
        self.model = info["model"] or DEFAULT_MODEL
        self.firmware = info["firmware"]
        self.serial = info["serial"]
        if info["channels"]:
            self.api.num_channels = info["channels"]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_status()
        except PowersoftAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PowersoftError as err:
            raise UpdateFailed(str(err)) from err

        snap = self.live.snapshot if self.live else None
        fresh = bool(snap and snap.fresh)
        system = data["system"]
        system["live"] = fresh
        system["temperature"] = snap.temperature if fresh else None
        system["fault"] = snap.fault if fresh else None
        system["fault_flags"] = dict(snap.fault_flags) if fresh else {}
        # /am is authoritative (and reflects our own writes); live is a fallback.
        if system["standby"] is None and fresh and snap.standby is not None:
            system["standby"] = snap.standby
            system["power_state"] = "standby" if snap.standby else "on"

        for number, channel in data["channels"].items():
            live_ch = (
                asdict(snap.channels[number - 1])
                if fresh and number - 1 < len(snap.channels)
                else {}
            )
            channel["live"] = live_ch
        return data

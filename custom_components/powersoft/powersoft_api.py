"""Powersoft API client for Quattrocanali amplifiers."""
import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class PowersoftAPI:
    """Client for Powersoft Quattrocanali amplifier Web App API."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        username: str | None = None,
        password: str | None = None,
    ):
        """Initialize the API client."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            auth = None
            if self.username and self.password:
                auth = aiohttp.BasicAuth(self.username, self.password)
            self._session = aiohttp.ClientSession(auth=auth, timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def close(self):
        """Close the API client."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _http_request(
        self, endpoint: str, method: str = "GET", data: dict | None = None
    ) -> dict | str:
        """Make HTTP request to the amplifier."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(method, url, json=data) as response:
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    return await response.json()
                else:
                    return await response.text()
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request to %s failed: %s", url, err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error in HTTP request: %s", err)
            raise

    async def get_status(self) -> dict[str, Any]:
        """Get amplifier status.
        
        This method tries different common endpoints for Powersoft amplifiers.
        The exact API endpoints vary by model and firmware version.
        """
        status_data = {
            "system": {
                "model": "Quattrocanali 8804 DSP",
                "firmware": "Unknown",
                "temperature": None,
                "power_state": "on",
                "serial": "Unknown"
            },
            "channels": {
                "channels": []
            }
        }

        try:
            # Try to get system/device information
            try:
                # Common endpoints for Powersoft Web App
                device_info = await self._http_request("/device/info")
                if isinstance(device_info, dict):
                    status_data["system"].update({
                        "model": device_info.get("model", "Quattrocanali 8804 DSP"),
                        "firmware": device_info.get("firmware", device_info.get("fw_version", "Unknown")),
                        "serial": device_info.get("serial", device_info.get("serial_number", "Unknown"))
                    })
                    _LOGGER.info("Got device info: %s", device_info)
            except Exception as e:
                _LOGGER.debug("Could not get /device/info: %s", e)

            # Try to get temperature/monitoring data
            try:
                monitoring = await self._http_request("/monitoring")
                if isinstance(monitoring, dict):
                    status_data["system"]["temperature"] = monitoring.get("temperature", monitoring.get("temp"))
                    _LOGGER.info("Got monitoring data: %s", monitoring)
            except Exception as e:
                _LOGGER.debug("Could not get /monitoring: %s", e)

            # Try to get channels information
            # Quattrocanali has 4 channels
            for ch in range(1, 5):
                channel_data = {
                    "number": ch,
                    "gain": -20.0,
                    "mute": False,
                    "polarity": "normal",
                    "delay": 0.0,
                    "voltage": None,
                    "current": None,
                    "power": None,
                    "impedance": None,
                    "signal_present": False,
                    "clip": False
                }
                
                try:
                    # Try to get individual channel data
                    ch_info = await self._http_request(f"/channel/{ch}")
                    if isinstance(ch_info, dict):
                        channel_data.update({
                            "gain": ch_info.get("gain", channel_data["gain"]),
                            "mute": ch_info.get("mute", channel_data["mute"]),
                            "polarity": "inverted" if ch_info.get("polarity_inverted") else "normal",
                            "delay": ch_info.get("delay", channel_data["delay"]),
                        })
                        _LOGGER.info("Got channel %d data: %s", ch, ch_info)
                except Exception as e:
                    _LOGGER.debug("Could not get channel %d info: %s", ch, e)

                try:
                    # Try to get channel metering/monitoring
                    ch_meter = await self._http_request(f"/channel/{ch}/meter")
                    if isinstance(ch_meter, dict):
                        channel_data.update({
                            "voltage": ch_meter.get("voltage", ch_meter.get("volt")),
                            "current": ch_meter.get("current", ch_meter.get("amp")),
                            "power": ch_meter.get("power", ch_meter.get("watt")),
                            "impedance": ch_meter.get("impedance", ch_meter.get("ohm")),
                            "clip": ch_meter.get("clip", False),
                            "signal_present": ch_meter.get("signal", ch_meter.get("signal_present", False))
                        })
                        _LOGGER.info("Got channel %d metering: %s", ch, ch_meter)
                except Exception as e:
                    _LOGGER.debug("Could not get channel %d metering: %s", ch, e)

                status_data["channels"]["channels"].append(channel_data)

        except Exception as err:
            _LOGGER.error("Failed to get complete status: %s", err)
            # Return partial data even if some requests failed

        _LOGGER.info("Final status data: %s", status_data)
        return status_data

    async def get_channel_info(self, channel: int) -> dict[str, Any]:
        """Get information for a specific channel."""
        try:
            return await self._http_request(f"/channel/{channel}")
        except Exception as e:
            _LOGGER.error("Failed to get channel %d info: %s", channel, e)
            return {}

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Set mute state for a channel."""
        try:
            await self._http_request(
                f"/channel/{channel}/mute",
                method="POST",
                data={"mute": mute},
            )
            _LOGGER.info("Set channel %d mute to %s", channel, mute)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set mute on channel %d: %s", channel, err)
            return False

    async def set_gain(self, channel: int, gain: float) -> bool:
        """Set gain (in dB) for a channel."""
        try:
            await self._http_request(
                f"/channel/{channel}/gain",
                method="POST",
                data={"gain": gain},
            )
            _LOGGER.info("Set channel %d gain to %.1f dB", channel, gain)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set gain on channel %d: %s", channel, err)
            return False

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Set polarity for a channel."""
        try:
            await self._http_request(
                f"/channel/{channel}/polarity",
                method="POST",
                data={"inverted": inverted},
            )
            _LOGGER.info("Set channel %d polarity inverted: %s", channel, inverted)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set polarity on channel %d: %s", channel, err)
            return False

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set delay (in milliseconds) for a channel."""
        try:
            await self._http_request(
                f"/channel/{channel}/delay",
                method="POST",
                data={"delay": delay_ms},
            )
            _LOGGER.info("Set channel %d delay to %.1f ms", channel, delay_ms)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set delay on channel %d: %s", channel, err)
            return False

    async def power_on(self) -> bool:
        """Power on the amplifier."""
        try:
            await self._http_request("/power", method="POST", data={"state": "on"})
            _LOGGER.info("Powered on amplifier")
            return True
        except Exception as err:
            _LOGGER.error("Failed to power on: %s", err)
            return False

    async def power_off(self) -> bool:
        """Power off the amplifier (standby mode)."""
        try:
            await self._http_request("/power", method="POST", data={"state": "off"})
            _LOGGER.info("Powered off amplifier")
            return True
        except Exception as err:
            _LOGGER.error("Failed to power off: %s", err)
            return False

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Load a snapshot/preset."""
        try:
            await self._http_request(
                "/snapshot/load",
                method="POST",
                data={"snapshot": snapshot_id},
            )
            _LOGGER.info("Loaded snapshot %d", snapshot_id)
            return True
        except Exception as err:
            _LOGGER.error("Failed to load snapshot: %s", err)
            return False

    async def get_snapshots(self) -> list[dict]:
        """Get available snapshots."""
        try:
            response = await self._http_request("/snapshots")
            if isinstance(response, dict):
                return response.get("snapshots", [])
            return []
        except Exception as err:
            _LOGGER.error("Failed to get snapshots: %s", err)
            return []
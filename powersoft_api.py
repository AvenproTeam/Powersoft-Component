"""Powersoft API client for HTTP and UDP protocols."""
import asyncio
import logging
import struct
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class PowersoftAPI:
    """Client for Powersoft amplifier API."""

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
        self._udp_socket = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            auth = None
            if self.username and self.password:
                auth = aiohttp.BasicAuth(self.username, self.password)
            self._session = aiohttp.ClientSession(auth=auth)
        return self._session

    async def close(self):
        """Close the API client."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._udp_socket:
            self._udp_socket.close()

    async def _http_request(
        self, endpoint: str, method: str = "GET", data: dict | None = None
    ) -> dict:
        """Make HTTP request to the amplifier."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(method, url, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request failed: %s", err)
            raise

    async def get_status(self) -> dict[str, Any]:
        """Get amplifier status."""
        try:
            # Get system info
            system_info = await self._http_request("/api/system")
            
            # Get channels info
            channels_info = await self._http_request("/api/channels")
            
            return {
                "system": system_info,
                "channels": channels_info,
            }
        except Exception as err:
            _LOGGER.error("Failed to get status: %s", err)
            raise

    async def get_channel_info(self, channel: int) -> dict[str, Any]:
        """Get information for a specific channel."""
        return await self._http_request(f"/api/channels/{channel}")

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Set mute state for a channel."""
        try:
            await self._http_request(
                f"/api/channels/{channel}/mute",
                method="POST",
                data={"mute": mute},
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set mute: %s", err)
            return False

    async def set_gain(self, channel: int, gain: float) -> bool:
        """Set gain (in dB) for a channel."""
        try:
            await self._http_request(
                f"/api/channels/{channel}/gain",
                method="POST",
                data={"gain": gain},
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set gain: %s", err)
            return False

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Set polarity for a channel."""
        try:
            await self._http_request(
                f"/api/channels/{channel}/polarity",
                method="POST",
                data={"inverted": inverted},
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set polarity: %s", err)
            return False

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set delay (in milliseconds) for a channel."""
        try:
            await self._http_request(
                f"/api/channels/{channel}/delay",
                method="POST",
                data={"delay": delay_ms},
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set delay: %s", err)
            return False

    async def power_on(self) -> bool:
        """Power on the amplifier."""
        try:
            await self._http_request("/api/power", method="POST", data={"state": "on"})
            return True
        except Exception as err:
            _LOGGER.error("Failed to power on: %s", err)
            return False

    async def power_off(self) -> bool:
        """Power off the amplifier (standby mode)."""
        try:
            await self._http_request("/api/power", method="POST", data={"state": "off"})
            return True
        except Exception as err:
            _LOGGER.error("Failed to power off: %s", err)
            return False

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Load a snapshot/preset."""
        try:
            await self._http_request(
                "/api/snapshots/load",
                method="POST",
                data={"snapshot": snapshot_id},
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to load snapshot: %s", err)
            return False

    async def get_snapshots(self) -> list[dict]:
        """Get available snapshots."""
        try:
            response = await self._http_request("/api/snapshots")
            return response.get("snapshots", [])
        except Exception as err:
            _LOGGER.error("Failed to get snapshots: %s", err)
            return []

    # UDP Protocol methods (for advanced control)
    async def send_udp_command(self, command: bytes) -> bytes | None:
        """Send UDP command to amplifier (port 8002)."""
        try:
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(),
                remote_addr=(self.host, 8002)
            )
            
            transport.sendto(command)
            await asyncio.sleep(0.1)  # Wait for response
            
            response = protocol.get_response()
            transport.close()
            
            return response
        except Exception as err:
            _LOGGER.error("UDP command failed: %s", err)
            return None


class UDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol for receiving responses."""

    def __init__(self):
        """Initialize protocol."""
        self.response = None

    def datagram_received(self, data, addr):
        """Handle received datagram."""
        self.response = data

    def get_response(self) -> bytes | None:
        """Get received response."""
        return self.response

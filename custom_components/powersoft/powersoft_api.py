"""Powersoft API client for Quattrocanali amplifiers."""
import asyncio
import logging
from typing import Any
import uuid

import aiohttp

_LOGGER = logging.getLogger(__name__)


class PowersoftAPI:
    """Client for Powersoft Quattrocanali amplifier Web App API.
    
    The Powersoft API uses a hierarchical ID system with READ/WRITE actions.
    Structure: /Device/Audio/Presets/Live/[Section]/Channels/Channel-X/[Parameter]/Value
    """

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
        self._client_id = "homeassistant-powersoft"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            auth = None
            if self.username and self.password:
                auth = aiohttp.BasicAuth(self.username, self.password)
            self._session = aiohttp.ClientSession(
                auth=auth, 
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Content-Type": "application/json"}
            )
        return self._session

    async def close(self):
        """Close the API client."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _am_request(self, action_type: str, values: list[dict]) -> dict:
        """Make request to /am endpoint.
        
        Args:
            action_type: "READ" or "WRITE"
            values: List of value dictionaries with 'id' and optionally 'data'
        """
        session = await self._get_session()
        url = f"{self.base_url}/am"

        payload = {
            "clientId": self._client_id,
            "payload": {
                "type": "ACTION",
                "action": {
                    "type": action_type,
                    "values": values
                }
            }
        }

        try:
            _LOGGER.debug("Sending to /am: %s", payload)
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                _LOGGER.debug("Response from /am: %s", result)
                return result
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request to /am failed: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error in /am request: %s", err)
            raise

    async def _read_value(self, param_id: str) -> Any:
        """Read a single value from the amplifier."""
        values = [{"id": param_id, "single": True}]
        result = await self._am_request("READ", values)
        
        try:
            value_data = result["payload"]["action"]["values"][0]["data"]
            
            # Extract value based on type
            if "boolValue" in value_data:
                return value_data["boolValue"]
            elif "floatValue" in value_data:
                return value_data["floatValue"]
            elif "intValue" in value_data:
                return value_data["intValue"]
            elif "stringValue" in value_data:
                return value_data["stringValue"]
            
            return None
        except (KeyError, IndexError) as e:
            _LOGGER.error("Failed to parse read response: %s", e)
            return None

    async def _write_value(self, param_id: str, value: Any, value_type: str) -> bool:
        """Write a single value to the amplifier.
        
        Args:
            param_id: Parameter ID path
            value: Value to write
            value_type: "BOOL", "FLOAT", "INT", or "STRING"
        """
        # Map value_type to the correct key
        value_key_map = {
            "BOOL": "boolValue",
            "FLOAT": "floatValue",
            "INT": "intValue",
            "STRING": "stringValue"
        }
        
        value_key = value_key_map.get(value_type)
        if not value_key:
            _LOGGER.error("Invalid value type: %s", value_type)
            return False

        values = [{
            "id": param_id,
            "data": {
                "type": value_type,
                value_key: value
            }
        }]
        
        try:
            result = await self._am_request("WRITE", values)
            # Check if result is 10 (success)
            result_code = result["payload"]["action"]["values"][0].get("result")
            return result_code == 10
        except Exception as e:
            _LOGGER.error("Failed to write value: %s", e)
            return False

    async def get_status(self) -> dict[str, Any]:
        """Get amplifier status."""
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
            # Read current snapshot
            try:
                current_snapshot = await self._read_value(
                    "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current"
                )
                status_data["system"]["current_snapshot"] = current_snapshot
            except Exception as e:
                _LOGGER.debug("Could not read current snapshot: %s", e)

            # Quattrocanali 8804 has 4 output channels (Channel-0 to Channel-3)
            for ch in range(4):
                channel_data = {
                    "number": ch + 1,  # Display as 1-4
                    "gain": None,
                    "mute": False,
                    "polarity": "normal",
                    "delay": None,
                    "voltage": None,
                    "current": None,
                    "power": None,
                    "impedance": None,
                    "signal_present": False,
                    "clip": False
                }
                
                try:
                    # Read mute status
                    mute = await self._read_value(
                        f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Mute/Value"
                    )
                    if mute is not None:
                        channel_data["mute"] = mute
                except Exception as e:
                    _LOGGER.debug("Could not read mute for channel %d: %s", ch, e)

                try:
                    # Read gain (output level)
                    gain = await self._read_value(
                        f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Gain/Value"
                    )
                    if gain is not None:
                        # Convert to dB if needed (assuming 0-1 range = -80 to 0 dB)
                        channel_data["gain"] = (gain * 80) - 80 if gain <= 1 else gain
                except Exception as e:
                    _LOGGER.debug("Could not read gain for channel %d: %s", ch, e)

                try:
                    # Read polarity
                    polarity = await self._read_value(
                        f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Polarity/Value"
                    )
                    if polarity is not None:
                        channel_data["polarity"] = "inverted" if polarity else "normal"
                except Exception as e:
                    _LOGGER.debug("Could not read polarity for channel %d: %s", ch, e)

                try:
                    # Read delay
                    delay = await self._read_value(
                        f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Delay/Value"
                    )
                    if delay is not None:
                        channel_data["delay"] = delay
                except Exception as e:
                    _LOGGER.debug("Could not read delay for channel %d: %s", ch, e)

                status_data["channels"]["channels"].append(channel_data)

        except Exception as err:
            _LOGGER.error("Failed to get complete status: %s", err)

        _LOGGER.info("Status data retrieved: %d channels", len(status_data["channels"]["channels"]))
        return status_data

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Set mute state for a channel.
        
        Args:
            channel: Channel number (1-4)
            mute: True to mute, False to unmute
        """
        ch_index = channel - 1  # Convert to 0-based index
        param_id = f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Mute/Value"
        
        success = await self._write_value(param_id, mute, "BOOL")
        if success:
            _LOGGER.info("Set channel %d mute to %s", channel, mute)
        return success

    async def set_gain(self, channel: int, gain: float) -> bool:
        """Set gain (in dB) for a channel.
        
        Args:
            channel: Channel number (1-4)
            gain: Gain in dB (typically -80 to 0)
        """
        ch_index = channel - 1
        param_id = f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Gain/Value"
        
        # Convert dB to 0-1 range if the API expects that
        # Assuming -80dB = 0.0, 0dB = 1.0
        normalized_gain = (gain + 80) / 80
        normalized_gain = max(0.0, min(1.0, normalized_gain))
        
        success = await self._write_value(param_id, normalized_gain, "FLOAT")
        if success:
            _LOGGER.info("Set channel %d gain to %.1f dB", channel, gain)
        return success

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Set polarity for a channel.
        
        Args:
            channel: Channel number (1-4)
            inverted: True to invert polarity, False for normal
        """
        ch_index = channel - 1
        param_id = f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Polarity/Value"
        
        success = await self._write_value(param_id, inverted, "BOOL")
        if success:
            _LOGGER.info("Set channel %d polarity inverted: %s", channel, inverted)
        return success

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set delay (in milliseconds) for a channel.
        
        Args:
            channel: Channel number (1-4)
            delay_ms: Delay in milliseconds
        """
        ch_index = channel - 1
        param_id = f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Delay/Value"
        
        success = await self._write_value(param_id, delay_ms, "FLOAT")
        if success:
            _LOGGER.info("Set channel %d delay to %.1f ms", channel, delay_ms)
        return success

    async def set_matrix_gain(self, input_ch: int, output_ch: int, gain: float) -> bool:
        """Set input matrix gain.
        
        Args:
            input_ch: Input channel (1-4)
            output_ch: Output channel (1-4)
            gain: Gain value (typically 0-1, where 1 = 0dB)
        """
        in_index = input_ch - 1
        out_index = output_ch - 1
        param_id = f"/Device/Audio/Presets/Live/InputMatrix/Channels/Channel-{in_index}/Gain-{out_index}/Value"
        
        success = await self._write_value(param_id, gain, "FLOAT")
        if success:
            _LOGGER.info("Set matrix gain Input %d -> Output %d to %.2f", input_ch, output_ch, gain)
        return success

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Load a snapshot/preset.
        
        Args:
            snapshot_id: Snapshot slot ID to load
        """
        param_id = "/Device/Audio/Presets/Live/Control/LoadSnapshot/Value"
        
        success = await self._write_value(param_id, snapshot_id, "INT")
        if success:
            _LOGGER.info("Loaded snapshot %d", snapshot_id)
        return success

    async def get_current_snapshot(self) -> str:
        """Get currently loaded snapshot ID."""
        try:
            snapshot_id = await self._read_value(
                "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current"
            )
            return snapshot_id if snapshot_id else "Unknown"
        except Exception as e:
            _LOGGER.error("Failed to get current snapshot: %s", e)
            return "Unknown"
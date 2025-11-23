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

    async def get_status(self) -> dict[str, Any]:
        """Get amplifier status by reading all channels at once."""
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
            # Build a list of all parameters to read in one request
            read_values = []
            
            # Read all 4 channels' parameters at once
            for ch in range(4):
                read_values.extend([
                    {
                        "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Mute/Value",
                        "single": True
                    },
                    {
                        "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Gain/Value",
                        "single": True
                    }
                ])
            
            # Also read current snapshot
            read_values.append({
                "id": "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current",
                "single": True
            })

            # Make single bulk request
            result = await self._am_request("READ", read_values)
            
            # Parse the response
            response_values = result.get("payload", {}).get("action", {}).get("values", [])
            
            # Map responses back to channels
            # Response order matches request order: Ch0 Mute, Ch0 Gain, Ch1 Mute, Ch1 Gain, etc.
            for ch in range(4):
                mute_idx = ch * 2
                gain_idx = ch * 2 + 1
                
                channel_data = {
                    "number": ch + 1,  # Display as 1-4
                    "gain": -80.0,  # Default
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
                
                # Extract mute
                if mute_idx < len(response_values):
                    mute_data = response_values[mute_idx].get("data", {})
                    if "boolValue" in mute_data:
                        channel_data["mute"] = mute_data["boolValue"]
                
                # Extract gain
                if gain_idx < len(response_values):
                    gain_data = response_values[gain_idx].get("data", {})
                    if "floatValue" in gain_data:
                        # Convert 0-1 range to dB (-80 to 0)
                        gain_value = gain_data["floatValue"]
                        channel_data["gain"] = (gain_value * 80) - 80
                
                status_data["channels"]["channels"].append(channel_data)
            
            # Extract snapshot (last value)
            if len(response_values) > 8:
                snapshot_data = response_values[-1].get("data", {})
                if "stringValue" in snapshot_data:
                    status_data["system"]["current_snapshot"] = snapshot_data["stringValue"]

            _LOGGER.info("Successfully retrieved status for %d channels", len(status_data["channels"]["channels"]))

        except Exception as err:
            _LOGGER.error("Failed to get status: %s", err, exc_info=True)
            # Return default data with 4 channels even on error
            for ch in range(1, 5):
                if len(status_data["channels"]["channels"]) < 4:
                    status_data["channels"]["channels"].append({
                        "number": ch,
                        "gain": -80.0,
                        "mute": False,
                        "polarity": "normal",
                        "delay": 0.0,
                        "voltage": None,
                        "current": None,
                        "power": None,
                        "impedance": None,
                        "signal_present": False,
                        "clip": False
                    })

        return status_data

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Set mute state for a channel.
        
        Args:
            channel: Channel number (1-4)
            mute: True to mute, False to unmute
        """
        try:
            ch_index = channel - 1  # Convert to 0-based index
            
            values = [{
                "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Mute/Value",
                "data": {
                    "type": "BOOL",
                    "boolValue": mute
                }
            }]
            
            result = await self._am_request("WRITE", values)
            
            # Check if result is 10 (success)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Set channel %d mute to %s", channel, mute)
            else:
                _LOGGER.warning("Mute command returned code %s for channel %d", result_code, channel)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to set mute on channel %d: %s", channel, e, exc_info=True)
            return False

    async def set_gain(self, channel: int, gain: float) -> bool:
        """Set gain (in dB) for a channel.
        
        Args:
            channel: Channel number (1-4)
            gain: Gain in dB (typically -80 to 0)
        """
        try:
            ch_index = channel - 1
            
            # Convert dB to 0-1 range
            # -80dB = 0.0, 0dB = 1.0
            normalized_gain = (gain + 80) / 80
            normalized_gain = max(0.0, min(1.0, normalized_gain))
            
            values = [{
                "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Gain/Value",
                "data": {
                    "type": "FLOAT",
                    "floatValue": normalized_gain
                }
            }]
            
            result = await self._am_request("WRITE", values)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Set channel %d gain to %.1f dB (%.3f normalized)", channel, gain, normalized_gain)
            else:
                _LOGGER.warning("Gain command returned code %s for channel %d", result_code, channel)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to set gain on channel %d: %s", channel, e, exc_info=True)
            return False

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Set polarity for a channel.
        
        Args:
            channel: Channel number (1-4)
            inverted: True to invert polarity, False for normal
        """
        try:
            ch_index = channel - 1
            
            values = [{
                "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Polarity/Value",
                "data": {
                    "type": "BOOL",
                    "boolValue": inverted
                }
            }]
            
            result = await self._am_request("WRITE", values)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Set channel %d polarity inverted: %s", channel, inverted)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to set polarity on channel %d: %s", channel, e, exc_info=True)
            return False

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set delay (in milliseconds) for a channel.
        
        Args:
            channel: Channel number (1-4)
            delay_ms: Delay in milliseconds
        """
        try:
            ch_index = channel - 1
            
            values = [{
                "id": f"/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch_index}/Delay/Value",
                "data": {
                    "type": "FLOAT",
                    "floatValue": delay_ms
                }
            }]
            
            result = await self._am_request("WRITE", values)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Set channel %d delay to %.1f ms", channel, delay_ms)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to set delay on channel %d: %s", channel, e, exc_info=True)
            return False

    async def set_matrix_gain(self, input_ch: int, output_ch: int, gain: float) -> bool:
        """Set input matrix gain.
        
        Args:
            input_ch: Input channel (1-4)
            output_ch: Output channel (1-4)
            gain: Gain value (typically 0-1, where 1 = 0dB)
        """
        try:
            in_index = input_ch - 1
            out_index = output_ch - 1
            
            values = [{
                "id": f"/Device/Audio/Presets/Live/InputMatrix/Channels/Channel-{in_index}/Gain-{out_index}/Value",
                "data": {
                    "type": "FLOAT",
                    "floatValue": gain
                }
            }]
            
            result = await self._am_request("WRITE", values)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Set matrix gain Input %d -> Output %d to %.2f", input_ch, output_ch, gain)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to set matrix gain: %s", e, exc_info=True)
            return False

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Load a snapshot/preset.
        
        Args:
            snapshot_id: Snapshot slot ID to load
        """
        try:
            values = [{
                "id": "/Device/Audio/Presets/Live/Control/LoadSnapshot/Value",
                "data": {
                    "type": "INT",
                    "intValue": snapshot_id
                }
            }]
            
            result = await self._am_request("WRITE", values)
            result_code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result")
            success = result_code == 10
            
            if success:
                _LOGGER.info("Loaded snapshot %d", snapshot_id)
            
            return success
        except Exception as e:
            _LOGGER.error("Failed to load snapshot: %s", e, exc_info=True)
            return False

    async def get_current_snapshot(self) -> str:
        """Get currently loaded snapshot ID."""
        try:
            values = [{
                "id": "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current",
                "single": True
            }]
            
            result = await self._am_request("READ", values)
            snapshot_data = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("data", {})
            
            if "stringValue" in snapshot_data:
                return snapshot_data["stringValue"]
            
            return "Unknown"
        except Exception as e:
            _LOGGER.error("Failed to get current snapshot: %s", e, exc_info=True)
            return "Unknown"
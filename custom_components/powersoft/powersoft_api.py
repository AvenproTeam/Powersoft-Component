"""Powersoft API client for Quattrocanali amplifiers.

Based on the Bitfocus Companion module implementation and reverse-engineered
from the Powersoft Web App HTTP API.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)


class PowersoftAPI:
    """Client for Powersoft Quattrocanali amplifier Web App API.
    
    The Powersoft API uses a hierarchical ID system with READ/WRITE actions.
    All communication happens through POST requests to /am endpoint with JSON payloads.
    
    Example paths:
    - /Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{N}/Mute/Value
    - /Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{N}/Gain/Value
    - /Device/Audio/Presets/Live/InputMatrix/Channels/Channel-{N}/Gain-{M}/Value
    """

    # Common parameter paths
    OUTPUT_MUTE = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Mute/Value"
    OUTPUT_GAIN = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Gain/Value"
    OUTPUT_POLARITY = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Polarity/Value"
    OUTPUT_DELAY = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Delay/Value"
    MATRIX_GAIN = "/Device/Audio/Presets/Live/InputMatrix/Channels/Channel-{in_ch}/Gain-{out_ch}/Value"
    SNAPSHOT_CURRENT = "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current"
    SNAPSHOT_LOAD = "/Device/Audio/Presets/Live/Control/LoadSnapshot/Value"
    
    # Power/Standby control (these paths need verification)
    POWER_STATE = "/Device/System/PowerState/Value"
    STANDBY_STATE = "/Device/System/Standby/Value"
    
    # Monitoring paths (may vary by model)
    TEMPERATURE = "/Device/System/Temperature/Value"
    OUTPUT_VOLTAGE = "/Device/Audio/ReadOnly/OutputChannels/Channel-{ch}/Voltage/Value"
    OUTPUT_CURRENT = "/Device/Audio/ReadOnly/OutputChannels/Channel-{ch}/Current/Value"
    OUTPUT_IMPEDANCE = "/Device/Audio/ReadOnly/OutputChannels/Channel-{ch}/Impedance/Value"
    OUTPUT_SIGNAL = "/Device/Audio/ReadOnly/OutputChannels/Channel-{ch}/SignalPresent/Value"
    OUTPUT_CLIP = "/Device/Audio/ReadOnly/OutputChannels/Channel-{ch}/Clip/Value"

    def __init__(
        self,
        host: str,
        port: int = 80,
        username: Optional[str] = None,
        password: Optional[str] = None,
        num_channels: int = 4,  # Quattrocanali has 4 channels
    ):
        """Initialize the API client.
        
        Args:
            host: Amplifier IP address
            port: HTTP port (default 80)
            username: Optional authentication username
            password: Optional authentication password
            num_channels: Number of output channels (4 for Quattrocanali 8804)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.num_channels = num_channels
        self.base_url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None
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
                headers={"Content-Type": "application/json"},
            )
        return self._session

    async def close(self):
        """Close the API client."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _am_request(self, action_type: str, values: List[Dict]) -> Dict:
        """Make request to /am endpoint.
        
        Args:
            action_type: "READ" or "WRITE"
            values: List of value dictionaries
            
        Returns:
            JSON response from amplifier
            
        Raises:
            aiohttp.ClientError: On HTTP errors
        """
        session = await self._get_session()
        url = f"{self.base_url}/am"

        payload = {
            "clientId": self._client_id,
            "payload": {
                "type": "ACTION",
                "action": {"type": action_type, "values": values},
            },
        }

        try:
            _LOGGER.debug("POST %s: %s", url, payload)
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                _LOGGER.debug("Response: %s", result)
                return result
        except aiohttp.ClientError as err:
            _LOGGER.error("Request failed: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err, exc_info=True)
            raise

    def _parse_response_values(self, result: Dict) -> List[Dict]:
        """Extract values array from response."""
        try:
            return result.get("payload", {}).get("action", {}).get("values", [])
        except (KeyError, AttributeError):
            return []

    def _check_result_code(self, value: Dict) -> bool:
        """Check if operation was successful (result code 10)."""
        return value.get("result") == 10

    async def get_status(self) -> Dict[str, Any]:
        """Get complete amplifier status for all channels.
        
        Returns:
            Dict with system info and channels data
        """
        status_data = {
            "system": {
                "model": "Quattrocanali 8804 DSP",
                "firmware": "Unknown",
                "temperature": None,
                "power_state": "on",
                "serial": "Unknown",
            },
            "channels": {"channels": []},
        }

        try:
            # Build bulk read request for all channel parameters
            read_values = []

            # Read mute and gain for all channels
            for ch in range(self.num_channels):
                read_values.extend([
                    {
                        "id": self.OUTPUT_MUTE.format(ch=ch),
                        "single": True,
                    },
                    {
                        "id": self.OUTPUT_GAIN.format(ch=ch),
                        "single": True,
                    },
                ])

            # Also read current snapshot
            read_values.append({
                "id": self.SNAPSHOT_CURRENT,
                "single": True,
            })

            # Make single bulk request
            result = await self._am_request("READ", read_values)
            response_values = self._parse_response_values(result)

            # Parse responses - format: [Ch0 Mute, Ch0 Gain, Ch1 Mute, Ch1 Gain, ...]
            for ch in range(self.num_channels):
                mute_idx = ch * 2
                gain_idx = ch * 2 + 1

                channel_data = {
                    "number": ch + 1,  # Display as 1-based
                    "gain": -80.0,
                    "mute": False,
                    "polarity": "normal",
                    "delay": 0.0,
                    "voltage": None,
                    "current": None,
                    "power": None,
                    "impedance": None,
                    "signal_present": False,
                    "clip": False,
                }

                # Extract mute status
                if mute_idx < len(response_values):
                    mute_data = response_values[mute_idx].get("data", {})
                    channel_data["mute"] = mute_data.get("boolValue", False)

                # Extract gain and convert to dB
                if gain_idx < len(response_values):
                    gain_data = response_values[gain_idx].get("data", {})
                    if "floatValue" in gain_data:
                        # Powersoft uses 0.0-1.0 range, convert to -80dB to 0dB
                        normalized = gain_data["floatValue"]
                        channel_data["gain"] = (normalized * 80) - 80

                status_data["channels"]["channels"].append(channel_data)

            # Extract snapshot info (last value)
            if len(response_values) > (self.num_channels * 2):
                snapshot_data = response_values[-1].get("data", {})
                status_data["system"]["current_snapshot"] = snapshot_data.get(
                    "stringValue", "Unknown"
                )

            _LOGGER.info(
                "Status retrieved: %d channels", len(status_data["channels"]["channels"])
            )

        except Exception as err:
            _LOGGER.error("Failed to get status: %s", err, exc_info=True)
            # Return default structure even on error
            for ch in range(1, self.num_channels + 1):
                if len(status_data["channels"]["channels"]) < self.num_channels:
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
                        "clip": False,
                    })

        return status_data

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Set mute state for a channel.
        
        Args:
            channel: Channel number (1-based, 1-4)
            mute: True to mute, False to unmute
            
        Returns:
            True if successful
        """
        try:
            ch_index = channel - 1
            values = [
                {
                    "id": self.OUTPUT_MUTE.format(ch=ch_index),
                    "data": {"type": "BOOL", "boolValue": mute},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info("Channel %d mute set to %s", channel, mute)
                return True

            _LOGGER.warning(
                "Mute command failed for channel %d, result: %s",
                channel,
                response_values[0].get("result") if response_values else "no response",
            )
            return False

        except Exception as e:
            _LOGGER.error(
                "Failed to set mute on channel %d: %s", channel, e, exc_info=True
            )
            return False

    async def set_gain(self, channel: int, gain_db: float) -> bool:
        """Set gain for a channel.
        
        Args:
            channel: Channel number (1-based, 1-4)
            gain_db: Gain in dB (typically -80 to 0)
            
        Returns:
            True if successful
        """
        try:
            ch_index = channel - 1

            # Convert dB to normalized 0-1 range
            # -80dB = 0.0, 0dB = 1.0
            normalized_gain = (gain_db + 80) / 80
            normalized_gain = max(0.0, min(1.0, normalized_gain))

            values = [
                {
                    "id": self.OUTPUT_GAIN.format(ch=ch_index),
                    "data": {"type": "FLOAT", "floatValue": normalized_gain},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info(
                    "Channel %d gain set to %.1f dB (%.3f)",
                    channel,
                    gain_db,
                    normalized_gain,
                )
                return True

            return False

        except Exception as e:
            _LOGGER.error(
                "Failed to set gain on channel %d: %s", channel, e, exc_info=True
            )
            return False

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Set polarity (phase inversion) for a channel.
        
        Args:
            channel: Channel number (1-based, 1-4)
            inverted: True to invert, False for normal
            
        Returns:
            True if successful
        """
        try:
            ch_index = channel - 1
            values = [
                {
                    "id": self.OUTPUT_POLARITY.format(ch=ch_index),
                    "data": {"type": "BOOL", "boolValue": inverted},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info("Channel %d polarity inverted: %s", channel, inverted)
                return True

            return False

        except Exception as e:
            _LOGGER.error(
                "Failed to set polarity on channel %d: %s", channel, e, exc_info=True
            )
            return False

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set delay for a channel.
        
        Args:
            channel: Channel number (1-based, 1-4)
            delay_ms: Delay in milliseconds
            
        Returns:
            True if successful
        """
        try:
            ch_index = channel - 1
            values = [
                {
                    "id": self.OUTPUT_DELAY.format(ch=ch_index),
                    "data": {"type": "FLOAT", "floatValue": delay_ms},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info("Channel %d delay set to %.1f ms", channel, delay_ms)
                return True

            return False

        except Exception as e:
            _LOGGER.error(
                "Failed to set delay on channel %d: %s", channel, e, exc_info=True
            )
            return False

    async def set_matrix_gain(
        self, input_ch: int, output_ch: int, gain: float
    ) -> bool:
        """Set input matrix routing gain.
        
        Args:
            input_ch: Input channel (1-based, 1-4)
            output_ch: Output channel (1-based, 1-4)
            gain: Gain value (0.0-1.0, where 1.0 = 0dB)
            
        Returns:
            True if successful
        """
        try:
            in_index = input_ch - 1
            out_index = output_ch - 1

            values = [
                {
                    "id": self.MATRIX_GAIN.format(in_ch=in_index, out_ch=out_index),
                    "data": {"type": "FLOAT", "floatValue": gain},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info(
                    "Matrix gain Input %d → Output %d set to %.2f",
                    input_ch,
                    output_ch,
                    gain,
                )
                return True

            return False

        except Exception as e:
            _LOGGER.error("Failed to set matrix gain: %s", e, exc_info=True)
            return False

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Load a snapshot/preset.
        
        Args:
            snapshot_id: Snapshot slot ID
            
        Returns:
            True if successful
        """
        try:
            values = [
                {
                    "id": self.SNAPSHOT_LOAD,
                    "data": {"type": "INT", "intValue": snapshot_id},
                }
            ]

            result = await self._am_request("WRITE", values)
            response_values = self._parse_response_values(result)

            if response_values and self._check_result_code(response_values[0]):
                _LOGGER.info("Loaded snapshot %d", snapshot_id)
                return True

            return False

        except Exception as e:
            _LOGGER.error("Failed to load snapshot: %s", e, exc_info=True)
            return False

    async def get_current_snapshot(self) -> str:
        """Get currently loaded snapshot ID.
        
        Returns:
            Snapshot ID as string, or "Unknown" on error
        """
        try:
            values = [{"id": self.SNAPSHOT_CURRENT, "single": True}]

            result = await self._am_request("READ", values)
            response_values = self._parse_response_values(result)

            if response_values:
                snapshot_data = response_values[0].get("data", {})
                return snapshot_data.get("stringValue", "Unknown")

            return "Unknown"

        except Exception as e:
            _LOGGER.error("Failed to get current snapshot: %s", e, exc_info=True)
            return "Unknown"

    async def power_on(self) -> bool:
        """Turn on the amplifier (exit standby mode).
        
        Returns:
            True if successful
        """
        try:
            # Try common power state paths
            # The exact path may vary by model
            paths_to_try = [
                self.POWER_STATE,
                self.STANDBY_STATE,
                "/Device/System/Control/PowerOn/Value",
                "/Device/Control/PowerState/Value",
            ]
            
            for path in paths_to_try:
                try:
                    values = [
                        {
                            "id": path,
                            "data": {"type": "BOOL", "boolValue": True},
                        }
                    ]
                    
                    result = await self._am_request("WRITE", values)
                    response_values = self._parse_response_values(result)
                    
                    if response_values and self._check_result_code(response_values[0]):
                        _LOGGER.info("Amplifier powered on using path: %s", path)
                        return True
                except Exception as e:
                    _LOGGER.debug("Path %s failed: %s", path, e)
                    continue
            
            _LOGGER.warning("Could not find valid power on endpoint")
            return False

        except Exception as e:
            _LOGGER.error("Failed to power on: %s", e, exc_info=True)
            return False

    async def power_off(self) -> bool:
        """Turn off the amplifier (enter standby mode).
        
        Returns:
            True if successful
        """
        try:
            # Try common power state paths
            paths_to_try = [
                self.STANDBY_STATE,
                self.POWER_STATE,
                "/Device/System/Control/Standby/Value",
                "/Device/Control/PowerState/Value",
            ]
            
            for path in paths_to_try:
                try:
                    values = [
                        {
                            "id": path,
                            "data": {"type": "BOOL", "boolValue": False},
                        }
                    ]
                    
                    result = await self._am_request("WRITE", values)
                    response_values = self._parse_response_values(result)
                    
                    if response_values and self._check_result_code(response_values[0]):
                        _LOGGER.info("Amplifier powered off using path: %s", path)
                        return True
                except Exception as e:
                    _LOGGER.debug("Path %s failed: %s", path, e)
                    continue
            
            _LOGGER.warning("Could not find valid power off endpoint")
            return False

        except Exception as e:
            _LOGGER.error("Failed to power off: %s", e, exc_info=True)
            return False
"""Powersoft API client (Quattrocanali / X / T / Unica Web App HTTP API).

All communication happens through POST requests to the ``/am`` endpoint with a
JSON payload describing a READ or WRITE action over hierarchical parameter IDs,
for example::

    /Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{N}/Mute/Value

Channel indexes on the wire are 0-based; this client exposes 1-based channels.
"""
from __future__ import annotations

from enum import IntEnum
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_VERSION = "1.0.0"
CLIENT_ID = "homeassistant-powersoft"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)

# Agile protocol codes (same as the embedded Web App)
PAYLOAD_ACTION = 100
ACTION_READ = 10
ACTION_WRITE = 20
RESULT_OK = 10


class ValueType(IntEnum):
    """``data.type`` codes and the field that carries each value."""

    STRING = 10
    FLOAT = 20
    INT = 30
    BOOL = 40
    FLOAT_ARRAY = 50
    UINT = 60


VALUE_FIELDS = {
    ValueType.STRING: "stringValue",
    ValueType.FLOAT: "floatValue",
    ValueType.INT: "intValue",
    ValueType.BOOL: "boolValue",
    ValueType.FLOAT_ARRAY: "floatArrayValue",
    ValueType.UINT: "uintValue",
}


class PowersoftError(Exception):
    """Base error for the Powersoft API."""


class PowersoftConnectionError(PowersoftError):
    """The amplifier could not be reached or returned an invalid response."""


class PowersoftAuthError(PowersoftError):
    """The amplifier rejected the credentials."""


class PowersoftAPI:
    """Client for the Powersoft amplifier Web App API."""

    # Identity
    DEVICE_NAME = "/Device/Config/Name"
    FIRMWARE = "/Device/Config/Software/Firmware/Version"
    SERIAL = "/Device/Config/Hardware/Model/Serial"
    CHANNEL_COUNT = "/Device/Config/Hardware/Channels"

    # Control parameters
    OUTPUT_MUTE = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Mute/Value"
    OUTPUT_GAIN = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Gain/Value"
    OUTPUT_POLARITY = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Polarity/Value"
    OUTPUT_DELAY = "/Device/Audio/Presets/Live/OutputProcess/Channels/Channel-{ch}/Delay/Value"
    MATRIX_GAIN = "/Device/Audio/Presets/Live/InputMatrix/Channels/Channel-{in_ch}/Gain-{out_ch}/Value"
    SNAPSHOT_CURRENT = "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current"
    SNAPSHOT_LOAD = "/Device/Audio/Presets/Live/Control/LoadSnapshot/Value"
    STANDBY_STATE = "/Device/Audio/Presets/Live/Generals/Standby/Value"
    INPUT_MUTE = "/Device/Audio/Presets/Live/InputProcess/Channels/Channel-{ch}/Mute/Value"
    SPEAKER_NAME = "/Device/Audio/Presets/Live/SpeakerLayout/Speaker-{ch}/ModelName"

    # Gain is exchanged as a normalised 0..1 value mapped to -80..0 dB
    GAIN_MIN_DB = -80.0
    GAIN_MAX_DB = 0.0

    def __init__(
        self,
        host: str,
        port: int = 80,
        username: str | None = None,
        password: str | None = None,
        num_channels: int = 4,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client.

        If ``session`` is given (Home Assistant's shared session) it is reused
        and never closed by this client.
        """
        self.host = host
        self.port = port
        self.num_channels = num_channels
        self.base_url = f"http://{host}:{port}"
        self._auth = (
            aiohttp.BasicAuth(username, password) if username and password else None
        )
        self._session = session
        self._owns_session = session is None
        # None = not probed yet, False = model does not expose these paths
        self._optional_supported: dict[str, bool] = {}

    # ------------------------------------------------------------------ helpers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if this client created it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _am_request(self, action_type: int, values: list[dict]) -> list[dict]:
        """POST an action to ``/am`` and return the response ``values`` list."""
        session = await self._get_session()
        payload = {
            "version": API_VERSION,
            "clientId": CLIENT_ID,
            "payload": {
                "type": PAYLOAD_ACTION,
                "action": {"type": action_type, "values": values},
            },
        }
        _LOGGER.debug("POST %s/am %s", self.base_url, payload)
        try:
            async with session.post(
                f"{self.base_url}/am",
                json=payload,
                auth=self._auth,
                timeout=DEFAULT_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise PowersoftAuthError(f"Authentication failed ({response.status})")
                response.raise_for_status()
                result = await response.json(content_type=None)
        except PowersoftError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise PowersoftConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err

        _LOGGER.debug("Response: %s", result)
        if not isinstance(result, dict):
            raise PowersoftConnectionError("Unexpected response format")
        values_out = result.get("payload", {}).get("action", {}).get("values", [])
        return values_out if isinstance(values_out, list) else []

    @staticmethod
    def _ok(value: dict | None) -> bool:
        """Return True if a response value reports success (or has no code)."""
        return bool(value) and value.get("result", RESULT_OK) == RESULT_OK

    @staticmethod
    def _extract(value: dict | None) -> Any:
        """Return the typed payload of a response value, or None."""
        if not PowersoftAPI._ok(value):
            return None
        data = value.get("data") or {}
        try:
            key = VALUE_FIELDS[ValueType(data.get("type"))]
        except ValueError:
            key = None
        if key and key in data:
            return data[key]
        for key in VALUE_FIELDS.values():  # untyped / unknown type code
            if key in data:
                return data[key]
        return None

    async def _read(self, ids: list[str]) -> list[Any]:
        """Bulk-read parameters, returning values aligned with ``ids``."""
        response = await self._am_request(
            ACTION_READ, [{"id": pid, "single": True} for pid in ids]
        )
        by_id = {v.get("id"): v for v in response if isinstance(v, dict) and v.get("id")}
        out: list[Any] = []
        for idx, pid in enumerate(ids):
            value = by_id.get(pid)
            if value is None and idx < len(response):
                value = response[idx]
            out.append(self._extract(value))
        return out

    async def _write(self, pid: str, value_type: ValueType, value: Any) -> bool:
        data = {"type": int(value_type), VALUE_FIELDS[value_type]: value}
        response = await self._am_request(ACTION_WRITE, [{"id": pid, "data": data}])
        if response and self._ok(response[0]):
            return True
        _LOGGER.warning(
            "Write to %s failed, result: %s",
            pid,
            response[0].get("result") if response else "no response",
        )
        return False

    async def _read_optional(self, group: str, ids: list[str]) -> list[Any]:
        """Read parameters that may not exist on every model.

        The group is probed once; if nothing comes back it is skipped on
        subsequent polls so it cannot break or slow down the main update.
        """
        if self._optional_supported.get(group) is False:
            return [None] * len(ids)
        try:
            values = await self._read(ids)
        except PowersoftError as err:
            if group not in self._optional_supported:
                _LOGGER.debug("Optional group %s not available: %s", group, err)
                self._optional_supported[group] = False
            return [None] * len(ids)
        if group not in self._optional_supported:
            self._optional_supported[group] = any(v is not None for v in values)
            if not self._optional_supported[group]:
                _LOGGER.info("Amplifier does not expose %s parameters", group)
        return values

    @classmethod
    def gain_to_db(cls, normalized: float) -> float:
        return round(normalized * (cls.GAIN_MAX_DB - cls.GAIN_MIN_DB) + cls.GAIN_MIN_DB, 2)

    @classmethod
    def db_to_gain(cls, gain_db: float) -> float:
        value = (gain_db - cls.GAIN_MIN_DB) / (cls.GAIN_MAX_DB - cls.GAIN_MIN_DB)
        return max(0.0, min(1.0, value))

    # ------------------------------------------------------------------ status

    async def get_device_info(self) -> dict[str, Any]:
        """Read model name, firmware, serial number and channel count."""
        name, firmware, serial, channels = await self._read(
            [self.DEVICE_NAME, self.FIRMWARE, self.SERIAL, self.CHANNEL_COUNT]
        )
        if all(v is None for v in (name, firmware, serial)):
            raise PowersoftConnectionError("Amplifier returned no identity data")
        try:
            num_channels = int(str(channels)) if channels is not None else None
        except ValueError:
            num_channels = None
        if num_channels is not None and not 1 <= num_channels <= 16:
            num_channels = None
        return {
            "model": str(name).strip() if name else None,
            "firmware": str(firmware).strip() if firmware else None,
            "serial": str(serial).strip() if serial not in (None, "") else None,
            "channels": num_channels,
        }

    async def test_connection(self) -> dict[str, Any]:
        """Return the device info, raising PowersoftError if unreachable."""
        return await self.get_device_info()

    async def get_status(self) -> dict[str, Any]:
        """Return the controllable state of the amplifier.

        Raises PowersoftError if the amplifier cannot be reached, so the
        coordinator marks the entities unavailable instead of showing stale or
        made-up values. Live meters come from Socket.IO (powersoft_live).
        """
        channels = range(self.num_channels)

        # Core parameters (verified on Quattrocanali 4804 DSP): must succeed.
        core_ids = [self.SNAPSHOT_CURRENT, self.STANDBY_STATE]
        for ch in channels:
            core_ids += [
                self.OUTPUT_MUTE.format(ch=ch),
                self.OUTPUT_GAIN.format(ch=ch),
                self.SPEAKER_NAME.format(ch=ch),
            ]
        core = await self._read(core_ids)

        # Optional parameters: probed once, skipped if the model lacks them.
        dsp = await self._read_optional(
            "dsp",
            [
                pid.format(ch=ch)
                for ch in channels
                for pid in (self.OUTPUT_POLARITY, self.OUTPUT_DELAY, self.INPUT_MUTE)
            ],
        )

        snapshot, standby = core[0], normalize_standby(core[1])
        status: dict[str, Any] = {
            "system": {
                "standby": standby,
                "power_state": None if standby is None else ("standby" if standby else "on"),
                "current_snapshot": snapshot,
            },
            "channels": {},
        }
        for ch in channels:
            mute, gain, speaker = core[2 + ch * 3: 5 + ch * 3]
            polarity, delay, input_mute = dsp[ch * 3: 3 + ch * 3]
            status["channels"][ch + 1] = {
                "number": ch + 1,
                "mute": bool(mute) if mute is not None else None,
                "gain": self.gain_to_db(gain) if gain is not None else None,
                "speaker": str(speaker).strip() or None if speaker else None,
                "polarity_inverted": bool(polarity) if polarity is not None else None,
                "delay": _as_float(delay),
                "input_mute": bool(input_mute) if input_mute is not None else None,
            }
        return status

    # ------------------------------------------------------------------ control

    async def set_mute(self, channel: int, mute: bool) -> bool:
        """Mute (True) or unmute (False) an output channel (1-based)."""
        return await self._write(
            self.OUTPUT_MUTE.format(ch=channel - 1), ValueType.BOOL, bool(mute)
        )

    async def set_input_mute(self, channel: int, mute: bool) -> bool:
        """Mute (True) or unmute (False) an input channel (1-based)."""
        return await self._write(
            self.INPUT_MUTE.format(ch=channel - 1), ValueType.BOOL, bool(mute)
        )

    async def set_gain(self, channel: int, gain_db: float) -> bool:
        """Set the output gain in dB (-80..0) of a channel (1-based)."""
        return await self._write(
            self.OUTPUT_GAIN.format(ch=channel - 1),
            ValueType.FLOAT,
            self.db_to_gain(gain_db),
        )

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        """Invert (True) or restore (False) the polarity of a channel."""
        return await self._write(
            self.OUTPUT_POLARITY.format(ch=channel - 1), ValueType.BOOL, bool(inverted)
        )

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        """Set the output delay in milliseconds of a channel."""
        return await self._write(
            self.OUTPUT_DELAY.format(ch=channel - 1), ValueType.FLOAT, float(delay_ms)
        )

    async def set_matrix_gain(self, input_ch: int, output_ch: int, gain: float) -> bool:
        """Set the input-matrix routing gain (0.0..1.0, 1.0 = 0 dB)."""
        return await self._write(
            self.MATRIX_GAIN.format(in_ch=input_ch - 1, out_ch=output_ch - 1),
            ValueType.FLOAT,
            max(0.0, min(1.0, float(gain))),
        )

    async def load_snapshot(self, snapshot_id: int) -> bool:
        """Recall a snapshot / preset slot."""
        return await self._write(self.SNAPSHOT_LOAD, ValueType.INT, int(snapshot_id))

    async def set_standby(self, standby: bool) -> bool:
        """Enter (True) or leave (False) standby.

        Some firmwares (e.g. Quattrocanali 4804 DSP) store standby as an INT,
        so fall back to 0/1 if the BOOL write is rejected.
        """
        if await self._write(self.STANDBY_STATE, ValueType.BOOL, bool(standby)):
            return True
        return await self._write(self.STANDBY_STATE, ValueType.INT, 1 if standby else 0)

    async def power_on(self) -> bool:
        """Turn the amplifier on (leave standby)."""
        return await self.set_standby(False)

    async def power_off(self) -> bool:
        """Put the amplifier in standby."""
        return await self.set_standby(True)


def normalize_standby(raw: Any) -> bool | None:
    """Return True when in standby; the value may be BOOL, INT or STRING."""
    if raw is None:
        return None
    if isinstance(raw, (bool, int, float)):
        return bool(raw)
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in {"true", "1", "on", "standby"}:
            return True
        if text in {"false", "0", "off"}:
            return False
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None

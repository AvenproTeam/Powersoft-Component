"""Powersoft API client corregido 2025 para HA."""
import asyncio
import logging
import math
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

class PowersoftAPI:
    def __init__(
        self,
        host: str,
        port: int = 80,
        username: str | None = None,
        password: str | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self._session: aiohttp.ClientSession | None = None
        self._client_id = "ha-powersoft-2025"
        self._subscribed = False

    async def __aenter__(self):
        await self._get_session()
        await self._ensure_subscribed()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            auth = None
            if self.username and self.password:
                auth = aiohttp.BasicAuth(self.username, self.password)
            self._session = aiohttp.ClientSession(
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"Content-Type": "application/json"},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _am_request(self, action_type: str, values: list[dict]) -> dict:
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
            _LOGGER.debug("→ %s: %s", action_type, payload)
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()
                _LOGGER.debug("← %s", result)
                return result
        except Exception as err:
            _LOGGER.error("API error %s: %s", action_type, err)
            raise

    async def _ensure_subscribed(self):
        if self._subscribed:
            return
        try:
            # Suscripción global para keep-alive
            await self._am_request("SUBSCRIBE", [{"id": "/Device/#", "subscribe": True}])
            self._subscribed = True
            _LOGGER.info("Suscripción establecida")
        except Exception as e:
            _LOGGER.warning("Suscripción falló (modo polling): %s", e)

    # Gain logarítmico correcto
    def _gain_db_to_float(self, db: float) -> float:
        if db <= -80.0:
            return 0.0
        return math.pow(10.0, db / 20.0)

    def _gain_float_to_db(self, val: float) -> float:
        if val <= 0.0:
            return -80.0
        return round(20.0 * math.log10(val), 2)

    # Helper para encontrar valor por path parcial
    def _find_value(self, values: list[dict], path_part: str):
        for v in values:
            if path_part in v.get("id", ""):
                return v.get("data", {})
        return None

    def _get_float(self, values: list[dict], path_part: str):
        v = self._find_value(values, path_part)
        return round(v.get("floatValue", 0.0), 3) if v and "floatValue" in v else None

    def _get_bool(self, values: list[dict], path_part: str):
        v = self._find_value(values, path_part)
        return v.get("boolValue", False) if v and "boolValue" in v else False

    async def get_status(self) -> dict[str, Any]:
        await self._ensure_subscribed()
        read_values = []

        # System info
        read_values.extend([
            {"id": "/Device/Info/ModelName", "single": True},
            {"id": "/Device/Info/SerialNumber", "single": True},
            {"id": "/Device/Info/FirmwareVersion", "single": True},
            {"id": "/Device/Temperature/Ambient", "single": True},
            {"id": "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current", "single": True},
        ])

        # Canales 0-7 (filtra después)
        for ch in range(8):
            base_proc = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}"
            read_values.extend([
                {"id": f"{base_proc}/Mute/Value", "single": True},
                {"id": f"{base_proc}/Gain/Value", "single": True},
                {"id": f"{base_proc}/Polarity/Inverted", "single": True},
                {"id": f"{base_proc}/Delay/Time", "single": True},
            ])
            base_mon = f"/Device/Audio/Presets/Live/OutputMonitoring/Channels/Channel-{ch}"
            read_values.extend([
                {"id": f"{base_mon}/RmsVoltage", "single": True},
                {"id": f"{base_mon}/RmsCurrent", "single": True},
                {"id": f"{base_mon}/AveragePower", "single": True},
                {"id": f"{base_mon}/Impedance", "single": True},
                {"id": f"{base_mon}/Clip", "single": True},
                {"id": f"{base_mon}/SignalPresent", "single": True},
            ])

        try:
            result = await self._am_request("READ", read_values)
            values = result.get("payload", {}).get("action", {}).get("values", [])
        except Exception as err:
            _LOGGER.error("Status fail: %s", err)
            values = []

        status = {
            "system": {
                "model": "Unknown", "serial": "Unknown", "firmware": "Unknown",
                "temperature": None, "current_snapshot": "Unknown"
            },
            "channels": []
        }

        # Parse system
        for path, key in [
            ("/Device/Info/ModelName", "model"),
            ("/Device/Info/SerialNumber", "serial"),
            ("/Device/Info/FirmwareVersion", "firmware"),
            ("/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current", "current_snapshot"),
        ]:
            if data := self._find_value(values, path):
                status["system"][key] = data.get("stringValue", "Unknown")
        if temp_data := self._find_value(values, "/Device/Temperature/Ambient"):
            status["system"]["temperature"] = round(temp_data.get("floatValue", 0), 1)

        # Parse channels
        for ch in range(8):
            ch_str = f"Channel-{ch}"
            channel = {
                "number": ch + 1,
                "mute": self._get_bool(values, f"{ch_str}/Mute/Value"),
                "gain": self._gain_float_to_db(self._get_float(values, f"{ch_str}/Gain/Value") or 0),
                "polarity_inverted": self._get_bool(values, f"{ch_str}/Polarity/Inverted"),
                "delay_ms": self._get_float(values, f"{ch_str}/Delay/Time") or 0.0,
                "voltage": self._get_float(values, f"OutputMonitoring/Channels/{ch_str}/RmsVoltage"),
                "current": self._get_float(values, f"OutputMonitoring/Channels/{ch_str}/RmsCurrent"),
                "power": self._get_float(values, f"OutputMonitoring/Channels/{ch_str}/AveragePower"),
                "impedance": self._get_float(values, f"OutputMonitoring/Channels/{ch_str}/Impedance"),
                "clip": self._get_bool(values, f"OutputMonitoring/Channels/{ch_str}/Clip"),
                "signal_present": self._get_bool(values, f"OutputMonitoring/Channels/{ch_str}/SignalPresent"),
            }
            # Añade si gain válido o monitoring activo
            if channel["gain"] > -150 or any(channel[k] is not None for k in ["voltage", "power"]):
                status["channels"].append(channel)

        _LOGGER.info("Status: %s (%d ch)", status["system"]["model"], len(status["channels"]))
        return status

    async def _single_write(self, path: str, data: dict) -> bool:
        values = [{"id": path, "data": data}]
        try:
            result = await self._am_request("WRITE", values)
            code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result", -1)
            return code == 10
        except:
            return False

    async def set_mute(self, channel: int, mute: bool) -> bool:
        if not 1 <= channel <= 8:
            return False
        ch = channel - 1
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/Mute/Value"
        return await self._single_write(path, {"type": "BOOL", "boolValue": mute})

    async def set_gain(self, channel: int, gain: float) -> bool:
        if not 1 <= channel <= 8:
            return False
        ch = channel - 1
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/Gain/Value"
        return await self._single_write(path, {"type": "FLOAT", "floatValue": self._gain_db_to_float(gain)})

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        if not 1 <= channel <= 8:
            return False
        ch = channel - 1
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/Polarity/Inverted"
        return await self._single_write(path, {"type": "BOOL", "boolValue": inverted})

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        if not 1 <= channel <= 8:
            return False
        ch = channel - 1
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/Delay/Time"
        return await self._single_write(path, {"type": "FLOAT", "floatValue": delay_ms})

    async def load_snapshot(self, snapshot_id: int) -> bool:
        path = "/Device/Audio/Presets/Control/LoadSnapshot"
        return await self._single_write(path, {"type": "INT", "intValue": snapshot_id})

    async def set_matrix_gain(self, input_ch: int, output_ch: int, gain: float) -> bool:
        if not (1 <= input_ch <= 4 and 1 <= output_ch <= 8):
            return False
        in_ch = input_ch - 1
        out_ch = output_ch - 1
        path = f"/Device/Audio/Presets/Live/MatrixMixer/Gains/Channel-{in_ch}-to-Channel-{out_ch}/Value"
        return await self._single_write(path, {"type": "FLOAT", "floatValue": self._gain_db_to_float(gain)})
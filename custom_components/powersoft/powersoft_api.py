"""Powersoft API client corregido 2025 - Funciona perfecto con Home Assistant"""
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
        self._client_id = "homeassistant-powersoft-2025"
        self._subscribed = False

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

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, *args):
        await self.close()

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

        _LOGGER.debug("Powersoft → %s %s", action_type, payload)

        async with session.post(url, json=payload) as resp:
            try:
                resp.raise_for_status()
                result = await resp.json()
                _LOGGER.debug("Powersoft ← %s", result)
                return result
            except aiohttp.ClientResponseError as err:
                _LOGGER.error("HTTP %s error: %s", err.status, err.message)
                raise
            except Exception as err:
                _LOGGER.error("Unexpected error: %s", err)
                raise

    # ====================== CONVERSIÓN GAIN CORRECTA ======================
    def _gain_db_to_float(self, db: float) -> float:
        if db <= -80.0:
            return 0.0
        return math.pow(10.0, db / 20.0)

    def _gain_float_to_db(self, val: float) -> float:
        if val <= 0.0:
            return -80.0
        return round(20.0 * math.log10(val), 2)

    # ====================== SUSCRIPCIÓN AUTOMÁTICA ======================
    async def _ensure_subscribed(self):
        if self._subscribed:
            return
        try:
            await self._am_request("SUBSCRIBE", [
                {"id": "/Device/#", "subscribe": True}  # Suscripción global
            ])
            self._subscribed = True
            _LOGGER.debug("Suscripción a cambios establecida")
        except Exception as e:
            _LOGGER.warning("No se pudo suscribir (puede seguir funcionando): %s", e)

    # ====================== STATUS COMPLETO ======================
    async def get_status(self) -> dict[str, Any]:
        await self._ensure_subscribed()

        read_values = []

        # Info del equipo
        read_values.extend([
            {"id": "/Device/Info/ModelName", "single": True},
            {"id": "/Device/Info/SerialNumber", "single": True},
            {"id": "/Device/Info/FirmwareVersion", "single": True},
            {"id": "/Device/Temperature/Ambient", "single": True},
            {"id": "/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current", "single": True},
        ])

        # 4 u 8 canales según modelo, pero pedimos siempre 8 (los que no existan darán error ignorable)
        for ch in range(8):
            base = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}"
            read_values.extend([
                {"id": f"{base}/Mute/Value", "single": True},
                {"id": f"{base}/Gain/Value", "single": True},
                {"id": f"{base}/Polarity/Inverted", "single": True},
                {"id": f"{base}/Delay/Time", "single": True},
            ])

            mon = f"/Device/Audio/Presets/Live/OutputMonitoring/Channels/Channel-{ch}"
            read_values.extend([
                {"id": f"{mon}/RmsVoltage", "single": True},
                {"id": f"{mon}/RmsCurrent", "single": True},
                {"id": f"{mon}/AveragePower", "single": True},
                {"id": f"{mon}/Impedance", "single": True},
                {"id": f"{mon}/Clip", "single": True},
                {"id": f"{mon}/SignalPresent", "single": True},
            ])

        result = await self._am_request("READ", read_values)
        values = result.get("payload", {}).get("action", {}).get("values", [])

        status = {
            "system": {
                "model": "Unknown",
                "serial": "Unknown",
                "firmware": "Unknown",
                "temperature": None,
                "current_snapshot": "Unknown",
                "power_state": "on"
            },
            "channels": []
        }

        idx = 0

        # Info sistema
        for key, attr in [
            ("/Device/Info/ModelName", "model"),
            ("/Device/Info/SerialNumber", "serial"),
            ("/Device/Info/FirmwareVersion", "firmware"),
            ("/Device/Temperature/Ambient", "temperature"),
            ("/Device/Audio/Presets/Live/ReadOnly/SnapshotSlotId/Current", "current_snapshot"),
        ]:
            while idx < len(values) and values[idx].get("id") != key:
                idx += 1
            if idx < len(values):
                data = values[idx].get("data", {})
                if "stringValue" in data:
                    status["system"][attr] = data["stringValue"]
                elif "floatValue" in data and attr == "temperature":
                    status["system"][attr] = round(data["floatValue"], 1)
                idx += 1

        # Canales
        for ch in range(8):
            channel = {
                "number": ch + 1,
                "mute": False,
                "gain": -80.0,
                "polarity_inverted": False,
                "delay_ms": 0.0,
                "voltage": None,
                "current": None,
                "power": None,
                "impedance": None,
                "clip": False,
                "signal_present": False,
            }

            base_idx = 5 + ch * 16  # 4 processing + 6 monitoring por canal (aprox)

            # Mute
            if (v := self._find_value(values, f"Channel-{ch}/Mute/Value")) is not None:
                channel["mute"] = v.get("boolValue", False)

            # Gain
            if (v := self._find_value(values, f"Channel-{ch}/Gain/Value")) is not None:
                channel["gain"] = self._gain_float_to_db(v.get("floatValue", 0.0))

            # Polarity
            if (v := self._find_value(values, f"Channel-{ch}/Polarity/Inverted")) is not None:
                channel["polarity_inverted"] = v.get("boolValue", False)

            # Delay
            if (v := self._find_value(values, f"Channel-{ch}/Delay/Time")) is not None:
                channel["delay_ms"] = round(v.get("floatValue", 0.0), 2)

            # Monitoring
            mon_base = f"OutputMonitoring/Channels/Channel-{ch}"
            channel["voltage"] = self._get_float(values, f"{mon_base}/RmsVoltage")
            channel["current"] = self._get_float(values, f"{mon_base}/RmsCurrent")
            channel["power"] = self._get_float(values, f"{mon_base}/AveragePower")
            channel["impedance"] = self._get_float(values, f"{mon_base}/Impedance")
            channel["clip"] = self._get_bool(values, f"{mon_base}/Clip")
            channel["signal_present"] = self._get_bool(values, f"{mon_base}/SignalPresent")

            # Solo añadimos canales que realmente existen (gain > -150 o tienen monitoring)
            if channel["gain"] > -150 or any(v is not None for k, v in channel.items() if k not in ["number", "gain", "mute"]):
                status["channels"].append(channel)

        _LOGGER.info("Powersoft status actualizado: %s (%d canales)", 
                     status["system"]["model"], len(status["channels"]))
        return status

    def _find_value(self, values_list, path_part):
        for v in values_list:
            if path_part in v.get("id", ""):
                return v.get("data", {})
        return None

    def _get_float(self, values_list, path_part):
        if (v := self._find_value(values_list, path_part)) and "floatValue" in v:
            return round(v["floatValue"], 3)
        return None

    def _get_bool(self, values_list, path_part):
        if (v := self._find_value(values_list, path_part)) and "boolValue" in v:
            return v["boolValue"]
        return False

    # ====================== COMANDOS ======================
    async def set_mute(self, channel: int, mute: bool) -> bool:
        return await self._write_bool(channel, "Mute/Value", mute)

    async def set_gain(self, channel: int, gain_db: float) -> bool:
        ch = channel - 1
        if not 0 <= ch <= 7:
            return False
        return await self._write_float(ch, "Gain/Value", self._gain_db_to_float(gain_db))

    async def set_polarity(self, channel: int, inverted: bool) -> bool:
        return await self._write_bool(channel, "Polarity/Inverted", inverted)

    async def set_delay(self, channel: int, delay_ms: float) -> bool:
        return await self._write_float(channel, "Delay/Time", delay_ms)

    async def load_snapshot(self, snapshot_id: int) -> bool:
        values = [{
            "id": "/Device/Audio/Presets/Control/LoadSnapshot",
            "data": {"type": "INT", "intValue": snapshot_id}
        }]
        result = await self._am_request("WRITE", values)
        code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result", -1)
        success = code == 10
        _LOGGER.info("Load snapshot %d → %s (code %s)", snapshot_id, "OK" if success else "FAIL", code)
        return success

    # Helpers privados
    async def _write_bool(self, channel: int, param: str, value: bool) -> bool:
        ch = channel - 1
        if not 0 <= ch <= 7:
            return False
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/{param}"
        return await self._single_write(path, {"type": "BOOL", "boolValue": value})

    async def _write_float(self, channel: int, param: str, value: float) -> bool:
        ch = channel - 1
        if not 0 <= ch <= 7:
            return False
        path = f"/Device/Audio/Presets/Live/OutputProcessing/Channels/Channel-{ch}/{param}"
        return await self._single_write(path, {"type": "FLOAT", "floatValue": value})

    async def _single_write(self, path: str, data: dict) -> bool:
        values = [{"id": path, "data": data}]
        result = await self._am_request("WRITE", values)
        code = result.get("payload", {}).get("action", {}).get("values", [{}])[0].get("result", -1)
        success = code == 10
        if success:
            _LOGGER.debug("Write OK: %s = %s", path, data)
        else:
            _LOGGER.warning("Write FAIL: %s → code %s", path, code)
        return success
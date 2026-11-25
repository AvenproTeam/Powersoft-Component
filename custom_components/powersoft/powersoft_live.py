"""Powersoft live meters over Socket.IO (Engine.IO v3, WebSocket transport).

The amplifier's embedded Web App receives its meters through Socket.IO
``status-update`` events instead of polling ``/am``::

    42["status-update",{"payload":{"readings":{"meters":{...}}}}]
    42["status-update",{"payload":{"readings":{"slows":{...}}}}]

``meters.output_process[]`` carries per-channel output readings and
``slows`` carries temperatures and the standby / fault state. Verified on a
Quattrocanali 4804 DSP (firmware 1.12.0.696).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import math
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

SOCKETIO_PATH = "/socket.io/?EIO=3&transport=websocket"
GR_ACTIVE_DB = -3.0  # Web App lights the GR lamp at <= -3 dB
VOLTAGE_SANITY_MAX = 200.0
FAULT_KEYS = (
    "generic_hw_fault",
    "high_over_temperature",
    "moderate_over_temperature",
    "mains",
    "power_supply",
)
STALE_AFTER_S = 15.0


@dataclass
class LiveChannel:
    """Live readings of one output channel."""

    voltage: float | None = None
    current: float | None = None
    power: float | None = None
    impedance: float | None = None
    gain_reduction: float | None = None
    limiter: bool = False
    clip: bool = False
    signal_present: bool = False
    temperature: float | None = None


@dataclass
class LiveSnapshot:
    """Latest live state pushed by the amplifier."""

    channels: list[LiveChannel] = field(default_factory=list)
    standby: bool | None = None
    fault: bool | None = None
    fault_flags: dict[str, bool] = field(default_factory=dict)
    temperature: float | None = None
    updated_at: float = 0.0

    @property
    def fresh(self) -> bool:
        return self.updated_at > 0 and time.monotonic() - self.updated_at < STALE_AFTER_S


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def gain_reduction_to_db(linear: Any) -> float | None:
    """Web App ``X8.Util.Convert.gainReductionToDb``."""
    value = _num(linear)
    if value is None or value <= 0:
        return None
    if value >= 0.98:
        return 0.0
    return round(20.0 * math.log10(value), 1)


def parse_output_process(channel: dict[str, Any]) -> LiveChannel:
    """Parse one ``meters.output_process[]`` entry."""
    presence = channel.get("signal_presence")
    signal_present = presence is True or presence == 1
    clip_raw = channel.get("signal_clipping")
    gr_db = gain_reduction_to_db(channel.get("user_gain_reduction_total"))

    rms_v, peak_v = _num(channel.get("meter_v_post_rms")), _num(channel.get("meter_v_post_peak"))
    rms_i, peak_i = _num(channel.get("meter_i_post_rms")), _num(channel.get("meter_i_post_peak"))

    voltage = next(
        (v for v in (rms_v, peak_v) if v is not None and v < VOLTAGE_SANITY_MAX), None
    )
    current = rms_i if rms_i is not None else peak_i

    power: float | None
    if not signal_present:
        power = 0.0
    elif rms_v is not None and rms_i is not None:
        power = rms_v * rms_i
    elif peak_v is not None and peak_i is not None:
        power = peak_v * peak_i
    else:
        power = None

    return LiveChannel(
        voltage=round(voltage, 2) if voltage is not None else None,
        current=round(current, 2) if current is not None else None,
        power=round(power, 1) if power is not None else None,
        impedance=_num(channel.get("nominal_impedence")),  # sic, firmware spelling
        gain_reduction=gr_db,
        limiter=bool(signal_present and gr_db is not None and gr_db <= GR_ACTIVE_DB),
        clip=bool(signal_present and (clip_raw is True or clip_raw == 1)),
        signal_present=signal_present,
    )


def apply_status_update(snapshot: LiveSnapshot, payload: dict[str, Any]) -> None:
    """Merge a ``status-update`` payload into ``snapshot``."""
    readings = payload.get("readings") if isinstance(payload, dict) else None
    if not isinstance(readings, dict):
        return

    meters = readings.get("meters")
    if isinstance(meters, dict) and isinstance(meters.get("output_process"), list):
        old_temps = [c.temperature for c in snapshot.channels]
        snapshot.channels = [
            parse_output_process(ch if isinstance(ch, dict) else {})
            for ch in meters["output_process"]
        ]
        for idx, temp in enumerate(old_temps[: len(snapshot.channels)]):
            snapshot.channels[idx].temperature = temp
        snapshot.updated_at = time.monotonic()

    slows = readings.get("slows")
    if isinstance(slows, dict):
        ext = slows.get("ext_state")
        if isinstance(ext, dict):
            standby = ext.get("standby")
            if isinstance(standby, (bool, int, float)):
                snapshot.standby = bool(standby)
            snapshot.fault_flags = {
                key: bool(_num(ext.get(key)) or 0) for key in FAULT_KEYS if key in ext
            }
            snapshot.fault = any(snapshot.fault_flags.values())

        ampli = slows.get("ampli")
        if isinstance(ampli, list):
            temps: list[float] = []
            for idx, channel in enumerate(snapshot.channels):
                block = ampli[idx // 2] if idx // 2 < len(ampli) else None
                if not isinstance(block, dict):
                    continue
                temp = _num(block.get("temp_ch_a_peak" if idx % 2 == 0 else "temp_ch_b_peak"))
                channel.temperature = temp
                if temp is not None:
                    temps.append(temp)
            if not snapshot.channels:  # meters not received yet
                for block in ampli:
                    if isinstance(block, dict):
                        temps += [
                            t
                            for t in (_num(block.get("temp_ch_a_peak")), _num(block.get("temp_ch_b_peak")))
                            if t is not None
                        ]
            if temps:
                snapshot.temperature = max(temps)
        snapshot.updated_at = time.monotonic()


class PowersoftLiveClient:
    """Keeps a Socket.IO connection open and stores the latest live snapshot."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int = 80) -> None:
        self._session = session
        self._url = f"ws://{host}:{port}{SOCKETIO_PATH}"
        self.host = host
        self.snapshot = LiveSnapshot()

    async def run(self) -> None:
        """Run forever, reconnecting with back-off. Cancel the task to stop."""
        backoff = 1.0
        while True:
            try:
                await self._session_loop()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - reconnect on anything
                _LOGGER.debug("Powersoft live meters %s: %s", self.host, err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _session_loop(self) -> None:
        async with self._session.ws_connect(
            self._url,
            origin=f"http://{self.host}",
            timeout=aiohttp.ClientWSTimeout(ws_close=5),
            autoping=True,
        ) as ws:
            open_msg = await ws.receive(timeout=10)
            if open_msg.type != aiohttp.WSMsgType.TEXT or not open_msg.data.startswith("0"):
                raise ConnectionError("expected Engine.IO open packet")
            try:
                ping_interval = json.loads(open_msg.data[1:]).get("pingInterval", 25000) / 1000
            except (ValueError, AttributeError):
                ping_interval = 25.0

            await ws.send_str("40")
            pinger = asyncio.create_task(self._pinger(ws, ping_interval))
            try:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
                        continue
                    text = msg.data
                    if text == "2":  # server ping (EIO4 style)
                        await ws.send_str("3")
                    elif text.startswith("42"):
                        self._handle_event(text[2:])
            finally:
                pinger.cancel()

    @staticmethod
    async def _pinger(ws: aiohttp.ClientWebSocketResponse, interval: float) -> None:
        """Engine.IO v3: the client is the one sending pings."""
        while not ws.closed:
            await asyncio.sleep(max(interval, 5.0))
            await ws.send_str("2")

    def _handle_event(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if not isinstance(event, list) or len(event) < 2 or event[0] != "status-update":
            return
        body = event[1]
        if isinstance(body, dict):
            payload = body.get("payload", body)
            if isinstance(payload, dict):
                apply_status_update(self.snapshot, payload)

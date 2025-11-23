"""Media Player platform for Powersoft amplifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_POWERSOFT = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft media_player from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    # Una sola entidad media_player por amplificador
    async_add_entities([PowersoftMediaPlayer(coordinator)], True)


class PowersoftMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representación del amplificador Powersoft como media_player."""

    _attr_has_entity_name = True
    _attr_name = None  # Usa el nombre del dispositivo
    _attr_supported_features = SUPPORT_POWERSOFT
    _attr_media_image_url = None

    def __init__(self, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        self._api = coordinator.api  # Asumimos que guardaste la instancia de PowersoftAPI en el coordinator
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial}_amplifier"

        # Opciones configurables desde UI (se guardan en config_entry.options)
        self._volume_channel = self.coordinator.config_entry.options.get("volume_channel", 0)  # 0 = Master
        self._mute_channel = self.coordinator.config_entry.options.get("mute_channel", 0)        # 0 = Global

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if any(ch.get("signal_present") for ch in self.coordinator.data.get("channels", [])):
            return STATE_ON
        return STATE_OFF

    @property
    def volume_level(self) -> float | None:
        """Volume level (0.0 to 1.0)."""
        channels = self.coordinator.data.get("channels", [])
        if not channels:
            return None

        if self._volume_channel == 0:  # Master = promedio de todos
            gains_db = [ch["gain"] for ch in channels if ch["gain"] > -150]
            if not gains_db:
                return 0.0
            avg_db = sum(gains_db) / len(gains_db)
        else:
            ch = next((c for c in channels if c["number"] == self._volume_channel), None)
            avg_db = ch["gain"] if ch else -80.0

        # Convertir dB (-80..0) → 0.0..1.0 (logarítmico para que suene bien en HA)
        if avg_db <= -80:
            return 0.0
        return (avg_db + 80) / 80  # HA espera escala lineal en UI, pero suena bien así

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0..1.0) → -80..0 dB."""
        target_db = volume * 80 - 80

        channels = self.coordinator.data.get("channels", [])
        targets = channels if self._volume_channel == 0 else [
            next((c for c in channels if c["number"] == self._volume_channel), None)
        ]
        targets = [c for c in targets if c is not None]

        success = True
        for ch in targets:
            if not await self._api.set_gain(ch["number"], target_db):
                success = False

        if success:
            _LOGGER.info("Volume set to %.1f dB (%d%%)", target_db, int(volume * 100))
        await self.coordinator.async_request_refresh()

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        channels = self.coordinator.data.get("channels", [])
        if self._mute_channel == 0:  # Global mute
            return all(ch["mute"] for ch in channels)
        else:
            ch = next((c for c in channels if c["number"] == self._mute_channel), None)
            return ch["mute"] if ch else False

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        channels = self.coordinator.data.get("channels", [])
        targets = channels if self._mute_channel == 0 else [
            next((c for c in channels if c["number"] == self._mute_channel), None)
        ]
        targets = [c for c in targets if c is not None]

        success = True
        for ch in targets:
            if not await self._api.set_mute(ch["number"], mute):
                success = False

        if success:
            _LOGGER.info("%s mute", "Activated" if mute else "Deactivated")
        await self.coordinator.async_request_refresh()

    @property
    def source(self) -> str | None:
        """Current snapshot/preset name."""
        return self.coordinator.data["system"]["current_snapshot"]

    @property
    def source_list(self) -> list[str]:
        """List of available snapshots (hardcode 1-20, los vacíos aparecen como "Slot X")"""
        return [f"Slot {i}" for i in range(1, 21)]

    async def async_select_source(self, source: str) -> None:
        """Load snapshot by name (Slot 1 → 1, etc.)."""
        try:
            slot = int(source.split()[-1])
            if 1 <= slot <= 20:
                if await self._api.load_snapshot(slot):
                    _LOGGER.info("Snapshot loaded: %s", source)
                else:
                    _LOGGER.warning("Failed to load snapshot: %s", source)
            await self.coordinator.async_request_refresh()
        except ValueError:
            _LOGGER.warning("Invalid snapshot name: %s", source)

    @property
    def icon(self) -> str:
        """Dynamic icon."""
        if self.state == STATE_OFF:
            return "mdi:amplifier-off"
        if self.is_volume_muted:
            return "mdi:volume-off"
        level = self.volume_level or 0
        if level < 0.3:
            return "mdi:volume-low"
        if level < 0.7:
            return "mdi:volume-medium"
        return "mdi:volume-high"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes."""
        attrs = {
            "volume_channel": "Master" if self._volume_channel == 0 else f"Channel {self._volume_channel}",
            "mute_channel": "Global" if self._mute_channel == 0 else f"Channel {self._mute_channel}",
            "total_channels": len(self.coordinator.data.get("channels", [])),
        }
        # Añade gain de cada canal
        for ch in self.coordinator.data.get("channels", []):
            attrs[f"channel_{ch['number']}_gain_db"] = round(ch["gain"], 1)
            attrs[f"channel_{ch['number']}_mute"] = ch["mute"]
        return attrs

    async def async_turn_on(self) -> None:
        """Unmute all channels (simula encendido)."""
        await self.async_mute_volume(False)

    async def async_turn_off(self) -> None:
        """Mute all channels (simula apagado)."""
        await self.async_mute_volume(True)
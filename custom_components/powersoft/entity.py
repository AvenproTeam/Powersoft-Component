"""Base entity for the Powersoft integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PowersoftCoordinator


class PowersoftEntity(CoordinatorEntity[PowersoftCoordinator]):
    """Common device info and data helpers for every Powersoft entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PowersoftCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=coordinator.model,
            sw_version=coordinator.firmware,
            serial_number=coordinator.serial,
            configuration_url=coordinator.api.base_url,
        )

    @property
    def system(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("system", {})


class PowersoftChannelEntity(PowersoftEntity):
    """Entity bound to one output channel."""

    def __init__(self, coordinator: PowersoftCoordinator, channel: int, key: str) -> None:
        super().__init__(coordinator, f"ch{channel}_{key}")
        self._channel = channel
        self._attr_translation_placeholders = {"channel": str(channel)}

    @property
    def channel_data(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("channels", {}).get(self._channel, {})

    @property
    def live_data(self) -> dict[str, Any]:
        return self.channel_data.get("live") or {}


class PowersoftLiveMixin:
    """Entities fed by Socket.IO live meters: unavailable when the feed is stale."""

    coordinator: PowersoftCoordinator

    @property
    def available(self) -> bool:
        return super().available and bool(  # type: ignore[misc]
            (self.coordinator.data or {}).get("system", {}).get("live")
        )

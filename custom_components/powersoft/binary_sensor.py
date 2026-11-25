"""Binary sensor platform for Powersoft amplifiers (live meters)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowersoftConfigEntry, PowersoftCoordinator
from .entity import PowersoftChannelEntity, PowersoftEntity, PowersoftLiveMixin

FAULT_SENSOR = BinarySensorEntityDescription(
    key="fault",
    translation_key="fault",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)

CHANNEL_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(key="signal_present", translation_key="signal"),
    BinarySensorEntityDescription(
        key="clip",
        translation_key="clip",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(key="limiter", translation_key="limiter"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowersoftConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [PowersoftFaultSensor(coordinator)]
    entities.extend(
        PowersoftChannelBinarySensor(coordinator, channel, description)
        for channel in coordinator.data["channels"]
        for description in CHANNEL_BINARY_SENSORS
    )
    async_add_entities(entities)


class PowersoftFaultSensor(PowersoftLiveMixin, PowersoftEntity, BinarySensorEntity):
    """Any hardware / temperature / mains / PSU fault (``slows.ext_state``)."""

    entity_description = FAULT_SENSOR

    def __init__(self, coordinator: PowersoftCoordinator) -> None:
        super().__init__(coordinator, FAULT_SENSOR.key)

    @property
    def is_on(self) -> bool | None:
        return self.system.get("fault")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.system.get("fault_flags") or {}


class PowersoftChannelBinarySensor(
    PowersoftLiveMixin, PowersoftChannelEntity, BinarySensorEntity
):
    """Per-channel live indicator (signal, clip, limiter / GR)."""

    def __init__(
        self,
        coordinator: PowersoftCoordinator,
        channel: int,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, channel, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.live_data.get(self.entity_description.key)

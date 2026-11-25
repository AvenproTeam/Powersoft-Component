"""Number platform for Powersoft amplifiers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PowersoftConfigEntry, PowersoftCoordinator
from .entity import PowersoftChannelEntity
from .powersoft_api import PowersoftAPI, PowersoftError


@dataclass(frozen=True, kw_only=True)
class PowersoftNumberDescription(NumberEntityDescription):
    """Describe a per-channel number."""

    setter: Callable[[PowersoftAPI, int, float], Awaitable[bool]]


CHANNEL_NUMBERS: tuple[PowersoftNumberDescription, ...] = (
    PowersoftNumberDescription(
        key="gain",
        translation_key="gain",
        native_min_value=PowersoftAPI.GAIN_MIN_DB,
        native_max_value=PowersoftAPI.GAIN_MAX_DB,
        native_step=0.5,
        native_unit_of_measurement="dB",
        mode=NumberMode.SLIDER,
        setter=lambda api, ch, v: api.set_gain(ch, v),
    ),
    PowersoftNumberDescription(
        key="delay",
        translation_key="delay",
        native_min_value=0.0,
        native_max_value=500.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        setter=lambda api, ch, v: api.set_delay(ch, v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowersoftConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        PowersoftChannelNumber(coordinator, channel, description)
        for channel in coordinator.data["channels"]
        for description in CHANNEL_NUMBERS
    )


class PowersoftChannelNumber(PowersoftChannelEntity, NumberEntity):
    """Per-channel numeric parameter (gain, delay)."""

    entity_description: PowersoftNumberDescription

    def __init__(
        self,
        coordinator: PowersoftCoordinator,
        channel: int,
        description: PowersoftNumberDescription,
    ) -> None:
        super().__init__(coordinator, channel, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        return self.channel_data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        try:
            ok = await self.entity_description.setter(
                self.coordinator.api, self._channel, value
            )
        except PowersoftError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        if not ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        self.channel_data[self.entity_description.key] = value
        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()

"""Switch platform for Powersoft amplifiers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PowersoftConfigEntry, PowersoftCoordinator
from .entity import PowersoftChannelEntity, PowersoftEntity
from .powersoft_api import PowersoftAPI, PowersoftError


@dataclass(frozen=True, kw_only=True)
class PowersoftChannelSwitchDescription(SwitchEntityDescription):
    """Describe a per-channel switch."""

    value_key: str
    setter: Callable[[PowersoftAPI, int, bool], Awaitable[bool]]


CHANNEL_SWITCHES: tuple[PowersoftChannelSwitchDescription, ...] = (
    PowersoftChannelSwitchDescription(
        key="mute",
        translation_key="mute",
        value_key="mute",
        setter=lambda api, ch, on: api.set_mute(ch, on),
    ),
    PowersoftChannelSwitchDescription(
        key="input_mute",
        translation_key="input_mute",
        value_key="input_mute",
        entity_registry_enabled_default=False,
        setter=lambda api, ch, on: api.set_input_mute(ch, on),
    ),
    PowersoftChannelSwitchDescription(
        key="polarity",
        translation_key="polarity",
        value_key="polarity_inverted",
        entity_category=EntityCategory.CONFIG,
        setter=lambda api, ch, on: api.set_polarity(ch, on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowersoftConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powersoft switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [PowersoftPowerSwitch(coordinator)]
    entities.extend(
        PowersoftChannelSwitch(coordinator, channel, description)
        for channel in coordinator.data["channels"]
        for description in CHANNEL_SWITCHES
    )
    async_add_entities(entities)


async def _run(
    coordinator: PowersoftCoordinator,
    command: Awaitable[bool],
    apply: Callable[[], None],
) -> None:
    """Send a command, reflect it immediately, then confirm with a refresh."""
    try:
        ok = await command
    except PowersoftError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_failed"
        ) from err
    if not ok:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_failed"
        )
    apply()
    coordinator.async_update_listeners()
    await coordinator.async_request_refresh()


class PowersoftPowerSwitch(PowersoftEntity, SwitchEntity):
    """Amplifier power (on / standby)."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: PowersoftCoordinator) -> None:
        super().__init__(coordinator, "power")

    @property
    def is_on(self) -> bool | None:
        standby = self.system.get("standby")
        return None if standby is None else not standby

    async def _set(self, on: bool) -> None:
        def apply() -> None:
            self.system["standby"] = not on
            self.system["power_state"] = "on" if on else "standby"

        await _run(self.coordinator, self.coordinator.api.set_standby(not on), apply)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class PowersoftChannelSwitch(PowersoftChannelEntity, SwitchEntity):
    """Per-channel boolean parameter (mute, polarity)."""

    entity_description: PowersoftChannelSwitchDescription

    def __init__(
        self,
        coordinator: PowersoftCoordinator,
        channel: int,
        description: PowersoftChannelSwitchDescription,
    ) -> None:
        super().__init__(coordinator, channel, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.channel_data.get(self.entity_description.value_key) is not None
        )

    @property
    def is_on(self) -> bool | None:
        return self.channel_data.get(self.entity_description.value_key)

    async def _set(self, on: bool) -> None:
        def apply() -> None:
            self.channel_data[self.entity_description.value_key] = on

        await _run(
            self.coordinator,
            self.entity_description.setter(self.coordinator.api, self._channel, on),
            apply,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

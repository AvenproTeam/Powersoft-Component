"""Config flow for Powersoft."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_NUM_CHANNELS, DEFAULT_NUM_CHANNELS, DEFAULT_PORT, DOMAIN
from .powersoft_api import PowersoftAPI, PowersoftAuthError, PowersoftError

_LOGGER = logging.getLogger(__name__)


def _unique_id(data: dict[str, Any], info: dict[str, Any]) -> str:
    """Serial number when available (survives IP changes), else host:port."""
    if info.get("serial"):
        return f"ps-{info['serial']}"
    return f"{data[CONF_HOST]}:{data.get(CONF_PORT, DEFAULT_PORT)}"


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_PASSWORD): str,
        }
    )


class PowersoftConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powersoft."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        api = PowersoftAPI(
            data[CONF_HOST],
            data.get(CONF_PORT, DEFAULT_PORT),
            data.get(CONF_USERNAME),
            data.get(CONF_PASSWORD),
            num_channels=data.get(CONF_NUM_CHANNELS, DEFAULT_NUM_CHANNELS),
            session=async_get_clientsession(self.hass),
        )
        try:
            info = await api.test_connection()
        except PowersoftAuthError:
            return "invalid_auth", {}
        except PowersoftError:
            return "cannot_connect", {}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating Powersoft amplifier")
            return "unknown", {}
        return None, info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            error, info = await self._validate(user_input)
            if error is None:
                await self.async_set_unique_id(_unique_id(user_input, info))
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                if info.get("channels"):
                    user_input[CONF_NUM_CHANNELS] = info["channels"]
                name = info.get("model") or "Powersoft"
                return self.async_create_entry(
                    title=f"{name} ({user_input[CONF_HOST]})", data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, port or credentials of an existing amplifier."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            error, info = await self._validate(user_input)
            if error is None:
                if (entry.unique_id or "").startswith("ps-") and info.get("serial"):
                    await self.async_set_unique_id(_unique_id(user_input, info))
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                if info.get("channels"):
                    user_input[CONF_NUM_CHANNELS] = info["channels"]
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or dict(entry.data)),
            errors=errors,
        )

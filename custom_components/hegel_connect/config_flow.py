"""Config flow: enter the IP address of the amplifier."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import HegelClient, HegelConnectionError, HegelError
from .const import CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HegelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Hegel H150/H400/H600."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = HegelClient(host, async_get_clientsession(self.hass))
            try:
                model = await client.product_name()
                name = await client.device_name() or model
                unique_id = await client.unique_id() or host
            except HegelConnectionError:
                errors["base"] = "cannot_connect"
            except HegelError:
                errors["base"] = "not_supported"
            except Exception:  # noqa: BLE001 - show a friendly error, log the rest
                _LOGGER.exception("Unexpected error talking to %s", host)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=f"Hegel {name}" if not name.lower().startswith("hegel") else name,
                    data={CONF_HOST: host, "model": model},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the IP address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                await HegelClient(host, async_get_clientsession(self.hass)).product_name()
            except HegelError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HegelOptionsFlow()


class HegelOptionsFlow(OptionsFlow):
    """Volume ceiling."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAX_VOLUME, default=current): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)
                    )
                }
            ),
        )

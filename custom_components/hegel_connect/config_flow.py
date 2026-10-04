"""Config flow: discovered on the network (SSDP / Google Cast) or entered by IP address."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .api import HegelClient, HegelConnectionError, HegelError
from .const import DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


class HegelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Hegel H150/H400/H600."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._model: str | None = None
        self._title: str | None = None

    async def _async_probe(self, host: str) -> tuple[str, str, str]:
        """Ask the amplifier who it is: (model, title, unique id)."""
        client = HegelClient(host, async_get_clientsession(self.hass))
        model = await client.product_name()
        name = await client.device_name() or model
        unique_id = await client.unique_id() or host
        title = name if name.lower().startswith("hegel") else f"Hegel {name}"
        return model, title, unique_id

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                model, title, unique_id = await self._async_probe(host)
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
                return self.async_create_entry(title=title, data={CONF_HOST: host, "model": model})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    # -------------------------------------------------------------- discovery
    # Same mechanism as the Hegel Control app: mDNS service _sues800device._tcp
    # (StreamUnlimited platform). Backups: UPnP/DLNA renderer (SSDP) and Google
    # Cast. Other brands on the same platform (Onkyo) also announce
    # _sues800device, so the model reported by the API decides.
    # A known amplifier on a new address gets its address updated silently.

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        host = urlparse(discovery_info.ssdp_location or "").hostname
        return await self._async_step_discovered(host)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        host = str(discovery_info.ip_address)
        if discovery_info.type.startswith("_sues800device."):
            # TXT records: manufacturer, uuid (= system member id), ip. Other brands
            # on the same platform (Onkyo) are skipped without connecting.
            props = discovery_info.properties
            if str(props.get("manufacturer") or "").lower() != "hegel":
                return self.async_abort(reason="not_supported")
            host = str(props.get("ip") or host)
            if uuid := props.get("uuid"):
                await self.async_set_unique_id(str(uuid))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        if ":" in host:
            return self.async_abort(reason="not_ipv4")
        return await self._async_step_discovered(host)

    async def _async_step_discovered(self, host: str | None) -> ConfigFlowResult:
        if not host:
            return self.async_abort(reason="cannot_connect")
        self._async_abort_entries_match({CONF_HOST: host})
        try:
            model, title, unique_id = await self._async_probe(host)
        except HegelConnectionError:
            return self.async_abort(reason="cannot_connect")
        except HegelError:
            return self.async_abort(reason="not_supported")
        if model.upper() not in SUPPORTED_MODELS:
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._host, self._model, self._title = host, model, title
        self.context["title_placeholders"] = {"name": title}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the user to confirm adding a discovered amplifier."""
        assert self._host is not None and self._title is not None
        if user_input is not None:
            return self.async_create_entry(title=self._title, data={CONF_HOST: self._host, "model": self._model})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._title, "host": self._host},
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

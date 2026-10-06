"""Config flow: discovered on the network (SSDP / Google Cast) or entered by IP address."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .api import HegelClient, HegelConnectionError, HegelError, async_has_ip_control
from .const import CONF_HIDDEN_SOURCES, CONF_SOURCE_NAMES, CORE_HEGEL_URL, DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


class HegelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Hegel H150/H200/H400/H600."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HegelOptionsFlow:
        """Rename and hide inputs."""
        return HegelOptionsFlow()

    def __init__(self) -> None:
        self._host: str | None = None
        self._model: str | None = None
        self._title: str | None = None

    async def _async_probe(self, host: str) -> tuple[str, str, str]:
        """Ask the amplifier who it is: (model, title, unique id).

        Raises HegelError when it is not a supported Hegel or has no stable id
        (never fall back to the IP address: that changes and would end up in the
        entity ids).
        """
        client = HegelClient(host, async_get_clientsession(self.hass))
        model = await client.product_name()
        if model.upper() not in SUPPORTED_MODELS:
            raise HegelError(f"Unsupported model {model}")
        unique_id = await client.unique_id()
        if not unique_id:
            raise HegelError("No stable id reported")
        name = await client.device_name() or model
        title = name if name.lower().startswith("hegel") else f"Hegel {name}"
        return model, title, unique_id

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                model, title, unique_id = await self._async_probe(host)
            except HegelConnectionError:
                errors["base"] = "legacy_model" if await async_has_ip_control(host) else "cannot_connect"
            except HegelError:
                errors["base"] = "legacy_model" if await async_has_ip_control(host) else "not_supported"
            except Exception:  # show a friendly error, log the rest
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
            description_placeholders={"core_url": CORE_HEGEL_URL},
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
                # Only to skip duplicate flows. A new address is NOT taken from the
                # announcement itself: _async_step_discovered first asks the device
                # at that address for its id, so another device cannot take over.
                await self.async_set_unique_id(str(uuid))
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
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._host, self._model, self._title = host, model, title
        self.context["title_placeholders"] = {"name": title}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the user to confirm adding a discovered amplifier."""
        if self._host is None or self._title is None:
            return self.async_abort(reason="cannot_connect")
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
                _model, _title, unique_id = await self._async_probe(host)
            except HegelConnectionError:
                errors["base"] = "cannot_connect"
            except HegelError:
                errors["base"] = "not_supported"
            except Exception:  # show a friendly error, log the rest
                _LOGGER.exception("Unexpected error talking to %s", host)
                errors["base"] = "unknown"
            else:
                # Same amplifier only: a different one is a new device, not a new address.
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )


class HegelOptionsFlow(OptionsFlow):
    """Hide inputs you do not use and give inputs your own name.

    Only how Home Assistant shows them changes (source list, dashboards); the
    amplifier itself is not changed. Hidden inputs can still be selected by
    automations. Renamed inputs also keep answering to their original name.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        sources = coordinator.sources if coordinator is not None else []
        if not sources:
            return self.async_abort(reason="no_inputs")
        options = self.config_entry.options
        names: dict[str, str] = dict(options.get(CONF_SOURCE_NAMES) or {})
        errors: dict[str, str] = {}
        if user_input is not None:
            hidden = [str(i) for i in user_input.get(CONF_HIDDEN_SOURCES, [])]
            new_names: dict[str, str] = {}
            for source in sources:
                label = str(user_input.get(source.name) or "").strip()
                if label and label != source.name:
                    new_names[str(source.index)] = label
            shown = [new_names.get(str(s.index), s.name) for s in sources]
            if len(set(shown)) != len(shown):
                errors["base"] = "duplicate_name"
            else:
                return self.async_create_entry(data={CONF_HIDDEN_SOURCES: hidden, CONF_SOURCE_NAMES: new_names})
        # One text field per input, labelled with the amplifier's own name
        # (empty = keep that name), plus the list of inputs to hide.
        schema: dict[Any, Any] = {
            vol.Optional(CONF_HIDDEN_SOURCES, default=list(options.get(CONF_HIDDEN_SOURCES) or [])): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value=str(s.index), label=s.name) for s in sources],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
        for source in sources:
            schema[vol.Optional(source.name, description={"suggested_value": names.get(str(source.index), "")})] = str
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema), errors=errors)

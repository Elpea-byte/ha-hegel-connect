"""Config flow tests."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hegel_connect.const import DOMAIN

from .conftest import FakeHegel


async def test_user_flow_creates_entry(hass: HomeAssistant, fake_hegel) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.10"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hegel H150"
    assert result["data"] == {"host": "192.0.2.10", "model": "H150"}
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000000"


async def test_user_flow_cannot_connect(hass: HomeAssistant, fake_hegel) -> None:
    FakeHegel.reachable = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.10"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.11"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

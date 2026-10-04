"""Config flow tests."""

from __future__ import annotations

from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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


# ------------------------------------------------------------------ discovery

SSDP_INFO = SsdpServiceInfo(
    ssdp_usn="uuid:00000000-0000-0000-0000-000000000001::upnp:rootdevice",
    ssdp_st="upnp:rootdevice",
    ssdp_location="http://192.0.2.10:16500/00000000-0000-0000-0000-000000000001.xml",
    upnp={
        "deviceType": "urn:schemas-upnp-org:device:MediaRenderer:2",
        "friendlyName": "H150",
        "manufacturer": "Hegel",
        "modelName": "H150",
    },
)

SUE_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.0.2.10"),
    ip_addresses=[ip_address("192.0.2.10")],
    hostname="h150.local.",
    name="H150._sues800device._tcp.local.",
    port=80,
    type="_sues800device._tcp.local.",
    properties={"name": "H150", "uuid": "hegelh600-00000000-0000-0000-0000-000000000000"},
)

ZEROCONF_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.0.2.10"),
    ip_addresses=[ip_address("192.0.2.10")],
    hostname="h150.local.",
    name="H150-0000._googlecast._tcp.local.",
    port=8009,
    type="_googlecast._tcp.local.",
    properties={"md": "H150", "fn": "H150"},
)


async def test_ssdp_discovery_confirm(hass: HomeAssistant, fake_hegel) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": "Hegel H150", "host": "192.0.2.10"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "192.0.2.10", "model": "H150"}
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000000"


async def test_zeroconf_discovery_confirm(hass: HomeAssistant, fake_hegel) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=ZEROCONF_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_discovery_updates_changed_address(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A known amplifier on a new address: update the entry, no new flow."""
    config_entry.add_to_hass(hass)
    info = SsdpServiceInfo(
        ssdp_usn=SSDP_INFO.ssdp_usn,
        ssdp_st=SSDP_INFO.ssdp_st,
        ssdp_location="http://192.0.2.20:16500/x.xml",
        upnp=SSDP_INFO.upnp,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "192.0.2.20"


async def test_discovery_same_address_skips_probe(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["reason"] == "already_configured"
    assert fake_hegel == []


async def test_discovery_unreachable(hass: HomeAssistant, fake_hegel) -> None:
    FakeHegel.reachable = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_sues800device_discovery(hass: HomeAssistant, fake_hegel) -> None:
    """The service the Hegel Control app looks for."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=SUE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_discovery_ignores_other_brands(hass: HomeAssistant, fake_hegel) -> None:
    """An Onkyo on the same StreamUnlimited platform is not offered."""
    FakeHegel.model = "TX-RZ810"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=SUE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"

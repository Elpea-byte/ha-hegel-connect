"""Config flow tests."""

from __future__ import annotations

import contextlib
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import pytest

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


async def test_user_flow_accepts_bracketed_ipv6(hass: HomeAssistant, fake_hegel) -> None:
    """An IPv6 address typed as [addr] is stored without brackets (the client adds them in URLs)."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "[2001:db8::10]"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "2001:db8::10"


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
    properties={
        "name": "H150",
        "manufacturer": "Hegel",
        "uuid": "00000000-0000-0000-0000-000000000000",
        "ip": "192.0.2.10",
    },
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
    """An Onkyo on the same StreamUnlimited platform is skipped without connecting."""
    onkyo = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.30"),
        ip_addresses=[ip_address("192.0.2.30")],
        hostname="onkyo.local.",
        name="TX-RZ810._sues800device._tcp.local.",
        port=80,
        type="_sues800device._tcp.local.",
        properties={"manufacturer": "Onkyo", "uuid": "onkyo-1"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=onkyo
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
    assert fake_hegel == []


async def test_discovery_rejects_unsupported_model(hass: HomeAssistant, fake_hegel) -> None:
    """Only H150/H200/H400/H600 are offered, whatever announces itself."""
    FakeHegel.model = "TX-RZ810"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=ZEROCONF_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_discovery_known_uuid_updates_host_after_probe(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A new address from mDNS is only used after the device there confirms its id."""
    config_entry.add_to_hass(hass)
    moved = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        hostname="h150.local.",
        name="H150._sues800device._tcp.local.",
        port=80,
        type="_sues800device._tcp.local.",
        properties={**SUE_INFO.properties, "ip": "192.0.2.20"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=moved
    )
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "192.0.2.20"
    assert fake_hegel != []  # the new address was asked first


async def test_discovery_cannot_take_over_address(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Another device announcing our uuid with its own address changes nothing."""
    config_entry.add_to_hass(hass)
    FakeHegel.uid = "11111111-1111-1111-1111-111111111111"  # what the device at .20 really is
    spoof = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        hostname="other.local.",
        name="Other._sues800device._tcp.local.",
        port=80,
        type="_sues800device._tcp.local.",
        properties={**SUE_INFO.properties, "ip": "192.0.2.20"},
    )
    await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=spoof)
    assert config_entry.data["host"] == "192.0.2.10"


async def test_user_flow_rejects_other_models(hass: HomeAssistant, fake_hegel) -> None:
    FakeHegel.model = "TX-RZ810"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.10"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_supported"}


async def test_reconfigure_same_amplifier(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.20"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["host"] == "192.0.2.20"


async def test_reconfigure_other_amplifier_refused(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    FakeHegel.uid = "11111111-1111-1111-1111-111111111111"
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.20"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data["host"] == "192.0.2.10"


async def test_user_flow_recognises_older_hegel(hass: HomeAssistant, fake_hegel) -> None:
    """No web API, but IP control answers: point to the built-in integration."""
    FakeHegel.reachable = False
    with patch("custom_components.hegel_connect.config_flow.async_has_ip_control", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.40"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "legacy_model"}


# ------------------------------------------------------- remaining branches


async def test_user_flow_no_stable_id(hass: HomeAssistant, fake_hegel) -> None:
    """Without an id the amplifier cannot be told apart from others: refuse."""
    FakeHegel.uid = ""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.10"})
    assert result["errors"] == {"base": "not_supported"}


async def test_user_flow_unexpected_error(hass: HomeAssistant, fake_hegel) -> None:
    with patch.object(FakeHegel, "product_name", AsyncMock(side_effect=RuntimeError("boom"))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.10"})
    assert result["errors"] == {"base": "unknown"}


async def test_sues800device_discovery_without_uuid(hass: HomeAssistant, fake_hegel) -> None:
    """No uuid in the TXT record: the id is read from the amplifier itself."""
    info = ZeroconfServiceInfo(
        ip_address=SUE_INFO.ip_address,
        ip_addresses=SUE_INFO.ip_addresses,
        hostname=SUE_INFO.hostname,
        name=SUE_INFO.name,
        port=SUE_INFO.port,
        type=SUE_INFO.type,
        properties={"manufacturer": "Hegel"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["step_id"] == "discovery_confirm"


async def test_discovery_ipv6_only_is_skipped(hass: HomeAssistant, fake_hegel) -> None:
    info = ZeroconfServiceInfo(
        ip_address=ip_address("2001:db8::10"),
        ip_addresses=[ip_address("2001:db8::10")],
        hostname="h150.local.",
        name=ZEROCONF_INFO.name,
        port=8009,
        type="_googlecast._tcp.local.",
        properties={"md": "H150"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ipv4"
    assert fake_hegel == []


async def test_ssdp_without_location(hass: HomeAssistant, fake_hegel) -> None:
    info = SsdpServiceInfo(ssdp_usn=SSDP_INFO.ssdp_usn, ssdp_st=SSDP_INFO.ssdp_st, upnp=SSDP_INFO.upnp)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("setup", "error"),
    [("unreachable", "cannot_connect"), ("other_model", "not_supported"), ("crash", "unknown")],
)
async def test_reconfigure_errors(hass: HomeAssistant, fake_hegel, config_entry, setup: str, error: str) -> None:
    """The form stays open with an error; the stored address is kept."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    if setup == "unreachable":
        FakeHegel.reachable = False
    elif setup == "other_model":
        FakeHegel.model = "TX-RZ810"
    crash = patch.object(FakeHegel, "product_name", AsyncMock(side_effect=RuntimeError("boom")))
    with crash if setup == "crash" else contextlib.nullcontext():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.0.2.20"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert config_entry.data["host"] == "192.0.2.10"


async def test_options_need_known_inputs(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Before the amplifier was ever reached its inputs are unknown: nothing to configure yet."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_inputs"

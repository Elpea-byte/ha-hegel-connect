"""Diagnostics must not leak the address."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from custom_components.hegel_connect.diagnostics import async_get_config_entry_diagnostics

from .conftest import FakeHegel


async def test_diagnostics_redacts_host(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    text = json.dumps(diag)
    assert "192.0.2.10" not in text
    assert diag["sources"][0]["name"] == "XLR"


async def test_diagnostics_shows_what_the_amplifier_offers(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device = (await async_get_config_entry_diagnostics(hass, config_entry))["device"]
    assert device["model"] == "H150"
    assert device["volume_range_max"] == 100
    assert device["auto_standby_choices_seconds"] == [0, 300, 600, 1200]
    assert isinstance(device["media_player_supported_features"], int)
    assert "firmware" in device


async def test_diagnostics_survives_an_amplifier_without_idle_setting(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    FakeHegel.idle_supported = False
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device = (await async_get_config_entry_diagnostics(hass, config_entry))["device"]
    assert str(device["auto_standby_choices_seconds"]).startswith("not available")

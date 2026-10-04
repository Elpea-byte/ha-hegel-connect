"""Diagnostics must not leak the address."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from custom_components.hegel_connect.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_host(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    text = json.dumps(diag)
    assert "192.0.2.10" not in text
    assert diag["sources"][0]["name"] == "XLR"

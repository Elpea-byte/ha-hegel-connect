"""Own names for inputs (options) never break scripts and blueprints that use the amplifier's own names."""

from __future__ import annotations

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import pytest

from custom_components.hegel_connect.const import CONF_SOURCE_NAMES

ENTITY = "media_player.hegel_h150"
NETWORK = 9


@pytest.mark.parametrize("name", ["Network", "Streamer"])
async def test_the_network_input_can_be_chosen_by_either_name(
    hass: HomeAssistant, fake_hegel, config_entry, name: str
) -> None:
    """The radio blueprint selects "Network"; that keeps working after renaming the input."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_SOURCE_NAMES: {str(NETWORK): "Streamer"}})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert "Streamer" in hass.states.get(ENTITY).attributes["source_list"]
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: "RCA"}, blocking=True
    )
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: name}, blocking=True
    )
    assert ("set_source", NETWORK) in fake_hegel[-1].calls
    await hass.async_block_till_done()
    # The player states (idle, paused) only exist on the network input, whatever it is called:
    # the standby blueprint relies on that.
    assert hass.states.get(ENTITY).state in ("idle", "paused", "playing", "buffering")
    assert hass.states.get(ENTITY).attributes["source"] == "Streamer"

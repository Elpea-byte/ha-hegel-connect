"""Media player tests with the fake H150."""

from __future__ import annotations

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import HomeAssistant

ENTITY = "media_player.hegel_h150"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_state_from_device(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.state == "playing"
    assert state.attributes["source"] == "Network"
    assert state.attributes["volume_level"] == 0.17
    assert state.attributes["media_title"] == "Marido Dansa"
    assert "RCA" in state.attributes["source_list"]


async def test_push_updates_state(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake_hegel[-1].push("player:volume", {"type": "i32_", "i32_": 30})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["volume_level"] == 0.3


async def test_volume_respects_ceiling(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"max_volume": 40})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_SET, {ATTR_ENTITY_ID: ENTITY, ATTR_MEDIA_VOLUME_LEVEL: 0.9}, blocking=True
    )
    assert ("set_volume", 40) in fake_hegel[-1].calls


async def test_select_source_pauses_stream_first(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: "RCA"}, blocking=True
    )
    calls = fake_hegel[-1].calls
    assert ("control", "pause") in calls
    assert ("set_source", 2) in calls
    assert calls.index(("control", "pause")) < calls.index(("set_source", 2))


async def test_spotify_has_no_skip_and_resumes(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Spotify Connect: no next/previous; play resumes instead of a bare play."""
    await _setup(hass, config_entry)
    features = hass.states.get(ENTITY).attributes["supported_features"]
    assert not features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not features & MediaPlayerEntityFeature.PREVIOUS_TRACK
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("control", "pause") in fake_hegel[-1].calls
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("resume_spotify",) in fake_hegel[-1].calls
    assert ("control", "play") not in fake_hegel[-1].calls

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

from .conftest import FakeHegel

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
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: "number.hegel_h150_maximum_volume", "value": 40}, blocking=True
    )
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


async def test_stream_sensors_and_network(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.hegel_h150_audio_quality").state == "lossy"
    assert hass.states.get("sensor.hegel_h150_streaming_service").state == "Spotify"
    assert hass.states.get("binary_sensor.hegel_h150_network").state == "on"


async def test_lost_connection_shows_off(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Off at the mains: media player off (not unavailable), network sensor off."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.connected = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "off"
    assert hass.states.get("binary_sensor.hegel_h150_network").state == "off"
    assert hass.states.get("sensor.hegel_h150_audio_quality").state == "unknown"


async def test_play_after_pause_resumes_spotify_even_without_service(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """Paused player data can lose the service name; the last one seen still counts."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", {"state": "paused", "controls": {"pause": True}})
    await hass.async_block_till_done()
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("resume_spotify",) in fake.calls
    assert ("control", "play") not in fake.calls


async def test_starts_while_off_at_the_mains(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Power strip off when Home Assistant starts: set up from saved data, shown as off."""
    await _setup(hass, config_entry)
    assert config_entry.data["cache"]["sources"]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    FakeHegel.reachable = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.state == "off"
    assert hass.states.get("binary_sensor.hegel_h150_network").state == "off"


async def test_stop_for_radio_not_for_spotify(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    assert not hass.states.get(ENTITY).attributes["supported_features"] & MediaPlayerEntityFeature.STOP
    radio = {
        "state": "playing",
        "controls": {"next_": False, "previous": False},
        "trackRoles": {"title": "Qmusic", "mediaData": {"metaData": {"serviceName": "airable Radio"}}},
    }
    fake = fake_hegel[-1]
    fake.push("player:player/data", radio)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["supported_features"] & MediaPlayerEntityFeature.STOP
    await hass.services.async_call(MP_DOMAIN, "media_stop", {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("control", "stop") in fake.calls

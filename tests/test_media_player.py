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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.hegel_connect.api import HegelError

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
    assert state.attributes["media_playlist"] == "New Dance 2026"
    assert "RCA" in state.attributes["source_list"]


async def test_push_updates_state(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake_hegel[-1].push("player:volume", {"type": "i32_", "i32_": 30})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["volume_level"] == 0.3


async def test_listener_survives_unexpected_event(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A malformed event is skipped; later events still arrive (push keeps running)."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("powermanager:target", "not-a-dict")
    fake.push("player:volume", {"type": "i32_", "i32_": 25})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["volume_level"] == 0.25


async def test_play_error_with_known_service_is_reported(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """No Spotify resume attempt when another service refuses play."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push(
        "player:player/data",
        {"state": "paused", "trackRoles": {"mediaData": {"metaData": {"serviceName": "TIDAL"}}}},
    )
    await hass.async_block_till_done()

    async def refuse(command: str) -> None:
        raise HegelError("refused")

    fake.control = refuse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("resume_spotify",) not in fake.calls


async def test_max_volume_attribute_follows_number(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: "number.hegel_h150_maximum_volume", "value": 35}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["max_volume"] == 35


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


async def test_radio_favorites_sensor_and_play(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    state = hass.states.get("sensor.hegel_h150_radio_favorites")
    assert state.state == "1"
    favorite = state.attributes["favorites"][0]
    assert favorite["title"] == "Qmusic"
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": favorite["path"]},
        blocking=True,
    )
    assert ("play_path", "airable:fav/qmusic") in fake_hegel[-1].calls


SERVER = "upnp:/uuid:nas?itemType=server"
ALBUM = "upnp:/uuid:nas/42?itemType=container"


def _library() -> None:
    folder = {"type": "container", "containerPlayable": True}
    FakeHegel.rows = {
        "ui:/upnp": {"rows": [{**folder, "path": SERVER, "title": "NAS"}], "roles": {"path": "upnp:"}},
        SERVER: {
            "rows": [
                {**folder, "path": "upnp:/uuid:nas/1?itemType=container", "title": "Music"},
                {**folder, "path": "upnp:/uuid:nas/2?itemType=container", "title": "Photo"},
                {**folder, "path": "upnp:/uuid:nas/3?itemType=container", "title": "Video"},
            ]
        },
        ALBUM: {
            "rows": [
                {"type": "audio", "path": "upnp:/uuid:nas/t1?itemType=track", "title": "One"},
                {"type": "audio", "path": "upnp:/uuid:nas/t2?itemType=track", "title": "Two"},
            ]
        },
        # USB: only the (empty) folder and a disabled refresh action
        "musiclibrary:/usbFolder": {"rows": [{"type": "action", "path": "musiclibrary:/refresh", "title": "Refresh"}]},
    }
    FakeHegel.raw = {ALBUM: {**folder, "path": ALBUM, "title": "Best of"}}


async def _browse(hass: HomeAssistant, ws, content_id: str | None) -> dict:
    msg = {"id": 1 + len(content_id or ""), "type": "media_player/browse_media", "entity_id": ENTITY}
    if content_id is not None:
        msg |= {"media_content_id": content_id, "media_content_type": "hegel_path"}
    await ws.send_json(msg)
    reply = await ws.receive_json()
    assert reply["success"], reply
    return reply["result"]


async def test_browse_media_servers(hass: HomeAssistant, fake_hegel, config_entry, hass_ws_client) -> None:
    _library()
    await _setup(hass, config_entry)
    ws = await hass_ws_client(hass)

    root = await _browse(hass, ws, None)
    titles = [c["title"] for c in root["children"]]
    assert "Media servers" in titles
    assert "USB" not in titles  # no stick in the amplifier

    server = await _browse(hass, ws, SERVER)
    assert server["title"] == "NAS"
    assert [c["title"] for c in server["children"]] == ["Music"]  # no photo/video folders
    assert server["children"][0]["can_expand"] and not server["children"][0]["can_play"]

    album = await _browse(hass, ws, ALBUM)
    assert album["title"] == "Best of"
    assert album["can_play"]
    second = album["children"][1]
    assert second["media_content_id"] == f"track:1:{ALBUM}"

    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": second["media_content_id"]},
        blocking=True,
    )
    assert ("play_in_container", ALBUM, 1) in fake_hegel[-1].calls


async def test_options_hide_and_rename_inputs(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Hidden inputs leave the source list; own names are shown and can be selected."""
    await _setup(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"hidden_sources": ["5", "6"], "RCA": "TV", "Network": ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    sources = hass.states.get(ENTITY).attributes["source_list"]
    assert "Optical 1" not in sources and "Optical 2" not in sources
    assert "TV" in sources and "RCA" not in sources
    assert "Network" in sources
    names = hass.states.get(ENTITY).attributes["input_names"]
    assert names["TV"] == "RCA" and "Optical 1" not in names.values()

    # The own name and the amplifier's name both select RCA (index 2)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: "TV"}, blocking=True
    )
    assert ("set_source", 2) in fake_hegel[-1].calls
    # The current input is shown with its own name
    assert hass.states.get(ENTITY).attributes["source"] == "TV"


async def test_options_refuse_duplicate_names(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"RCA": "XLR"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "duplicate_name"}


async def test_options_keep_typed_input_on_error(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """After a duplicate name the form shows what was typed, not the stored values."""
    await _setup(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"hidden_sources": ["5"], "RCA": "XLR", "Phono": "Turntable"}
    )
    assert result["errors"] == {"base": "duplicate_name"}
    suggested = {str(key): key.description["suggested_value"] for key in result["data_schema"].schema}
    assert suggested["RCA"] == "XLR"
    assert suggested["Phono"] == "Turntable"
    assert suggested["hidden_sources"] == ["5"]


async def test_options_ignore_stale_hidden_inputs(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A stored input the amplifier no longer has is left out of the form."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"hidden_sources": ["5", "99"]})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    suggested = {str(key): key.description["suggested_value"] for key in result["data_schema"].schema}
    assert suggested["hidden_sources"] == ["5"]


async def test_unknown_source_is_a_user_error(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: "Cassette"}, blocking=True
        )


async def test_stream_detail_sensors_on_without_statistics(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Stream details are on by default (hi-fi users want them) but keep no long-term statistics."""
    await _setup(hass, config_entry)
    registry = er.async_get(hass)
    for key in ("audio_quality", "codec", "sample_rate", "bit_depth", "bitrate", "streaming_service"):
        entry = registry.async_get(f"sensor.hegel_h150_{key}")
        assert entry is not None
        assert entry.disabled_by is None
        state = hass.states.get(f"sensor.hegel_h150_{key}")
        assert state is not None
        assert "state_class" not in state.attributes


async def test_seek_only_where_the_amplifier_allows_it(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Spotify Connect cannot seek; a track from a media server can (controls.seekTime)."""
    await _setup(hass, config_entry)
    assert not hass.states.get(ENTITY).attributes["supported_features"] & MediaPlayerEntityFeature.SEEK
    track = {
        "state": "playing",
        "controls": {"pause": True, "next_": True, "previous": True, "seekTime": True},
        "status": {"duration": 240000},
        "trackRoles": {"title": "So What", "mediaData": {"metaData": {"serviceName": "UPnP"}}},
    }
    fake = fake_hegel[-1]
    fake.push("player:player/data", track)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["supported_features"] & MediaPlayerEntityFeature.SEEK
    await hass.services.async_call(
        MP_DOMAIN, "media_seek", {ATTR_ENTITY_ID: ENTITY, "seek_position": 92.5}, blocking=True
    )
    assert ("seek", 92500) in fake.calls


async def test_shuffle_and_repeat_on_a_media_server(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Spotify Connect: no play modes. A media server: shuffle and repeat, combined as the amplifier names them."""
    await _setup(hass, config_entry)
    features = hass.states.get(ENTITY).attributes["supported_features"]
    assert not features & MediaPlayerEntityFeature.SHUFFLE_SET
    assert not features & MediaPlayerEntityFeature.REPEAT_SET
    modes = {"shuffle": True, "repeatOne": True, "repeatAll": True, "shuffleRepeatOne": True, "shuffleRepeatAll": True}
    fake = fake_hegel[-1]
    fake.push(
        "player:player/data",
        {
            "state": "playing",
            "controls": {"pause": True, "seekTime": True, "playMode": modes},
            "status": {"duration": 240000},
            "trackRoles": {"title": "So What", "mediaData": {"metaData": {"serviceName": "Media Servers"}}},
        },
    )
    fake.push("player:player/data/playMode", {"type": "playerPlayMode", "playerPlayMode": "normal"})
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes["supported_features"] & MediaPlayerEntityFeature.SHUFFLE_SET
    assert state.attributes["supported_features"] & MediaPlayerEntityFeature.REPEAT_SET
    assert state.attributes["shuffle"] is False
    assert state.attributes["repeat"] == "off"

    await hass.services.async_call(MP_DOMAIN, "shuffle_set", {ATTR_ENTITY_ID: ENTITY, "shuffle": True}, blocking=True)
    await hass.async_block_till_done()
    assert ("play_mode", "shuffle") in fake.calls
    await hass.services.async_call(MP_DOMAIN, "repeat_set", {ATTR_ENTITY_ID: ENTITY, "repeat": "all"}, blocking=True)
    await hass.async_block_till_done()
    assert ("play_mode", "shuffleRepeatAll") in fake.calls
    state = hass.states.get(ENTITY)
    assert state.attributes["shuffle"] is True
    assert state.attributes["repeat"] == "all"

"""Parsing tests for the API client, using a real H150 recording."""

from __future__ import annotations

import json

from custom_components.hegel_connect.api import EVENT_PATHS, HegelState, PlayerData, unwrap

from .conftest import FIXTURE, snapshot_value


def test_unwrap_typed_values() -> None:
    assert unwrap({"type": "i32_", "i32_": 5}) == 5
    assert unwrap({"type": "bool_", "bool_": True}) is True
    assert unwrap([{"type": "string_", "string_": "H150"}]) == "H150"
    assert unwrap({"state": "playing"}) == {"state": "playing"}


def test_snapshot_state() -> None:
    state = HegelState()
    for path in EVENT_PATHS:
        state.apply_event(path, snapshot_value(path))
    assert state.is_on
    assert state.volume == 17
    assert state.muted is False
    assert state.source_index == 9
    assert state.volume_fixed is False
    assert state.player.title == "Marido Dansa"
    assert state.player.artist == "Franky Rizardo"
    assert state.player.image_url.startswith("https://")


def test_replay_recorded_events() -> None:
    state = HegelState()
    seen_states = set()
    for item in FIXTURE["events"]:
        event = item["e"]
        state.apply_event(event["path"], event["itemValue"])
        if event["path"] == "player:player/data":
            seen_states.add(state.player.state)
    assert {"playing", "paused", "stopped"} <= seen_states
    assert state.power == "online"
    assert state.source_index == 9


def test_radio_has_no_skip() -> None:
    radio = next(
        e["e"]["itemValue"]
        for e in FIXTURE["events"]
        if e["e"]["path"] == "player:player/data"
        and "radioStation" in json.dumps(e["e"]["itemValue"])
        and e["e"]["itemValue"].get("state") == "playing"
    )
    player = PlayerData(radio)
    assert player.is_radio
    assert player.title == "Qmusic"
    assert player.control_allowed("next_") is False


def test_fixed_volume_inputs() -> None:
    state = HegelState()
    state.apply_event("settings:/hegel/volumeType", {"type": "i32_", "i32_": 1})
    assert state.volume_fixed is True


def test_missing_control_flag_means_not_allowed() -> None:
    """Spotify reports only {"pause": true}; next/previous are then refused."""
    player = PlayerData({"controls": {"pause": True}, "state": "playing"})
    assert player.control_allowed("pause") is True
    assert player.control_allowed("next_") is False
    assert player.control_allowed("previous") is False
    assert PlayerData({"controls": {"next_": True, "previous": True}}).control_allowed("next_") is True


def _radio_playing() -> dict:
    """The last radio event: by then the stream format is complete."""
    return [
        e["e"]["itemValue"]
        for e in FIXTURE["events"]
        if e["e"]["path"] == "player:player/data"
        and "radioStation" in json.dumps(e["e"]["itemValue"])
        and e["e"]["itemValue"].get("state") == "playing"
    ][-1]


def test_stream_format_internet_radio() -> None:
    """MP3 16-bit/48 kHz radio is lossy, not CD quality."""
    player = PlayerData(_radio_playing())
    assert player.quality == "lossy"
    assert player.short_codec == "MP3"
    assert player.sample_rate == 48.0
    assert player.bit_depth == 16
    assert player.bitrate == 128
    assert player.duration is None


def test_stream_format_spotify_and_lossless() -> None:
    spotify = {
        "trackRoles": {
            "mediaData": {"activeResource": {"mimeType": "audio/unknown", "quality": {"spotifyHifi": False}}}
        }
    }
    assert PlayerData(spotify).quality == "lossy"
    spotify["trackRoles"]["mediaData"]["activeResource"]["quality"]["spotifyHifi"] = True
    assert PlayerData(spotify).quality == "lossless"

    def flac(bits: int, rate: int) -> PlayerData:
        resource = {"shortCodec": "FLAC", "bitsPerSample": bits, "sampleFrequency": rate}
        return PlayerData({"trackRoles": {"mediaData": {"activeResource": resource}}})

    assert flac(16, 44100).quality == "cd"
    assert flac(24, 96000).quality == "hi_res"
    assert PlayerData({}).quality is None


def test_duration_from_status() -> None:
    assert PlayerData({"status": {"duration": 154153}}).duration == 154
    assert PlayerData({"status": {"duration": 0}}).duration is None


def test_stream_format_airplay_badging() -> None:
    """AirPlay sends its own label (as shown by the amplifier's web client)."""

    def airplay(badge: str) -> PlayerData:
        resource = {"quality": {"airplayBadging": badge}}
        return PlayerData({"trackRoles": {"mediaData": {"activeResource": resource}}})

    assert airplay("Hi-Res Lossless").quality == "hi_res"
    assert airplay("Lossless").quality == "lossless"
    assert airplay("Lossless").short_codec == "Lossless"

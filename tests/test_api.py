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

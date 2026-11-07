"""The now-playing event: one ``track_changed`` per track, with the details the amplifier reports."""

from __future__ import annotations

import copy
import json
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
import pytest

from .conftest import FIXTURE

NOW_PLAYING = "event.hegel_h150_now_playing"
SPOTIFY_PLAYING = 37
SPOTIFY_PAUSED = 38
RADIO_PLAYING = 42
STOPPED = 46


@pytest.fixture(autouse=True)
def stopped_at_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """The recording starts with a Spotify track; these tests start with nothing playing."""
    stopped = FIXTURE["events"][STOPPED]["e"]["itemValue"]
    monkeypatch.setitem(FIXTURE["snap"], "player:player/data", {"status": 200, "body": json.dumps({"value": stopped})})


@pytest.fixture
def fired(hass: HomeAssistant) -> list[dict[str, Any]]:
    """The data of every event the entity fires (a new event changes the state)."""
    seen: list[dict[str, Any]] = []

    def on_change(event: Event) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        if event.data["entity_id"] == NOW_PLAYING and old and new and old.state != new.state:
            seen.append(dict(new.attributes))

    hass.bus.async_listen(EVENT_STATE_CHANGED, on_change)
    return seen


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _replay(hass: HomeAssistant, fake, first: int, last: int) -> None:
    """Replay the player events of the recorded session (Spotify, then a radio station, then stop)."""
    for index in range(first, last + 1):
        event = FIXTURE["events"][index]["e"]
        if event.get("path") == "player:player/data":
            fake.push(event["path"], event["itemValue"])
            await hass.async_block_till_done()


async def _push_track(hass: HomeAssistant, fake, title: str, state: str = "playing") -> None:
    """The recorded Spotify track with another title (and state)."""
    value = copy.deepcopy(FIXTURE["events"][SPOTIFY_PLAYING]["e"]["itemValue"])
    data = value.get("playLogicData", value)
    data["trackRoles"]["title"] = title
    data["state"] = state
    fake.push("player:player/data", value)
    await hass.async_block_till_done()


async def test_a_new_track_fires_once_with_its_details(hass: HomeAssistant, fake_hegel, config_entry, fired) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 35, SPOTIFY_PLAYING)
    assert len(fired) == 1
    event = fired[0]
    assert event["event_type"] == "track_changed"
    assert event["title"] == "Marido Dansa"
    assert event["artist"] == "Franky Rizardo"
    assert event["album"] == "Marido Dansa EP"
    assert event["service"] == "Spotify"
    assert event["source"] == "Network"
    assert event["is_radio"] is False
    assert event["audio_quality"] in ("lossless", "lossy")


async def test_pause_and_resume_do_not_fire(hass: HomeAssistant, fake_hegel, config_entry, fired) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 35, SPOTIFY_PLAYING)
    await _replay(hass, fake, SPOTIFY_PAUSED, SPOTIFY_PAUSED)
    await _replay(hass, fake, SPOTIFY_PLAYING, SPOTIFY_PLAYING)  # resume: the same track
    assert len(fired) == 1


async def test_internet_radio_fires_with_the_stream_details(
    hass: HomeAssistant, fake_hegel, config_entry, fired
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 35, 41)  # switching: nothing plays yet, so nothing is announced
    assert [e["title"] for e in fired] == ["Marido Dansa"]
    await _replay(hass, fake, RADIO_PLAYING, 43)  # "playing" twice: still one event
    assert len(fired) == 2
    radio = fired[1]
    assert radio["title"] == "Qmusic"
    assert radio["service"] == "airable Radio"
    assert radio["is_radio"] is True
    assert radio["audio_quality"] == "lossy"
    assert radio["bitrate"] == 128


async def test_the_same_track_fires_again_after_another_one(
    hass: HomeAssistant, fake_hegel, config_entry, fired
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _push_track(hass, fake, "One")
    await _push_track(hass, fake, "Two")
    await _push_track(hass, fake, "One")
    assert [e["title"] for e in fired] == ["One", "Two", "One"]


async def test_the_same_track_playing_on_does_not_fire_again(
    hass: HomeAssistant, fake_hegel, config_entry, fired
) -> None:
    """Repeat: the amplifier goes through "transitioning" and plays the same track again."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _push_track(hass, fake, "One")
    await _push_track(hass, fake, "One", state="transitioning")
    await _push_track(hass, fake, "One")
    assert len(fired) == 1


async def test_the_same_track_fires_again_after_stopping(hass: HomeAssistant, fake_hegel, config_entry, fired) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _push_track(hass, fake, "One")
    await _replay(hass, fake, STOPPED, STOPPED)
    await _push_track(hass, fake, "One")
    assert [e["title"] for e in fired] == ["One", "One"]


async def test_a_track_that_plays_when_home_assistant_starts_is_not_announced(
    hass: HomeAssistant, fake_hegel, config_entry, fired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing new happened: only a track that starts while Home Assistant runs is an event."""
    playing = FIXTURE["events"][SPOTIFY_PLAYING]["e"]["itemValue"]
    monkeypatch.setitem(FIXTURE["snap"], "player:player/data", {"status": 200, "body": json.dumps({"value": playing})})
    await _setup(hass, config_entry)
    assert hass.states.get("media_player.hegel_h150").attributes["media_title"] == "Marido Dansa"
    assert fired == []
    await _push_track(hass, fake_hegel[-1], "Two")
    assert [e["title"] for e in fired] == ["Two"]


async def test_another_input_fires_nothing(hass: HomeAssistant, fake_hegel, config_entry, fired) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("hegel:activePhysicalSource", {"type": "i32_", "i32_": 1})  # an analog input, not the network input
    await hass.async_block_till_done()
    await _push_track(hass, fake, "One")
    assert fired == []

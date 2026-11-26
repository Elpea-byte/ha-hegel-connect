"""0.8 small fixes: options without hidden_sources, renamed inputs, play after a searched station, favorites retry."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hegel_connect.api import HegelError
from custom_components.hegel_connect.const import DOMAIN, FAVORITES_RETRIES, FAVORITES_RETRY_DELAY

from .conftest import FakeHegel

ENTITY = "media_player.hegel_h150"
SEARCHED = "airable:radios/search/result/42"
START_VOLUME_RCA = "number.hegel_h150_start_volume_rca"
QMUSIC = [{"title": "Qmusic", "path": "airable:fav/qmusic", "id": "fav-1", "icon": None}]


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _options(hass: HomeAssistant, config_entry, user_input: dict) -> None:
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


def _radio(media_id: str, state: str = "playing") -> dict:
    return {
        "state": state,
        "controls": {"next_": False, "previous": False},
        "mediaRoles": {"id": media_id},
        "trackRoles": {"title": "Station", "mediaData": {"metaData": {"serviceName": "Airable", "radioStation": True}}},
    }


# ------------------------------------------------------------------ options


async def test_options_without_hidden_sources_keep_the_hidden_inputs(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """A script that only renames (no hidden_sources) no longer shows the hidden inputs again."""
    await _setup(hass, config_entry)
    await _options(hass, config_entry, {"hidden_sources": ["5", "6"]})
    await _options(hass, config_entry, {"Phono": "Turntable"})
    assert config_entry.options["hidden_sources"] == ["5", "6"]
    assert config_entry.options["source_names"]


async def test_options_with_an_empty_list_show_every_input(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await _options(hass, config_entry, {"hidden_sources": ["5"]})
    await _options(hass, config_entry, {"hidden_sources": []})
    assert config_entry.options["hidden_sources"] == []


async def test_hiding_does_not_reload_renaming_does(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """The start volume entities carry the input's name, which Home Assistant reads when they are added."""
    config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(  # enabled, as a user who switched it on
        "number",
        DOMAIN,
        f"{config_entry.unique_id}_start_volume_2",
        config_entry=config_entry,
        suggested_object_id="hegel_h150_start_volume_rca",
        translation_key="start_volume",
    )
    await _setup(hass, config_entry)
    assert hass.states.get(START_VOLUME_RCA).name.endswith("Start volume RCA")
    first = config_entry.runtime_data
    await _options(hass, config_entry, {"hidden_sources": ["5"]})
    assert config_entry.runtime_data is first
    await _options(hass, config_entry, {"hidden_sources": ["5"], "RCA": "TV"})
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not first
    assert config_entry.runtime_data.names_at_setup == {"2": "TV"}
    assert hass.states.get(START_VOLUME_RCA).name.endswith("Start volume TV")
    # The same names again: no second reload.
    second = config_entry.runtime_data
    await _options(hass, config_entry, {"hidden_sources": [], "RCA": "TV"})
    assert config_entry.runtime_data is second


# ------------------------------------------------------------------ play after a searched station


async def test_play_after_stop_starts_a_searched_station_again(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": SEARCHED},
        blocking=True,
    )
    fake.push("player:player/data", _radio("station-42"))
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    fake.calls.clear()
    await hass.services.async_call(MP_DOMAIN, "media_play", {ATTR_ENTITY_ID: ENTITY}, blocking=True)
    assert ("play_path", SEARCHED) in fake.calls


async def test_the_station_from_before_the_command_is_not_bound(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Until the amplifier reports the new station, the old one keeps playing: its id gets no new path."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("old-station"))
    await hass.async_block_till_done()
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": SEARCHED},
        blocking=True,
    )
    fake.push("player:player/data", _radio("old-station"))
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    assert "old-station" not in coordinator.radio_paths
    fake.push("player:player/data", _radio("station-42"))
    await hass.async_block_till_done()
    assert coordinator.radio_paths == {"station-42": SEARCHED}


async def test_the_new_station_reported_while_the_command_runs_is_bound(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    """The amplifier can report the new station before it answers the play command."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    fake = fake_hegel[-1]

    async def play_path(self, path: str) -> None:
        self.calls.append(("play_path", path))
        self.push("player:player/data", _radio("station-42"))
        for _ in range(20):  # let the listener handle the event before the answer comes
            if coordinator.data.last_radio_id == "station-42":
                break
            await asyncio.sleep(0)
        assert coordinator.data.last_radio_id == "station-42"

    monkeypatch.setattr(FakeHegel, "play_path", play_path)
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": SEARCHED},
        blocking=True,
    )
    assert coordinator.radio_paths == {"station-42": SEARCHED}
    assert coordinator._started_radio is None
    assert fake.calls.count(("play_path", SEARCHED)) == 1


async def test_a_refused_station_is_not_bound_to_a_later_one(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data

    async def refused(self, path: str) -> None:
        raise HegelError("setData 500")

    monkeypatch.setattr(FakeHegel, "play_path", refused)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            "play_media",
            {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": SEARCHED},
            blocking=True,
        )
    assert coordinator._started_radio is None
    # A station started later in the Hegel app keeps no path of ours.
    fake_hegel[-1].push("player:player/data", _radio("station-7"))
    await hass.async_block_till_done()
    assert coordinator.radio_paths == {}


async def test_a_podcast_episode_is_not_noted_as_a_station(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY,
            "media_content_type": "hegel_path",
            "media_content_id": "airable:https://0000000000.airable.io/id/airable/feed.episode/2",
        },
        blocking=True,
    )
    assert config_entry.runtime_data._started_radio is None


async def test_only_the_last_stations_are_kept(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    fake = fake_hegel[-1]
    for number in range(25):
        coordinator.radio_started(f"airable:radios/{number}")
        fake.push("player:player/data", _radio(f"station-{number}"))
        await hass.async_block_till_done()
    assert len(coordinator.radio_paths) == 20
    assert "station-0" not in coordinator.radio_paths
    assert coordinator.radio_paths["station-24"] == "airable:radios/24"


async def test_a_media_server_track_is_no_radio_to_restart(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": "upnp:/uuid:x/album"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert config_entry.runtime_data._started_radio is None


# ------------------------------------------------------------------ favorites retry


async def test_empty_favorites_after_a_start_are_read_again(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    answers: list[list[dict]] = [[], QMUSIC]

    async def favorites(self) -> list[dict]:
        return answers.pop(0) if answers else QMUSIC

    monkeypatch.setattr(FakeHegel, "favorites", favorites)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator.favorites == []
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=FAVORITES_RETRY_DELAY + 1))
    await hass.async_block_till_done()
    assert coordinator.favorites == QMUSIC
    assert hass.states.get("sensor.hegel_h150_radio_favorites").state == "1"


async def test_a_failed_read_keeps_the_last_good_list(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator.favorites == QMUSIC

    async def broken(self) -> list[dict]:
        raise HegelError("not ready")

    monkeypatch.setattr(FakeHegel, "favorites", broken)
    await coordinator.async_refresh_favorites()
    assert coordinator.favorites == QMUSIC


async def test_an_empty_list_counts_after_the_retries(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    """Somebody removed every favorite in the Hegel app: after the retries the empty list is shown."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data

    async def empty(self) -> list[dict]:
        return []

    monkeypatch.setattr(FakeHegel, "favorites", empty)
    await coordinator.async_refresh_favorites()
    assert coordinator.favorites == QMUSIC  # one empty answer is not trusted yet
    for _ in range(FAVORITES_RETRIES):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=FAVORITES_RETRY_DELAY + 1))
        await hass.async_block_till_done()
    assert coordinator.favorites == []


async def test_the_retry_is_cancelled_on_unload(hass: HomeAssistant, fake_hegel, config_entry, monkeypatch) -> None:
    async def empty(self) -> list[dict]:
        return []

    monkeypatch.setattr(FakeHegel, "favorites", empty)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator._favorites_retry is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator._favorites_retry is None


async def test_an_amplifier_without_favorites_is_not_asked_again_and_again(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    """After the retries of the start, the next reads (every 6 hours) take an empty list at once."""
    reads = 0

    async def empty(self) -> list[dict]:
        nonlocal reads
        reads += 1
        return []

    monkeypatch.setattr(FakeHegel, "favorites", empty)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    for _ in range(FAVORITES_RETRIES):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=FAVORITES_RETRY_DELAY + 1))
        await hass.async_block_till_done()
    assert reads == 1 + FAVORITES_RETRIES
    assert coordinator._favorites_retry is None
    await coordinator.async_refresh_favorites()  # the periodic read
    assert reads == 2 + FAVORITES_RETRIES
    assert coordinator._favorites_retry is None


async def test_a_good_read_cancels_the_pending_retry(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    answers: list[list[dict]] = [[], QMUSIC]

    async def favorites(self) -> list[dict]:
        return answers.pop(0) if answers else QMUSIC

    monkeypatch.setattr(FakeHegel, "favorites", favorites)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator._favorites_retry is not None
    await coordinator.async_refresh_favorites()  # e.g. on reconnecting
    assert coordinator.favorites == QMUSIC
    assert coordinator._favorites_retry is None
    assert coordinator._favorites_retries == 0


async def test_going_away_resets_the_retries(hass: HomeAssistant, fake_hegel, config_entry, monkeypatch) -> None:
    async def empty(self) -> list[dict]:
        return []

    monkeypatch.setattr(FakeHegel, "favorites", empty)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator._favorites_retries == 1
    await coordinator._async_connection_lost("test")
    assert coordinator._favorites_retry is None
    assert coordinator._favorites_retries == 0


async def test_a_retry_while_gone_resets_the_count(hass: HomeAssistant, fake_hegel, config_entry, monkeypatch) -> None:
    async def empty(self) -> list[dict]:
        return []

    monkeypatch.setattr(FakeHegel, "favorites", empty)
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.connected = False  # gone without the listener noticing yet
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=FAVORITES_RETRY_DELAY + 1))
    await hass.async_block_till_done()
    assert coordinator._favorites_retries == 0
    assert coordinator._favorites_retry is None

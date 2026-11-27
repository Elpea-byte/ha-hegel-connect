"""The blueprints in blueprints/ are valid Home Assistant blueprints and stay in step with the README."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
import re
import shutil
from urllib.parse import quote

from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.components.script.config import async_validate_config_item as async_validate_script
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

ROOT = Path(__file__).parent.parent
DIR = ROOT / "blueprints" / "automation" / "hegel_connect"
SCRIPT_DIR = ROOT / "blueprints" / "script" / "hegel_connect"
FILES = sorted(DIR.glob("*.yaml")) + sorted(SCRIPT_DIR.glob("*.yaml"))
REPO_BLOB = "https://github.com/Elpea-byte/ha-hegel-connect/blob/main/blueprints/"
# Inputs that pick an entity of another integration (the plug, the TV, Cast, text-to-speech).
OTHER_ENTITIES = {"plug", "tv", "cast_player", "tts_engine"}


def _domain(path: Path) -> str:
    return path.parent.parent.name  # automation or script


# Values for every input, so each blueprint can be filled in and checked as an automation.
SAMPLE_INPUTS = {
    "amplifier": "media_player.hegel_h150",
    "favorite_select": "select.hegel_h150_radio_favorite",
    "station": "Radio 10",
    "at": "07:00:00",
    "days": ["mon", "tue"],
    "volume": 20,
    "only_when_off": True,
    "plug": "switch.audio_plug",
    "connected": "binary_sensor.hegel_h150_network",
    "give_up_after": 120,
    "idle_minutes": 30,
    "when_away": False,
    "max_volume": "number.hegel_h150_maximum_volume",
    "night_from": "22:00:00",
    "night_until": "07:00:00",
    "night_max": 30,
    "day_max": 100,
    "event_entity": "event.hegel_h150_now_playing",
    "logbook": True,
    "notify_action": [],
    "only_quality": [],
    "skip_radio": False,
    "tv": "media_player.tv",
    "source": "Optical 1",
    "standby_with_tv": True,
    "off_delay": 10,
    "default_minutes": 30,
    "steps": 10,
    "restore_volume": True,
    "cast_player": "media_player.hegel_h150_cast",
    "tts_engine": "tts.speech",
    "max_seconds": 60,
    "language": "nl",
}


def _load(path: Path) -> Blueprint:
    return Blueprint(load_yaml_dict(str(path)), path=str(path), expected_domain=_domain(path), schema=BLUEPRINT_SCHEMA)


def test_the_blueprints_are_there() -> None:
    assert [f"{_domain(f)}/{f.stem}" for f in FILES] == [
        "automation/follow_the_tv",
        "automation/night_volume_limit",
        "automation/now_playing",
        "automation/radio_at_time",
        "automation/smart_plug_reconnect",
        "automation/standby_when_idle",
        "automation/switch_on_from_the_mains",
        "script/announcement",
        "script/sleep_timer",
    ]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_blueprint_is_valid(path: Path) -> None:
    blueprint = _load(path)
    meta = blueprint.data["blueprint"]
    assert meta["source_url"] == f"{REPO_BLOB}{_domain(path)}/hegel_connect/{path.name}"
    assert meta["name"].startswith("Hegel Connect")
    assert meta["description"]
    assert meta["homeassistant"]["min_version"]
    assert set(blueprint.inputs) <= set(SAMPLE_INPUTS)
    for name, option in blueprint.inputs.items():
        assert option and option.get("name"), f"{name} needs a name"
        selector = option["selector"]
        # Entity pickers show only this integration's entities (except the ones of other integrations).
        if "entity" in selector and name not in OTHER_ENTITIES:
            assert [f["integration"] for f in selector["entity"]["filter"]] == ["hegel_connect"], name


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
async def test_blueprint_makes_a_valid_automation(hass: HomeAssistant, path: Path) -> None:
    blueprint = _load(path)
    inputs = {name: SAMPLE_INPUTS[name] for name in blueprint.inputs}
    config = BlueprintInputs(blueprint, {"use_blueprint": {"path": path.name, "input": inputs}}).async_substitute()
    if _domain(path) == "script":
        validated = await async_validate_script(hass, "test", {"alias": "test", **config})
    else:
        validated = await async_validate_config_item(hass, "test", {"id": "test", "alias": "test", **config})
    assert validated is not None
    assert validated.validation_status == "ok", validated.validation_error


def test_the_blueprint_page_lists_every_blueprint_with_an_import_button() -> None:
    readme = (ROOT / "docs" / "blueprints.md").read_text(encoding="utf-8")
    assert "docs/blueprints.md" in (ROOT / "README.md").read_text(encoding="utf-8")  # the README links to the page
    for path in FILES:
        raw = (
            "https://raw.githubusercontent.com/Elpea-byte/ha-hegel-connect/main/blueprints/"
            f"{_domain(path)}/hegel_connect/{path.name}"
        )
        assert f"blueprint_import/?blueprint_url={quote(raw, safe='')}" in readme, path.name
    assert not re.search(r"blueprint_url=https:(//|%2F%2F)github\.com", readme)


EVENT = "event.hegel_h150_now_playing"


def _install_blueprint(hass: HomeAssistant) -> None:
    target = Path(hass.config.path("blueprints/automation/hegel_connect"))
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(DIR / "now_playing.yaml", target / "now_playing.yaml")


async def _now_playing_automation(hass: HomeAssistant, **inputs) -> list:
    """Install the now-playing blueprint in a test Home Assistant and return the logbook entries it writes."""
    logbook = async_mock_service(hass, "logbook", "log")  # the real logbook needs the recorder and the frontend
    await hass.async_add_executor_job(_install_blueprint, hass)
    config = {
        "automation": {
            "alias": "now playing",
            "use_blueprint": {
                "path": "hegel_connect/now_playing.yaml",
                "input": {"event_entity": EVENT, **inputs},
            },
        }
    }
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()
    return logbook


def _track(hass: HomeAssistant, when: str, title: str, **attributes) -> None:
    hass.states.async_set(
        EVENT,
        when,
        {
            "event_type": "track_changed",
            "title": title,
            "artist": "Artist",
            "audio_quality": "hi_res",
            "is_radio": False,
        }
        | attributes,
    )


async def test_now_playing_blueprint_logs_each_new_track_and_ignores_a_reload(hass: HomeAssistant) -> None:
    entries = await _now_playing_automation(hass)
    _track(hass, "2026-11-09T20:00:00.000+00:00", "One")
    await hass.async_block_till_done()
    assert [c.data["message"] for c in entries] == ["Artist - One (hi_res)"]
    # The integration reloads: unavailable, then the old time again. Neither is a new track.
    hass.states.async_set(EVENT, "unavailable")
    await hass.async_block_till_done()
    _track(hass, "2026-11-09T20:00:00.000+00:00", "One")
    await hass.async_block_till_done()
    assert len(entries) == 1
    _track(hass, "2026-11-09T20:05:00.000+00:00", "Two")
    await hass.async_block_till_done()
    assert [c.data["message"] for c in entries] == ["Artist - One (hi_res)", "Artist - Two (hi_res)"]


async def test_now_playing_blueprint_filters(hass: HomeAssistant) -> None:
    entries = await _now_playing_automation(hass, only_quality=["hi_res", "lossless"], skip_radio=True)
    _track(hass, "2026-11-09T20:00:00.000+00:00", "Hi-res track")
    _track(hass, "2026-11-09T20:01:00.000+00:00", "Lossy track", audio_quality="lossy")
    _track(hass, "2026-11-09T20:02:00.000+00:00", "Radio song", is_radio=True)
    _track(hass, "2026-11-09T20:03:00.000+00:00", "Lossless track", audio_quality="lossless")
    await hass.async_block_till_done()
    assert [c.data["message"] for c in entries] == [
        "Artist - Hi-res track (hi_res)",
        "Artist - Lossless track (lossless)",
    ]


async def test_now_playing_blueprint_runs_the_action_of_the_user_and_sends_nothing_otherwise(
    hass: HomeAssistant,
) -> None:
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    await _now_playing_automation(
        hass,
        logbook=False,
        notify_action=[
            {"action": "notify.mobile_app_phone", "data": {"message": "{{ title }} by {{ artist }}"}},
        ],
    )
    _track(hass, "2026-11-09T20:00:00.000+00:00", "One")
    await hass.async_block_till_done()
    assert [c.data["message"] for c in calls] == ["One by Artist"]


# ------------------------------------------------------------------ behaviour of the 0.8 blueprints

AMP = "media_player.hegel_h150"
TV = "media_player.tv"


def _install(hass: HomeAssistant, domain: str, name: str) -> None:
    target = Path(hass.config.path(f"blueprints/{domain}/hegel_connect"))
    target.mkdir(parents=True, exist_ok=True)
    source = DIR if domain == "automation" else SCRIPT_DIR
    shutil.copy(source / name, target / name)


def _amp(hass: HomeAssistant, state: str, source: str = "Optical 1", **attributes) -> None:
    hass.states.async_set(
        AMP,
        state,
        {"source": source, "input_names": {"TV": "Optical 1", "Network": "Network"}, "volume_level": 0.3} | attributes,
    )


async def _follow_the_tv(hass: HomeAssistant, **inputs) -> dict[str, list]:
    names = ("turn_off", "select_source", "volume_set")
    calls = {name: async_mock_service(hass, "media_player", name) for name in names}
    calls["turn_on"] = []

    async def turn_on(call) -> None:
        calls["turn_on"].append(call)
        _amp(hass, "on", hass.states.get(AMP).attributes["source"])

    hass.services.async_register("media_player", "turn_on", turn_on)
    await hass.async_add_executor_job(_install, hass, "automation", "follow_the_tv.yaml")
    config = {
        "automation": {
            "alias": "follow the tv",
            "use_blueprint": {
                "path": "hegel_connect/follow_the_tv.yaml",
                "input": {"tv": TV, "amplifier": AMP, "source": "Optical 1", "off_delay": 0, **inputs},
            },
        }
    }
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()
    return calls


async def test_follow_the_tv_switches_on_to_the_tv_input(hass: HomeAssistant) -> None:
    _amp(hass, "off", "Network")
    hass.states.async_set(TV, "off")
    calls = await _follow_the_tv(hass, volume=25)
    hass.states.async_set(TV, "on")
    await hass.async_block_till_done()
    assert len(calls["turn_on"]) == 1
    assert [c.data["source"] for c in calls["select_source"]] == ["Optical 1"]
    assert [c.data["volume_level"] for c in calls["volume_set"]] == [0.25]


async def test_follow_the_tv_standby_only_on_the_tv_input(hass: HomeAssistant) -> None:
    """Shown name "TV" is the amplifier's "Optical 1" (renamed in the options): still the TV input."""
    _amp(hass, "on", "TV")
    hass.states.async_set(TV, "on")
    calls = await _follow_the_tv(hass)
    hass.states.async_set(TV, "off")
    await hass.async_block_till_done()
    assert len(calls["turn_off"]) == 1
    # Music started in the meantime: the TV going off leaves it playing.
    _amp(hass, "playing", "Network")
    hass.states.async_set(TV, "on")
    await hass.async_block_till_done()
    _amp(hass, "playing", "Network")
    hass.states.async_set(TV, "off")
    await hass.async_block_till_done()
    assert len(calls["turn_off"]) == 1


async def test_follow_the_tv_ignores_a_tv_that_comes_back_after_a_restart(hass: HomeAssistant) -> None:
    """unavailable/unknown -> on (Home Assistant or the TV integration starting) is no "TV switched on"."""
    _amp(hass, "off", "Network")
    hass.states.async_set(TV, "unavailable")
    calls = await _follow_the_tv(hass)
    hass.states.async_set(TV, "on")
    await hass.async_block_till_done()
    assert calls["turn_on"] == []


async def _sleep_timer(hass: HomeAssistant, **inputs) -> dict[str, list]:
    calls: dict[str, list] = {}

    async def volume_set(call) -> None:
        calls["volume_set"].append(call)
        _amp(hass, hass.states.get(AMP).state, "Network", volume_level=call.data["volume_level"])

    async def turn_off(call) -> None:
        calls["turn_off"].append(call)
        _amp(hass, "off", "Network", volume_level=hass.states.get(AMP).attributes["volume_level"])

    calls["volume_set"], calls["turn_off"] = [], []
    hass.services.async_register("media_player", "volume_set", volume_set)
    hass.services.async_register("media_player", "turn_off", turn_off)
    await hass.async_add_executor_job(_install, hass, "script", "sleep_timer.yaml")
    config = {
        "script": {
            "sleep": {
                "use_blueprint": {
                    "path": "hegel_connect/sleep_timer.yaml",
                    "input": {"amplifier": AMP, **inputs},
                }
            }
        }
    }
    assert await async_setup_component(hass, "script", config)
    await hass.async_block_till_done()
    return calls


async def _start_sleep_timer(hass: HomeAssistant) -> None:
    """Start the script without waiting for it (it runs for a minute of the frozen clock)."""
    await hass.services.async_call(
        "script", "turn_on", {"entity_id": "script.sleep", "variables": {"minutes": 1}}, blocking=True
    )


async def _tick(hass: HomeAssistant, freezer, seconds: int) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await _settle()


async def _settle() -> None:
    """Let the script run its next steps; async_block_till_done would also wait for its next delay."""
    for _ in range(50):
        await asyncio.sleep(0)


async def test_sleep_timer_fades_goes_to_standby_and_puts_the_volume_back(hass: HomeAssistant, freezer) -> None:
    _amp(hass, "playing", "Network")
    calls = await _sleep_timer(hass, steps=2)
    await _start_sleep_timer(hass)
    await _settle()
    await _tick(hass, freezer, 30)
    assert [c.data["volume_level"] for c in calls["volume_set"]] == [0.2]
    await _tick(hass, freezer, 30)
    assert len(calls["turn_off"]) == 1
    assert [c.data["volume_level"] for c in calls["volume_set"]] == [0.2, 0.3]  # back to the start


async def test_sleep_timer_stops_when_someone_sets_the_volume(hass: HomeAssistant, freezer) -> None:
    _amp(hass, "playing", "Network")
    calls = await _sleep_timer(hass, steps=2)
    await _start_sleep_timer(hass)
    await _settle()
    await _tick(hass, freezer, 30)
    _amp(hass, "playing", "Network", volume_level=0.5)  # turned up by hand
    await _tick(hass, freezer, 30)
    assert calls["turn_off"] == []
    assert [c.data["volume_level"] for c in calls["volume_set"]] == [0.2]


async def test_sleep_timer_on_fixed_volume_only_waits(hass: HomeAssistant, freezer) -> None:
    _amp(hass, "playing", "Optical 1", fixed_volume=True)
    calls = await _sleep_timer(hass, steps=2)
    await _start_sleep_timer(hass)
    await _settle()
    await _tick(hass, freezer, 30)
    await _tick(hass, freezer, 30)
    assert len(calls["turn_off"]) == 1
    assert calls["volume_set"] == []


async def test_sleep_timer_stops_at_one_step_by_hand(hass: HomeAssistant, freezer) -> None:
    """Seen on an H150: 10 -> 11 at the knob went unnoticed with a margin of two steps."""
    _amp(hass, "playing", "Network")
    calls = await _sleep_timer(hass, steps=2)
    await _start_sleep_timer(hass)
    await _settle()
    await _tick(hass, freezer, 30)
    _amp(hass, "playing", "Network", volume_level=0.21)  # one step up from the 0.2 the script set
    await _tick(hass, freezer, 30)
    assert calls["turn_off"] == []


CAST = "media_player.hegel_h150_cast"


async def test_announcement_starts_what_played_again_and_passes_the_language(hass: HomeAssistant, freezer) -> None:
    """Seen on an H150: after the message the amplifier stayed on Cast's receiver, buffering."""
    _amp(hass, "playing", "Network", service="Airable")
    hass.states.async_set(CAST, "idle")
    scene_calls = {name: async_mock_service(hass, "scene", name) for name in ("create", "turn_on")}
    play = async_mock_service(hass, "media_player", "media_play")
    spoken: list = []

    async def speak(call) -> None:
        spoken.append(call)
        hass.states.async_set(CAST, "playing")
        _amp(hass, "buffering", "Network", service="Casting Default Media Receiver")

    hass.services.async_register("tts", "speak", speak)
    await hass.async_add_executor_job(_install, hass, "script", "announcement.yaml")
    inputs = {"amplifier": AMP, "cast_player": CAST, "tts_engine": "tts.speech", "language": "nl"}
    config = {"script": {"say": {"use_blueprint": {"path": "hegel_connect/announcement.yaml", "input": inputs}}}}
    assert await async_setup_component(hass, "script", config)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "script", "turn_on", {"entity_id": "script.say", "variables": {"message": "Eten!"}}, blocking=True
    )
    await _settle()
    assert [(c.data["message"], c.data["language"]) for c in spoken] == [("Eten!", "nl")]
    hass.states.async_set(CAST, "idle")  # the message has played
    await _settle()
    await _tick(hass, freezer, 1)
    assert len(scene_calls["turn_on"]) == 1
    assert play == []
    await _tick(hass, freezer, 5)  # still on Cast's receiver
    assert len(play) == 1

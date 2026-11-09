"""The blueprints in blueprints/ are valid Home Assistant blueprints and stay in step with the README."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
from urllib.parse import quote

from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

ROOT = Path(__file__).parent.parent
DIR = ROOT / "blueprints" / "automation" / "hegel_connect"
FILES = sorted(DIR.glob("*.yaml"))
REPO_BLOB = "https://github.com/Elpea-byte/ha-hegel-connect/blob/main/blueprints/automation/hegel_connect/"

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
}


def _load(path: Path) -> Blueprint:
    return Blueprint(load_yaml_dict(str(path)), path=str(path), expected_domain="automation", schema=BLUEPRINT_SCHEMA)


def test_the_five_blueprints_are_there() -> None:
    names = ["night_volume_limit", "now_playing", "radio_at_time", "smart_plug_reconnect", "standby_when_idle"]
    assert [f.stem for f in FILES] == names


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_blueprint_is_valid(path: Path) -> None:
    blueprint = _load(path)
    meta = blueprint.data["blueprint"]
    assert meta["source_url"] == REPO_BLOB + path.name
    assert meta["name"].startswith("Hegel Connect")
    assert meta["description"]
    assert meta["homeassistant"]["min_version"]
    assert set(blueprint.inputs) <= set(SAMPLE_INPUTS)
    for name, option in blueprint.inputs.items():
        assert option and option.get("name"), f"{name} needs a name"
        selector = option["selector"]
        # Entity pickers show only this integration's entities (except the smart plug, which is not ours).
        if "entity" in selector and name != "plug":
            assert [f["integration"] for f in selector["entity"]["filter"]] == ["hegel_connect"], name


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
async def test_blueprint_makes_a_valid_automation(hass: HomeAssistant, path: Path) -> None:
    blueprint = _load(path)
    inputs = {name: SAMPLE_INPUTS[name] for name in blueprint.inputs}
    config = BlueprintInputs(blueprint, {"use_blueprint": {"path": path.name, "input": inputs}}).async_substitute()
    validated = await async_validate_config_item(hass, "test", {"id": "test", "alias": "test", **config})
    assert validated.validation_status == "ok", validated.validation_error


def test_readme_lists_every_blueprint_with_an_import_button() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for path in FILES:
        raw = f"https://raw.githubusercontent.com/Elpea-byte/ha-hegel-connect/main/blueprints/automation/hegel_connect/{path.name}"
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

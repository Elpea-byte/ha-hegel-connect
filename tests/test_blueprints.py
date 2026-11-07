"""The blueprints in blueprints/ are valid Home Assistant blueprints and stay in step with the README."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import quote

from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml_dict
import pytest

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
}


def _load(path: Path) -> Blueprint:
    return Blueprint(load_yaml_dict(str(path)), path=str(path), expected_domain="automation", schema=BLUEPRINT_SCHEMA)


def test_the_four_blueprints_are_there() -> None:
    names = ["night_volume_limit", "radio_at_time", "smart_plug_reconnect", "standby_when_idle"]
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

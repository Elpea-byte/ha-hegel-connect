"""docs/REFERENCE.md and the README tables stay in step with the code."""

from __future__ import annotations

import json
from pathlib import Path
import re

from custom_components.hegel_connect.const import SUPPORTED_MODELS

ROOT = Path(__file__).parent.parent
STRINGS = json.loads((ROOT / "custom_components" / "hegel_connect" / "strings.json").read_text(encoding="utf-8"))
REFERENCE = (ROOT / "docs" / "REFERENCE.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_every_entity_translation_key_is_in_the_reference() -> None:
    keys = [key for platform in STRINGS["entity"].values() for key in platform]
    assert keys, "no entity translations found"
    missing = [key for key in keys if f"`{key}`" not in REFERENCE]
    assert not missing, f"docs/REFERENCE.md does not mention: {missing}"


def test_every_exception_key_is_in_the_reference() -> None:
    keys = list(STRINGS["exceptions"])
    assert keys
    missing = [key for key in keys if f"`{key}`" not in REFERENCE]
    assert not missing, f"docs/REFERENCE.md does not mention: {missing}"


def test_the_reference_lists_every_extra_attribute_of_the_media_player() -> None:
    source = (ROOT / "custom_components" / "hegel_connect" / "media_player.py").read_text(encoding="utf-8")
    block = source[source.index("def extra_state_attributes") :]
    block = block[: block.index("# ----")]
    attributes = re.findall(r'^\s+"(\w+)":', block, re.M)
    assert attributes
    missing = [name for name in attributes if f"| `{name}` |" not in REFERENCE]
    assert not missing, f"docs/REFERENCE.md does not mention: {missing}"


def test_the_readme_models_match_the_supported_models() -> None:
    row = re.search(r"\| \*\*Streaming platform\*\* \| ([^|]+) \|", README)
    assert row, "the README table of generations changed"
    listed = {model.strip() for model in row.group(1).split(",")}
    assert listed == set(SUPPORTED_MODELS)
    table = README[README.index("| Model | Status |") :]
    table = table[: table.index("\n\n")]
    for model in SUPPORTED_MODELS:
        assert model in table, f"{model} is not in the README models table"


def test_the_reference_lists_every_key_of_the_now_playing_event() -> None:
    source = (ROOT / "custom_components" / "hegel_connect" / "event.py").read_text(encoding="utf-8")
    block = source[source.index("def _event_data") :]
    keys = re.findall(r'^\s+"(\w+)":', block, re.M)
    assert len(keys) >= 12
    missing = [key for key in keys if f"`{key}`" not in REFERENCE]
    assert not missing, f"docs/REFERENCE.md does not mention: {missing}"


def test_the_reference_has_the_standard_attributes_and_the_favorites_attributes() -> None:
    for name in ("source_list", "media_playlist", "entity_picture", "shuffle", "media_position", "favorites"):
        assert f"`{name}`" in REFERENCE, name

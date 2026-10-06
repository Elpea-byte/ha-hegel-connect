"""Every translation has exactly the keys and placeholders of strings.json."""
import json
from pathlib import Path
import re

import pytest

BASE = Path(__file__).parent.parent / "custom_components" / "hegel_connect"
STRINGS = json.loads((BASE / "strings.json").read_text(encoding="utf-8"))
FILES = sorted((BASE / "translations").glob("*.json"))


def _flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{pre}{k}."))
        else:
            out[pre + k] = v
    return out


def test_all_languages_present():
    assert {f.stem for f in FILES} >= {"en", "nl", "nb", "de", "fr", "es"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_same_keys_and_placeholders(path):
    ref = _flat(STRINGS)
    tr = _flat(json.loads(path.read_text(encoding="utf-8")))
    assert set(tr) == set(ref)
    for key, text in ref.items():
        if text.startswith("[%key:"):
            continue
        assert sorted(re.findall(r"\{\w+\}", tr[key])) == sorted(re.findall(r"\{\w+\}", text)), key

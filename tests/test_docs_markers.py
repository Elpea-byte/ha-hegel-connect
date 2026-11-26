"""Docs for a feature that is not released yet carry a marker; it must go when the version is released."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
MARKER = re.compile(r"[Nn]ew in (\d+)\.(\d+)\D{0,12}not released yet")


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def test_no_marker_names_a_version_that_is_released() -> None:
    manifest = json.loads((ROOT / "custom_components" / "hegel_connect" / "manifest.json").read_text(encoding="utf-8"))
    released = _version(manifest["version"])
    stale = []
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        for match in MARKER.finditer(path.read_text(encoding="utf-8")):
            if (int(match.group(1)), int(match.group(2))) <= released:
                stale.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert not stale, "remove these markers with the release: " + "; ".join(stale)


def test_the_markers_are_found() -> None:
    """The pattern matches the markers as they are written, so the test above can fail when it should."""
    assert MARKER.search("> **New in 0.7 (not released yet).** x")
    assert MARKER.search("log what plays, new in 0.7 and not released yet)")
    assert MARKER.search("New in 0.7, not released yet |")

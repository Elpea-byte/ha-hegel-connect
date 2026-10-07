"""Shared fixtures: a fake Hegel built from a real H150 recording."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hegel_connect.api import EVENT_PATHS, HegelConnectionError, HegelQueueLost, HegelSource, url_host
from custom_components.hegel_connect.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "h150_session.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components in every test."""
    return


def snapshot_value(path: str) -> Any:
    return json.loads(FIXTURE["snap"][path]["body"])["value"]


class FakeHegel:
    """Stands in for HegelClient; records commands and replays recorded data."""

    reachable = True
    model = "H150"
    uid = "00000000-0000-0000-0000-000000000000"

    def __init__(self, host: str, session: Any = None, **_: Any) -> None:
        self.host = host
        self.base_url = f"http://{url_host(host)}"
        self.calls: list[tuple] = []
        self.values = {path: snapshot_value(path) for path in FIXTURE["snap"]}
        self._events: asyncio.Queue = asyncio.Queue()

    def _check(self) -> None:
        if not FakeHegel.reachable:
            raise HegelConnectionError("offline")

    async def product_name(self) -> str:
        self._check()
        return FakeHegel.model

    async def device_name(self) -> str:
        return "H150"

    async def unique_id(self) -> str:
        return FakeHegel.uid

    async def sources(self) -> list[HegelSource]:
        self._check()
        rows = json.loads(FIXTURE["rows"]["hegel:listPhysicalSources"])["rows"]
        return [HegelSource(r["value"]["i32_"], r["title"]) for r in rows]

    async def firmware(self) -> str:
        return "1205.1011"

    async def volume_max(self) -> int:
        return 100

    async def get_value(self, path: str) -> Any:
        self._check()
        from custom_components.hegel_connect.api import unwrap

        return unwrap(self.values[path])

    async def fetch_state(self):
        self._check()
        from custom_components.hegel_connect.api import HegelState

        state = HegelState()
        for path in EVENT_PATHS:
            if path in self.values:
                state.apply_event(path, self.values[path])
        return state

    # True: every poll fails as if the event queue is gone (e.g. HTTP 500)
    queue_broken = False

    async def subscribe(self, paths=EVENT_PATHS) -> str:
        self._check()
        self.calls.append(("subscribe",))
        return "{queue}"

    async def poll(self, queue_id: str, timeout: int = 30) -> list[dict]:
        self.calls.append(("poll",))
        if FakeHegel.queue_broken:
            if self.calls.count(("poll",)) > 50:
                # Safety stop: a listener without back-off would loop here forever.
                raise asyncio.CancelledError
            raise HegelQueueLost("500")
        return [await self._events.get()]

    def push(self, path: str, value: Any) -> None:
        """Simulate the amplifier reporting a change."""
        self.values[path] = value
        self._events.put_nowait({"itemType": "update", "path": path, "itemValue": value})

    # commands
    async def power_on(self) -> None:
        self.calls.append(("power_on",))

    async def power_off(self) -> None:
        self.calls.append(("power_off",))

    async def set_volume(self, volume: int) -> None:
        self.calls.append(("set_volume", volume))
        self.push("player:volume", {"type": "i32_", "i32_": volume})

    async def set_mute(self, mute: bool) -> None:
        self.calls.append(("set_mute", mute))

    async def set_source(self, index: int) -> None:
        self.calls.append(("set_source", index))
        self.push("hegel:activePhysicalSource", {"type": "i32_", "i32_": index})

    async def control(self, command: str) -> None:
        self.calls.append(("control", command))

    async def play_time(self) -> dict:
        return {"type": "i64_", "i64_": 30000}

    async def resume_spotify(self) -> None:
        self.calls.append(("resume_spotify",))

    async def seek(self, position_ms: int) -> None:
        self.calls.append(("seek", position_ms))

    async def set_play_mode(self, mode: str) -> None:
        self.calls.append(("play_mode", mode))
        self.push("player:player/data/playMode", {"type": "playerPlayMode", "playerPlayMode": mode})

    async def favorites(self) -> list[dict]:
        return [{"title": "Qmusic", "path": "airable:fav/qmusic", "id": "fav-1", "icon": None}]

    async def favorites_path(self) -> str:
        return "airable:fav"

    async def play_path(self, path: str) -> None:
        self.calls.append(("play_path", path))

    async def play_in_container(self, path: str, index: int, parent: dict | None = None) -> None:
        self.calls.append(("play_in_container", path, index))

    # Browse tree per path; tests fill it in. Unknown paths are empty folders.
    rows: ClassVar[dict[str, dict]] = {}
    raw: ClassVar[dict[str, dict]] = {}

    async def get_rows(self, path: str, start: int = 0, count: int = 50) -> dict:
        data = FakeHegel.rows.get(path, {"rows": [], "roles": {"title": path}})
        rows = data.get("rows", [])
        return {**data, "rows": rows[start : start + count], "rowsCount": len(rows)}

    async def get_raw(self, path: str, roles: str = "@all") -> dict:
        return FakeHegel.raw.get(path, {"type": "container", "path": path})


@pytest.fixture
def fake_hegel():
    """Patch the client everywhere; yields the instance the integration uses."""
    FakeHegel.reachable = True
    FakeHegel.model = "H150"
    FakeHegel.uid = "00000000-0000-0000-0000-000000000000"
    FakeHegel.queue_broken = False
    FakeHegel.rows = {}
    FakeHegel.raw = {}
    instances: list[FakeHegel] = []

    def factory(*args: Any, **kwargs: Any) -> FakeHegel:
        inst = FakeHegel(*args, **kwargs)
        instances.append(inst)
        return inst

    with (
        patch("custom_components.hegel_connect.HegelClient", side_effect=factory),
        patch("custom_components.hegel_connect.config_flow.HegelClient", side_effect=factory),
        patch("custom_components.hegel_connect.coordinator.SOURCE_VERIFY_WAIT", 0.05),
        patch("custom_components.hegel_connect.config_flow.async_has_ip_control", return_value=False),
    ):
        yield instances


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hegel H150",
        unique_id="00000000-0000-0000-0000-000000000000",
        data={"host": "192.0.2.10", "model": "H150"},
    )

"""Shared fixtures: a fake Hegel built from a real H150 recording."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hegel_connect.api import EVENT_PATHS, HegelConnectionError, HegelSource
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

    def __init__(self, host: str, session: Any = None, **_: Any) -> None:
        self.host = host
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
        return "00000000-0000-0000-0000-000000000000"

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
            state.apply_event(path, self.values[path])
        return state

    async def subscribe(self, paths=EVENT_PATHS) -> str:
        self._check()
        return "{queue}"

    async def poll(self, queue_id: str, timeout: int = 30) -> list[dict]:
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

    async def resume_spotify(self) -> None:
        self.calls.append(("resume_spotify",))

    async def play_path(self, path: str) -> None:
        self.calls.append(("play_path", path))

    async def get_rows(self, path: str, start: int = 0, count: int = 50) -> dict:
        return {"rows": [], "roles": {"title": path}}


@pytest.fixture
def fake_hegel():
    """Patch the client everywhere; yields the instance the integration uses."""
    FakeHegel.reachable = True
    FakeHegel.model = "H150"
    instances: list[FakeHegel] = []

    def factory(*args: Any, **kwargs: Any) -> FakeHegel:
        inst = FakeHegel(*args, **kwargs)
        instances.append(inst)
        return inst

    with (
        patch("custom_components.hegel_connect.HegelClient", side_effect=factory),
        patch("custom_components.hegel_connect.config_flow.HegelClient", side_effect=factory),
        patch("custom_components.hegel_connect.coordinator.SOURCE_VERIFY_WAIT", 0.05),
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

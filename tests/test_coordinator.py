"""Push listener tests (the coordinator itself, without the entities)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.hegel_connect.coordinator import HegelCoordinator, queue_lost_delay

from .conftest import FakeHegel


def test_queue_lost_delay_grows() -> None:
    assert [queue_lost_delay(n) for n in range(1, 7)] == [0, 5, 10, 20, 40, 60]


async def test_broken_event_queue_backs_off(hass: HomeAssistant, config_entry) -> None:
    """Subscribe works but every poll fails with a lost queue (e.g. HTTP 500 on pollQueue).

    The listener must re-subscribe once at once and then wait longer each time,
    instead of hammering the amplifier.
    """
    config_entry.add_to_hass(hass)
    FakeHegel.queue_broken = True
    fake = FakeHegel("192.0.2.10")
    coordinator = HegelCoordinator(hass, config_entry, fake)
    real_sleep = asyncio.sleep
    delays: list[float] = []

    async def fake_sleep(delay: float, *args, **kwargs) -> None:
        delays.append(delay)
        if len(delays) >= 5:
            raise asyncio.CancelledError
        await real_sleep(0)

    with (
        patch("custom_components.hegel_connect.coordinator.asyncio.sleep", fake_sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator.async_listen()

    assert delays == [5, 10, 20, 40, 60]
    # One subscribe per failed poll: first retry at once, then one per wait.
    assert fake.calls.count(("subscribe",)) == len(delays) + 1

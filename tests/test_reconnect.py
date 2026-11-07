"""homeassistant.update_entity makes a waiting listener reconnect at once."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest

from custom_components.hegel_connect.api import EVENT_PATHS
from custom_components.hegel_connect.coordinator import HegelCoordinator

from .conftest import FakeHegel

BACKOFF = "custom_components.hegel_connect.coordinator.BACKOFF_START"

# Every platform of the integration: they all share one coordinator.
ENTITIES = [
    "media_player.hegel_h150",
    "sensor.hegel_h150_codec",
    "sensor.hegel_h150_radio_favorites",
    "number.hegel_h150_maximum_volume",
    "select.hegel_h150_radio_favorite",
    "binary_sensor.hegel_h150_network",
]


async def _until(check, timeout: float = 3.0) -> bool:
    """Wait (in real time, briefly) until ``check()`` is true."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if check():
            return True
        await asyncio.sleep(0.01)
    return check()


async def _setup_waiting_in_backoff(hass: HomeAssistant, config_entry):
    """Start with the amplifier off at the mains: the listener waits a long back-off."""
    assert await async_setup_component(hass, "homeassistant", {})  # provides update_entity
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    FakeHegel.reachable = False
    with patch(BACKOFF, 60):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await asyncio.sleep(0.05)  # the first attempt failed, the listener is waiting now
    coordinator = config_entry.runtime_data
    assert not coordinator.connected
    return coordinator


@pytest.mark.parametrize("entity_id", ENTITIES)
async def test_update_entity_reconnects_during_backoff(
    hass: HomeAssistant, fake_hegel, config_entry, entity_id: str
) -> None:
    """The amplifier is back; update_entity on any Hegel entity ends the wait (up to 60 s) at once."""
    coordinator = await _setup_waiting_in_backoff(hass, config_entry)
    FakeHegel.reachable = True
    await hass.services.async_call("homeassistant", "update_entity", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    assert await _until(lambda: coordinator.connected)
    assert hass.states.get("binary_sensor.hegel_h150_network").state == "on"


async def test_update_entity_while_connected_changes_nothing(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    assert await async_setup_component(hass, "homeassistant", {})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    fake = fake_hegel[-1]
    subscribed = fake.calls.count(("subscribe",))
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: "media_player.hegel_h150"}, blocking=True
    )
    await hass.async_block_till_done()
    assert fake.calls.count(("subscribe",)) == subscribed
    assert not config_entry.runtime_data._reconnect_now.is_set()


async def test_backoff_starts_over_after_a_wake(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A wake resets the counter: the waits go 5, 10, 20, 40, (wake), 5, 10."""
    config_entry.add_to_hass(hass)
    FakeHegel.reachable = False
    coordinator = HegelCoordinator(hass, config_entry, FakeHegel("192.0.2.10"))
    delays: list[float] = []

    async def scripted_wait(delay: float) -> bool:
        delays.append(delay)
        if len(delays) >= 6:
            raise asyncio.CancelledError
        return len(delays) == 4  # the fourth wait is cut short

    with patch.object(coordinator, "_wait", scripted_wait), pytest.raises(asyncio.CancelledError):
        await coordinator.async_listen()
    assert delays == [5, 10, 20, 40, 5, 10]


class _SlowFake(FakeHegel):
    """An amplifier whose connection attempt takes a while (until ``gate`` opens)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.gate = asyncio.Event()
        self.attempts = 0
        self.in_flight = 0
        self.max_in_flight = 0

    async def subscribe(self, paths=EVENT_PATHS) -> str:
        self.attempts += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await self.gate.wait()
            return await super().subscribe(paths)
        finally:
            self.in_flight -= 1


async def test_wake_during_an_attempt_gives_one_retry_not_a_second_listener(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """Several wakes while an attempt is running: that attempt ends, one more follows, never two at once."""
    config_entry.add_to_hass(hass)
    FakeHegel.reachable = False
    fake = _SlowFake("192.0.2.10")
    coordinator = HegelCoordinator(hass, config_entry, fake)
    with patch(BACKOFF, 60):
        listener = asyncio.create_task(coordinator.async_listen())
        assert await _until(lambda: fake.attempts == 1)

        for _ in range(3):  # three update_entity calls while the first attempt is still running
            coordinator.request_reconnect()
        fake.gate.set()  # the attempts now fail at once (amplifier unreachable)
        assert await _until(lambda: fake.attempts == 2)
        await asyncio.sleep(0.1)
        assert fake.attempts == 2  # one retry for all three wakes, then it waits again
        assert fake.max_in_flight == 1  # never two attempts at the same time
        assert not coordinator.connected

        FakeHegel.reachable = True
        coordinator.request_reconnect()
        assert await _until(lambda: coordinator.connected)
        assert fake.attempts == 3
        assert fake.max_in_flight == 1
        assert fake.calls.count(("subscribe",)) == 1

        listener.cancel()
        with pytest.raises(asyncio.CancelledError):
            await listener

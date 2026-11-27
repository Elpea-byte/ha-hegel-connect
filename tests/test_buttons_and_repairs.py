"""0.8: the Reconnect and Refresh radio favorites buttons, and the repair issue when the amplifier is gone long."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hegel_connect.api import HegelError
from custom_components.hegel_connect.const import DOMAIN, UNREACHABLE_ISSUE_AFTER

from .conftest import FakeHegel

RECONNECT = "button.hegel_h150_reconnect"
REFRESH = "button.hegel_h150_refresh_radio_favorites"
NEW_FAVORITES = [
    {"title": "Qmusic", "path": "airable:fav/qmusic", "id": "fav-1", "icon": None},
    {"title": "Radio 10", "path": "airable:fav/radio10", "id": "fav-2", "icon": None},
]


def _enable(hass: HomeAssistant, config_entry) -> None:
    """As a user who switched the buttons on (they are disabled by default)."""
    registry = er.async_get(hass)
    for key, object_id in (("reconnect", "hegel_h150_reconnect"), ("refresh_favorites", object_id_refresh())):
        registry.async_get_or_create(
            "button",
            DOMAIN,
            f"{config_entry.unique_id}_{key}",
            config_entry=config_entry,
            suggested_object_id=object_id,
            translation_key=key,
        )


def object_id_refresh() -> str:
    return "hegel_h150_refresh_radio_favorites"


async def _setup(hass: HomeAssistant, config_entry, enable: bool = True) -> None:
    config_entry.add_to_hass(hass)
    if enable:
        _enable(hass, config_entry)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)


async def _gone(hass: HomeAssistant, config_entry) -> None:
    await config_entry.runtime_data._async_connection_lost("test")
    await hass.async_block_till_done()


def _later(hass: HomeAssistant, delta: timedelta) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + delta)


def _issue(hass: HomeAssistant, config_entry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"unreachable_{config_entry.entry_id}")


# ------------------------------------------------------------------ buttons


async def test_the_buttons_are_disabled_by_default(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry, enable=False)
    registry = er.async_get(hass)
    for entity_id in (RECONNECT, REFRESH):
        entry = registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(RECONNECT).entity_category == "diagnostic"
    assert registry.async_get(REFRESH).entity_category == "config"


async def test_reconnect_asks_the_listener_and_reads_the_state(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    asked: list[bool] = []
    monkeypatch.setattr(coordinator, "request_reconnect", lambda: asked.append(True))
    reads: list[bool] = []
    real_fetch = FakeHegel.fetch_state

    async def fetch_state(self):
        reads.append(True)
        return await real_fetch(self)

    monkeypatch.setattr(FakeHegel, "fetch_state", fetch_state)
    await _press(hass, RECONNECT)
    await hass.async_block_till_done()
    assert asked
    assert reads


async def test_reconnect_stays_available_while_the_amplifier_is_gone(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    await _gone(hass, config_entry)
    assert hass.states.get(RECONNECT).state != STATE_UNAVAILABLE
    assert hass.states.get(REFRESH).state == STATE_UNAVAILABLE  # needs the amplifier


async def test_refresh_reads_the_favorites_now(hass: HomeAssistant, fake_hegel, config_entry, monkeypatch) -> None:
    await _setup(hass, config_entry)

    async def favorites(self) -> list[dict]:
        return NEW_FAVORITES

    monkeypatch.setattr(FakeHegel, "favorites", favorites)
    await _press(hass, REFRESH)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.hegel_h150_radio_favorites").state == "2"


async def test_refresh_says_so_when_the_amplifier_refuses(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch
) -> None:
    await _setup(hass, config_entry)

    async def refused(self) -> list[dict]:
        raise HegelError("getRows 500")

    monkeypatch.setattr(FakeHegel, "favorites", refused)
    with pytest.raises(HomeAssistantError) as err:
        await _press(hass, REFRESH)
    assert err.value.translation_key == "command_failed"
    assert hass.states.get("sensor.hegel_h150_radio_favorites").state == "1"  # the last good list stays


# ------------------------------------------------------------------ repair issue


async def test_no_issue_for_a_night_without_power(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry, enable=False)
    await _gone(hass, config_entry)
    _later(hass, timedelta(hours=9))
    await hass.async_block_till_done()
    assert _issue(hass, config_entry) is None


async def test_an_issue_after_a_day_without_an_answer(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry, enable=False)
    await _gone(hass, config_entry)
    _later(hass, UNREACHABLE_ISSUE_AFTER + timedelta(seconds=1))
    await hass.async_block_till_done()
    issue = _issue(hass, config_entry)
    assert issue is not None
    assert issue.translation_key == "unreachable"
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_placeholders == {"name": "Hegel H150", "host": config_entry.data["host"], "hours": "24"}
    # Unloading the integration removes it (nothing watches the amplifier then).
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _issue(hass, config_entry) is None


async def test_the_issue_goes_away_when_the_amplifier_answers(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Started while the amplifier was off at the mains, a day without it, then it answers again."""
    await _setup(hass, config_entry, enable=False)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    FakeHegel.reachable = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    _later(hass, UNREACHABLE_ISSUE_AFTER + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert _issue(hass, config_entry) is not None
    FakeHegel.reachable = True
    coordinator = config_entry.runtime_data
    coordinator.request_reconnect()
    for _ in range(50):  # the listener runs in the background
        if coordinator.connected:
            break
        await asyncio.sleep(0)
    await hass.async_block_till_done()
    assert coordinator.connected
    assert _issue(hass, config_entry) is None


async def test_back_before_a_day_raises_none_later(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry, enable=False)
    await _gone(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator._clear_unreachable()  # what connecting again does (see the test above)
    coordinator.connected = True
    _later(hass, UNREACHABLE_ISSUE_AFTER + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert _issue(hass, config_entry) is None

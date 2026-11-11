"""The optional auto-standby select: the amplifier's own idle timer (#42)."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hegel_connect.api import HegelError
from custom_components.hegel_connect.const import DOMAIN

from .conftest import FakeHegel

ENTITY = "select.hegel_h150_auto_standby"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    """Set up with the (disabled by default) select enabled, as a user who switched it on."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "select",
        DOMAIN,
        f"{config_entry.unique_id}_auto_standby",
        config_entry=config_entry,
        suggested_object_id="hegel_h150_auto_standby",
        translation_key="auto_standby",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _choose(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": option}, blocking=True
    )


async def test_the_select_is_disabled_by_default(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entry = er.async_get(hass).async_get(ENTITY)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is er.EntityCategory.CONFIG
    assert hass.states.get(ENTITY) is None


async def test_it_shows_the_choices_and_the_value_of_the_amplifier(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    FakeHegel.idle_seconds = 600
    await _setup(hass, config_entry)
    state = hass.states.get(ENTITY)
    assert state.state == "10_min"
    assert state.attributes["options"] == ["off", "5_min", "10_min", "20_min"]


async def test_choosing_writes_the_value_to_the_amplifier(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).state == "off"
    await _choose(hass, "5_min")
    assert ("set_idle_time", 300) in fake_hegel[-1].calls
    assert hass.states.get(ENTITY).state == "5_min"
    await _choose(hass, "off")
    assert ("set_idle_time", 0) in fake_hegel[-1].calls
    assert hass.states.get(ENTITY).state == "off"


async def test_a_failing_write_is_reported_and_the_value_stays(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)

    async def refuse(seconds: int) -> None:
        raise HegelError("setData 500: nope")

    fake_hegel[-1].set_idle_time = refuse
    with pytest.raises(HomeAssistantError):
        await _choose(hass, "10_min")
    assert hass.states.get(ENTITY).state == "off"


async def test_an_amplifier_without_the_setting_leaves_the_select_unavailable(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    FakeHegel.idle_supported = False
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_the_value_is_read_again_now_and_then(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A change made elsewhere (the Hegel app) shows up at the next read."""
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).state == "off"
    FakeHegel.idle_seconds = 1200
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=7))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "20_min"


async def test_the_value_is_read_again_after_the_connection_returns(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.connected = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE  # not connected: nothing to show
    FakeHegel.idle_seconds = 300
    coordinator.connected = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "5_min"


async def test_a_value_the_amplifier_does_not_offer_shows_no_option(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    FakeHegel.idle_seconds = 450
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).state == "unknown"

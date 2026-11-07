"""Optional volume per input: a start volume and "remember the last volume" (#29)."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.hegel_connect.api import HegelError
from custom_components.hegel_connect.const import DOMAIN
from custom_components.hegel_connect.number import HegelStartVolume

ENTITY = "media_player.hegel_h150"
NUMBER_RCA = "number.hegel_h150_start_volume_rca"
SWITCH = "switch.hegel_h150_remember_volume_per_input"
RCA = 2
NETWORK = 1  # the recorded session plays on the network input; read from the amplifier below


async def _setup(hass: HomeAssistant, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


async def _select(hass: HomeAssistant, source: str) -> None:
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_SELECT_SOURCE, {ATTR_ENTITY_ID: ENTITY, ATTR_INPUT_SOURCE: source}, blocking=True
    )
    await hass.async_block_till_done()


def _volumes(fake) -> list[int]:
    return [call[1] for call in fake.calls if call[0] == "set_volume"]


async def test_nothing_changes_by_default(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await _select(hass, "RCA")
    assert ("set_source", RCA) in fake_hegel[-1].calls
    assert _volumes(fake_hegel[-1]) == []


async def test_the_optional_entities_are_disabled_by_default(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    registry = er.async_get(hass)
    for entity_id in (NUMBER_RCA, SWITCH):
        entry = registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None


async def test_start_volume_is_set_after_switching(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.start_volumes[RCA] = 20
    await _select(hass, "RCA")
    fake = fake_hegel[-1]
    assert _volumes(fake) == [20]
    assert fake.calls.index(("set_source", RCA)) < fake.calls.index(("set_volume", 20))


async def test_start_volume_stays_within_the_maximum_volume(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.start_volumes[RCA] = 60
    coordinator.max_volume = 35
    await _select(hass, "RCA")
    assert _volumes(fake_hegel[-1]) == [35]


async def test_start_volume_equal_to_the_current_volume_sends_nothing(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.start_volumes[RCA] = coordinator.data.volume
    await _select(hass, "RCA")
    assert _volumes(fake_hegel[-1]) == []


async def test_a_fixed_volume_is_left_alone(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.start_volumes[RCA] = 20
    coordinator.data.volume_fixed = True
    await _select(hass, "RCA")
    assert _volumes(fake_hegel[-1]) == []


async def test_a_failing_volume_command_does_not_fail_the_switch(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.start_volumes[RCA] = 20

    async def refuse(volume: int) -> None:
        raise HegelError("refused")

    monkeypatch.setattr(fake_hegel[-1], "set_volume", refuse)
    await _select(hass, "RCA")
    assert ("set_source", RCA) in fake_hegel[-1].calls


async def test_remember_volume_returns_to_the_last_volume_of_each_input(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    coordinator = await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    network = coordinator.data.source_index
    coordinator.remember_volume = True
    fake.push("player:volume", {"type": "i32_", "i32_": 33})
    await hass.async_block_till_done()
    await _select(hass, "RCA")
    assert _volumes(fake) == []  # nothing remembered for RCA yet
    fake.push("player:volume", {"type": "i32_", "i32_": 12})
    await hass.async_block_till_done()
    await _select(hass, coordinator.source_name(network))
    assert _volumes(fake) == [33]
    await _select(hass, "RCA")
    assert _volumes(fake) == [33, 12]


async def test_remember_volume_is_off_by_default(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    network = coordinator.data.source_index
    fake.push("player:volume", {"type": "i32_", "i32_": 33})
    await hass.async_block_till_done()
    assert coordinator.last_volumes == {}
    await _select(hass, "RCA")
    await _select(hass, coordinator.source_name(network))
    assert _volumes(fake) == []


async def test_a_start_volume_wins_over_the_remembered_one(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    coordinator.remember_volume = True
    coordinator.last_volumes[RCA] = 12
    coordinator.start_volumes[RCA] = 25
    await _select(hass, "RCA")
    assert _volumes(fake_hegel[-1]) == [25]


async def test_remembered_volumes_are_saved_and_loaded(
    hass: HomeAssistant, fake_hegel, config_entry, hass_storage: dict
) -> None:
    hass_storage[f"{DOMAIN}.{config_entry.entry_id}.volumes"] = {
        "version": 1,
        "key": f"{DOMAIN}.{config_entry.entry_id}.volumes",
        "data": {"2": 18},
    }
    coordinator = await _setup(hass, config_entry)
    assert coordinator.last_volumes == {RCA: 18}
    coordinator.remember_volume = True
    fake_hegel[-1].push("player:volume", {"type": "i32_", "i32_": 29})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    saved = hass_storage[f"{DOMAIN}.{config_entry.entry_id}.volumes"]["data"]["volumes"]
    assert saved["2"] == 18
    assert 29 in saved.values()


async def _reload_after_registry_change(hass: HomeAssistant) -> None:
    """Enabling or disabling an entity makes Home Assistant reload the entry after a short delay."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=40))
    await hass.async_block_till_done()


async def _enable(hass: HomeAssistant, config_entry, *entity_ids: str) -> None:
    registry = er.async_get(hass)
    for entity_id in entity_ids:
        registry.async_update_entity(entity_id, disabled_by=None)
    await _reload_after_registry_change(hass)


async def test_the_start_volume_number_sets_and_clears(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    await _enable(hass, config_entry, NUMBER_RCA)
    coordinator = config_entry.runtime_data
    assert float(hass.states.get(NUMBER_RCA).state) == 0
    await hass.services.async_call(NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: NUMBER_RCA, "value": 22}, blocking=True)
    assert coordinator.start_volumes == {RCA: 22}
    assert float(hass.states.get(NUMBER_RCA).state) == 22
    await hass.services.async_call(NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: NUMBER_RCA, "value": 0}, blocking=True)
    assert coordinator.start_volumes == {}


def _enabled_entity(hass: HomeAssistant, config_entry, domain: str, key: str, object_id: str) -> None:
    """Put an enabled entity in the registry before setup, as if the user had enabled it earlier."""
    er.async_get(hass).async_get_or_create(
        domain,
        DOMAIN,
        f"{config_entry.unique_id}_{key}",
        suggested_object_id=object_id,
        config_entry=config_entry,
    )


async def test_the_start_volume_number_is_restored(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "number", f"start_volume_{RCA}", "hegel_h150_start_volume_rca")
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(NUMBER_RCA, "24"),
                {
                    "native_max_value": 100,
                    "native_min_value": 0,
                    "native_step": 1,
                    "native_unit_of_measurement": None,
                    "native_value": 24,
                },
            )
        ],
    )
    coordinator = await _setup(hass, config_entry)
    assert coordinator.start_volumes == {RCA: 24}
    # Switching the entity off takes its start volume away again.
    er.async_get(hass).async_update_entity(NUMBER_RCA, disabled_by=er.RegistryEntryDisabler.USER)
    await _reload_after_registry_change(hass)
    assert config_entry.runtime_data.start_volumes == {}


async def test_the_remember_switch(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "switch", "remember_volume", "hegel_h150_remember_volume_per_input")
    coordinator = await _setup(hass, config_entry)
    assert hass.states.get(SWITCH).state == STATE_OFF
    await hass.services.async_call(SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: SWITCH}, blocking=True)
    assert coordinator.remember_volume
    assert hass.states.get(SWITCH).state == STATE_ON
    assert coordinator.last_volumes  # the volume of the current input is kept straight away
    await hass.services.async_call(SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: SWITCH}, blocking=True)
    assert not coordinator.remember_volume


async def test_the_remember_switch_is_restored(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "switch", "remember_volume", "hegel_h150_remember_volume_per_input")
    mock_restore_cache(hass, [State(SWITCH, STATE_ON)])
    coordinator = await _setup(hass, config_entry)
    assert coordinator.remember_volume
    assert hass.states.get(SWITCH).state == STATE_ON


async def test_lowering_the_maximum_brings_a_louder_volume_down(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    coordinator = await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:volume", {"type": "i32_", "i32_": 40})
    await hass.async_block_till_done()
    await hass.services.async_call(
        NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: "number.hegel_h150_maximum_volume", "value": 30}, blocking=True
    )
    assert _volumes(fake) == [30]
    assert coordinator.max_volume == 30


@pytest.mark.parametrize("case", ["below", "fixed", "off", "offline"])
async def test_lowering_the_maximum_leaves_other_cases_alone(
    hass: HomeAssistant, fake_hegel, config_entry, case: str
) -> None:
    coordinator = await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:volume", {"type": "i32_", "i32_": 40 if case != "below" else 10})
    await hass.async_block_till_done()
    if case == "fixed":
        coordinator.data.volume_fixed = True
    elif case == "off":
        fake.push("powermanager:target", {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}})
        await hass.async_block_till_done()
    elif case == "offline":
        coordinator.connected = False
    await hass.services.async_call(
        NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: "number.hegel_h150_maximum_volume", "value": 30}, blocking=True
    )
    assert _volumes(fake) == []


async def test_lowering_the_maximum_survives_a_refusing_amplifier(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:volume", {"type": "i32_", "i32_": 40})
    await hass.async_block_till_done()

    async def refuse(volume: int) -> None:
        raise HegelError("refused")

    monkeypatch.setattr(fake, "set_volume", refuse)
    await hass.services.async_call(
        NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: "number.hegel_h150_maximum_volume", "value": 30}, blocking=True
    )


async def test_an_input_with_fixed_volume_is_learned_and_its_number_is_unavailable(
    hass: HomeAssistant, fake_hegel, config_entry, hass_storage: dict
) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "number", f"start_volume_{RCA}", "hegel_h150_start_volume_rca")
    coordinator = await _setup(hass, config_entry)
    assert hass.states.get(NUMBER_RCA).state != "unavailable"
    coordinator.start_volumes[RCA] = 18
    coordinator.data.volume_fixed = True  # what the amplifier reports once it sits on RCA
    await _select(hass, "RCA")
    assert _volumes(fake_hegel[-1]) == []  # fixed volume: nothing is set
    assert coordinator.fixed_inputs == {RCA}
    assert hass.states.get(NUMBER_RCA).state == "unavailable"
    # Remembered between restarts.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert hass_storage[f"{DOMAIN}.{config_entry.entry_id}.volumes"]["data"]["fixed"] == [RCA]
    # And forgotten when the input turns out to have a variable volume again.
    coordinator.data.volume_fixed = False
    coordinator.note_fixed_volume(RCA, False)
    assert coordinator.fixed_inputs == set()
    assert hass.states.get(NUMBER_RCA).state != "unavailable"


async def test_the_number_range_follows_the_maximum_volume(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "number", f"start_volume_{RCA}", "hegel_h150_start_volume_rca")
    coordinator = await _setup(hass, config_entry)
    assert hass.states.get(NUMBER_RCA).attributes["max"] == coordinator.volume_max
    coordinator.max_volume = 35
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(NUMBER_RCA).attributes["max"] == 35


async def test_turning_remember_off_clears_the_saved_volumes(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "switch", "remember_volume", "hegel_h150_remember_volume_per_input")
    coordinator = await _setup(hass, config_entry)
    await hass.services.async_call(SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: SWITCH}, blocking=True)
    assert coordinator.last_volumes
    await hass.services.async_call(SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: SWITCH}, blocking=True)
    assert coordinator.last_volumes == {}


async def test_the_older_storage_format_is_still_read(
    hass: HomeAssistant, fake_hegel, config_entry, hass_storage: dict
) -> None:
    """Dev versions saved the volumes without the "volumes"/"fixed" keys."""
    key = f"{DOMAIN}.{config_entry.entry_id}.volumes"
    hass_storage[key] = {"version": 1, "key": key, "data": {"2": 18, "x": "bad"}}
    coordinator = await _setup(hass, config_entry)
    assert coordinator.last_volumes == {RCA: 18}
    assert coordinator.fixed_inputs == set()


async def test_a_start_volume_on_a_fixed_volume_input_is_refused(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Home Assistant itself skips service calls to the unavailable entity; the entity refuses too, with a reason."""
    config_entry.add_to_hass(hass)
    _enabled_entity(hass, config_entry, "number", f"start_volume_{RCA}", "hegel_h150_start_volume_rca")
    coordinator = await _setup(hass, config_entry)
    coordinator.note_fixed_volume(RCA, True)
    await hass.async_block_till_done()
    assert hass.states.get(NUMBER_RCA).state == "unavailable"
    # Through the service: skipped by Home Assistant (a warning in the log), nothing is stored.
    await hass.services.async_call(NUMBER_DOMAIN, "set_value", {ATTR_ENTITY_ID: NUMBER_RCA, "value": 18}, blocking=True)
    assert coordinator.start_volumes == {}
    # Straight on the entity: a clear, translated error.
    entity = HegelStartVolume(coordinator, RCA)
    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_native_value(18)
    assert err.value.translation_key == "fixed_volume_input"
    assert err.value.translation_placeholders == {"input": "RCA"}
    assert coordinator.start_volumes == {}
    # Clearing it (0) is fine.
    entity.hass = hass
    entity.async_write_ha_state = lambda: None  # type: ignore[method-assign]
    await entity.async_set_native_value(0)

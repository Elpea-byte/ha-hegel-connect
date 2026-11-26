"""0.8: entities that need the amplifier are unavailable while it does not answer at all.

Standby is not "gone": the amplifier still answers then, so the media player is off and
available. The network sensor tells the two apart and is always available.
"""

from __future__ import annotations

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hegel_connect.const import DOMAIN

from .conftest import FakeHegel

PLAYER = "media_player.hegel_h150"
NETWORK = "binary_sensor.hegel_h150_network"
RADIO_SELECT = "select.hegel_h150_radio_favorite"

# Need the amplifier: unavailable while it is gone.
FOLLOW = [
    PLAYER,
    "sensor.hegel_h150_audio_quality",
    "sensor.hegel_h150_codec",
    "sensor.hegel_h150_sample_rate",
    "sensor.hegel_h150_bit_depth",
    "sensor.hegel_h150_bitrate",
    "sensor.hegel_h150_streaming_service",
    "binary_sensor.hegel_h150_fixed_volume",
    RADIO_SELECT,
]
# Their value lives in Home Assistant (settings, the saved favorites), or they report "gone" themselves.
STAY = [
    NETWORK,
    "sensor.hegel_h150_radio_favorites",
    "number.hegel_h150_maximum_volume",
]


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _gone(hass: HomeAssistant, config_entry) -> None:
    await config_entry.runtime_data._async_connection_lost("test")
    await hass.async_block_till_done()


async def test_gone_makes_the_amplifier_entities_unavailable(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    for entity_id in FOLLOW + STAY:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id
    await _gone(hass, config_entry)
    for entity_id in FOLLOW:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE, entity_id
    for entity_id in STAY:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id
    assert hass.states.get(NETWORK).state == "off"


async def test_standby_is_off_not_unavailable(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake_hegel[-1].push("powermanager:target", {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}})
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == "off"
    assert hass.states.get(NETWORK).state == "on"
    assert hass.states.get(RADIO_SELECT).state != STATE_UNAVAILABLE


async def test_back_after_gone(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await _gone(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.connected = True
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    for entity_id in FOLLOW:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id
    assert hass.states.get(NETWORK).state == "on"


async def test_a_normal_start_never_shows_unavailable(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """The first read works, so the entities start with their state, not unavailable for a moment."""
    seen: list[str] = []

    def on_change(event: Event) -> None:
        if event.data["entity_id"] == PLAYER and event.data["new_state"] is not None:
            seen.append(event.data["new_state"].state)

    hass.bus.async_listen(EVENT_STATE_CHANGED, on_change)
    await _setup(hass, config_entry)
    assert seen
    assert STATE_UNAVAILABLE not in seen


async def test_a_command_while_gone_is_not_sent(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Home Assistant skips service calls to an unavailable entity: nothing reaches the amplifier."""
    await _setup(hass, config_entry)
    await _gone(hass, config_entry)
    fake = fake_hegel[-1]
    before = len(fake.calls)
    await hass.services.async_call(
        "media_player", "volume_set", {"entity_id": PLAYER, "volume_level": 0.5}, blocking=True
    )
    assert not [call for call in fake.calls[before:] if call[0] == "set_volume"]


async def test_started_offline_is_unavailable_but_keeps_the_favorites(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    FakeHegel.reachable = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == STATE_UNAVAILABLE
    assert hass.states.get(NETWORK).state == "off"
    assert hass.states.get("sensor.hegel_h150_radio_favorites").state != STATE_UNAVAILABLE


async def test_a_failed_refresh_leaves_the_kept_entities_and_the_event_available(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """A refresh that fails (a bad answer, not "gone") must not flip the now-playing event either."""
    config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "event",
        DOMAIN,
        f"{config_entry.unique_id}_now_playing",
        config_entry=config_entry,
        suggested_object_id="hegel_h150_now_playing",
        translation_key="now_playing",
    )
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    for entity_id in [*STAY, "event.hegel_h150_now_playing"]:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id
    assert hass.states.get(PLAYER).state == STATE_UNAVAILABLE

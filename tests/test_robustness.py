"""Odd values from the amplifier (or a fake one) must not stop the integration."""

from __future__ import annotations

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.hegel_connect.api import PATH_SOURCE, PATH_VOLUME, HegelClient

ENTITY = "media_player.hegel_h150"
# What the JSON text 1e999 becomes in Python.
HUGE = float("inf")


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_event_with_a_huge_number_does_not_restart_the_listener(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """int(1e999) raises OverflowError: the event is skipped, push keeps running without a new subscription."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    subscribed = fake.calls.count(("subscribe",))
    fake.push(PATH_VOLUME, {"type": "i32_", "i32_": HUGE})
    fake.push(PATH_VOLUME, {"type": "i32_", "i32_": 25})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).attributes["volume_level"] == 0.25
    assert fake.calls.count(("subscribe",)) == subscribed
    assert config_entry.runtime_data.connected


async def test_switching_input_survives_a_huge_number_when_reading_the_input(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    fake = fake_hegel[-1]

    async def get_value(path: str):
        return HUGE  # get_value returns the plain value

    async def set_source(index: int) -> None:
        fake.calls.append(("set_source", index))  # no push back: the coordinator must read the input itself

    reads: list[str] = []

    async def counting_get_value(path: str):
        reads.append(path)
        return await get_value(path)

    monkeypatch.setattr(fake, "set_source", set_source)
    monkeypatch.setattr(fake, "get_value", counting_get_value)
    coordinator.connected = False
    await coordinator.async_select_source("RCA")  # does not raise
    assert ("set_source", 2) in fake.calls
    assert reads  # the huge value was really read


async def _client_with(monkeypatch: pytest.MonkeyPatch, **answers) -> HegelClient:
    client = HegelClient("192.0.2.10", None)  # type: ignore[arg-type]

    async def get_raw(path: str, roles: str = "@all"):
        return answers["raw"]

    async def get_value(path: str):
        return answers["value"](path) if callable(answers["value"]) else answers["value"]

    monkeypatch.setattr(client, "get_raw", get_raw)
    monkeypatch.setattr(client, "get_value", get_value)
    return client


async def test_volume_range_with_a_huge_number_falls_back_to_100(monkeypatch: pytest.MonkeyPatch) -> None:
    client = await _client_with(monkeypatch, raw={"edit": {"max": HUGE}}, value=None)
    assert await client.volume_max() == 100


async def test_reading_the_state_skips_a_huge_number(monkeypatch: pytest.MonkeyPatch) -> None:
    def value(path: str):
        if path == PATH_SOURCE:
            return {"type": "i32_", "i32_": HUGE}
        if path == "powermanager:target":
            return {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}}
        return {"type": "i32_", "i32_": 7}

    client = await _client_with(monkeypatch, raw=None, value=value)
    state = await client.fetch_state()
    assert state.volume == 7  # the other paths are still read
    assert state.source_index is None


@pytest.mark.parametrize("media_id", ["track:²:folder", "track:x:folder", "track::folder", "track:1:"])
async def test_track_id_with_odd_digits_is_refused(
    hass: HomeAssistant, fake_hegel, config_entry, media_id: str
) -> None:
    """str.isdigit() accepts a superscript two that int() cannot read; isdecimal() does not."""
    await _setup(hass, config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            MP_DOMAIN,
            "play_media",
            {ATTR_ENTITY_ID: ENTITY, "media_content_type": "hegel_path", "media_content_id": media_id},
            blocking=True,
        )
    assert err.value.translation_key == "unknown_media"
    assert not any(call[0] == "play_in_container" for call in fake_hegel[-1].calls)

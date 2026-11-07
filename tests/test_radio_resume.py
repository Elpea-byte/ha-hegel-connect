"""Play after live radio was stopped starts the same favorite again (#30)."""

from __future__ import annotations

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest

ENTITY = "media_player.hegel_h150"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def _radio(media_id: str, state: str = "playing") -> dict:
    return {
        "state": state,
        "controls": {"next_": False, "previous": False},
        "mediaRoles": {"id": media_id},
        "trackRoles": {"title": "Qmusic", "mediaData": {"metaData": {"serviceName": "Airable", "radioStation": True}}},
    }


def _track(state: str = "playing") -> dict:
    return {
        "state": state,
        "controls": {"next_": True, "previous": True},
        "mediaRoles": {"id": "song-1"},
        "trackRoles": {"title": "Song", "mediaData": {"metaData": {"serviceName": "Qobuz"}}},
    }


async def _play(hass: HomeAssistant) -> None:
    await hass.services.async_call(MP_DOMAIN, "media_play", {ATTR_ENTITY_ID: ENTITY}, blocking=True)


async def test_play_after_stopped_radio_starts_the_favorite(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", "airable:fav/qmusic") in fake.calls


async def test_play_while_radio_plays_does_nothing(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert not any(call[0] == "play_path" for call in fake.calls)


async def test_play_after_something_else_has_nothing_to_resume(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Radio first, then a track: the radio is no longer the last thing played."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    fake.push("player:player/data", _track())
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await _play(hass)
    assert err.value.translation_key == "nothing_to_resume"


async def test_play_after_a_station_that_is_no_favorite_has_nothing_to_resume(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("not-a-favorite"))
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await _play(hass)


async def test_the_last_station_survives_a_full_refresh(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """A fresh read while stopped (reconnect, power on) must not forget the station."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", "airable:fav/qmusic") in fake.calls

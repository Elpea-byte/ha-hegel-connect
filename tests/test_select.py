"""The radio favorite select: options, current station and starting one."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hegel_connect.api import HegelError

from .conftest import FakeHegel

ENTITY = "select.hegel_h150_radio_favorite"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def _radio(media_id: str | None, state: str = "playing") -> dict:
    player: dict = {
        "state": state,
        "controls": {"next_": False, "previous": False},
        "trackRoles": {"title": "Qmusic", "mediaData": {"metaData": {"serviceName": "Airable", "radioStation": True}}},
    }
    if media_id is not None:
        player["mediaRoles"] = {"id": media_id}
    return player


async def test_options_are_the_favorites(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.attributes["options"] == ["Qmusic"]


async def test_state_is_unknown_when_no_favorite_plays(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """The recorded session plays from Spotify, which is not one of the favorites."""
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_state_follows_the_playing_favorite(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Qmusic"
    # Another station that is not a favorite: nothing selected.
    fake.push("player:player/data", _radio("other-station"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    # Nothing playing any more.
    fake.push("player:player/data", _radio("fav-1", state="stopped"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    # A player without an id.
    fake.push("player:player/data", _radio(None))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_state_unknown_when_amplifier_is_off(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("fav-1"))
    await hass.async_block_till_done()
    fake.push("powermanager:target", {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_select_option_starts_the_station(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": "Qmusic"}, blocking=True
    )
    assert ("play_path", "airable:fav/qmusic") in fake_hegel[-1].calls


async def test_select_unknown_option_is_refused(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": "Nope"}, blocking=True
        )
    assert not any(call[0] == "play_path" for call in fake_hegel[-1].calls)


async def test_select_option_reports_amplifier_errors(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _setup(hass, config_entry)

    async def refuse(path: str) -> None:
        raise HegelError("Control is not supported")

    monkeypatch.setattr(fake_hegel[-1], "play_path", refuse)
    with pytest.raises(HomeAssistantError, match="Control is not supported"):
        await hass.services.async_call(
            SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": "Qmusic"}, blocking=True
        )
    # A failed start is not shown as chosen.
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_equal_titles_get_a_number(hass: HomeAssistant, fake_hegel, config_entry, monkeypatch) -> None:
    """Two favorites with the same name stay separate options, each with its own station."""

    async def favorites(self) -> list[dict]:
        return [
            {"title": "Radio 2", "path": "airable:fav/a", "id": "a", "icon": None},
            {"title": "Radio 2", "path": "airable:fav/b", "id": "b", "icon": None},
        ]

    monkeypatch.setattr(FakeHegel, "favorites", favorites)
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).attributes["options"] == ["Radio 2", "Radio 2 (2)"]
    await hass.services.async_call(
        SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": "Radio 2 (2)"}, blocking=True
    )
    assert ("play_path", "airable:fav/b") in fake_hegel[-1].calls
    fake_hegel[-1].push("player:player/data", _radio("b"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Radio 2 (2)"


async def _choose(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN, "select_option", {ATTR_ENTITY_ID: ENTITY, "option": option}, blocking=True
    )


async def test_chosen_station_stays_selected_while_switching(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Choosing shows the station at once and keeps it through the buffering phase (no flicker to unknown)."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _choose(hass, "Qmusic")
    assert hass.states.get(ENTITY).state == "Qmusic"
    # The amplifier is buffering the station, then plays it.
    fake.push("player:player/data", _radio("fav-1", state="buffering"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Qmusic"
    fake.push("player:player/data", _radio("fav-1"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Qmusic"
    # Once it plays, the select follows the amplifier again.
    fake.push("player:player/data", _radio("other-station"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_chosen_station_is_released_after_a_time_out(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """If the station never starts, the select falls back to what really plays."""
    await _setup(hass, config_entry)
    await _choose(hass, "Qmusic")
    assert hass.states.get(ENTITY).state == "Qmusic"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_chosen_station_wins_over_the_old_favorite_until_it_plays(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def favorites(self) -> list[dict]:
        return [
            {"title": "Radio 10", "path": "airable:fav/r10", "id": "r10", "icon": None},
            {"title": "Qmusic", "path": "airable:fav/q", "id": "q", "icon": None},
        ]

    monkeypatch.setattr(FakeHegel, "favorites", favorites)
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio("r10"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Radio 10"
    await _choose(hass, "Qmusic")
    # Radio 10 is still reported for a moment: the choice is kept.
    fake.push("player:player/data", _radio("r10", state="paused"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Qmusic"
    fake.push("player:player/data", _radio("q"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Qmusic"
    # The choice is gone now: a later change from outside is followed.
    fake.push("player:player/data", _radio("r10"))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "Radio 10"


async def test_chosen_station_is_dropped_when_the_amplifier_goes_off(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _choose(hass, "Qmusic")
    fake.push("powermanager:target", {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    fake.push("powermanager:target", {"type": "powerTarget", "powerTarget": {"target": "online"}})
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN


async def test_unload_cancels_the_time_out(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    await _choose(hass, "Qmusic")
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

"""Small things a Home Assistant reviewer looks for: device class, media type, pictures, limits, offline."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.hegel_connect.diagnostics import async_get_config_entry_diagnostics
from custom_components.hegel_connect.media_player import HegelMediaPlayer

from .test_event import SPOTIFY_PLAYING, _push_radio_title, _replay, _setup, stopped_at_start  # noqa: F401

ENTITY = "media_player.hegel_h150"
FIXED = "binary_sensor.hegel_h150_fixed_volume"
MAX_VOLUME = "number.hegel_h150_maximum_volume"


async def test_the_media_player_is_a_receiver(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get(ENTITY).attributes["device_class"] == "receiver"


async def test_radio_is_a_channel_with_a_station_and_other_streams_are_music(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 35, SPOTIFY_PLAYING)
    attributes = hass.states.get(ENTITY).attributes
    assert attributes["media_content_type"] == "music"
    assert "media_channel" not in attributes
    await _replay(hass, fake, 38, 43)
    await _push_radio_title(hass, fake, "Toto - Pamela")
    attributes = hass.states.get(ENTITY).attributes
    assert attributes["media_content_type"] == "channel"
    assert attributes["media_channel"] == "Qmusic"


async def test_pictures_over_plain_http_are_fetched_by_home_assistant(
    hass: HomeAssistant, fake_hegel, config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Radio logos come over http: sent straight to the browser they are blocked on an https page."""
    await _setup(hass, config_entry)
    player = next(e for e in hass.data["entity_components"]["media_player"].entities if e.entity_id == ENTITY)
    assert isinstance(player, HegelMediaPlayer)
    for url, direct in (
        ("https://cdn.example/cover.jpg", True),
        ("HTTPS://cdn.example/cover.jpg", True),
        ("http://static.example/logo.png", False),
        ("http://192.0.2.5/cover.jpg", False),
        ("https://192.0.2.5/cover.jpg", False),  # local https: the browser cannot reach it from outside
        ("https://nas.local/cover.jpg", False),
        ("https://nas/cover.jpg", False),
        (None, False),
    ):
        monkeypatch.setattr(HegelMediaPlayer, "media_image_url", url)
        assert player.media_image_remotely_accessible is direct


async def test_the_maximum_volume_follows_the_range_of_the_amplifier(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.volume_max = 60
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(MAX_VOLUME).attributes["max"] == 60
    assert float(hass.states.get(MAX_VOLUME).state) == 60  # the saved 100 does not stay above the range
    with pytest.raises(ServiceValidationError):  # Home Assistant refuses a value above the range
        await hass.services.async_call("number", "set_value", {"entity_id": MAX_VOLUME, "value": 90}, blocking=True)


async def test_hidden_inputs_have_a_start_volume_entity_too(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Unhiding an input later must not leave it without one."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, config_entry.entry_id)
        if "start_volume" in (e.translation_key or "")
    ]
    assert len(entries) == len(coordinator.sources)


async def test_fixed_volume_is_unavailable_while_the_amplifier_does_not_answer(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.data.volume_fixed = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(FIXED).state == "on"
    coordinator.connected = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(FIXED).state == "unavailable"


async def test_diagnostics_do_not_wait_for_an_amplifier_that_is_gone(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    coordinator.connected = False
    asked = len(fake_hegel[-1].calls)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert str(diag["device"]["auto_standby_choices_seconds"]).startswith("not available")
    assert len(fake_hegel[-1].calls) == asked
    for key in ("started_offline", "max_volume", "remember_volume", "fixed_inputs", "favorites_count"):
        assert key in diag
    assert "192.0.2" not in json.dumps(diag)

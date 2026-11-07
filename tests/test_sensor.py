"""Stream sensors during a track change: they show what the amplifier reports, no more and no less."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
import pytest

from .conftest import FIXTURE

QUALITY = "sensor.hegel_h150_audio_quality"
BITRATE = "sensor.hegel_h150_bitrate"
SERVICE = "sensor.hegel_h150_streaming_service"
CODEC = "sensor.hegel_h150_codec"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _replay(hass: HomeAssistant, fake, up_to: int, start: int = 36) -> None:
    """Replay the recorded session (a switch from Spotify to a radio station) event by event."""
    for index in range(start, up_to + 1):
        event = FIXTURE["events"][index]["e"]
        if event.get("path") == "player:player/data":
            fake.push(event["path"], event["itemValue"])
    await hass.async_block_till_done()


async def test_values_show_while_the_amplifier_is_still_switching(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """Recorded: quality and bitrate arrive at event 41, a second before the player says "playing"."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 39)
    assert FIXTURE["events"][39]["e"]["itemValue"]["state"] == "transitioning"
    assert hass.states.get(SERVICE).state == "airable Radio"  # reported from the first event of the switch
    await _replay(hass, fake, 41, start=40)
    assert FIXTURE["events"][41]["e"]["itemValue"]["state"] == "transitioning"
    assert hass.states.get(QUALITY).state == "lossy"
    assert hass.states.get(BITRATE).state == "128"


async def test_values_that_are_not_reported_yet_stay_empty(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Nothing is made up: the codec is only known once the amplifier reports it."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 41)
    assert hass.states.get(CODEC).state == "unknown"
    await _replay(hass, fake, 43, start=42)
    assert hass.states.get(CODEC).state != "unknown"


@pytest.mark.parametrize("sensor", [QUALITY, BITRATE, SERVICE, CODEC])
async def test_sensors_are_empty_when_nothing_plays(hass: HomeAssistant, fake_hegel, config_entry, sensor: str) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 43)
    stopped = next(i for i in range(44, 56) if FIXTURE["events"][i]["e"].get("itemValue", {}).get("state") == "stopped")
    await _replay(hass, fake, stopped, start=44)
    assert hass.states.get(sensor).state == "unknown"

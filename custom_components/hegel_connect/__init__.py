"""Hegel Connect: local push integration for Hegel H150, H400 and H600.

Unofficial; not affiliated with Hegel Music Systems AS.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HegelClient
from .coordinator import HegelCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.MEDIA_PLAYER]

type HegelConfigEntry = ConfigEntry[HegelCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Set up an amplifier from a config entry."""
    client = HegelClient(entry.data[CONF_HOST], async_get_clientsession(hass))
    coordinator = HegelCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, coordinator.async_listen(), f"hegel_connect_listen_{entry.entry_id}")
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Unload; the background listener is cancelled automatically."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: HegelConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

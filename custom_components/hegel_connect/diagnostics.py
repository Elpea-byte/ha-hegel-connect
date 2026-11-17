"""Diagnostics: shareable in issue reports (no IP address or device ids)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HegelConfigEntry
from .api import HegelError

# Host, device ids and every URL/URI (stream and artwork links can point to a
# NAS or other device on the local network).
TO_REDACT = {
    CONF_HOST,
    "systemMemberId",
    "contentPlayContextPath",
    "data",
    "context",
    "uri",
    "url",
    "icon",
    "albumArtUri",
    "albumArtURI",
    "albumCoverUri",
    "path",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: HegelConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    state = coordinator.data
    # What a model report needs to see: what the amplifier offers and what Home Assistant makes of it.
    # Only settings and capabilities, nothing that identifies the amplifier or its owner.
    try:
        idle_choices: list[int] | str = await coordinator.client.idle_time_options()
    except HegelError as err:
        idle_choices = f"not available: {err}"
    registry = er.async_get(hass)
    player = next(
        (e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if e.domain == "media_player"),
        None,
    )
    player_state = hass.states.get(player.entity_id) if player else None
    return {
        "device": {
            "model": entry.data.get("model"),
            "firmware": coordinator.firmware,
            "volume_range_max": coordinator.volume_max,
            "auto_standby_choices_seconds": idle_choices,
            "media_player_supported_features": player_state.attributes.get("supported_features")
            if player_state
            else None,
        },
        "entry": {"config": async_redact_data(dict(entry.data), TO_REDACT), "options": dict(entry.options)},
        "connected": coordinator.connected,
        "volume_max": coordinator.volume_max,
        "sources": [asdict(source) for source in coordinator.sources],
        "state": None
        if state is None
        else async_redact_data(
            {
                "power": state.power,
                "volume": state.volume,
                "muted": state.muted,
                "source_index": state.source_index,
                "volume_fixed": state.volume_fixed,
                "player": state.player.raw,
            },
            TO_REDACT,
        ),
    }

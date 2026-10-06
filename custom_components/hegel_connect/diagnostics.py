"""Diagnostics: shareable in issue reports (no IP address or device ids)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import HegelConfigEntry

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
    return {
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

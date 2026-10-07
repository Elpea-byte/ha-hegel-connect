"""Push-driven coordinator: one long-poll connection per amplifier."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NETWORK_SOURCE_NAME,
    PATH_PLAYER,
    PATH_SOURCE,
    HegelClient,
    HegelConnectionError,
    HegelError,
    HegelQueueLost,
    HegelSource,
    HegelState,
)
from .const import (
    BACKOFF_MAX,
    BACKOFF_START,
    CACHE_KEY,
    CONF_HIDDEN_SOURCES,
    CONF_SOURCE_NAMES,
    DEFAULT_MAX_VOLUME,
    DOMAIN,
    FAVORITES_INTERVAL,
    POLL_TIMEOUT,
    POWER_ON_WAIT,
    SOURCE_ATTEMPTS,
    SOURCE_VERIFY_WAIT,
)

_LOGGER = logging.getLogger(__name__)


def queue_lost_delay(lost: int) -> float:
    """Wait before subscribing again after the event queue was lost ``lost`` times in a row.

    The first time at once (normal after a reboot of the amplifier), then
    BACKOFF_START, doubling up to BACKOFF_MAX.
    """
    if lost <= 1:
        return 0
    return float(min(BACKOFF_START * 2 ** (lost - 2), BACKOFF_MAX))


class HegelCoordinator(DataUpdateCoordinator[HegelState]):
    """Keeps the amplifier state up to date via the event queue (no polling)."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: HegelClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=None,  # push, see async_listen
        )
        self.client = client
        self.sources: list[HegelSource] = []
        self.volume_max = 100
        self.firmware: str | None = None
        self.started_offline = False
        self.favorites: list[dict[str, str | None]] = []
        # Volume ceiling, set by the "Maximum volume" number entity.
        self.max_volume = DEFAULT_MAX_VOLUME
        self.connected = False

    async def _async_setup(self) -> None:
        """Read the static facts; fall back to the copy saved at the last start.

        Off at the mains (e.g. a power strip switched off at night) while Home
        Assistant starts: set up from the saved copy, show the amplifier as off
        and let the listener connect as soon as it is back.
        """
        try:
            self.sources = await self.client.sources()
            self.volume_max = await self.client.volume_max()
            self.firmware = await self.client.firmware()
        except HegelConnectionError as err:
            if not self._load_cache():
                raise UpdateFailed(str(err)) from err
            _LOGGER.info("Hegel at %s not reachable; starting from saved data", self.client.host)
        except HegelError as err:
            raise UpdateFailed(str(err)) from err
        else:
            self._save_cache()
            await self.async_refresh_favorites()
        # Also when started offline: the favorites are then read on connecting
        # (async_listen) and refreshed by this timer like normal.
        self.config_entry.async_on_unload(
            async_track_time_interval(self.hass, self._async_favorites_tick, FAVORITES_INTERVAL)
        )

    async def _async_favorites_tick(self, _now: datetime) -> None:
        """Periodic favorites refresh (only while connected; offline is skipped)."""
        if self.connected:
            await self.async_refresh_favorites()

    async def async_refresh_favorites(self) -> None:
        """Re-read the radio favorites (they change only in the Hegel Control app)."""
        try:
            favorites = await self.client.favorites()
        except HegelError as err:
            _LOGGER.debug("Radio favorites not available: %s", err)
            return
        if favorites != self.favorites:
            self.favorites = favorites
            if self.data is not None:
                self.async_update_listeners()

    def _save_cache(self) -> None:
        cache = {
            "sources": [[s.index, s.name] for s in self.sources],
            "volume_max": self.volume_max,
            "firmware": self.firmware,
        }
        entry = self.config_entry
        if entry.data.get(CACHE_KEY) != cache:
            self.hass.config_entries.async_update_entry(entry, data={**entry.data, CACHE_KEY: cache})

    def _load_cache(self) -> bool:
        cache = self.config_entry.data.get(CACHE_KEY)
        if not cache or not cache.get("sources"):
            return False
        self.sources = [HegelSource(int(i), str(n)) for i, n in cache["sources"]]
        self.volume_max = int(cache.get("volume_max") or 100)
        self.firmware = cache.get("firmware")
        self.started_offline = True
        return True

    async def _async_update_data(self) -> HegelState:
        try:
            return self._carry_over(await self.client.fetch_state())
        except HegelConnectionError as err:
            if self.started_offline or self.data is not None:
                # Not reachable: shown as off (connected stays False), not unavailable.
                return self.data or HegelState()
            raise UpdateFailed(str(err)) from err
        except HegelError as err:
            raise UpdateFailed(str(err)) from err

    def _carry_over(self, state: HegelState) -> HegelState:
        """Keep what a fresh read cannot know (the last streaming service)."""
        if self.data is not None and not state.last_service:
            state.last_service = self.data.last_service
        return state

    # ------------------------------------------------------------------ push

    async def _wait(self, delay: float) -> None:
        """Wait between listener attempts (own method, so tests can patch it per coordinator)."""
        await asyncio.sleep(delay)

    async def async_listen(self) -> None:
        """Run forever: subscribe, wait for events, reconnect with backoff."""
        backoff = BACKOFF_START
        lost = 0
        while True:
            try:
                queue_id = await self.client.subscribe()
                state = self._carry_over(await self.client.fetch_state())
                if not self.connected:
                    _LOGGER.info("Connected to Hegel at %s", self.client.host)
                    if not self.favorites:
                        self.hass.async_create_task(self.async_refresh_favorites())
                self.connected = True
                backoff = BACKOFF_START
                self.async_set_updated_data(state)
                while True:
                    started = time.monotonic()
                    events = await self.client.poll(queue_id, POLL_TIMEOUT)
                    # Only a poll that worked counts as "queue is fine again"
                    # (subscribe can succeed while every poll fails).
                    lost = 0
                    if events:
                        self._apply(events)
                    elif time.monotonic() - started < 1:
                        await self._wait(2)  # never spin if the device answers at once
            except asyncio.CancelledError:
                raise
            except HegelQueueLost:
                # Normal after a reboot of the amplifier: subscribe again at once.
                # If it keeps happening (e.g. HTTP 500 on every poll), back off.
                lost += 1
                _LOGGER.debug("Event queue lost on %s (%s), subscribing again", self.client.host, lost)
                if delay := queue_lost_delay(lost):
                    await self._wait(delay)
                continue
            except HegelError as err:
                await self._async_connection_lost(str(err))
                await self._wait(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
            except Exception:
                # Safety net: an unexpected answer must never stop push updates
                # until a restart. Log it, then reconnect like a lost connection.
                _LOGGER.exception("Unexpected error in the Hegel listener for %s", self.client.host)
                await self._async_connection_lost("unexpected error")
                await self._wait(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)

    async def _async_connection_lost(self, reason: str) -> None:
        """Show the amplifier as off (not unavailable) until it answers again."""
        if self.connected:
            _LOGGER.warning("Lost connection to Hegel at %s: %s", self.client.host, reason)
            # Not unavailable: the media player shows off and the network
            # sensor off (switched off at the mains, unplugged, network down).
            self.connected = False
            self.async_update_listeners()

    def _apply(self, events: list[dict[str, Any]]) -> None:
        state = self.data or HegelState()
        was_on = state.is_on
        changed = False
        player_changed = False
        for event in events:
            path = event.get("path")
            if isinstance(path, str) and "itemValue" in event:
                try:
                    applied = state.apply_event(path, event["itemValue"])
                except (TypeError, ValueError, AttributeError, KeyError) as err:
                    _LOGGER.debug("Ignoring event %s: %s", path, err)
                    continue
                changed |= applied
                player_changed |= applied and path == PATH_PLAYER
        if player_changed and state.is_on:
            if state.player.duration:
                self.hass.async_create_task(self._async_update_position())
            else:
                state.set_play_time(None)
        if not was_on and state.is_on:
            # Just switched on: read everything once (player data was invalid in standby).
            self.hass.async_create_task(self.async_request_refresh())
        if changed:
            self.async_set_updated_data(state)

    async def _async_update_position(self) -> None:
        """Read the playback position once (it is not pushed)."""
        try:
            value = await self.client.play_time()
        except HegelError as err:
            _LOGGER.debug("Play time not available: %s", err)
            return
        if self.data is not None:
            self.data.set_play_time(value)
            self.async_set_updated_data(self.data)

    # -------------------------------------------------------------- commands

    def source_name(self, index: int | None) -> str | None:
        """The amplifier's own name of the input with this index (None if unknown)."""
        return next((s.name for s in self.sources if s.index == index), None)

    # Inputs as shown to the user (options: own names, hidden inputs). Logic such
    # as "is this the network input" keeps using source_name().

    def source_label(self, index: int | None) -> str | None:
        """Name shown for an input: the user's own name if set, else the amplifier's."""
        names = self.config_entry.options.get(CONF_SOURCE_NAMES) or {}
        return names.get(str(index)) or self.source_name(index)

    @property
    def visible_sources(self) -> list[HegelSource]:
        """Inputs that are not hidden in the options, in the amplifier's order."""
        hidden = set(self.config_entry.options.get(CONF_HIDDEN_SOURCES) or [])
        return [s for s in self.sources if str(s.index) not in hidden]

    def source_name_for(self, label: str) -> str | None:
        """Amplifier name for a shown name; the amplifier's own name is accepted too
        (so scripts that use "Network" keep working after a rename)."""
        for source in self.sources:
            if self.source_label(source.index) == label:
                return source.name
        return label if any(s.name == label for s in self.sources) else None

    async def async_wait_for(self, check: Callable[[HegelState], bool], timeout: float) -> bool:
        """Wait until ``check(state)`` is true or the timeout passes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.data is not None and check(self.data):
                return True
            await asyncio.sleep(0.25)
        return self.data is not None and check(self.data)

    async def async_select_source(self, name: str) -> None:
        """Switch input reliably.

        Seen on the H150: right after power-on the amplifier resumes its last
        network stream and jumps back to Network within a second. So: wait until
        it is on, pause a running stream when leaving Network, set the input and
        check it stuck (retry a few times).
        """
        source = next((s for s in self.sources if s.name == name), None)
        if source is None:
            raise HegelError(f"Unknown input {name}")
        if not (self.data and self.data.is_on):
            await self.client.power_on()
            await self.async_wait_for(lambda s: s.is_on, POWER_ON_WAIT)
        for _attempt in range(SOURCE_ATTEMPTS):
            state = self.data
            if (
                state is not None
                and source.name != NETWORK_SOURCE_NAME
                and self.source_name(state.source_index) == NETWORK_SOURCE_NAME
                and state.player.state in ("playing", "buffering", "transitioning")
            ):
                try:
                    await self.client.control("pause")
                except HegelError as err:
                    _LOGGER.debug("Pause before switching failed: %s", err)
                await asyncio.sleep(0.5)
            await self.client.set_source(source.index)
            await asyncio.sleep(SOURCE_VERIFY_WAIT)
            if not self.connected and self.data is not None:
                # No push right now: read the input ourselves.
                with contextlib.suppress(HegelError, TypeError, ValueError):
                    self.data.source_index = int(await self.client.get_value(PATH_SOURCE))
            if self.data is not None and self.data.source_index == source.index:
                return
        _LOGGER.warning("Hegel did not keep input %s after %s attempts", name, SOURCE_ATTEMPTS)

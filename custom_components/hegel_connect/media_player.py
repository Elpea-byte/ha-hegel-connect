"""Media player entity for Hegel Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HegelConfigEntry
from .api import PATH_AIRABLE_ROOT, PATH_PLAY_HISTORY, HegelError
from .const import CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME
from .coordinator import HegelCoordinator
from .entity import HegelEntity

MEDIA_TYPE_HEGEL = "hegel_path"
ROOT_ID = "root"
FAVORITES_ID = "favorites"

_PLAYER_STATES = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "buffering": MediaPlayerState.BUFFERING,
    "transitioning": MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HegelMediaPlayer(entry.runtime_data)])


class HegelMediaPlayer(HegelEntity, MediaPlayerEntity):
    """The amplifier and its built-in streamer."""

    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_volume_step = 0.02
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator: HegelCoordinator) -> None:
        super().__init__(coordinator, "media_player")

    # ------------------------------------------------------------------ state

    @property
    def _max_volume(self) -> int:
        """User ceiling (options) within the amplifier's own range."""
        ceiling = int(self.coordinator.config_entry.options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME))
        return max(1, min(ceiling, self.coordinator.volume_max))

    @property
    def state(self) -> MediaPlayerState | None:
        data = self.coordinator.data
        if data is None:
            return None
        if not data.is_on:
            return MediaPlayerState.OFF
        if self.coordinator.source_name(data.source_index) == "Network":
            return _PLAYER_STATES.get(data.player.state or "", MediaPlayerState.IDLE)
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        volume = self.coordinator.data.volume if self.coordinator.data else None
        return None if volume is None else volume / self.coordinator.volume_max

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.muted if self.coordinator.data else None

    @property
    def source(self) -> str | None:
        data = self.coordinator.data
        return self.coordinator.source_name(data.source_index) if data else None

    @property
    def source_list(self) -> list[str]:
        return [source.name for source in self.coordinator.sources]

    def _playing_network(self) -> bool:
        return self.source == "Network" and bool(self.coordinator.data and self.coordinator.data.is_on)

    @property
    def media_title(self) -> str | None:
        return self.coordinator.data.player.title if self._playing_network() else None

    @property
    def media_artist(self) -> str | None:
        return self.coordinator.data.player.artist if self._playing_network() else None

    @property
    def media_album_name(self) -> str | None:
        return self.coordinator.data.player.album if self._playing_network() else None

    @property
    def media_image_url(self) -> str | None:
        return self.coordinator.data.player.image_url if self._playing_network() else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "fixed_volume": data.volume_fixed,
            "service": data.player.service if self._playing_network() else None,
            "audio_format": data.player.codec if self._playing_network() else None,
            "volume_raw": data.volume,
            "max_volume": self._max_volume,
        }

    # --------------------------------------------------------------- commands

    async def _run(self, coro) -> None:
        try:
            await coro
        except HegelError as err:
            raise HomeAssistantError(f"Hegel did not accept the command: {err}") from err

    async def async_turn_on(self) -> None:
        await self._run(self.coordinator.client.power_on())

    async def async_turn_off(self) -> None:
        await self._run(self.coordinator.client.power_off())

    async def async_set_volume_level(self, volume: float) -> None:
        if self.coordinator.data and self.coordinator.data.volume_fixed:
            raise HomeAssistantError("This input uses fixed volume (home theater bypass)")
        raw = round(volume * self.coordinator.volume_max)
        await self._run(self.coordinator.client.set_volume(max(0, min(raw, self._max_volume))))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.coordinator.client.set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        await self._run(self.coordinator.async_select_source(source))

    async def async_media_play(self) -> None:
        await self._run(self.coordinator.client.control("play"))

    async def async_media_pause(self) -> None:
        await self._run(self.coordinator.client.control("pause"))

    async def async_media_next_track(self) -> None:
        await self._run(self.coordinator.client.control("next"))

    async def async_media_previous_track(self) -> None:
        await self._run(self.coordinator.client.control("previous"))

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        if media_id in (ROOT_ID, FAVORITES_ID):
            raise HomeAssistantError("Choose a station, not a folder")
        await self._run(self.coordinator.client.play_path(media_id))

    # ------------------------------------------------------------- browsing

    async def async_browse_media(
        self, media_content_type: MediaType | str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Radio favorites, internet radio (Airable) and recently played."""
        if media_content_id in (None, ROOT_ID):
            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id=ROOT_ID,
                media_content_type=MEDIA_TYPE_HEGEL,
                title=self.coordinator.config_entry.title,
                can_play=False,
                can_expand=True,
                children=[
                    _folder(FAVORITES_ID, "Radio favorites"),
                    _folder(PATH_AIRABLE_ROOT, "Internet radio"),
                    _folder(PATH_PLAY_HISTORY, "Recently played"),
                ],
            )
        path = media_content_id
        try:
            if path == FAVORITES_ID:
                path = await self._favorites_path()
            data = await self.coordinator.client.get_rows(path, 0, 100)
        except HegelError as err:
            raise BrowseError(f"Cannot browse {media_content_id}: {err}") from err
        roles = data.get("roles") or {}
        children = [child for row in data.get("rows", []) if (child := _child(row)) is not None]
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_HEGEL,
            title=roles.get("title") or "Hegel",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _favorites_path(self) -> str:
        """Find the radio favorites folder (contains a per-device Airable id)."""
        client = self.coordinator.client
        root = await client.get_rows(PATH_AIRABLE_ROOT, 0, 10)
        rows = [r for r in root.get("rows", []) if isinstance(r, dict)]
        radios = next((r.get("path") for r in rows if str(r.get("path", "")).endswith("/radios")), None)
        if radios is None:
            raise HegelError("No radio section found")
        return f"{radios}/favorites"


def _folder(content_id: str, title: str) -> BrowseMedia:
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=content_id,
        media_content_type=MEDIA_TYPE_HEGEL,
        title=title,
        can_play=False,
        can_expand=True,
    )


def _child(row: Any) -> BrowseMedia | None:
    if not isinstance(row, dict) or not row.get("path") or not row.get("title"):
        return None
    is_folder = row.get("type") == "container"
    playable = bool(row.get("containerPlayable")) or row.get("type") == "audio"
    icon = row.get("icon")
    return BrowseMedia(
        media_class=MediaClass.CHANNEL
        if row.get("audioType") == "audioBroadcast"
        else (MediaClass.DIRECTORY if is_folder else MediaClass.MUSIC),
        media_content_id=row["path"],
        media_content_type=MEDIA_TYPE_HEGEL,
        title=row["title"],
        can_play=playable,
        can_expand=is_folder and not playable,
        thumbnail=icon if isinstance(icon, str) and icon.startswith(("http://", "https://")) else None,
    )

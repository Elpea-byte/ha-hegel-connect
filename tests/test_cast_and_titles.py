"""0.8, from the H150 test: play after a Cast message, and the real title of a podcast episode.

While a Cast message (text-to-speech) plays, an H150 shows Cast's receiver ("Casting Default Media
Receiver", title "Google Cast") and stays "buffering" on it afterwards. While a podcast episode plays it
reports the title "Title Placeholder Episode ID: <number>" and no artist; the real title is only in the
episode list and, once, in the report at the change to the next episode.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from custom_components.hegel_connect.api import TRACK_TITLES_KEPT, HegelClient, HegelState, remember_title

ENTITY = "media_player.hegel_h150"
HOST = "https://0000000000.airable.io"
EPISODE = f"airable:{HOST}/id/airable/feed.episode/7"
EPISODE_ID = "airable://airable/feed.episode/7"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def _radio(media_id: str = "fav-1", state: str = "playing") -> dict[str, Any]:
    return {
        "state": state,
        "mediaRoles": {"id": media_id},
        "trackRoles": {"title": "Qmusic", "mediaData": {"metaData": {"serviceName": "Airable", "radioStation": True}}},
    }


def _cast(state: str = "buffering") -> dict[str, Any]:
    return {
        "state": state,
        "mediaRoles": {"id": "cast"},
        "trackRoles": {
            "title": "Google Cast",
            "mediaData": {"metaData": {"serviceName": "Casting Default Media Receiver"}},
        },
    }


def _episode(title: str, number: int = 7) -> dict[str, Any]:
    return {
        "state": "playing",
        "mediaRoles": {"title": "Episodes", "type": "container", "containerPlayable": True},
        "trackRoles": {
            "type": "audio",
            "title": title,
            "id": f"airable://airable/feed.episode/{number}",
            "path": f"airable:{HOST}/id/airable/feed.episode/{number}",
            "mediaData": {
                "metaData": {"serviceID": "airablePodcasts", "serviceName": "airable Podcasts", "album": "A podcast"}
            },
        },
    }


async def _play(hass: HomeAssistant) -> None:
    await hass.services.async_call(MP_DOMAIN, "media_play", {ATTR_ENTITY_ID: ENTITY}, blocking=True)


# ------------------------------------------------------------------ Cast message


async def test_play_after_a_cast_message_starts_the_radio_again(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio())
    fake.push("player:player/data", _cast("playing"))
    fake.push("player:player/data", _cast("buffering"))  # where an H150 stays after the message
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    assert coordinator.data.last_radio_id == "fav-1"
    assert coordinator.data.last_service == "Airable"
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", "airable:fav/qmusic") in fake.calls


async def test_play_after_a_cast_message_resumes_spotify(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push(
        "player:player/data",
        {"state": "playing", "trackRoles": {"title": "Song", "mediaData": {"metaData": {"serviceName": "Spotify"}}}},
    )
    fake.push("player:player/data", _cast())
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert fake.calls == [("resume_spotify",)]


async def test_something_else_buffering_still_counts_as_playing(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    """Only Cast's receiver is skipped: a station that is buffering is not started again."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _radio(state="buffering"))
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert not any(call[0] == "play_path" for call in fake.calls)


# ------------------------------------------------------------------ podcast episode titles


def test_the_placeholder_is_not_shown_as_the_title() -> None:
    state = HegelState()
    state.apply_event("player:player/data", _episode("Title Placeholder Episode ID: 123"))
    assert state.player.title is None
    assert state.player.album == "A podcast"


def test_the_real_title_seen_once_is_kept_for_that_episode() -> None:
    """At the change to the next episode an H150 sends the real title once, then the placeholder again."""
    state = HegelState()
    state.apply_event("player:player/data", _episode("Achter de schermen", 8))
    state.apply_event("player:player/data", _episode("Title Placeholder Episode ID: 8", 8))
    assert state.player.title == "Achter de schermen"
    # Another episode does not get that title.
    state.apply_event("player:player/data", _episode("Title Placeholder Episode ID: 9", 9))
    assert state.player.title is None


async def test_an_episode_started_from_its_list_shows_the_title_of_the_row() -> None:
    sent: list[dict] = []

    class _Client(HegelClient):
        def __init__(self) -> None:
            self.track_titles = {}

        async def activate(self, path: str, value: dict | None = None, **extra: Any) -> None:
            sent.append(value or {})

    client = _Client()
    row = {"type": "audio", "id": EPISODE_ID, "path": EPISODE, "title": "De dagen zijn geteld"}
    await client._play(row, {"type": "container", "containerPlayable": True}, 3)
    assert sent
    state = HegelState(track_titles=client.track_titles)
    state.apply_event("player:player/data", _episode("Title Placeholder Episode ID: 7"))
    assert state.player.title == "De dagen zijn geteld"


def test_only_the_last_titles_are_kept() -> None:
    titles: dict[str, str] = {}
    for number in range(TRACK_TITLES_KEPT + 10):
        remember_title(titles, [f"id-{number}"], f"Title {number}")
    remember_title(titles, ["id-x"], "Title Placeholder Episode ID: 1")  # never kept
    assert len(titles) == TRACK_TITLES_KEPT
    assert "id-0" not in titles
    assert "id-x" not in titles


async def test_the_media_player_and_the_event_skip_the_placeholder(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _episode("Title Placeholder Episode ID: 7"))
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY).attributes
    assert attributes.get("media_title") is None
    assert attributes.get("media_album_name") == "A podcast"


# ------------------------------------------------------------------ the last station, also through a Cast message

STATION_PATH = f"airable:{HOST}/id/airable/radio/55"


def _station(state: str = "playing") -> dict[str, Any]:
    """A station that is no favorite, with the path an H150 reports for it in mediaRoles."""
    return {
        "state": state,
        "mediaRoles": {"id": "airable://airable/radio/55", "path": STATION_PATH, "title": "Sublime"},
        "trackRoles": {"title": "Sublime", "mediaData": {"metaData": {"serviceName": "Airable", "radioStation": True}}},
    }


async def test_play_starts_any_station_again_by_the_path_it_reported(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    """Also one that Home Assistant did not start (or started before a restart, which forgets that)."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _station())
    fake.push("player:player/data", {"state": "stopped"})
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", STATION_PATH) in fake.calls


async def test_a_cast_message_whose_first_report_has_no_service_keeps_the_station(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _station())
    fake.push("player:player/data", {"state": "buffering", "trackRoles": {}})  # nothing known yet
    fake.push("player:player/data", {"state": "playing", "trackRoles": {"title": "Google Cast"}})
    fake.push("player:player/data", _cast("buffering"))
    await hass.async_block_till_done()
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", STATION_PATH) in fake.calls


async def test_a_full_read_during_a_cast_message_keeps_the_station(
    hass: HomeAssistant, fake_hegel, config_entry
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _station())
    await hass.async_block_till_done()
    fake.values["player:player/data"] = _cast("buffering")  # what a read gives during the message
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert config_entry.runtime_data.data.last_radio_path == STATION_PATH
    fake.calls.clear()
    await _play(hass)
    assert ("play_path", STATION_PATH) in fake.calls


async def test_something_else_playing_forgets_the_station(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    fake.push("player:player/data", _station())
    fake.push(
        "player:player/data",
        {"state": "playing", "mediaRoles": {"id": "song"}, "trackRoles": {"title": "Song"}},
    )
    await hass.async_block_till_done()
    data = config_entry.runtime_data.data
    assert (data.last_radio_id, data.last_radio_path) == (None, None)

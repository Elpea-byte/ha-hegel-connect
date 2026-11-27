"""Podcasts in the media browser: open a podcast, open or play its episode list, play an episode.

The rows have the shape an H150 gives (read from the amplifier, ids and the Airable host replaced).
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from custom_components.hegel_connect.api import HegelClient, HegelConnectionError, HegelError

from .conftest import FakeHegel

ENTITY = "media_player.hegel_h150"
HOST = "https://0000000000.airable.io"
PODCAST = f"airable:{HOST}/id/airable/feed/1001"
EPISODES = f"airable:{HOST}/airable/feed/1001/episodes"
SERVICE = {"metaData": {"serviceID": "airablePodcasts"}}


def _episode(number: int, title: str) -> dict[str, Any]:
    return {
        "type": "audio",
        "path": f"airable:{HOST}/id/airable/feed.episode/{number}",
        "containerType": "none",
        "id": f"airable://airable/feed.episode/{number}",
        "mediaData": {
            "metaData": {
                "contentPlayContextPath": f"airable:playContext:{HOST}/id/airable/feed.episode/{number}",
                "playbackStateChangePath": "airable:statechange",
                "serviceID": "airablePodcasts",
                "maximumRetryCount": 1,
            },
            "resources": [{"mimeType": "audio/mpeg", "uid": "0", "bitRate": 128000, "duration": 1884000}],
        },
        "title": title,
    }


@pytest.fixture(autouse=True)
def podcast_rows(fake_hegel) -> None:
    """After fake_hegel, which starts every test with an empty browse tree."""
    FakeHegel.rows = {
        PODCAST: {
            "rows": [
                {
                    "type": "container",
                    "path": EPISODES,
                    "containerPlayable": True,
                    "containerType": "none",
                    "id": "airable://airable/listing/feed.1001.episodes",
                    "mediaData": SERVICE,
                    "title": "Episodes",
                }
            ],
            "roles": {"path": PODCAST, "title": "A news podcast", "mediaData": SERVICE, "containerType": "none"},
        },
        EPISODES: {
            "rows": [_episode(1, "Monday"), _episode(2, "Tuesday")],
            "roles": {"path": EPISODES, "title": "Episodes", "mediaData": SERVICE},
        },
    }


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _browse(hass: HomeAssistant, ws, content_id: str) -> dict:
    await ws.send_json(
        {
            "id": 1 + len(content_id),
            "type": "media_player/browse_media",
            "entity_id": ENTITY,
            "media_content_id": content_id,
            "media_content_type": "hegel_path",
        }
    )
    reply = await ws.receive_json()
    assert reply["success"], reply
    return reply["result"]


async def test_a_podcast_opens_to_an_episode_list_that_opens_and_plays(
    hass: HomeAssistant, fake_hegel, config_entry, hass_ws_client
) -> None:
    await _setup(hass, config_entry)
    ws = await hass_ws_client(hass)
    podcast = await _browse(hass, ws, PODCAST)
    assert podcast["title"] == "A news podcast"
    assert (podcast["media_class"], podcast["can_play"]) == ("podcast", False)
    episodes = podcast["children"][0]
    assert episodes["title"] == "Episodes"
    # Before 0.8 a playable folder could not be opened, so no single episode could be picked.
    assert episodes["can_expand"] and episodes["can_play"]


async def test_episodes_are_episodes_that_play(hass: HomeAssistant, fake_hegel, config_entry, hass_ws_client) -> None:
    await _setup(hass, config_entry)
    ws = await hass_ws_client(hass)
    listing = await _browse(hass, ws, EPISODES)
    # Opened, the list still plays as a whole (its play button), as it does one level up.
    assert (listing["media_class"], listing["can_play"], listing["can_expand"]) == ("directory", True, True)
    assert [(c["title"], c["media_class"], c["can_play"], c["can_expand"]) for c in listing["children"]] == [
        ("Monday", "episode", True, False),
        ("Tuesday", "episode", True, False),
    ]


async def test_an_episode_plays_as_an_item_of_its_list(
    hass: HomeAssistant, fake_hegel, config_entry, hass_ws_client
) -> None:
    """The amplifier refuses to open an episode on its own path; in its list it plays (and goes on)."""
    await _setup(hass, config_entry)
    ws = await hass_ws_client(hass)
    tuesday = (await _browse(hass, ws, EPISODES))["children"][1]
    assert tuesday["media_content_id"] == f"track:1:{EPISODES}"
    await hass.services.async_call(
        "media_player",
        "play_media",
        {"entity_id": ENTITY, "media_content_type": "hegel_path", "media_content_id": tuesday["media_content_id"]},
        blocking=True,
    )
    assert ("play_in_container", EPISODES, 1) in fake_hegel[-1].calls


class _Episodes(HegelClient):
    """The answers of an H150 for one episode: getData calls it a container, getRows on it fails."""

    def __init__(self, item: dict[str, Any], rows_error: HegelError) -> None:
        self.item = item
        self.rows_error = rows_error
        self.sent: list[dict[str, Any]] = []
        self.track_titles: dict[str, str] = {}

    async def get_raw(self, path: str, roles: str = "@all") -> Any:
        return self.item

    async def get_rows(self, path: str, start: int = 0, count: int = 50) -> dict[str, Any]:
        raise self.rows_error

    async def activate(self, path: str, value: dict[str, Any] | None = None, **extra: Any) -> None:
        self.sent.append(value or {})


def _episode_as_get_data() -> dict[str, Any]:
    item = _episode(3, "Wednesday")
    item["type"] = "container"  # what getData says for an episode
    item["mediaData"]["resources"][0]["data"] = f"{HOST}/airable/play/feed.episode/3/0"
    return item


async def test_the_client_plays_an_episode_path_on_its_own() -> None:
    """play_media with an episode path (a script, a saved path) plays that one episode."""
    client = _Episodes(_episode_as_get_data(), HegelError('getRows 500: {"error": "Error during communication"}'))
    await client.play_path(_episode_as_get_data()["path"])
    [sent] = client.sent
    assert sent["control"] == "play"
    assert sent["trackRoles"]["type"] == "audio"
    assert sent["trackRoles"]["title"] == "Wednesday"
    assert sent["type"] is None  # on its own, not as part of a list


async def test_a_real_folder_that_fails_still_fails() -> None:
    """Only an item with its own audio is played on its own; an empty folder keeps its error."""
    folder = {"type": "container", "path": "airable:x/folder", "title": "Folder"}
    client = _Episodes(folder, HegelError("getRows 500"))
    with pytest.raises(HegelError, match="getRows 500"):
        await client.play_path("airable:x/folder")
    assert client.sent == []


async def test_no_answer_is_not_mistaken_for_an_episode() -> None:
    client = _Episodes(_episode_as_get_data(), HegelConnectionError("no answer (TimeoutError)"))
    with pytest.raises(HegelConnectionError):
        await client.play_path("airable:x/episode")
    assert client.sent == []


async def test_playing_an_episode_sends_its_path(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    episode = f"airable:{HOST}/id/airable/feed.episode/2"
    await hass.services.async_call(
        "media_player",
        "play_media",
        {"entity_id": ENTITY, "media_content_type": "hegel_path", "media_content_id": episode},
        blocking=True,
    )
    fake = fake_hegel[-1]
    assert ("play_path", episode) in fake.calls
    # The episode plays (no radio station): it is not kept as a station to restart, so a station started
    # later from the Hegel app is not mistaken for it.
    fake.push(
        "player:player/data",
        {"state": "playing", "mediaRoles": {"id": "ep-2"}, "trackRoles": {"title": "Tuesday"}},
    )
    fake.push(
        "player:player/data",
        {
            "state": "playing",
            "mediaRoles": {"id": "station-9"},
            "trackRoles": {"title": "Other", "mediaData": {"metaData": {"radioStation": True}}},
        },
    )
    await hass.async_block_till_done()
    assert config_entry.runtime_data.radio_paths == {}


async def test_radio_stations_still_play_without_opening(
    hass: HomeAssistant, fake_hegel, config_entry, hass_ws_client
) -> None:
    """The podcast rule does not touch stations: a station is a playable folder that does not open."""
    station = {
        "title": "Qmusic",
        "type": "container",
        "containerPlayable": True,
        "audioType": "audioBroadcast",
        "path": f"airable:{HOST}/id/airable/radio/5",
        "id": "airable://airable/radio/5",
    }
    folder = f"airable:{HOST}/airable/radios/popular"
    FakeHegel.rows[folder] = {"rows": [station], "roles": {"title": "Popular stations"}}
    await _setup(hass, config_entry)
    ws = await hass_ws_client(hass)
    child = (await _browse(hass, ws, folder))["children"][0]
    assert (child["media_class"], child["can_play"], child["can_expand"]) == ("channel", True, False)

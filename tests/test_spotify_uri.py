"""Spotify tracks are recognisable: the amplifier reports ids (no media id), Hegel Connect gives URIs."""

from __future__ import annotations

import copy

from homeassistant.core import HomeAssistant
import pytest

from custom_components.hegel_connect.api import PlayerData

from .conftest import FIXTURE
from .test_event import (
    RADIO_PLAYING,
    SPOTIFY_PLAYING,
    _replay,
    _setup,
    fired,  # noqa: F401  (pytest fixture, imported for use here)
    stopped_at_start,  # noqa: F401  (autouse fixture of the event tests)
)

ID = "1wceODcNiRPq4kwo9vh3oE"
PLAYER = "media_player.hegel_h150"


def _player(service_id: str = "spotify", **meta: str) -> PlayerData:
    return PlayerData(
        {"state": "playing", "trackRoles": {"title": "T", "mediaData": {"metaData": {"serviceID": service_id, **meta}}}}
    )


@pytest.mark.parametrize(
    "value",
    [
        f"spotify:track:{ID}",
        ID,
        f"  spotify:track:{ID} ",
        f"https://open.spotify.com/track/{ID}",
        f"https://open.spotify.com/intl-nl/track/{ID}?si=abc",
    ],
)
def test_the_track_id_becomes_a_spotify_uri(value: str) -> None:
    assert _player(trackId=value).spotify_track_uri == f"spotify:track:{ID}"


@pytest.mark.parametrize(
    "value",
    [None, "", "spotify:album:" + ID, "spotify:track:short", "not an id at all", 42, ID + "x", f"spotify:track:{ID}:x"],
)
def test_anything_else_gives_no_uri(value: object) -> None:
    assert _player(trackId=value).spotify_track_uri is None  # type: ignore[arg-type]


def test_album_and_artist_uris() -> None:
    player = _player(albumId=f"spotify:album:{ID}", artistId=f"spotify:artist:{ID}")
    assert player.spotify_album_uri == f"spotify:album:{ID}"
    assert player.spotify_artist_uri == f"spotify:artist:{ID}"
    assert player.spotify_track_uri is None  # no track id reported


def test_the_playlist_it_plays_from() -> None:
    assert _player(playbackSourceId=f"spotify:playlist:{ID}").spotify_playlist_uri == f"spotify:playlist:{ID}"
    # Playing from an album or an artist is not a playlist.
    assert _player(playbackSourceId=f"spotify:album:{ID}").spotify_playlist_uri is None
    assert _player(playbackSourceId=f"spotify:artist:{ID}").spotify_playlist_uri is None
    assert _player(service_id="tidal", playbackSourceId=f"spotify:playlist:{ID}").spotify_playlist_uri is None


def test_only_for_spotify() -> None:
    """Another service that happens to report a trackId is not Spotify."""
    assert _player(service_id="tidal", trackId=ID).spotify_track_uri is None
    assert _player(service_id="", trackId=ID).spotify_track_uri is None
    assert _player(service_id="Spotify", trackId=ID).spotify_track_uri == f"spotify:track:{ID}"


async def test_the_recorded_spotify_track_has_its_uris(hass: HomeAssistant, fake_hegel, config_entry, fired) -> None:  # noqa: F811
    await _setup(hass, config_entry)
    await _replay(hass, fake_hegel[-1], 35, SPOTIFY_PLAYING)
    event = fired[0]
    assert event["spotify_uri"] == f"spotify:track:{ID}"
    assert event["spotify_album_uri"].startswith("spotify:album:")
    assert event["spotify_artist_uri"].startswith("spotify:artist:")
    assert event["spotify_playlist_uri"].startswith("spotify:playlist:")  # the recorded track plays from a playlist
    assert hass.states.get(PLAYER).attributes["media_content_id"] == f"spotify:track:{ID}"


async def test_radio_has_no_spotify_uris_and_keeps_its_media_id(
    hass: HomeAssistant,
    fake_hegel,
    config_entry,
    fired,  # noqa: F811
) -> None:
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    await _replay(hass, fake, 35, SPOTIFY_PLAYING)
    await _replay(hass, fake, 38, 43)
    value = copy.deepcopy(FIXTURE["events"][RADIO_PLAYING]["e"]["itemValue"])
    (value.get("playLogicData", value))["trackRoles"]["title"] = "Carole King - You've Got A Friend"
    fake.push("player:player/data", value)
    await hass.async_block_till_done()
    radio = fired[-1]
    assert radio["is_radio"] is True
    assert (
        radio["spotify_uri"],
        radio["spotify_album_uri"],
        radio["spotify_artist_uri"],
        radio["spotify_playlist_uri"],
    ) == (
        None,
        None,
        None,
        None,
    )
    state = hass.states.get(PLAYER)
    assert state.attributes.get("media_content_id") is None
    assert state.attributes["media_id"]  # the radio station id, as before


async def test_two_versions_with_the_same_title_are_two_tracks(
    hass: HomeAssistant,
    fake_hegel,
    config_entry,
    fired,  # noqa: F811
) -> None:
    """Same title, artist, album and service, another track id (a remaster or a re-release): two events."""
    await _setup(hass, config_entry)
    fake = fake_hegel[-1]
    for track_id in (ID, "2abcdefghijklmnopqrstu"):
        value = copy.deepcopy(FIXTURE["events"][SPOTIFY_PLAYING]["e"]["itemValue"])
        data = value.get("playLogicData", value)
        data["trackRoles"]["mediaData"]["metaData"]["trackId"] = f"spotify:track:{track_id}"
        fake.push("player:player/data", value)
        await hass.async_block_till_done()
    assert [e["spotify_uri"] for e in fired] == [f"spotify:track:{ID}", "spotify:track:2abcdefghijklmnopqrstu"]

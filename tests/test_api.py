"""Parsing tests for the API client, using a real H150 recording."""

from __future__ import annotations

import json
from pathlib import Path

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from custom_components.hegel_connect.api import (
    EVENT_PATHS,
    MAX_RESPONSE,
    PATH_PLAY_MODE,
    READ_CHUNK,
    HegelClient,
    HegelConnectionError,
    HegelError,
    HegelQueueLost,
    HegelState,
    PlayerData,
    _finite_float,
    _reject_constant,
    play_mode_parts,
    play_request,
    unwrap,
    url_host,
)

from .conftest import FIXTURE, snapshot_value


def test_unwrap_typed_values() -> None:
    assert unwrap({"type": "i32_", "i32_": 5}) == 5
    assert unwrap({"type": "bool_", "bool_": True}) is True
    assert unwrap([{"type": "string_", "string_": "H150"}]) == "H150"
    assert unwrap({"state": "playing"}) == {"state": "playing"}


def test_snapshot_state() -> None:
    state = HegelState()
    for path in EVENT_PATHS:
        state.apply_event(path, snapshot_value(path))
    assert state.is_on
    assert state.play_mode == "normal"
    assert state.volume == 17
    assert state.muted is False
    assert state.source_index == 9
    assert state.volume_fixed is False
    assert state.player.title == "Marido Dansa"
    assert state.player.artist == "Franky Rizardo"
    assert state.player.playback_source == "New Dance 2026"
    assert state.player.image_url.startswith("https://")


def test_play_mode_event() -> None:
    state = HegelState()
    assert state.play_mode is None
    assert state.apply_event(PATH_PLAY_MODE, {"type": "playerPlayMode", "playerPlayMode": "shuffleRepeatAll"})
    assert state.play_mode == "shuffleRepeatAll"
    assert play_mode_parts(state.play_mode) == (True, "all")
    assert play_mode_parts(None) == (False, "off")
    assert play_mode_parts("somethingNew") == (False, "off")


def test_next_track_starts_at_zero() -> None:
    state = HegelState()
    track = {"state": "playing", "status": {"duration": 180000}, "trackRoles": {"title": "One"}}
    state.apply_event("player:player/data", track)
    state.set_play_time(179000)
    assert state.position == 179
    state.apply_event("player:player/data", {**track, "trackRoles": {"title": "Two"}})
    assert state.position == 0
    state.set_play_time(5000)
    state.apply_event("player:player/data", {**track, "trackRoles": {"title": "Two"}, "state": "paused"})
    assert state.position == 5  # same track: position kept


def test_replay_recorded_events() -> None:
    state = HegelState()
    seen_states = set()
    for item in FIXTURE["events"]:
        event = item["e"]
        state.apply_event(event["path"], event["itemValue"])
        if event["path"] == "player:player/data":
            seen_states.add(state.player.state)
    assert {"playing", "paused", "stopped"} <= seen_states
    assert state.power == "online"
    assert state.source_index == 9


def test_radio_has_no_skip() -> None:
    radio = next(
        e["e"]["itemValue"]
        for e in FIXTURE["events"]
        if e["e"]["path"] == "player:player/data"
        and "radioStation" in json.dumps(e["e"]["itemValue"])
        and e["e"]["itemValue"].get("state") == "playing"
    )
    player = PlayerData(radio)
    assert player.is_radio
    assert player.title == "Qmusic"
    assert player.control_allowed("next_") is False


def test_fixed_volume_inputs() -> None:
    state = HegelState()
    state.apply_event("settings:/hegel/volumeType", {"type": "i32_", "i32_": 1})
    assert state.volume_fixed is True


def test_missing_control_flag_means_not_allowed() -> None:
    """Spotify reports only {"pause": true}; next/previous are then refused."""
    player = PlayerData({"controls": {"pause": True}, "state": "playing"})
    assert player.control_allowed("pause") is True
    assert player.control_allowed("next_") is False
    assert player.control_allowed("previous") is False
    assert PlayerData({"controls": {"next_": True, "previous": True}}).control_allowed("next_") is True


def _radio_playing() -> dict:
    """The last radio event: by then the stream format is complete."""
    return [
        e["e"]["itemValue"]
        for e in FIXTURE["events"]
        if e["e"]["path"] == "player:player/data"
        and "radioStation" in json.dumps(e["e"]["itemValue"])
        and e["e"]["itemValue"].get("state") == "playing"
    ][-1]


def test_stream_format_internet_radio() -> None:
    """MP3 16-bit/48 kHz radio is lossy, not CD quality."""
    player = PlayerData(_radio_playing())
    assert player.quality == "lossy"
    assert player.short_codec == "MP3"
    assert player.sample_rate == 48.0
    assert player.bit_depth == 16
    assert player.bitrate == 128
    assert player.duration is None


def test_stream_format_spotify_and_lossless() -> None:
    spotify = {
        "trackRoles": {
            "mediaData": {"activeResource": {"mimeType": "audio/unknown", "quality": {"spotifyHifi": False}}}
        }
    }
    assert PlayerData(spotify).quality == "lossy"
    spotify["trackRoles"]["mediaData"]["activeResource"]["quality"]["spotifyHifi"] = True
    assert PlayerData(spotify).quality == "lossless"

    def flac(bits: int, rate: int) -> PlayerData:
        resource = {"shortCodec": "FLAC", "bitsPerSample": bits, "sampleFrequency": rate}
        return PlayerData({"trackRoles": {"mediaData": {"activeResource": resource}}})

    assert flac(16, 44100).quality == "cd"
    assert flac(24, 96000).quality == "hi_res"
    assert PlayerData({}).quality is None


def test_duration_from_status() -> None:
    assert PlayerData({"status": {"duration": 154153}}).duration == 154
    assert PlayerData({"status": {"duration": 0}}).duration is None


def test_stream_format_airplay_badging() -> None:
    """AirPlay sends its own label (as shown by the amplifier's web client)."""

    def airplay(badge: str) -> PlayerData:
        resource = {"quality": {"airplayBadging": badge}}
        return PlayerData({"trackRoles": {"mediaData": {"activeResource": resource}}})

    assert airplay("Hi-Res Lossless").quality == "hi_res"
    assert airplay("Lossless").quality == "lossless"
    assert airplay("Lossless").short_codec == "Lossless"


def test_play_request_keeps_album_together() -> None:
    album = {"type": "container", "containerPlayable": True, "path": "upnp:/a"}
    track = {"type": "audio", "path": "upnp:/t"}
    station = {"type": "audio", "audioType": "audioBroadcast", "path": "airable:/s"}
    assert play_request(track, album, 3) == {
        "control": "play",
        "mediaRoles": album,
        "trackRoles": track,
        "type": "itemInContainer",
        "index": 3,
    }
    assert play_request(station, album, 0)["type"] is None
    assert play_request(track, None, 0)["mediaRoles"] is track


def test_url_host_brackets_ipv6() -> None:
    assert url_host("192.0.2.10") == "192.0.2.10"
    assert url_host("h150.local") == "h150.local"
    assert url_host("2001:db8::10") == "[2001:db8::10]"
    assert url_host("fe80::1%eth0") == "[fe80::1%25eth0]"


class _FakeResponse:
    """Just enough of aiohttp's ClientResponse for HegelClient._request."""

    def __init__(self, status: int, chunks: list[bytes], charset: str | None = "utf-8") -> None:
        self.status = status
        self.charset = charset
        self.read_chunks = 0
        self._chunks = chunks
        self.content = self

    async def iter_chunked(self, size: int):
        for chunk in self._chunks:
            self.read_chunks += 1
            yield chunk


class _FakeSession:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    def request(self, *args, **kwargs):
        response = self._response

        class _Context:
            async def __aenter__(self_inner):
                if isinstance(response, Exception):
                    raise response
                return response

            async def __aexit__(self_inner, *exc):
                return False

        return _Context()


async def _ask(response: _FakeResponse | Exception, endpoint: str = "getData"):
    client = HegelClient("192.0.2.10", _FakeSession(response))  # type: ignore[arg-type]
    return await client._request("GET", endpoint)


async def test_request_parses_json_in_chunks() -> None:
    body = json.dumps({"value": "café"}).encode()
    result = await _ask(_FakeResponse(200, [body[:5], body[5:]]))
    assert result == {"value": "café"}


async def test_request_empty_body_is_none() -> None:
    assert await _ask(_FakeResponse(200, [])) is None


async def test_request_invalid_json_is_an_error() -> None:
    with pytest.raises(HegelError, match="invalid JSON"):
        await _ask(_FakeResponse(200, [b"<html>"]))


async def test_request_error_text_is_cut_at_200() -> None:
    with pytest.raises(HegelError) as err:
        await _ask(_FakeResponse(500, [b"x" * 500]))
    assert str(err.value) == "getData 500: " + "x" * 200


async def test_request_lost_queue_has_its_own_error() -> None:
    with pytest.raises(HegelQueueLost):
        await _ask(_FakeResponse(500, [b"gone"]), endpoint="event/pollQueue")


async def test_request_unknown_charset_and_bad_bytes_are_tolerated() -> None:
    assert await _ask(_FakeResponse(200, [b'{"a": 1}'], charset="no-such-charset")) == {"a": 1}
    with pytest.raises(HegelError, match="invalid JSON"):
        await _ask(_FakeResponse(200, [bytes([0xFF, 0xFE])]))


async def test_request_connection_problem_is_a_connection_error() -> None:
    with pytest.raises(HegelConnectionError):
        await _ask(TimeoutError())


async def test_request_too_large_is_refused_and_stops_reading() -> None:
    chunks = [b"0" * READ_CHUNK] * (MAX_RESPONSE // READ_CHUNK + 50)
    response = _FakeResponse(200, chunks)
    with pytest.raises(HegelError, match="response too large"):
        await _ask(response)
    assert response.read_chunks == MAX_RESPONSE // READ_CHUNK + 1  # not read to the end
    # Also for an error answer: nothing of it is used.
    with pytest.raises(HegelError, match="response too large"):
        await _ask(_FakeResponse(500, chunks))


async def test_request_exactly_at_the_limit_is_accepted() -> None:
    body = b'"' + b"0" * (MAX_RESPONSE - 2) + b'"'
    assert len(body) == MAX_RESPONSE
    chunks = [body[i : i + READ_CHUNK] for i in range(0, len(body), READ_CHUNK)]
    assert len(await _ask(_FakeResponse(200, chunks))) == MAX_RESPONSE - 2


@pytest.mark.usefixtures("socket_enabled")
async def test_request_against_a_real_http_server() -> None:
    """The same reading code on real aiohttp (own server on localhost): normal, empty and runaway answers."""

    async def small(request: web.Request) -> web.Response:
        return web.json_response({"value": "café"})

    async def empty(request: web.Request) -> web.Response:
        return web.Response(status=200)

    async def runaway(request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse()
        await resp.prepare(request)
        try:
            for _ in range(MAX_RESPONSE // READ_CHUNK + 50):
                await resp.write(b"0" * READ_CHUNK)
        except ConnectionError:  # the client hung up, as it should
            pass
        return resp

    app = web.Application()
    app.router.add_get("/api/small", small)
    app.router.add_get("/api/empty", empty)
    app.router.add_get("/api/runaway", runaway)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        client = HegelClient(f"{server.host}:{server.port}", session)
        assert await client._request("GET", "small") == {"value": "café"}
        assert await client._request("GET", "empty") is None
        with pytest.raises(HegelError, match="response too large"):
            await client._request("GET", "runaway")


@pytest.mark.parametrize(
    "body", [b'{"a": 1e999}', b'{"a": NaN}', b'{"a": Infinity}', b'{"a": -Infinity}', b'{"a": -1e999}']
)
async def test_request_refuses_non_finite_numbers(body: bytes) -> None:
    """json.loads turns 1e999 into inf, which later breaks round() and int(): refuse it as invalid JSON."""
    with pytest.raises(HegelError, match="getData: invalid JSON"):
        await _ask(_FakeResponse(200, [body]))


async def test_request_ordinary_numbers_are_unchanged() -> None:
    result = await _ask(_FakeResponse(200, [b'{"a": 1.5, "b": [2, 3.25], "c": -7, "d": 0.0, "e": 1e3}']))
    assert result == {"a": 1.5, "b": [2, 3.25], "c": -7, "d": 0.0, "e": 1000.0}
    assert isinstance(result["b"][0], int)


def test_recorded_h150_session_has_no_non_finite_numbers() -> None:
    """The check does not touch the real recording: every body of the session still loads."""
    session = Path(__file__).parent / "fixtures" / "h150_session.json"
    text = session.read_text(encoding="utf-8")
    json.loads(text, parse_float=_finite_float, parse_constant=_reject_constant)
    # Many values inside it are JSON texts themselves (the recorded answer bodies).
    checked = 0

    def walk(node: object) -> None:
        nonlocal checked
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.lstrip().startswith(("{", "[")):
            json.loads(node, parse_float=_finite_float, parse_constant=_reject_constant)
            checked += 1

    walk(json.loads(text))
    assert checked > 10

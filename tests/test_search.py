"""Searching internet radio and podcasts on the amplifier (#27)."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.hegel_connect.api import HegelClient, HegelError

from .conftest import FakeHegel

ENTITY = "media_player.hegel_h150"
HOST = "https://0000000000.airable.io"
# Search in the media browser exists from a newer Home Assistant on; the minimum version just does not offer it.
needs_search = pytest.mark.skipif(
    not hasattr(MediaPlayerEntityFeature, "SEARCH_MEDIA"), reason="this Home Assistant has no media search"
)
SECTIONS = {
    "rows": [
        {"title": "Radio", "path": f"airable:{HOST}/airable/radios"},
        {"title": "Podcasts", "path": f"airable:{HOST}/airable/feeds"},
    ]
}


RADIOS_ONLY = {"rows": [{"path": f"airable:{HOST}/airable/radios"}]}


def _station(title: str, number: int) -> dict[str, Any]:
    return {
        "title": title,
        "type": "container",
        "containerPlayable": True,
        "audioType": "audioBroadcast",
        "path": f"airable:{HOST}/id/airable/radio/{number}",
        "id": f"airable://airable/radio/{number}",
        "icon": f"http://static.airable.io/{number}.png",
    }


def _feed(title: str, number: int) -> dict[str, Any]:
    return {
        "title": title,
        "type": "container",
        "path": f"airable:{HOST}/id/airable/feed/{number}",
        "id": f"airable://airable/feed/{number}",
        "icon": f"http://static.airable.io/f{number}.png",
    }


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _search(hass: HomeAssistant, query: str, **extra: Any) -> list[dict[str, Any]]:
    response = await hass.services.async_call(
        "media_player",
        "search_media",
        {"entity_id": ENTITY, "search_query": query, **extra},
        blocking=True,
        return_response=True,
    )
    return response[ENTITY].as_dict()["result"]


@needs_search
async def test_search_is_offered(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    await _setup(hass, config_entry)
    features = hass.states.get(ENTITY).attributes["supported_features"]
    assert features & MediaPlayerEntityFeature.SEARCH_MEDIA


@needs_search
async def test_the_search_gives_stations(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    FakeHegel.search_results = {"radio": [_station("Radio 10", 1), _station("Radio 10 - 80s Hits", 2)]}
    await _setup(hass, config_entry)
    result = await _search(hass, "radio 10")
    assert [(item["title"], item["media_class"]) for item in result] == [
        ("Radio 10", "channel"),
        ("Radio 10 - 80s Hits", "channel"),
    ]
    station = result[0]
    assert station["can_play"] and not station["can_expand"]
    assert station["media_content_type"] == "hegel_path"
    assert station["media_content_id"] == f"airable:{HOST}/id/airable/radio/1"
    assert station["thumbnail"] == "http://static.airable.io/1.png"
    assert fake_hegel[-1].searches == [("radio", "radio 10")]


@needs_search
async def test_a_found_station_starts_like_a_favorite(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    FakeHegel.search_results = {"radio": [_station("Qmusic", 5)]}
    await _setup(hass, config_entry)
    found = (await _search(hass, "qmusic"))[0]
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": ENTITY,
            "media_content_type": found["media_content_type"],
            "media_content_id": found["media_content_id"],
        },
        blocking=True,
    )
    assert ("play_path", f"airable:{HOST}/id/airable/radio/5") in fake_hegel[-1].calls


@pytest.mark.parametrize("filter_classes", [["channel"], ["music"], ["podcast", "channel"]])
@needs_search
async def test_a_filter_for_anything_but_podcasts_still_searches_radio(
    hass: HomeAssistant, fake_hegel, config_entry, filter_classes: list[str]
) -> None:
    FakeHegel.search_results = {"radio": [_station("A", 1)]}
    await _setup(hass, config_entry)
    assert len(await _search(hass, "x", media_filter_classes=filter_classes)) == 1


@needs_search
async def test_podcasts_alone_are_not_searched_yet(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    FakeHegel.search_results = {"radio": [_station("A", 1)]}
    await _setup(hass, config_entry)
    assert await _search(hass, "x", media_filter_classes=["podcast"]) == []
    assert fake_hegel[-1].searches == []


@needs_search
async def test_nothing_found_is_an_empty_list(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    FakeHegel.search_results = {"radio": []}
    await _setup(hass, config_entry)
    assert await _search(hass, "zzzz") == []


@needs_search
async def test_a_failing_search_tells_the_user_why(hass: HomeAssistant, fake_hegel, config_entry) -> None:
    FakeHegel.search_results = {"radio": HegelError("boom")}
    await _setup(hass, config_entry)
    with pytest.raises(HomeAssistantError, match="boom"):
        await _search(hass, "radio 10")


# ------------------------------------------------------------------ the client against recorded-style answers


class _Replies:
    """A session that answers request after request from a list, and remembers what was asked."""

    def __init__(self, bodies: list[Any]) -> None:
        self.bodies = list(bodies)
        self.asked: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any):
        self.asked.append((method, url.rsplit("/", 1)[-1], kwargs.get("params") or kwargs.get("json") or {}))
        body = json.dumps(self.bodies.pop(0)).encode()

        class _Response:
            status = 200
            charset = "utf-8"

            def __init__(self) -> None:
                self.content = self

            async def iter_chunked(self, size: int):
                yield body

        class _Context:
            async def __aenter__(self_inner):
                return _Response()

            async def __aexit__(self_inner, *exc):
                return False

        return _Context()


def _filters() -> list[dict[str, Any]]:
    return [
        {
            "title": name,
            "type": "container",
            "path": f"airable:{HOST}/x/{i}",
            "id": f"airable://airable/radios/filter/filter.{i}",
        }
        for i, name in enumerate(["By Location", "By Language", "By Genre"])
    ]


async def test_the_client_follows_the_form_like_the_web_client() -> None:
    results_path = f"airable:{HOST}/airable/radios/search\\?q\\=Radio%2010"
    session = _Replies(
        [
            {
                "rows": [
                    {"title": "Radio", "path": f"airable:{HOST}/airable/radios"},
                    {"title": "Podcasts", "path": f"airable:{HOST}/airable/feeds"},
                ]
            },
            {"rowsRedirect": "airable:form7", "rows": []},
            True,
            {"xclass": "NsdkActionReply", "result": {"path": results_path}},
            {"rowsCount": 349, "rows": [*_filters(), _station("Radio 10", 1), _station("Radio 10 - 60s", 2)]},
        ]
    )
    client = HegelClient("192.0.2.10", session)  # type: ignore[arg-type]
    rows = await client.search_airable("radio", "  Radio 10 ")
    assert [r["title"] for r in rows] == ["Radio 10", "Radio 10 - 60s"]  # the three filter rows are left out
    assert [(m, e) for m, e, _ in session.asked] == [
        ("GET", "getRows"),
        ("GET", "getRows"),
        ("POST", "setData"),
        ("POST", "setData"),
        ("GET", "getRows"),
    ]
    # The form is the one the search node redirects to (the number changes), the text is trimmed,
    # and the result path goes back exactly as the amplifier gave it (it contains \\? and \\=).
    assert session.asked[1][2]["path"] == f"airable:{HOST}/airable/radios/search"
    assert session.asked[2][2] == {
        "path": "airable:form7:q",
        "role": "value",
        "value": {"type": "string_", "string_": "Radio 10"},
    }
    assert session.asked[3][2] == {"path": "airable:form7:submit", "role": "activate", "value": {}}
    assert session.asked[4][2]["path"] == results_path
    assert session.asked[4][2]["from"] == "0" and session.asked[4][2]["to"] == "19"


async def test_the_client_can_search_podcasts_too() -> None:
    """The client is ready for podcasts (planned for a later version); the integration does not use it yet."""
    session = _Replies(
        [
            {
                "rows": [
                    {"title": "Radio", "path": f"airable:{HOST}/airable/radios"},
                    {"title": "Podcasts", "path": f"airable:{HOST}/airable/feeds"},
                ]
            },
            {"rowsRedirect": "airable:form2", "rows": []},
            True,
            {"result": {"path": f"airable:{HOST}/airable/feeds/search\\?q\\=nieuws"}},
            {"rows": [*_filters(), _feed("Nieuwsweekend", 3)]},
        ]
    )
    client = HegelClient("192.0.2.10", session)  # type: ignore[arg-type]
    assert [r["title"] for r in await client.search_airable("podcast", "nieuws")] == ["Nieuwsweekend"]
    assert session.asked[1][2]["path"] == f"airable:{HOST}/airable/feeds/search"


async def test_an_empty_search_asks_nothing() -> None:
    session = _Replies([])
    assert await HegelClient("192.0.2.10", session).search_airable("radio", "   ") == []  # type: ignore[arg-type]
    assert session.asked == []


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ([{"rows": []}], "No radios section found"),
        ([RADIOS_ONLY, {"rows": []}], "no search form"),
        (
            [
                {"rows": [{"path": f"airable:{HOST}/airable/radios"}]},
                {"rowsRedirect": "airable:form1"},
                True,
                {"result": {}},
            ],
            "no result list",
        ),
    ],
)
async def test_a_search_that_cannot_run_says_why(answers: list[Any], message: str) -> None:
    client = HegelClient("192.0.2.10", _Replies(answers))  # type: ignore[arg-type]
    with pytest.raises(HegelError, match=message):
        await client.search_airable("radio", "x")

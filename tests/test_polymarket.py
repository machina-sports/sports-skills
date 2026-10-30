"""Unit tests for the polymarket module (no network)."""

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from sports_skills import cli, polymarket
from sports_skills.polymarket import _connector as poly_connector
from sports_skills.polymarket._connector import (
    _normalize_market,
    _text_match,
    _text_match_market,
)


def test_league_search_provider_error_is_returned_without_fallback():
    calls = []

    def fake_gamma(endpoint, params=None, ttl=120):
        calls.append(endpoint)
        return {"error": True, "status_code": 503, "message": "Service Unavailable"}

    with (
        patch.object(poly_connector, "_get_sports_config", return_value={"nfl": {"series": "10187"}}),
        patch.object(poly_connector, "_gamma_request", side_effect=fake_gamma),
    ):
        result = poly_connector.search_markets({"params": {"sport": "nfl", "query": "49ers"}})

    assert result["status"] is False
    assert result["message"] == "API error (503): Service Unavailable"
    assert calls == ["/events"]


class TestTextMatch:
    """Cross-venue callers (markets.compare_odds) build "<away> <home>"
    queries whose tokens are never contiguous in Polymarket titles."""

    def test_normalize_market_tolerates_null_tags(self):
        market = _normalize_market(
            {
                "id": "m1",
                "question": "Will the Orioles beat the Rays?",
                "tags": None,
                "events": None,
            }
        )
        assert market["tags"] == []
        assert market["event_id"] == ""

    def test_contiguous_match_still_works(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Tampa Bay Rays", event) is True

    def test_two_token_query_matches_non_contiguous_title(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Orioles Rays", event) is True

    def test_two_token_query_requires_all_tokens(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Orioles Yankees", event) is False

    def test_tokens_must_match_one_semantic_field(self):
        event = {"title": "Orioles moneyline", "description": "Rays futures", "slug": "mlb"}
        assert _text_match("Orioles Rays", event) is False

    def test_token_matching_uses_word_boundaries(self):
        event = {"title": "Programs featuring Eagles", "description": "", "slug": ""}
        assert _text_match("Rams Eagles", event) is False

    def test_null_provider_fields_are_tolerated(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": None, "slug": None}
        assert _text_match("Orioles Rays", event) is True

    def test_single_token_stays_contiguous_only(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Cardinals", event) is False


class TestTextMatchMarket:
    def test_two_token_query_matches_market_question(self):
        market = {"question": "Will the Orioles beat the Rays?", "slug": "", "events": []}
        assert _text_match_market("Orioles Rays", market) is True

    def test_two_token_query_matches_parent_event_title(self):
        market = {
            "question": "Moneyline",
            "slug": "",
            "events": [{"title": "Baltimore Orioles vs. Tampa Bay Rays", "slug": ""}],
        }
        assert _text_match_market("Orioles Rays", market) is True

    def test_tokens_must_not_span_multiple_parent_events(self):
        market = {
            "question": "Moneyline",
            "slug": "",
            "events": [
                {"title": "Baltimore Orioles", "slug": "orioles"},
                {"title": "Tampa Bay Rays", "slug": "rays"},
            ],
        }
        assert _text_match_market("Orioles Rays", market) is False

    def test_null_events_are_tolerated(self):
        market = {"question": "Will the Orioles beat the Rays?", "slug": None, "events": None}
        assert _text_match_market("Orioles Rays", market) is True

    def test_no_match_returns_false(self):
        market = {"question": "Moneyline", "slug": "", "events": [{"title": "Cubs vs. Cards", "slug": ""}]}
        assert _text_match_market("Orioles Rays", market) is False


class TestSearchMarketsApostrophes:
    """#162: Polymarket titles use a curly apostrophe ("2026 Men’s US Open
    Winner (Tennis)") and slugs drop it ("2026-mens-us-open-winner-tennis"),
    so a straight-apostrophe query found nothing."""

    @staticmethod
    def _search(monkeypatch, query):
        from sports_skills.polymarket import _connector

        event = json.loads((Path(__file__).parent / "fixtures" / "polymarket_us_open_event.json").read_text())
        # The captured fixture's markets have since closed; these tests pin
        # text matching on live markets, so mark them open explicitly.
        for market in event["markets"]:
            market["closed"] = False
        monkeypatch.setattr(
            _connector,
            "_gamma_request",
            lambda endpoint, params=None, ttl=120: [event] if endpoint == "/events" else [],
        )
        return _connector.search_markets({"params": {"query": query}})

    def test_possessive_query_matches_curly_apostrophe_title(self, monkeypatch):
        assert self._search(monkeypatch, "2026 Men's US Open")["data"]["count"] == 2

    def test_query_without_apostrophe_matches(self, monkeypatch):
        assert self._search(monkeypatch, "Mens US Open")["data"]["count"] == 2

    def test_plain_query_still_matches(self, monkeypatch):
        assert self._search(monkeypatch, "US Open")["data"]["count"] == 2

    def test_other_draw_does_not_match(self, monkeypatch):
        assert self._search(monkeypatch, "2026 Women's US Open")["data"]["count"] == 0


def _gm(market_id, active=True, closed=False, question="Seahawks vs. 49ers"):
    """Raw Gamma market; ``None`` drops the flag entirely."""
    market = {"id": market_id, "question": question, "slug": f"m-{market_id}", "outcomes": '["A", "B"]'}
    if active is not None:
        market["active"] = active
    if closed is not None:
        market["closed"] = closed
    return market


class TestSearchMarketsOpenOnly:
    """An active event does not make its nested markets active: every search
    branch yields only markets whose own flags are active=True, closed!=True."""

    @staticmethod
    def _search(monkeypatch, responses, config=None, **params):
        from sports_skills.polymarket import _connector

        calls = []

        def fake_gamma(endpoint, params=None, ttl=120):
            calls.append((endpoint, dict(params or {})))
            return responses.get(endpoint, [])

        monkeypatch.setattr(_connector, "_gamma_request", fake_gamma)
        monkeypatch.setattr(_connector, "_get_sports_config", lambda: config or {})
        result = _connector.search_markets({"params": params})
        return result, calls

    MIXED = [
        _gm("open"),
        _gm("closed", closed=True),
        _gm("inactive", active=False),
        _gm("no-flags", active=None, closed=None),
        _gm("string-flags", active="true", closed="false"),
    ]

    def _ids(self, result):
        return [m["id"] for m in result["data"]["markets"]]

    def test_series_branch_excludes_closed_children(self, monkeypatch):
        events = [{"id": "e1", "title": "Seahawks vs. 49ers", "active": True, "closed": False, "markets": self.MIXED}]
        result, _ = self._search(monkeypatch, {"/events": events}, config={"nfl": {"series": "10187"}}, sport="nfl")
        assert self._ids(result) == ["open"]

    def test_direct_markets_branch_excludes_closed_payloads(self, monkeypatch):
        result, _ = self._search(monkeypatch, {"/markets": self.MIXED})
        assert self._ids(result) == ["open"]

    def test_query_events_branch_excludes_closed_children(self, monkeypatch):
        events = [{"id": "e1", "title": "Seahawks vs. 49ers", "active": True, "closed": False, "markets": self.MIXED}]
        result, _ = self._search(monkeypatch, {"/events": events}, query="Seahawks")
        assert self._ids(result) == ["open"]

    def test_series_branch_deduplicates_before_limit(self, monkeypatch):
        events = [
            {"id": "e1", "title": "a", "markets": [_gm("A"), _gm("A")]},
            {"id": "e2", "title": "b", "markets": [_gm("A"), _gm("B")]},
        ]
        result, _ = self._search(
            monkeypatch, {"/events": events}, config={"nfl": {"series": "10187"}}, sport="nfl", limit=2
        )
        assert self._ids(result) == ["A", "B"]

    def test_league_search_never_falls_back_to_unscoped_markets(self, monkeypatch):
        responses = {"/events": [], "/markets": [_gm("other-sport")]}
        result, calls = self._search(monkeypatch, responses, config={"nfl": {"series": "10187"}}, sport="nfl")
        assert result["status"] is True
        assert self._ids(result) == []
        assert [endpoint for endpoint, _ in calls] == ["/events"]

    def test_unresolvable_sport_fails_instead_of_returning_every_sport(self, monkeypatch):
        responses = {"/events": [], "/markets": [_gm("other-sport")]}
        result, calls = self._search(monkeypatch, responses, config={}, sport="nfl")
        assert result["status"] is False
        assert "nfl" in result["message"]
        assert calls == []

    def test_event_details_keep_closed_markets_for_history(self, monkeypatch):
        from sports_skills.polymarket import _connector

        event = {"id": "e1", "slug": "s", "title": "t", "markets": [_gm("open"), _gm("closed", closed=True)]}
        monkeypatch.setattr(_connector, "_gamma_request", lambda endpoint, params=None, ttl=120: [event])
        result = _connector.get_event_details({"params": {"slug": "s"}})
        assert [m["status"] for m in result["data"]["markets"]] == ["active", "closed"]


# ============================================================
# get_todays_events: date-scoped, one bounded page, tradable markets
# ============================================================

# Field names/formats follow a public Gamma event: startDate is the listing
# time, startTime the game kickoff, endDate the game day; nested markets carry
# gameStartTime ("YYYY-MM-DD HH:MM:SS+00"). All IDs and values are synthetic.
_LISTING = "2026-10-23T00:51:16Z"
_CONFIG = {"nba": {"series": "S-NBA"}, "wnba": {"series": "S-WNBA"}}


def _mm(market_id, smt="moneyline", accepting=True, order_book=True, game_start=None, **flags):
    """Raw Gamma nested market; ``None`` drops an order flag entirely."""
    market = {
        "id": market_id,
        "question": f"Synthetic Owls vs. Synthetic Foxes ({market_id})",
        "slug": f"syn-{market_id}",
        "description": "Long resolution rules. " * 50,
        "outcomes": '["Owls", "Foxes"]',
        "outcomePrices": '["0.55", "0.45"]',
        "clobTokenIds": f'["{market_id}-tok-a", "{market_id}-tok-b"]',
        "active": True,
        "closed": False,
        "sportsMarketType": smt,
    }
    if accepting is not None:
        market["acceptingOrders"] = accepting
    if order_book is not None:
        market["enableOrderBook"] = order_book
    if game_start is not None:
        market["gameStartTime"] = game_start
    market.update(flags)
    return market


def _ge(event_id, start_time=None, markets=None, start_date=_LISTING, end_date=None, **extra):
    """Raw Gamma event; ``start_time`` is the kickoff, ``start_date`` the listing time."""
    event = {
        "id": event_id,
        "title": f"Synthetic event {event_id}",
        "slug": f"syn-{event_id}",
        "description": "Long event description. " * 50,
        "active": True,
        "closed": False,
        "startDate": start_date,
        "endDate": end_date or start_time or start_date,
        "markets": [_mm(f"{event_id}-ml")] if markets is None else markets,
    }
    if start_time is not None:
        event["startTime"] = start_time
    event.update(extra)
    return event


def _today(monkeypatch, response, **params):
    calls = []

    def fake_gamma(endpoint, params=None, ttl=120):
        calls.append((endpoint, dict(params or {})))
        return response

    monkeypatch.setattr(poly_connector, "_gamma_request", fake_gamma)
    monkeypatch.setattr(poly_connector, "_get_sports_config", lambda: _CONFIG)
    result = poly_connector.get_todays_events({"params": {"sport": "nba", **params}})
    return result, calls


_DATED_PAGE = [
    # 00:00Z on the 30th is still the 29th in New York (EDT, UTC-4).
    _ge("late", "2026-10-30T00:00:00Z", [_mm("late-ml", game_start="2026-10-30 00:00:00+00")], eventDate="2026-10-29"),
    # Listed on the 29th, but the game is days later.
    _ge("next", "2026-11-02T00:00:00Z", start_date="2026-10-29T12:00:00Z"),
    _ge("old", "2026-10-28T18:00:00Z"),
    # Kickoff only on the nested market.
    _ge("mkt-only", None, [_mm("mkt-only-ml", game_start="2026-10-29 18:00:00+00")]),
    # No kickoff anywhere: listing/end/eventDate all say the 29th but are not a game time.
    _ge("undated", None, start_date="2026-10-29T10:00:00Z", end_date="2026-10-29T23:00:00Z", eventDate="2026-10-29"),
]


@pytest.mark.parametrize(
    "date,tz,expected",
    [
        ("2026-10-29", "America/New_York", ["late", "mkt-only"]),
        ("2026-10-29", "UTC", ["mkt-only"]),
        ("2026-10-30", "UTC", ["late"]),
    ],
)
def test_todays_events_scope_kickoff_to_local_date(monkeypatch, date, tz, expected):
    result, calls = _today(monkeypatch, _DATED_PAGE, date=date, timezone=tz)
    assert result["status"] is True
    data = result["data"]
    assert [e["id"] for e in data["events"]] == expected
    assert data["count"] == len(expected)
    assert (data["date"], data["timezone"]) == (date, tz)
    # Unknown kickoff is reported, never guessed from listing/end dates.
    assert data["unknown_start"] == ["undated"]
    assert data["complete"] is False
    assert data["scanned"] == len(_DATED_PAGE)
    assert len(calls) == 1


def test_todays_events_expose_authoritative_game_start(monkeypatch):
    result, _ = _today(monkeypatch, _DATED_PAGE, date="2026-10-30", timezone="UTC")
    event = result["data"]["events"][0]
    assert event["game_start_time"] == "2026-10-30T00:00:00Z"
    assert event["start_date"] == _LISTING
    assert event["markets"][0]["game_start_time"] == "2026-10-30 00:00:00+00"


def test_todays_events_default_to_today_in_utc(monkeypatch):
    result, _ = _today(monkeypatch, [])
    assert result["status"] is True
    assert result["data"]["timezone"] == "UTC"
    assert result["data"]["date"] == datetime.now(timezone.utc).date().isoformat()


@pytest.mark.parametrize("params", [{"date": "2026-13-01"}, {"date": "tomorrow"}, {"timezone": "Mars/Base"}])
def test_todays_events_reject_invalid_date_or_timezone(monkeypatch, params):
    result, calls = _today(monkeypatch, [], **params)
    assert result["status"] is False
    assert calls == []


@pytest.mark.parametrize(
    "page,offset,expected",
    [
        # Full page filtered to nothing: more may follow, so not exhaustive.
        ([_ge("a", "2026-11-05T00:00:00Z"), _ge("b", "2026-11-06T00:00:00Z")], 0, (2, True, False)),
        ([_ge("a", "2026-11-05T00:00:00Z"), _ge("b", "2026-11-06T00:00:00Z")], 4, (6, True, False)),
        # Short page after skipped rows: earlier pages were not scanned here.
        ([_ge("a", "2026-11-05T00:00:00Z")], 4, (None, False, False)),
        # Short first page, every kickoff known: a real exhaustive empty.
        ([_ge("a", "2026-11-05T00:00:00Z")], 0, (None, False, True)),
        ([], 0, (None, False, True)),
    ],
)
def test_todays_events_scan_one_bounded_page(monkeypatch, page, offset, expected):
    result, calls = _today(monkeypatch, page, date="2026-10-29", limit=2, offset=offset)
    assert result["status"] is True
    data = result["data"]
    assert data["events"] == []
    assert (data["next_offset"], data["truncated"], data["complete"]) == expected
    assert data["scanned"] == len(page)
    assert data["offset"] == offset
    assert len(calls) == 1
    assert calls[0][1]["limit"] == 2
    assert calls[0][1].get("offset", 0) == offset


@pytest.mark.parametrize(
    "response",
    [
        {"error": True, "status_code": 503, "message": "Service Unavailable"},
        {"unexpected": "shape"},
        {"events": "nope"},
        None,
        "not-json-collection",
        ["not-an-event"],
    ],
)
def test_todays_events_failures_are_not_empty_success(monkeypatch, response):
    result, calls = _today(monkeypatch, response, date="2026-10-29")
    assert result["status"] is False
    assert result["data"] is None
    assert len(calls) == 1


_MIXED_MARKETS = [
    _mm("ml-open", game_start="2026-10-30 00:00:00+00"),
    _mm("ml-closed", closed=True),
    _mm("ml-inactive", active=False),
    _mm("ml-not-accepting", accepting=False),
    _mm("spread-open", smt="spreads"),
    _mm("ml-no-order-flags", accepting=None, order_book=None),
]


def _mixed(monkeypatch, **params):
    page = [_ge("game", "2026-10-30T00:00:00Z", _MIXED_MARKETS)]
    result, _ = _today(monkeypatch, page, date="2026-10-29", timezone="America/New_York", **params)
    assert result["status"] is True
    (event,) = result["data"]["events"]
    return event


def test_todays_events_exclude_known_unavailable_markets(monkeypatch):
    event = _mixed(monkeypatch)
    markets = {m["id"]: m for m in event["markets"]}
    assert list(markets) == ["ml-open", "spread-open", "ml-no-order-flags"]
    # Full read by default: compact is opt-in.
    assert "description" in event and "description" in markets["ml-open"]
    assert markets["ml-open"]["accepting_orders"] is True
    assert markets["ml-open"]["enable_order_book"] is True
    # Missing provider flags stay unknown, never fabricated as tradable.
    assert markets["ml-no-order-flags"].get("accepting_orders") is None
    assert markets["ml-no-order-flags"].get("enable_order_book") is None


def test_todays_events_compact_moneyline_summary(monkeypatch):
    event = _mixed(monkeypatch, sports_market_types="moneyline", compact=True)
    assert event["id"] == "game"
    assert "description" not in event
    assert [m["id"] for m in event["markets"]] == ["ml-open", "ml-no-order-flags"]
    market = event["markets"][0]
    assert "description" not in market
    assert market["question"] == "Synthetic Owls vs. Synthetic Foxes (ml-open)"
    assert market["slug"] == "syn-ml-open"
    assert [o["clob_token_id"] for o in market["outcomes"]] == ["ml-open-tok-a", "ml-open-tok-b"]
    assert [o["name"] for o in market["outcomes"]] == ["Owls", "Foxes"]
    assert market["game_start_time"] == "2026-10-30 00:00:00+00"
    assert market["status"] == "active"
    assert (market["accepting_orders"], market["enable_order_book"]) == (True, True)
    assert event["markets"][1].get("accepting_orders") is None


# ============================================================
# Broad listings keep future fixtures (markets/_connector, markets/_ucl)
# ============================================================


def _broad(monkeypatch, **params):
    calls = []

    def fake_gamma(endpoint, params=None, ttl=120):
        calls.append((endpoint, dict(params or {})))
        return [_ge("future", "2027-03-01T00:00:00Z", [_mm("future-ml"), _mm("future-closed", closed=True)])]

    monkeypatch.setattr(poly_connector, "_gamma_request", fake_gamma)
    monkeypatch.setattr(poly_connector, "_get_sports_config", lambda: _CONFIG)
    return poly_connector.get_sports_events({"params": params}), calls


def test_sports_events_sport_routes_to_exact_series_without_date_filter(monkeypatch):
    result, calls = _broad(monkeypatch, sport="NBA", limit=100, offset=100)
    assert result["status"] is True
    assert [(endpoint, p.get("series_id")) for endpoint, p in calls] == [("/events", "S-NBA")]
    assert (calls[0][1]["limit"], calls[0][1]["offset"]) == (100, 100)
    (event,) = result["data"]["events"]
    assert event["id"] == "future"
    assert "description" in event
    assert [m["status"] for m in event["markets"]] == ["active", "closed"]


def test_sports_events_unknown_sport_fails_closed(monkeypatch):
    result, calls = _broad(monkeypatch, sport="quidditch")
    assert result["status"] is False
    assert "quidditch" in result["message"]
    assert calls == []


def test_public_surface_advertises_new_options():
    today = inspect.signature(polymarket.get_todays_events).parameters
    new = {"date", "timezone", "sports_market_types", "compact"}
    assert {"sport", "limit", "offset"} | new <= set(today)
    assert today["limit"].default == 30
    assert today["date"].default is None
    assert today["timezone"].default == "UTC"
    assert today["compact"].default is False
    assert "sport" in inspect.signature(polymarket.get_sports_events).parameters

    registry = cli._REGISTRY["polymarket"]
    assert {"limit", "offset"} | new <= set(registry["get_todays_events"].get("optional", []))
    assert "sport" in registry["get_sports_events"]["optional"]


@pytest.mark.parametrize("reader", ["get_todays_events", "get_sports_events"])
@pytest.mark.parametrize("response", [{"unexpected": "shape"}, [_ge("bad", "2026-10-29T12:00:00Z", markets={})], [_ge("bad", "2026-10-29T12:00:00Z", markets=False)]])
def test_event_readers_reject_malformed_even_empty_containers(monkeypatch, reader, response):
    monkeypatch.setattr(poly_connector, "_gamma_request", lambda *a, **k: response)
    monkeypatch.setattr(poly_connector, "_get_sports_config", lambda: _CONFIG)
    result = getattr(poly_connector, reader)({"params": {"sport": "nba", "date": "2026-10-29"}})
    assert result["status"] is False
    assert result["data"] is None


@pytest.mark.parametrize("missing", ["active", "closed", "acceptingOrders", "enableOrderBook"])
def test_unknown_market_state_cannot_prove_complete_availability(monkeypatch, missing):
    market = _mm("unknown-state")
    del market[missing]
    result, _ = _today(monkeypatch, [_ge("game", "2026-10-29T12:00:00Z", [market])], date="2026-10-29")
    assert result["status"] is True
    expected_status = "unknown" if missing in ("active", "closed") else "active"
    assert result["data"]["events"][0]["markets"][0]["status"] == expected_status
    assert result["data"]["complete"] is False
    assert result["data"]["unknown_market_state"] == ["unknown-state"]


@pytest.mark.parametrize("market_type", [["moneyline"], [], False, 0, {}])
def test_invalid_market_type_is_not_a_successful_empty_lookup(monkeypatch, market_type):
    result, calls = _today(monkeypatch, [], date="2026-10-29", sports_market_types=market_type)
    assert result["status"] is False
    assert calls == []

"""Tests for markets.compare_market_url — pasted venue URL → same-game comparison.

Fixtures are trimmed from live public responses of
polymarket.get_event_details(slug='nfl-sf-sea-2026-10-11') and
kalshi.get_event(event_ticker='KXNFLGAME-26OCT11SFSEA', with_nested_markets=True).
No network: providers, the ESPN scoreboard and compare_odds are patched.
"""

import copy
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from sports_skills import markets
from sports_skills.cli import _REGISTRY, _generate_schema

POLY_URL = "https://polymarket.com/event/nfl-sf-sea-2026-10-11"
KALSHI_URL = "https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sfsea"


def _poly_market(market_id, slug, market_type, outcomes=("49ers", "Seahawks"), status="active"):
    return {
        "id": market_id,
        "question": "49ers vs. Seahawks",
        "slug": slug,
        "status": status,
        "outcomes": [
            {"name": name, "price": price, "clob_token_id": f"tok-{market_id}-{i}"}
            for i, (name, price) in enumerate(zip(outcomes, (0.385, 0.615, 0.1)))
        ],
        "sports_market_type": market_type,
        "event_id": "",
    }


POLY_EVENT = {
    "id": "941347",
    "title": "49ers vs. Seahawks",
    "slug": "nfl-sf-sea-2026-10-11",
    "status": "active",
    "end_date": "2026-10-11T20:25:00Z",
    "market_count": 4,
    "markets": [
        _poly_market("4024680", "nfl-sf-sea-2026-10-11", "moneyline"),
        _poly_market("4061336", "nfl-sf-sea-2026-10-11-spread-home-1pt5", "spreads", ("Seahawks", "49ers")),
        _poly_market("5337953", "nfl-sf-sea-2026-10-11-3q-moneyline", "q3_moneyline"),
        _poly_market("5337954", "nfl-sf-sea-2026-10-11-4q-moneyline", "q4_moneyline"),
    ],
    "tags": ["Sports", "NFL (All)", "Games"],
}


def _kalshi_market(ticker, team, status="active"):
    return {
        "event_ticker": "KXNFLGAME-26OCT11SFSEA",
        "market_type": "binary",
        "status": status,
        "ticker": ticker,
        "title": f"{team} wins",
        "yes_sub_title": team,
        "yes_bid_dollars": "0.6100",
        "occurrence_datetime": "2026-10-11T23:25:00Z",
    }


KALSHI_EVENT = {
    "event": {
        "event_ticker": "KXNFLGAME-26OCT11SFSEA",
        "series_ticker": "KXNFLGAME",
        "title": "SF 49ers vs SEA Seahawks",
        "sub_title": "SF vs SEA (Oct 11)",
        "mutually_exclusive": True,
        "product_metadata": {"competition": "Pro Football", "competition_scope": "Game"},
        "markets": [
            _kalshi_market("KXNFLGAME-26OCT11SFSEA-SEA", "Seattle"),
            _kalshi_market("KXNFLGAME-26OCT11SFSEA-SF", "San Francisco"),
        ],
    },
    "markets": [],
}


def _espn_event(event_id="401772", start="2026-10-11T20:25Z", away=("San Francisco 49ers", "SF")):
    return {
        "id": event_id,
        "start_time": start,
        "competitors": [
            {"team": {"id": "26", "name": "Seattle Seahawks", "abbreviation": "SEA"}, "home_away": "home"},
            {"team": {"id": "25", "name": away[0], "abbreviation": away[1]}, "home_away": "away"},
        ],
    }


COMPARE_RESULT = {
    "status": True,
    "data": {
        "sport": "nfl",
        "event_id": "401772",
        "polymarket_markets": [{"source": "polymarket", "market_id": "4024680", "slug": "nfl-sf-sea-2026-10-11"}],
        "kalshi_markets": [{"source": "kalshi", "event_ticker": "KXNFLGAME-26OCT11SFSEA", "markets": []}],
        "side_prices": {"home": {"team": "Seattle Seahawks", "quotes": []}, "away": {"team": "San Francisco 49ers"}},
        "sources": {"polymarket": {"outcome": "ok"}, "novig": {"outcome": "error", "detail": "down"}},
        "warnings": ["novig search failed: down"],
    },
    "message": "Odds comparison for San Francisco 49ers @ Seattle Seahawks.",
}


class _Scoreboard:
    """Fake sport module: per-date scoreboard responses, recording calls."""

    def __init__(self, by_date=None, default=None, fail_dates=()):
        self.by_date = by_date or {}
        self.default = default if default is not None else []
        self.fail_dates = set(fail_dates)
        self.calls = []

    def get_scoreboard(self, date=None):
        self.calls.append(date)
        if date in self.fail_dates:
            return {"status": False, "data": None, "message": "ESPN 503"}
        return {"status": True, "data": {"events": self.by_date.get(date, self.default)}, "message": ""}


@pytest.fixture
def env():
    """Patch every outbound seam; tests tweak return values per case."""
    board = _Scoreboard(by_date={"2026-10-11": [_espn_event()]})
    poly = MagicMock(return_value={"status": True, "data": copy.deepcopy(POLY_EVENT), "message": ""})
    kalshi = MagicMock(return_value={"status": True, "data": copy.deepcopy(KALSHI_EVENT), "message": ""})
    compare = MagicMock(return_value=copy.deepcopy(COMPARE_RESULT))
    with ExitStack() as stack:
        stack.enter_context(patch("sports_skills.polymarket.get_event_details", poly))
        stack.enter_context(patch("sports_skills.kalshi.get_event", kalshi))
        stack.enter_context(patch("sports_skills.markets._connector._load_sport_module", return_value=board))
        stack.enter_context(patch("sports_skills.markets._connector.compare_odds", compare))
        yield {"board": board, "poly": poly, "kalshi": kalshi, "compare": compare}


def _no_calls(env):
    assert not env["poly"].called
    assert not env["kalshi"].called
    assert env["board"].calls == []
    assert not env["compare"].called


# ============================================================
# Happy paths
# ============================================================


class TestPolymarketUrl:
    def test_resolves_event_to_one_espn_game_and_compares_once(self, env):
        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        env["poly"].assert_called_once_with(slug="nfl-sf-sea-2026-10-11")
        env["compare"].assert_called_once_with({"params": {"sport": "nfl", "event_id": "401772"}})
        source = result["data"]["source_market"]
        assert source["venue"] == "polymarket"
        assert source["url"] == POLY_URL
        assert source["event_id"] == "941347"
        assert source["market_id"] == "4024680"
        assert source["market_slug"] == "nfl-sf-sea-2026-10-11"
        assert source["sport"] == "nfl"
        assert source["espn_event_id"] == "401772"
        assert source["in_downstream_search"] is True

    def test_preserves_compare_odds_content(self, env):
        result = markets.compare_market_url(url=POLY_URL)

        data = result["data"]
        assert data["side_prices"] == COMPARE_RESULT["data"]["side_prices"]
        assert data["sources"]["novig"] == {"outcome": "error", "detail": "down"}
        assert "novig search failed: down" in data["warnings"]
        assert result["message"] == COMPARE_RESULT["message"]

    def test_scoreboard_window_is_source_date_and_neighbours(self, env):
        markets.compare_market_url(url=POLY_URL)
        assert sorted(env["board"].calls) == ["2026-10-10", "2026-10-11", "2026-10-12"]

    def test_explicit_market_slug_selects_that_market(self, env):
        result = markets.compare_market_url(url=POLY_URL + "/nfl-sf-sea-2026-10-11")
        assert result["status"] is True, result["message"]
        assert result["data"]["source_market"]["market_id"] == "4024680"
        assert result["data"]["source_market"]["url"] == POLY_URL + "/nfl-sf-sea-2026-10-11"

    def test_explicit_non_moneyline_market_is_refused(self, env):
        result = markets.compare_market_url(url=POLY_URL + "/nfl-sf-sea-2026-10-11-spread-home-1pt5")
        assert result["status"] is False
        assert "moneyline" in result["message"]
        assert not env["compare"].called

    def test_explicit_market_absent_from_event_is_refused(self, env):
        result = markets.compare_market_url(url=POLY_URL + "/nfl-sf-sea-2026-10-11-nope")
        assert result["status"] is False
        assert not env["compare"].called

    def test_tracking_query_is_ignored(self, env):
        result = markets.compare_market_url(url=POLY_URL + "?utm_source=x&tid=123")
        assert result["status"] is True, result["message"]

    def test_www_host_is_accepted(self, env):
        result = markets.compare_market_url(url="https://www.polymarket.com/event/nfl-sf-sea-2026-10-11")
        assert result["status"] is True, result["message"]
        assert result["data"]["source_market"]["url"] == POLY_URL


class TestKalshiUrl:
    def test_resolves_event_to_one_espn_game_and_compares_once(self, env):
        result = markets.compare_market_url(url=KALSHI_URL)

        assert result["status"] is True, result["message"]
        env["kalshi"].assert_called_once_with(event_ticker="KXNFLGAME-26OCT11SFSEA", with_nested_markets=True)
        env["compare"].assert_called_once_with({"params": {"sport": "nfl", "event_id": "401772"}})
        source = result["data"]["source_market"]
        assert source["venue"] == "kalshi"
        assert source["url"] == KALSHI_URL
        assert source["event_id"] == "KXNFLGAME-26OCT11SFSEA"
        assert sorted(source["market_tickers"]) == ["KXNFLGAME-26OCT11SFSEA-SEA", "KXNFLGAME-26OCT11SFSEA-SF"]
        assert source["in_downstream_search"] is True

    def test_www_and_uppercase_ticker_accepted(self, env):
        result = markets.compare_market_url(
            url="https://www.kalshi.com/markets/KXNFLGAME/sf-vs-sea/KXNFLGAME-26OCT11SFSEA"
        )
        assert result["status"] is True, result["message"]

    def test_closed_kalshi_market_is_refused(self, env):
        data = copy.deepcopy(KALSHI_EVENT)
        data["event"]["markets"][0]["status"] = "finalized"
        env["kalshi"].return_value = {"status": True, "data": data, "message": ""}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "finalized" in result["message"]
        assert not env["compare"].called

    def test_returned_event_ticker_mismatch_is_refused(self, env):
        data = copy.deepcopy(KALSHI_EVENT)
        data["event"]["event_ticker"] = "KXNFLGAME-26OCT18SFSEA"
        env["kalshi"].return_value = {"status": True, "data": data, "message": ""}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert not env["compare"].called

    def test_series_and_ticker_disagree_is_refused_before_calls(self, env):
        result = markets.compare_market_url(url="https://kalshi.com/markets/kxnbagame/x/kxnflgame-26oct11sfsea")
        assert result["status"] is False
        _no_calls(env)

    def test_unsupported_kalshi_series_is_refused_before_calls(self, env):
        result = markets.compare_market_url(url="https://kalshi.com/markets/kxeplgame/ars-che/kxeplgame-26oct11arsche")
        assert result["status"] is False
        assert "unsupported" in result["message"].lower()
        _no_calls(env)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("ticker", "KXNFLGAME-26OCT18SFSEA-SEA"),
            ("ticker", "KXNBAGAME-26OCT11SFSEA-SEA"),
            ("event_ticker", "KXNFLGAME-26OCT18SFSEA"),
        ],
    )
    def test_child_market_of_another_event_is_refused(self, env, field, value):
        data = copy.deepcopy(KALSHI_EVENT)
        data["event"]["markets"][0][field] = value
        env["kalshi"].return_value = {"status": True, "data": data, "message": ""}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert value in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called

    def test_declared_series_mismatch_is_refused(self, env):
        data = copy.deepcopy(KALSHI_EVENT)
        data["event"]["series_ticker"] = "KXNBAGAME"
        env["kalshi"].return_value = {"status": True, "data": data, "message": ""}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "KXNBAGAME" in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called

    def test_children_without_declared_event_ticker_are_accepted(self, env):
        data = copy.deepcopy(KALSHI_EVENT)
        for m in data["event"]["markets"]:
            del m["event_ticker"]
        env["kalshi"].return_value = {"status": True, "data": data, "message": ""}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is True, result["message"]

    def test_kalshi_provider_error_is_preserved(self, env):
        env["kalshi"].return_value = {"status": False, "data": None, "message": "API error (404): not found"}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "API error (404): not found" in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called


# ============================================================
# URL validation — nothing is fetched for a rejected URL
# ============================================================


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://polymarket.com/event/nfl-sf-sea-2026-10-11",
        "https://polymarket.com.evil.com/event/nfl-sf-sea-2026-10-11",
        "https://evil.com/event/nfl-sf-sea-2026-10-11",
        "https://user:pw@polymarket.com/event/nfl-sf-sea-2026-10-11",
        "https://user@kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sfsea",
        "https://polymarket.com:8443/event/nfl-sf-sea-2026-10-11",
        "https://polymarket.com/event/nfl-sf-sea-2026-10-11%2F..%2Fx",
        "https://polymarket.com/event/%2e%2e/nfl-sf-sea-2026-10-11",
        "https://polymarket.com/event/../nfl-sf-sea-2026-10-11",
        "https://polymarket.com/event//nfl-sf-sea-2026-10-11",
        "https://polymarket.com/sports/nfl",
        "https://polymarket.com/event/nfl-sf-sea-2026-10-11/a/b",
        "https://kalshi.com/markets/kxnflgame/sf-vs-sea",
        "https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sfsea/extra",
        "https://polymarket.com/event/nfl-sf-sea-2026-10-11?ticker=other",
        "https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sfsea?ticker=KXNFLGAME-26OCT11SFSEA-SF",
        "https://polymarket.com/event/nfl-sf-sea-2026-10-11#x",
        "https://polymarket.com/event/epl-ars-che-2026-10-11",
        "https://polymarket.com/event/nfl-sf-sea-2026-02-30",
        "https://polymarket.com/event/nfl-sf-sea-2026-13-01",
        "https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26feb30sfsea",
        "https://polymarket.com/event/nfl-sf-sea-0001-01-01",
        "https://polymarket.com/event/nfl-sf-sea-9999-12-31",
        "https://poly\nmarket.com/event/nfl-sf-sea-2026-10-11",
        "https://polymarket.com/event/nfl-sf-sea-\t2026-10-11",
        "https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sf\rsea",
    ],
)
def test_rejected_url_makes_no_calls(env, url):
    result = markets.compare_market_url(url=url)
    assert result["status"] is False
    assert result["message"]
    _no_calls(env)


# ============================================================
# Source market selection
# ============================================================


class TestPolymarketSelection:
    def _event(self, env, mutate):
        data = copy.deepcopy(POLY_EVENT)
        mutate(data)
        env["poly"].return_value = {"status": True, "data": data, "message": ""}

    def test_closed_moneyline_is_refused(self, env):
        self._event(env, lambda d: d["markets"][0].update(status="closed"))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "closed" in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called

    def test_closed_event_is_refused(self, env):
        self._event(env, lambda d: d.update(status="closed"))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert not env["compare"].called

    def test_event_without_moneyline_is_refused(self, env):
        self._event(env, lambda d: d.update(markets=d["markets"][1:]))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "moneyline" in result["message"]
        assert not env["compare"].called

    def test_two_moneylines_are_ambiguous(self, env):
        extra = _poly_market("999", "nfl-sf-sea-2026-10-11-more-markets", "moneyline")
        self._event(env, lambda d: d["markets"].append(extra))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "ambiguous" in result["message"].lower()
        assert not env["compare"].called

    def test_three_way_moneyline_is_refused(self, env):
        self._event(env, lambda d: d["markets"][0].update(outcomes=d["markets"][0]["outcomes"] + [{"name": "Tie"}]))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert not env["compare"].called

    @pytest.mark.parametrize(
        "child_slug",
        [
            "nfl-sf-sea-2026-10-12",
            "nba-sf-sea-2026-10-11",
            "nfl-lar-sea-2026-10-11",
            "nfl-sf-sea-2026-10-11-more-markets",
        ],
    )
    def test_moneyline_slug_must_be_the_requested_event(self, env, child_slug):
        self._event(env, lambda d: d["markets"][0].update(slug=child_slug))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert child_slug in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called

    def test_returned_slug_mismatch_is_refused(self, env):
        self._event(env, lambda d: d.update(slug="nfl-sf-sea-2026-12-20"))
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "nfl-sf-sea-2026-12-20" in result["message"]
        assert not env["compare"].called

    def test_provider_error_is_preserved(self, env):
        env["poly"].return_value = {"status": False, "data": None, "message": "Event not found: nfl-sf-sea-2026-10-11"}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "Event not found" in result["message"]
        assert env["board"].calls == []
        assert not env["compare"].called

    def test_provider_exception_fails_gracefully(self, env):
        env["poly"].side_effect = RuntimeError("socket closed")
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "socket closed" in result["message"]


# ============================================================
# ESPN game resolution
# ============================================================


_MISSING = object()


class TestGameResolution:
    def test_same_event_on_adjacent_days_is_deduplicated(self, env):
        env["board"].by_date = {"2026-10-11": [_espn_event()], "2026-10-12": [_espn_event()]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is True, result["message"]
        env["compare"].assert_called_once()

    def test_two_matching_espn_events_are_ambiguous(self, env):
        env["board"].by_date = {"2026-10-11": [_espn_event("401772"), _espn_event("401999", "2026-10-11T23:00Z")]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "401772" in result["message"] and "401999" in result["message"]
        assert not env["compare"].called

    @pytest.mark.parametrize("raw_id", [_MISSING, None, "", "abc", True, 0, -5])
    def test_matching_event_without_valid_id_is_refused(self, env, raw_id):
        event = _espn_event()
        if raw_id is _MISSING:
            del event["id"]
        else:
            event["id"] = raw_id
        env["board"].by_date = {"2026-10-11": [event]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "event id" in result["message"].lower()
        assert not env["compare"].called

    def test_unidentified_match_is_not_skipped_for_an_identified_one(self, env):
        bad = _espn_event(event_id=None)
        env["board"].by_date = {"2026-10-11": [bad, _espn_event()]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "event id" in result["message"].lower()
        assert not env["compare"].called

    def test_two_unidentified_matches_do_not_collapse(self, env):
        env["board"].by_date = {
            "2026-10-11": [_espn_event(event_id=None), _espn_event(event_id=None, start="2026-10-11T23:00Z")]
        }
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert not env["compare"].called

    def test_positive_int_event_id_is_accepted_as_string(self, env):
        env["board"].by_date = {"2026-10-11": [_espn_event(event_id=401772)]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is True, result["message"]
        env["compare"].assert_called_once_with({"params": {"sport": "nfl", "event_id": "401772"}})

    def test_other_games_on_the_date_are_ignored(self, env):
        env["board"].by_date = {
            "2026-10-11": [_espn_event("401000", away=("Los Angeles Rams", "LAR")), _espn_event()],
        }
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is True, result["message"]
        env["compare"].assert_called_once_with({"params": {"sport": "nfl", "event_id": "401772"}})

    def test_same_matchup_on_wrong_date_is_not_matched(self, env):
        env["board"].by_date = {"2026-10-12": [_espn_event(start="2026-10-12T20:25Z")]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert not env["compare"].called

    def test_no_game_found(self, env):
        env["board"].by_date = {}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "no espn" in result["message"].lower()
        assert result["data"]["source_market"]["market_id"] == "4024680"
        assert not env["compare"].called

    def test_scoreboard_failure_is_not_reported_as_no_game(self, env):
        env["board"].by_date = {}
        env["board"].fail_dates = {"2026-10-10"}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "ESPN 503" in result["message"]
        assert "no espn" not in result["message"].lower()
        assert not env["compare"].called


# ============================================================
# Downstream comparison
# ============================================================


class TestDownstream:
    def test_source_absent_from_downstream_search_is_surfaced(self, env):
        compare = copy.deepcopy(COMPARE_RESULT)
        compare["data"]["polymarket_markets"] = []
        env["compare"].return_value = compare
        result = markets.compare_market_url(url=POLY_URL)
        assert result["data"]["source_market"]["in_downstream_search"] is False
        assert any("4024680" in w for w in result["data"]["warnings"])
        assert "novig search failed: down" in result["data"]["warnings"]

    def test_compare_odds_failure_keeps_source_metadata(self, env):
        env["compare"].return_value = {"status": False, "data": None, "message": "ESPN returned error: boom"}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert result["message"] == "ESPN returned error: boom"
        assert result["data"]["source_market"]["venue"] == "kalshi"


# ============================================================
# CLI / schema registry
# ============================================================


def test_cli_registry_and_schema_expose_compare_market_url():
    assert _REGISTRY["markets"]["compare_market_url"] == {"required": ["url"]}
    tools = {t["command"]: t for t in _generate_schema("markets")["tools"]}
    tool = tools["compare_market_url"]
    assert tool["parameters"]["required"] == ["url"]
    assert tool["parameters"]["properties"]["url"]["type"] == "string"
    assert "description" in tool["parameters"]["properties"]["url"]

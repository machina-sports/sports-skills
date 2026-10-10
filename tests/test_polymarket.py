"""Unit tests for the polymarket module (no network)."""

import json
from pathlib import Path
from unittest.mock import patch

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

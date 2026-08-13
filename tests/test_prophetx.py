"""Unit tests for the prophetx module (no network)."""

import io
import json
import os
import urllib.error
from unittest.mock import patch

import pytest

from sports_skills.prophetx import _connector
from sports_skills.prophetx._connector import (
    _american_to_probability,
    _normalize_event,
    _normalize_market,
    _request,
    _unwrap,
    get_market,
    get_markets,
    get_sports_config,
    get_todays_events,
    get_tournaments,
    search_markets,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Isolate cache and rate limiter between tests."""
    _connector._cache.clear()
    _connector._rate_limiter.tokens = _connector._rate_limiter.max_tokens
    yield
    _connector._cache.clear()


# ============================================================
# Fixtures (shapes observed live on 2026-08-13)
# ============================================================


def _tournament(tid, name, sport_id, sport_name):
    return {
        "id": tid,
        "name": name,
        "sport": {"id": sport_id, "name": sport_name},
        "category": {"id": 0, "name": "N/A"},
    }


def _tournaments_page(items, next_cursor):
    return {"next": next_cursor, "data": {"tournaments": items}}


def _event(eid, name="Bengals at Eagles", scheduled="2026-08-13T23:00:00Z"):
    return {
        "id": eid,
        "name": name,
        "tournament": {"id": 27, "name": "NFL"},
        "scheduled": scheduled,
        "status": "not_started",
        "competitors": [
            {"id": 11, "name": "Eagles", "displayName": "Philadelphia Eagles", "seq": 0, "abbreviation": "PHI"},
            {"id": 12, "name": "Bengals", "displayName": "Cincinnati Bengals", "seq": 1, "abbreviation": "CIN"},
        ],
        "venue": {"name": "Lincoln Financial Field", "countryCode": "<nil>"},
    }


def _market_v1(event_id=19742):
    return {
        "id": 219,
        "name": "Moneyline",
        "status": "active",
        "type": "moneyline",
        "sportEventId": event_id,
        "totalStake": 7156.789999999998,
        "highRisk": False,
        "selections": [None, None],
        "outcomes": [{"id": 4, "competitorId": 11}, {"id": 5, "competitorId": 12}],
    }


def _market_v2(event_id=19742):
    market = _market_v1(event_id)
    market.update(
        {
            "subType": "moneyline",
            "categoryID": 3,
            "categoryName": "Game Lines",
            "marketLines": [
                {
                    "id": 219,
                    "name": "Spread -2.5",
                    "line": -2.5,
                    "selections": [None, None],
                    "outcomes": [
                        {
                            "id": 1714,
                            "displayName": "Eagles -2.5",
                            "competitorId": 11,
                            "line": -2.5,
                            "displayLine": "-2.5",
                            "lineID": "a" * 32,
                        }
                    ],
                }
            ],
        }
    )
    return market


# ============================================================
# Envelope tolerance (schema drift)
# ============================================================


class TestUnwrap:
    def test_object_data(self):
        items, cursor = _unwrap({"next": 27, "data": {"tournaments": [{"id": 1}]}}, "tournaments")
        assert items == [{"id": 1}]
        assert cursor == 27

    def test_list_data(self):
        items, cursor = _unwrap({"next": "123_9", "data": [{"id": 9}]}, "events")
        assert items == [{"id": 9}]
        assert cursor == "123_9"

    def test_empty_body(self):
        items, cursor = _unwrap({}, "events")
        assert items == []
        assert cursor is None

    def test_missing_key_in_object(self):
        items, _ = _unwrap({"data": {"other": []}}, "markets")
        assert items == []

    def test_drifted_payload_fails_closed(self):
        items, _ = _unwrap({"data": {"markets": "not-a-list"}}, "markets")
        assert items is None
        items, _ = _unwrap("garbage", "markets")
        assert items is None


class TestSchemaDriftCommands:
    @patch("sports_skills.prophetx._connector._request")
    def test_markets_drift_fails_closed(self, mock_request):
        mock_request.return_value = {"data": {"markets": "not-a-list"}}
        result = get_markets({"params": {"event_id": 1}})
        assert result["status"] is False
        assert "schema drift" in result["message"]

    @patch("sports_skills.prophetx._connector._request")
    def test_tournaments_drift_fails_closed(self, mock_request):
        mock_request.return_value = {"data": {"tournaments": 42}}
        result = get_tournaments({"params": {}})
        assert result["status"] is False
        assert "schema drift" in result["message"]


# ============================================================
# HTTP layer: retries, backoff, 403 fail-closed, malformed JSON, caching
# ============================================================


def _http_error(code, body=b'{"error":"boom","error_code":10001}', headers=None):
    return urllib.error.HTTPError(
        url="https://cash.api.prophetx.co/x",
        code=code,
        msg="err",
        hdrs=headers,
        fp=io.BytesIO(body),
    )


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestRequestLayer:
    @patch("sports_skills.prophetx._connector.time.sleep")
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_retries_on_5xx_then_succeeds(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            _http_error(503),
            _FakeResponse(json.dumps({"data": {"tournaments": []}}).encode()),
        ]
        result = _request("/v1/tournaments", ttl=0)
        assert result == {"data": {"tournaments": []}}
        assert mock_urlopen.call_count == 2
        assert mock_sleep.called  # backoff happened

    @patch("sports_skills.prophetx._connector.time.sleep")
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_429_retries_then_gives_up(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [_http_error(429), _http_error(429), _http_error(429)]
        result = _request("/v1/tournaments", ttl=0)
        assert result["error"] is True
        assert result["status_code"] == 429
        assert mock_urlopen.call_count == 3  # initial + 2 retries

    @patch("sports_skills.prophetx._connector.time.sleep")
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_403_fails_closed_without_retry(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [_http_error(403)]
        result = _request("/v1/tournaments", ttl=0)
        assert result["error"] is True
        assert result["status_code"] == 403
        assert "Not retrying" in result["message"]
        assert mock_urlopen.call_count == 1

    @patch("sports_skills.prophetx._connector.time.sleep")
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_404_no_retry(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [_http_error(404)]
        result = _request("/v1/events/999999999/markets", ttl=0)
        assert result["error"] is True
        assert result["status_code"] == 404
        assert "10001" in result["message"]
        assert mock_urlopen.call_count == 1

    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_malformed_json_is_error_envelope(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"<html>WAF says hi</html>")
        result = _request("/v1/tournaments", ttl=0)
        assert result["error"] is True
        assert "Malformed JSON" in result["message"]

    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_caching_second_call_skips_network(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"data": {"tournaments": []}}).encode())
        first = _request("/v1/tournaments", params={"limit": 5}, ttl=300)
        second = _request("/v1/tournaments", params={"limit": 5}, ttl=300)
        assert first == second
        assert mock_urlopen.call_count == 1

    @patch("sports_skills.prophetx._connector._rate_limiter.acquire")
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_throttle_acquired_per_network_call(self, mock_urlopen, mock_acquire):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"data": {"tournaments": []}}).encode())
        _request("/v1/tournaments", ttl=0)
        assert mock_acquire.called

    def test_rate_limiter_is_conservative(self):
        assert _connector._rate_limiter.max_tokens <= 4
        assert _connector._rate_limiter.refill_rate <= 2.0


# ============================================================
# Read-only guard (unsupported write attempts)
# ============================================================


class TestReadOnlyGuard:
    @patch("sports_skills.prophetx._connector.urllib.request.urlopen")
    def test_requests_are_get_and_unauthenticated(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"data": {"tournaments": []}}).encode())
        _request("/v1/tournaments", ttl=0)
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_method() == "GET"
        assert not request_obj.has_header("Authorization")

    def test_no_write_commands_exposed(self):
        import sports_skills.prophetx as prophetx

        public = [name for name in dir(prophetx) if not name.startswith("_")]
        forbidden = ("place", "create", "cancel", "order", "wager", "trade", "bet")
        for name in public:
            assert not any(word in name.lower() for word in forbidden), name


# ============================================================
# Pagination
# ============================================================


class TestPagination:
    @patch("sports_skills.prophetx._connector._request")
    def test_tournaments_follow_int_cursor(self, mock_request):
        page1 = _tournaments_page([_tournament(i, f"T{i}", 1, "Soccer") for i in range(1, 51)], 50)
        page2 = _tournaments_page([_tournament(i, f"T{i}", 1, "Soccer") for i in range(51, 61)], None)
        mock_request.side_effect = [page1, page2]

        result = get_tournaments({"params": {"limit": 60}})
        assert result["status"] is True
        assert result["data"]["count"] == 60
        assert mock_request.call_count == 2
        second_params = mock_request.call_args_list[1].kwargs.get("params") or mock_request.call_args_list[1][0][1]
        assert second_params["next"] == 50

    @patch("sports_skills.prophetx._connector._request")
    def test_limit_stops_paging(self, mock_request):
        page1 = _tournaments_page([_tournament(i, f"T{i}", 1, "Soccer") for i in range(1, 11)], 10)
        mock_request.side_effect = [page1]
        result = get_tournaments({"params": {"limit": 10}})
        assert result["status"] is True
        assert mock_request.call_count == 1

    @patch("sports_skills.prophetx._connector._request")
    def test_events_follow_string_cursor_and_partial_on_later_failure(self, mock_request):
        page1 = {"next": "1765662000_19742", "data": [_event(i) for i in range(1, 51)]}
        boom = {"error": True, "status_code": 500, "message": "upstream"}
        mock_request.side_effect = [page1, boom]

        from sports_skills.prophetx._connector import get_events

        result = get_events({"params": {"tournament_id": 27, "limit": 100}})
        assert result["status"] is True
        assert result["data"]["count"] == 50  # partial preserved

    @patch("sports_skills.prophetx._connector._request")
    def test_first_page_failure_is_error(self, mock_request):
        mock_request.return_value = {"error": True, "status_code": 503, "message": "down"}
        from sports_skills.prophetx._connector import get_events

        result = get_events({"params": {"tournament_id": 27}})
        assert result["status"] is False
        assert "503" in result["message"]


# ============================================================
# Empty results
# ============================================================


class TestEmptyResults:
    @patch("sports_skills.prophetx._connector._request")
    def test_tournament_without_events_empty_body(self, mock_request):
        mock_request.return_value = {}
        from sports_skills.prophetx._connector import get_events

        result = get_events({"params": {"tournament_id": 4}})
        assert result["status"] is True
        assert result["data"]["events"] == []
        assert result["data"]["count"] == 0


# ============================================================
# v2 -> v1 fallback
# ============================================================


class TestV2Fallback:
    @patch("sports_skills.prophetx._connector._request")
    def test_v2_error_falls_back_to_v1(self, mock_request):
        def route(endpoint, params=None, ttl=60):
            if endpoint.startswith("/v2/"):
                return {"error": True, "status_code": 500, "message": "v2 down"}
            return {"data": {"markets": [_market_v1()]}}

        mock_request.side_effect = route
        result = get_markets({"params": {"event_id": 19742, "api_version": "v2"}})
        assert result["status"] is True
        assert result["data"]["api_version"] == "v1"
        assert "fell back" in result["message"]

    @patch("sports_skills.prophetx._connector._request")
    def test_v2_drift_falls_back_to_v1(self, mock_request):
        def route(endpoint, params=None, ttl=60):
            if endpoint.startswith("/v2/"):
                return {"data": {"markets": "drifted"}}
            return {"data": {"markets": [_market_v1()]}}

        mock_request.side_effect = route
        result = get_markets({"params": {"event_id": 19742, "api_version": "v2"}})
        assert result["status"] is True
        assert result["data"]["api_version"] == "v1"

    @patch("sports_skills.prophetx._connector._request")
    def test_v2_success_stays_v2(self, mock_request):
        mock_request.return_value = {"data": {"markets": [_market_v2()]}}
        result = get_markets({"params": {"event_id": 19742, "api_version": "v2"}})
        assert result["status"] is True
        assert result["data"]["api_version"] == "v2"
        market = result["data"]["markets"][0]
        assert market["category"] == "Game Lines"
        assert market["market_lines"][0]["outcomes"][0]["line"] == -2.5

    def test_invalid_api_version_rejected(self):
        result = get_markets({"params": {"event_id": 1, "api_version": "v3"}})
        assert result["status"] is False


# ============================================================
# Normalization
# ============================================================


class TestNormalization:
    def test_event_home_away_by_seq(self):
        normalized = _normalize_event(_event(19742))
        assert normalized["home"] == "Philadelphia Eagles"
        assert normalized["away"] == "Cincinnati Bengals"
        assert normalized["tournament"] == "NFL"
        assert normalized["scheduled"] == "2026-08-13T23:00:00Z"
        assert normalized["_raw"]["venue"]["countryCode"] == "<nil>"
        assert normalized["retrieved_at"]
        assert "prophetx.co" in normalized["source_url"]

    def test_market_key_combines_event_and_type_id(self):
        normalized = _normalize_market(_market_v1(19742), api_version="v1")
        assert normalized["id"] == 219
        assert normalized["market_key"] == "19742:219"
        assert normalized["event_id"] == 19742
        assert normalized["type"] == "moneyline"
        assert normalized["total_stake"] == pytest.approx(7156.79, abs=0.01)

    def test_null_selections_tolerated(self):
        normalized = _normalize_market(_market_v1(), api_version="v1")
        assert normalized["selections_available"] is False
        for outcome in normalized["outcomes"]:
            assert outcome.get("selections") is None
            assert "odds_american" not in outcome

    def test_populated_selection_derives_probability(self):
        market = _market_v1()
        market["selections"] = [{"odds": -150, "stake": 100}, {"odds": 130, "stake": 50}]
        normalized = _normalize_market(market, api_version="v1")
        assert normalized["selections_available"] is True
        fav, dog = normalized["outcomes"]
        assert fav["selections"]["odds_american"] == -150
        assert fav["selections"]["implied_probability"] == 0.6
        assert dog["selections"]["implied_probability"] == pytest.approx(0.4348, abs=0.0001)
        assert fav["selections"]["_raw"] == {"odds": -150, "stake": 100}

    def test_american_to_probability(self):
        assert _american_to_probability(-150) == 0.6
        assert _american_to_probability(100) == 0.5
        assert _american_to_probability(0) is None
        assert _american_to_probability("n/a") is None


# ============================================================
# get_market (filter from event payload)
# ============================================================


class TestGetMarket:
    @patch("sports_skills.prophetx._connector._request")
    def test_finds_by_id_and_key(self, mock_request):
        mock_request.return_value = {"data": {"markets": [_market_v1(19742)]}}
        by_id = get_market({"params": {"event_id": 19742, "market_id": 219}})
        assert by_id["status"] is True
        by_key = get_market({"params": {"event_id": 19742, "market_id": "19742:219"}})
        assert by_key["status"] is True

    @patch("sports_skills.prophetx._connector._request")
    def test_missing_market_errors(self, mock_request):
        mock_request.return_value = {"data": {"markets": [_market_v1(19742)]}}
        result = get_market({"params": {"event_id": 19742, "market_id": 999}})
        assert result["status"] is False
        assert "not found" in result["message"]

    def test_required_params(self):
        assert get_market({"params": {"market_id": 1}})["status"] is False
        assert get_market({"params": {"event_id": 1}})["status"] is False


# ============================================================
# Composite commands
# ============================================================


class TestSearchAndToday:
    def _route(self, endpoint, params=None, ttl=60):
        if endpoint == "/v1/tournaments":
            return _tournaments_page(
                [
                    _tournament(27, "NFL", 16, "American Football"),
                    _tournament(3, "MLB", 3, "Baseball"),
                ],
                None,
            )
        if endpoint.startswith("/v1/tournaments/27/events"):
            return {"next": None, "data": [_event(19742)]}
        if endpoint.startswith("/v1/tournaments/3/events"):
            return {"next": None, "data": []}
        if endpoint.startswith("/v1/events/19742/markets"):
            return {"data": {"markets": [_market_v1(19742)]}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    @patch("sports_skills.prophetx._connector._request")
    def test_search_by_sport_and_query(self, mock_request):
        mock_request.side_effect = self._route
        result = search_markets({"params": {"sport": "nfl", "query": "eagles"}})
        assert result["status"] is True
        assert result["data"]["count"] == 1
        market = result["data"]["markets"][0]
        assert market["event_name"] == "Bengals at Eagles"
        assert market["tournament"] == "NFL"

    @patch("sports_skills.prophetx._connector._request")
    def test_search_unknown_sport_errors(self, mock_request):
        result = search_markets({"params": {"sport": "quidditch"}})
        assert result["status"] is False
        assert "Unknown sport" in result["message"]
        assert mock_request.call_count == 0

    @patch("sports_skills.prophetx._connector._request")
    def test_search_no_match_is_empty_success(self, mock_request):
        mock_request.side_effect = self._route
        result = search_markets({"params": {"sport": "nfl", "query": "zebras"}})
        assert result["status"] is True
        assert result["data"]["markets"] == []

    @patch("sports_skills.prophetx._connector._connector_today", create=True)
    @patch("sports_skills.prophetx._connector._request")
    def test_todays_events_filters_by_utc_date(self, mock_request, _):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")

        def route(endpoint, params=None, ttl=60):
            if endpoint == "/v1/tournaments":
                return _tournaments_page([_tournament(27, "NFL", 16, "American Football")], None)
            if endpoint.startswith("/v1/tournaments/27/events"):
                return {
                    "next": None,
                    "data": [
                        _event(1, scheduled=today),
                        _event(2, scheduled="2020-01-01T12:00:00Z"),
                    ],
                }
            raise AssertionError(f"unexpected endpoint {endpoint}")

        mock_request.side_effect = route
        result = get_todays_events({"params": {"sport": "nfl"}})
        assert result["status"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["events"][0]["id"] == 1

    @patch("sports_skills.prophetx._connector._request")
    def test_sports_config_groups_by_sport(self, mock_request):
        mock_request.return_value = _tournaments_page(
            [
                _tournament(27, "NFL", 16, "American Football"),
                _tournament(1, "Premier League", 1, "Soccer"),
                _tournament(2, "La Liga", 1, "Soccer"),
            ],
            None,
        )
        result = get_sports_config({"params": {}})
        assert result["status"] is True
        codes = {s["sport"] for s in result["data"]["sports"]}
        assert {"american-football", "soccer"} <= codes
        soccer = next(s for s in result["data"]["sports"] if s["sport"] == "soccer")
        assert len(soccer["tournaments"]) == 2
        assert result["data"]["aliases"]["nfl"] == "american-football"


# ============================================================
# Opt-in live smoke test (bounded; never runs in CI by default)
# ============================================================


@pytest.mark.skipif(
    not os.getenv("PROPHETX_LIVE_SMOKE"),
    reason="live smoke is opt-in: set PROPHETX_LIVE_SMOKE=1",
)
class TestLiveSmoke:
    def test_tournaments_events_markets_chain(self):
        tournaments = get_tournaments({"params": {"limit": 10}})
        assert tournaments["status"] is True
        assert tournaments["data"]["count"] > 0

        from sports_skills.prophetx._connector import get_events

        first_events = None
        for tournament in tournaments["data"]["tournaments"]:
            events = get_events({"params": {"tournament_id": tournament["id"], "limit": 5}})
            assert events["status"] is True
            if events["data"]["count"]:
                first_events = events
                break
        assert first_events is not None, "no tournament with events found in first page"

        event_id = first_events["data"]["events"][0]["id"]
        markets = get_markets({"params": {"event_id": event_id}})
        assert markets["status"] is True
        assert isinstance(markets["data"]["markets"], list)

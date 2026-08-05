"""Unit tests for the esports skill + esports odds filters (no network).

Covers the pure-logic pieces the connectors depend on: OpenDota/Leaguepedia
normalization, the Cargo in-body-error path, input validation (tier, match_id,
region escaping), the token-bucket rate limiter, the TTL cache eviction cap, and
the Kalshi/Polymarket esports odds accessors.
"""

from unittest.mock import patch

import sports_skills.esports._connector as ec
from sports_skills.esports._connector import (
    _cargo_rows,
    _RateLimiter,
    _safe_float,
    get_leagues,
    get_lol_tournaments,
    get_match,
    get_pro_matches,
    lol_cargo_query,
)

# ---------------------------------------------------------------- helpers


class TestSafeFloat:
    def test_parses_number(self):
        assert _safe_float("1.5") == 1.5

    def test_blank_and_none_return_default(self):
        assert _safe_float("") is None
        assert _safe_float(None) is None
        assert _safe_float("", default=0) == 0

    def test_malformed_returns_default(self):
        assert _safe_float("n/a") is None


class TestCargoRows:
    def test_unwraps_titles_and_drops_precision_keys(self):
        resp = {
            "cargoquery": [
                {"title": {"Name": "Worlds", "DateStart": "2026-10-01", "X__precision": 3}},
                {"title": {"Name": "MSI"}},
            ]
        }
        rows = _cargo_rows(resp)
        assert rows == [{"Name": "Worlds", "DateStart": "2026-10-01"}, {"Name": "MSI"}]

    def test_empty(self):
        assert _cargo_rows({}) == []


# ---------------------------------------------------------------- rate limiter


class TestRateLimiter:
    def test_returns_immediately_when_tokens_available(self):
        rl = _RateLimiter(max_tokens=2, refill_rate=1.0)
        with patch("sports_skills.esports._connector.time.sleep") as slept:
            rl.acquire()
            rl.acquire()
        slept.assert_not_called()
        assert rl.tokens < 1

    def test_sleeps_and_returns_when_exhausted(self):
        # One token: the 2nd acquire must wait, not recurse forever. The clock is
        # frozen so the bucket cannot refill between the two acquires — with a
        # real clock, any ≥1ms hiccup (refill_rate=1000/s) refilled the bucket
        # and the second acquire sailed through without sleeping, which made this
        # test flake on loaded CI runners. Only the mocked sleep advances time.
        rl = _RateLimiter(max_tokens=1, refill_rate=1000.0)
        fake_now = [rl.last_refill]

        def advance(seconds):
            fake_now[0] += max(seconds, 0.001)

        with patch(
            "sports_skills.esports._connector.time.monotonic",
            side_effect=lambda: fake_now[0],
        ):
            rl.acquire()  # consumes the only token; no time passes
            with patch(
                "sports_skills.esports._connector.time.sleep", side_effect=advance
            ) as slept:
                rl.acquire()  # must sleep — sleeping is what refills the bucket
        assert slept.called


# ---------------------------------------------------------------- cache cap


class TestCacheEviction:
    def test_hard_cap_on_live_entries(self):
        with ec._cache_lock:
            ec._cache.clear()
        # Insert well past the 500 cap with long TTLs (all live).
        for i in range(520):
            ec._cache_set(f"k{i}", i, ttl=3600)
        assert len(ec._cache) <= 500
        with ec._cache_lock:
            ec._cache.clear()


# ---------------------------------------------------------------- OpenDota


class TestGetProMatches:
    @patch("sports_skills.esports._connector._opendota_get")
    def test_normalizes_matches(self, mock_get):
        mock_get.return_value = [
            {
                "match_id": 1,
                "radiant_name": "Team A",
                "dire_name": "Team B",
                "radiant_win": True,
                "radiant_score": 30,
                "dire_score": 20,
            }
        ]
        out = get_pro_matches({"params": {"limit": 5}})
        assert out["status"] is True
        m = out["data"]["matches"][0]
        assert m["radiant"]["name"] == "Team A"
        assert m["radiant_win"] is True

    @patch("sports_skills.esports._connector._opendota_get")
    def test_http_error_surfaces_gracefully(self, mock_get):
        mock_get.return_value = {"error": True, "status_code": 429, "message": "rate limited"}
        out = get_pro_matches({"params": {}})
        assert out["status"] is False
        assert "429" in out["message"]

    @patch("sports_skills.esports._connector._opendota_get")
    def test_non_list_body_yields_empty(self, mock_get):
        mock_get.return_value = {"unexpected": "shape"}
        out = get_pro_matches({"params": {}})
        assert out["status"] is True
        assert out["data"]["count"] == 0


class TestGetLeaguesTierValidation:
    def test_unknown_tier_rejected(self):
        out = get_leagues({"params": {"tier": "platinum"}})
        assert out["status"] is False
        assert "Unknown tier" in out["message"]

    @patch("sports_skills.esports._connector._opendota_get")
    def test_valid_tier_filters(self, mock_get):
        mock_get.return_value = [
            {"leagueid": 1, "name": "Premium Cup", "tier": "premium"},
            {"leagueid": 2, "name": "Amateur", "tier": "professional"},
        ]
        out = get_leagues({"params": {"tier": "premium"}})
        assert out["status"] is True
        assert out["data"]["count"] == 1
        assert out["data"]["leagues"][0]["name"] == "Premium Cup"


class TestGetMatchValidation:
    def test_missing_match_id(self):
        assert get_match({"params": {}})["status"] is False

    def test_non_numeric_match_id_rejected(self):
        # Path-injection guard: only digits reach the URL.
        out = get_match({"params": {"match_id": "../teams"}})
        assert out["status"] is False
        assert "Invalid match_id" in out["message"]

    @patch("sports_skills.esports._connector._opendota_get")
    def test_valid_match(self, mock_get):
        mock_get.return_value = {
            "match_id": 123,
            "radiant_win": True,
            "players": [{"account_id": 9, "player_slot": 1, "kills": 5}],
        }
        out = get_match({"params": {"match_id": "123"}})
        assert out["status"] is True
        assert out["data"]["players"][0]["is_radiant"] is True

    @patch("sports_skills.esports._connector._opendota_get")
    def test_not_found(self, mock_get):
        mock_get.return_value = {"error_msg": "not found"}
        out = get_match({"params": {"match_id": "999"}})
        assert out["status"] is False
        assert "not found" in out["message"].lower()


# ---------------------------------------------------------------- Leaguepedia


class TestLolCargoQuery:
    def test_requires_tables_and_fields(self):
        assert lol_cargo_query({"params": {"tables": "Tournaments"}})["status"] is False

    @patch("sports_skills.esports._connector._leaguepedia_get")
    def test_in_body_error_on_http_200_surfaced(self, mock_get):
        # Leaguepedia's throttle arrives as an in-body error on HTTP 200.
        mock_get.return_value = {"error": {"code": "ratelimited", "info": "exceeded rate limit"}}
        out = lol_cargo_query({"params": {"tables": "Tournaments", "fields": "Name"}})
        assert out["status"] is False
        assert "Leaguepedia API error" in out["message"]
        assert "exceeded rate limit" in out["message"]

    @patch("sports_skills.esports._connector._leaguepedia_get")
    def test_rows_returned(self, mock_get):
        mock_get.return_value = {"cargoquery": [{"title": {"Name": "Worlds 2026"}}]}
        out = lol_cargo_query({"params": {"tables": "Tournaments", "fields": "Name"}})
        assert out["status"] is True
        assert out["data"]["rows"] == [{"Name": "Worlds 2026"}]


class TestGetLolTournamentsRegionEscaping:
    @patch("sports_skills.esports._connector._leaguepedia_get")
    def test_region_single_quote_escaped(self, mock_get):
        mock_get.return_value = {"cargoquery": []}
        get_lol_tournaments({"params": {"region": "Ivan's Region"}})
        # The WHERE clause passed to Leaguepedia must have the quote doubled.
        sent = mock_get.call_args[0][0]
        assert sent["where"] == "Tournaments.Region='Ivan''s Region'"


# ---------------------------------------------------------------- Kalshi odds


class TestKalshiEsportsOdds:
    @patch("sports_skills.kalshi._connector._request")
    def test_prices_are_cents_and_derive_probability(self, mock_request):
        # Post-migration markets carry only *_dollars; output must be 0-100 cents.
        mock_request.return_value = {
            "markets": [
                {
                    "ticker": "KXCS2GAME-A",
                    "last_price_dollars": "0.3100",
                    "yes_bid_dollars": "0.3000",
                    "yes_ask_dollars": "0.3200",
                    "volume_fp": "500.0",
                    "open_interest": 42,
                    "status": "active",
                }
            ]
        }
        from sports_skills.kalshi._connector import get_esports_odds

        out = get_esports_odds({"params": {"game": "cs2"}})
        assert out["status"] is True
        m = out["data"]["markets"][0]
        assert m["last_price"] == 31  # cents (0.3100 -> 31), same scale as search_markets
        assert m["yes_bid"] == 30
        assert m["implied_probability"] == 0.31
        assert m["decimal_odds"] == round(100 / 31, 2)
        assert m["volume"] == 500.0
        assert m["open_interest"] == 42
        assert "volume_24h" not in m  # dropped the non-existent *_fp field

    @patch("sports_skills.kalshi._connector._request")
    def test_midpoint_fallback_when_no_last(self, mock_request):
        mock_request.return_value = {
            "markets": [{"ticker": "X", "yes_bid_dollars": "0.4000", "yes_ask_dollars": "0.5000"}]
        }
        from sports_skills.kalshi._connector import get_esports_odds

        m = get_esports_odds({"params": {"game": "lol"}})["data"]["markets"][0]
        assert m["last_price"] == 0
        assert m["implied_probability"] == 0.45  # midpoint of 40/50 cents

    @patch("sports_skills.kalshi._connector._request")
    def test_no_price_data_yields_none_odds_not_crash(self, mock_request):
        mock_request.return_value = {"markets": [{"ticker": "X"}]}
        from sports_skills.kalshi._connector import get_esports_odds

        m = get_esports_odds({"params": {"game": "dota2"}})["data"]["markets"][0]
        assert m["implied_probability"] is None
        assert m["decimal_odds"] is None

    def test_unknown_game_rejected(self):
        from sports_skills.kalshi._connector import get_esports_odds

        out = get_esports_odds({"params": {"game": "valorant"}})
        assert out["status"] is False
        assert "Unknown game" in out["message"]

    def test_esports_series_derived_from_kalshi_series(self):
        from sports_skills.kalshi._connector import ESPORTS_SERIES, KALSHI_SERIES

        for g in ("cs2", "lol", "dota2"):
            assert ESPORTS_SERIES[g] == KALSHI_SERIES[g][0]


# ---------------------------------------------------------------- Polymarket


class TestPolymarketEsportsEvents:
    @patch("sports_skills.polymarket._connector._gamma_request")
    def test_non_dict_elements_skipped(self, mock_request):
        mock_request.return_value = [
            {"title": "LoL Worlds Final", "slug": "lol-worlds"},
            "garbage-non-dict-element",
            None,
        ]
        from sports_skills.polymarket._connector import get_esports_events

        out = get_esports_events({"params": {}})
        assert out["status"] is True
        # Only the one valid dict event is normalized; no crash on the junk.
        assert out["data"]["count"] == 1

    @patch("sports_skills.polymarket._connector._gamma_request")
    def test_query_filter(self, mock_request):
        mock_request.return_value = [
            {"title": "LoL Worlds Final", "slug": "lol-worlds"},
            {"title": "CS2 Major", "slug": "cs2-major"},
        ]
        from sports_skills.polymarket._connector import get_esports_events

        out = get_esports_events({"params": {"query": "lol"}})
        assert out["data"]["count"] == 1

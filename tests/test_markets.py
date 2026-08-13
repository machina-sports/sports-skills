"""Tests for markets orchestration module."""

from unittest.mock import MagicMock, patch

import pytest

from sports_skills.markets._connector import (
    KALSHI_SERIES,
    MATCH_THRESHOLD,
    META_SPORT_ALIASES,
    META_SPORTS,
    POLYMARKET_SPORTS,
    SCOREBOARD_SPORTS,
    _best_matches,
    _extract_games,
    _match_score,
    _normalize_name,
    _normalize_price,
    _parse_kalshi_event_tail,
    _success_partial,
    compare_odds,
    evaluate_market,
    get_live_tick,
    get_mock_tick,
    get_plays_near_timestamp,
    get_sport_markets,
    get_sport_schedule,
    get_todays_markets,
    normalize_price,
    resolve_game_market,
    search_entity,
)

# ============================================================
# Name Normalization
# ============================================================


class TestNormalizeName:
    def test_lowercase(self):
        assert _normalize_name("Kansas City Chiefs") == "kansas city chiefs"

    def test_strip_punctuation(self):
        assert _normalize_name("L.A. Lakers") == "la lakers"

    def test_collapse_whitespace(self):
        assert _normalize_name("  New   York   Knicks  ") == "new york knicks"

    def test_empty(self):
        assert _normalize_name("") == ""

    def test_mixed(self):
        assert _normalize_name("St. Louis Blues!") == "st louis blues"


# ============================================================
# Match Score
# ============================================================


class TestMatchScore:
    def test_exact_match(self):
        assert _match_score("Lakers", "Lakers") == 1.0

    def test_case_insensitive(self):
        assert _match_score("lakers", "LAKERS") == 1.0

    def test_substring_containment(self):
        # "Chiefs" in "Kansas City Chiefs" → high score
        score = _match_score("Chiefs", "Kansas City Chiefs")
        assert score >= 0.85

    def test_substring_reverse(self):
        # "Kansas City Chiefs" contains "Chiefs"
        score = _match_score("Kansas City Chiefs", "Chiefs")
        assert score >= 0.85

    def test_no_match(self):
        score = _match_score("Chiefs", "New York Yankees")
        assert score < MATCH_THRESHOLD

    def test_similar_names(self):
        score = _match_score("LA Lakers", "Los Angeles Lakers")
        assert score >= MATCH_THRESHOLD

    def test_empty_query(self):
        assert _match_score("", "Lakers") == 0.0

    def test_empty_candidate(self):
        assert _match_score("Lakers", "") == 0.0

    def test_both_empty(self):
        assert _match_score("", "") == 0.0


# ============================================================
# Best Matches
# ============================================================


class TestBestMatches:
    def test_filters_by_threshold(self):
        candidates = [
            {"name": "Kansas City Chiefs"},
            {"name": "Chicago Bears"},
            {"name": "Green Bay Packers"},
        ]
        results = _best_matches("Chiefs", candidates, "name")
        assert len(results) == 1
        assert results[0]["name"] == "Kansas City Chiefs"

    def test_sorts_by_score(self):
        candidates = [
            {"name": "New York Giants"},
            {"name": "New York Knicks"},
            {"name": "Knicks"},
        ]
        results = _best_matches("Knicks", candidates, "name")
        # "Knicks" exact match should be first
        assert results[0]["name"] == "Knicks"

    def test_respects_limit(self):
        candidates = [{"name": f"Team {i}"} for i in range(20)]
        # With substring matching on "Team"
        results = _best_matches("Team", candidates, "name", limit=3)
        assert len(results) <= 3

    def test_empty_candidates(self):
        results = _best_matches("Lakers", [], "name")
        assert results == []


# ============================================================
# Mapping Tables
# ============================================================


class TestMappingTables:
    def test_kalshi_series_contains_us_sports(self):
        us_sports = {"nfl", "nba", "mlb", "nhl", "wnba", "cfb", "cbb"}
        assert us_sports.issubset(set(KALSHI_SERIES.keys()))

    def test_kalshi_series_contains_football(self):
        football_sports = {"epl", "ucl", "laliga", "bundesliga", "seriea", "ligue1", "mls"}
        assert football_sports.issubset(set(KALSHI_SERIES.keys()))

    def test_worldcup_on_both_venues(self):
        # FIFA World Cup 2026 markets live in dedicated Kalshi series and a
        # dedicated Polymarket sport code (fifwc); neither is reachable via
        # keyword search alone.
        assert KALSHI_SERIES["worldcup"] == "KXWCGAME"
        assert POLYMARKET_SPORTS["worldcup"] == "fifwc"

    def test_kalshi_series_values_are_strings(self):
        for series in KALSHI_SERIES.values():
            assert isinstance(series, str)
            assert series.startswith("KX")

    def test_scoreboard_sports(self):
        assert {"nfl", "nba", "mlb", "nhl", "wnba", "cfb", "cbb"} == SCOREBOARD_SPORTS

    def test_scoreboard_sports_have_kalshi_series(self):
        # Every ESPN scoreboard sport should have a Kalshi series mapping
        assert SCOREBOARD_SPORTS.issubset(set(KALSHI_SERIES.keys()))


# ============================================================
# Price Normalization (no mocking needed)
# ============================================================


class TestNormalizePrice:
    def test_polymarket_price(self):
        result = _normalize_price(0.65, "polymarket")
        assert abs(result["implied_probability"] - 0.65) < 0.001
        assert result["american"] < 0  # Favorite
        assert result["decimal"] > 1
        assert result["source"] == "polymarket"

    def test_kalshi_price_0_to_100(self):
        # Kalshi returns 0-100 integers
        result = _normalize_price(65, "kalshi")
        assert abs(result["implied_probability"] - 0.65) < 0.001
        assert result["source"] == "kalshi"

    def test_kalshi_price_0_to_1(self):
        # Also handle 0-1 format
        result = _normalize_price(0.65, "kalshi")
        assert abs(result["implied_probability"] - 0.65) < 0.001

    def test_espn_american_negative(self):
        # -150 → 60% implied probability
        result = _normalize_price(-150, "espn")
        assert abs(result["implied_probability"] - 0.6) < 0.001
        assert result["source"] == "espn"

    def test_espn_american_positive(self):
        # +130 → ~43.5% implied probability
        result = _normalize_price(130, "espn")
        assert abs(result["implied_probability"] - 0.4348) < 0.001

    def test_unknown_source(self):
        result = _normalize_price(0.5, "unknown")
        assert result["implied_probability"] == 0.0

    def test_edge_case_zero_prob(self):
        result = _normalize_price(0, "polymarket")
        assert result["implied_probability"] == 0

    def test_edge_case_one_prob(self):
        result = _normalize_price(1.0, "polymarket")
        assert result["implied_probability"] == 1.0


# ============================================================
# Normalize Price CLI Command
# ============================================================


class TestNormalizePriceCommand:
    def test_valid_polymarket(self):
        result = normalize_price({"params": {"price": 0.65, "source": "polymarket"}})
        assert result["status"] is True
        assert abs(result["data"]["implied_probability"] - 0.65) < 0.001

    def test_valid_kalshi(self):
        result = normalize_price({"params": {"price": 65, "source": "kalshi"}})
        assert result["status"] is True

    def test_valid_espn(self):
        result = normalize_price({"params": {"price": -150, "source": "espn"}})
        assert result["status"] is True

    def test_invalid_source(self):
        result = normalize_price({"params": {"price": 0.5, "source": "draftkings"}})
        assert result["status"] is False

    def test_invalid_price(self):
        result = normalize_price({"params": {"price": "abc", "source": "polymarket"}})
        assert result["status"] is False


# ============================================================
# Success Partial
# ============================================================


class TestSuccessPartial:
    def test_no_warnings(self):
        result = _success_partial({"key": "value"}, [], "msg")
        assert result["status"] is True
        assert "warnings" not in result["data"]

    def test_with_warnings(self):
        result = _success_partial({"key": "value"}, ["oops"], "msg")
        assert result["status"] is True
        assert result["data"]["warnings"] == ["oops"]


# ============================================================
# Extract Games from Scoreboard
# ============================================================


class TestExtractGames:
    def test_extracts_from_valid_scoreboard(self):
        scoreboard = {
            "status": True,
            "data": {
                "events": [
                    {
                        "id": "401234567",
                        "name": "Los Angeles Lakers at Boston Celtics",
                        "short_name": "LAL @ BOS",
                        "start_time": "2025-02-26T00:00:00Z",
                        "status": "scheduled",
                        "status_detail": "7:30 PM ET",
                        "competitors": [
                            {
                                "team": {"name": "Boston Celtics", "abbreviation": "BOS", "id": "2"},
                                "home_away": "home",
                            },
                            {
                                "team": {"name": "Los Angeles Lakers", "abbreviation": "LAL", "id": "13"},
                                "home_away": "away",
                            },
                        ],
                        "odds": {"home_odds": "-150", "away_odds": "+130"},
                    }
                ]
            },
        }
        games = _extract_games("nba", scoreboard)
        assert len(games) == 1
        assert games[0]["sport"] == "nba"
        assert games[0]["event_id"] == "401234567"
        assert games[0]["home"]["name"] == "Boston Celtics"
        assert games[0]["away"]["name"] == "Los Angeles Lakers"

    def test_empty_events(self):
        scoreboard = {"status": True, "data": {"events": []}}
        games = _extract_games("nba", scoreboard)
        assert games == []

    def test_failed_response(self):
        scoreboard = {"status": False, "data": None, "message": "Error"}
        games = _extract_games("nba", scoreboard)
        assert games == []


# ============================================================
# Mocked: Schedule Fetching
# ============================================================


class TestFetchScheduleMocked:
    @patch("sports_skills.markets._connector._load_sport_module")
    def test_fetch_schedule_returns_games(self, mock_load):
        mock_mod = MagicMock()
        mock_mod.get_scoreboard.return_value = {
            "status": True,
            "data": {
                "events": [
                    {
                        "id": "123",
                        "name": "Game 1",
                        "short_name": "G1",
                        "start_time": "2025-02-26",
                        "status": "scheduled",
                        "status_detail": "",
                        "competitors": [
                            {"team": {"name": "Team A", "abbreviation": "TA", "id": "1"}, "home_away": "home"},
                            {"team": {"name": "Team B", "abbreviation": "TB", "id": "2"}, "home_away": "away"},
                        ],
                        "odds": {},
                    }
                ]
            },
        }
        mock_load.return_value = mock_mod

        from sports_skills.markets._connector import _fetch_schedule

        games = _fetch_schedule("nba", None)
        assert len(games) == 1
        assert games[0]["home"]["name"] == "Team A"
        assert games[0]["away"]["name"] == "Team B"

    @patch("sports_skills.markets._connector._load_sport_module")
    def test_fetch_schedule_handles_failure(self, mock_load):
        mock_load.return_value = None

        from sports_skills.markets._connector import _fetch_schedule

        games = _fetch_schedule("nba", None)
        assert games == []


# ============================================================
# Mocked: Search Entity
# ============================================================


class TestSearchEntityMocked:
    @patch("sports_skills.markets._connector._search_prophetx")
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    def test_search_entity_combines_results(self, mock_kalshi, mock_poly, mock_prophetx):
        mock_kalshi.return_value = [
            {"source": "kalshi", "title": "Lakers vs Celtics", "event_ticker": "EVT1", "markets": []}
        ]
        mock_poly.return_value = [{"source": "polymarket", "title": "Lakers Game", "market_id": "MKT1", "outcomes": []}]
        mock_prophetx.return_value = [
            {"source": "prophetx", "title": "Lakers at Celtics", "event_id": 1, "markets": []}
        ]

        result = search_entity({"params": {"query": "Lakers"}})
        assert result["status"] is True
        assert result["data"]["total_results"] == 3
        assert len(result["data"]["kalshi"]) == 1
        assert len(result["data"]["polymarket"]) == 1
        assert len(result["data"]["prophetx"]) == 1

    @patch("sports_skills.markets._connector._search_prophetx")
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    def test_search_entity_partial_failure(self, mock_kalshi, mock_poly, mock_prophetx):
        mock_kalshi.side_effect = Exception("Kalshi down")
        mock_poly.return_value = [{"source": "polymarket", "title": "Lakers Game", "market_id": "MKT1", "outcomes": []}]
        mock_prophetx.side_effect = Exception("ProphetX down")

        result = search_entity({"params": {"query": "Lakers"}})
        assert result["status"] is True
        assert len(result["data"]["polymarket"]) == 1
        assert result["data"]["prophetx"] == []
        assert "warnings" in result["data"]

    def test_search_entity_missing_query(self):
        result = search_entity({"params": {}})
        assert result["status"] is False


# ============================================================
# Mocked: Get Todays Markets
# ============================================================


class TestGetTodaysMarketsMocked:
    @patch("sports_skills.markets._connector._search_prophetx")
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    @patch("sports_skills.markets._connector._fetch_all_schedules")
    def test_returns_dashboard(self, mock_schedules, mock_kalshi, mock_poly, mock_prophetx):
        mock_schedules.return_value = (
            [
                {
                    "sport": "nba",
                    "event_id": "123",
                    "name": "Lakers at Celtics",
                    "short_name": "LAL @ BOS",
                    "start_time": "",
                    "status": "scheduled",
                    "status_detail": "",
                    "home": {"name": "Boston Celtics", "abbreviation": "BOS", "id": "2"},
                    "away": {"name": "Los Angeles Lakers", "abbreviation": "LAL", "id": "13"},
                    "espn_odds": {},
                }
            ],
            [],
        )
        mock_kalshi.return_value = []
        mock_poly.return_value = []

        result = get_todays_markets({"params": {"sport": "nba"}})
        assert result["status"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["markets_searched"] is True

    @patch("sports_skills.markets._connector._fetch_all_schedules")
    def test_no_games(self, mock_schedules):
        mock_schedules.return_value = ([], [])

        result = get_todays_markets({"params": {"sport": "nba"}})
        assert result["status"] is True
        assert result["data"]["count"] == 0
        assert result["data"]["markets_searched"] is False

    def test_invalid_sport(self):
        result = get_todays_markets({"params": {"sport": "cricket"}})
        assert result["status"] is False


# ============================================================
# Mocked: Get Sport Schedule
# ============================================================


class TestGetSportScheduleMocked:
    @patch("sports_skills.markets._connector._fetch_all_schedules")
    def test_single_sport(self, mock_schedules):
        mock_schedules.return_value = (
            [{"sport": "nba", "event_id": "1", "name": "Game"}],
            [],
        )
        result = get_sport_schedule({"params": {"sport": "nba"}})
        assert result["status"] is True
        assert result["data"]["count"] == 1

    def test_invalid_sport(self):
        result = get_sport_schedule({"params": {"sport": "curling"}})
        assert result["status"] is False


# ============================================================
# Mocked: Compare Odds
# ============================================================


class TestCompareOddsMocked:
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    @patch("sports_skills.markets._connector._load_sport_module")
    def test_compare_odds_pipeline(self, mock_load, mock_kalshi, mock_poly):
        mock_mod = MagicMock()
        mock_mod.get_game_summary.return_value = {
            "status": True,
            "data": {
                "competitors": [
                    {"team": {"name": "Boston Celtics"}, "home_away": "home"},
                    {"team": {"name": "Los Angeles Lakers"}, "home_away": "away"},
                ],
                "odds": {"home_odds": -150, "away_odds": 130},
            },
        }
        mock_load.return_value = mock_mod
        mock_kalshi.return_value = []
        mock_poly.return_value = [
            {
                "source": "polymarket",
                "title": "Celtics vs Lakers",
                "market_id": "M1",
                "outcomes": [
                    {"token_id": "T1", "outcome": "Yes", "price": 0.62},
                    {"token_id": "T2", "outcome": "No", "price": 0.38},
                ],
            }
        ]

        result = compare_odds({"params": {"sport": "nba", "event_id": "123"}})
        assert result["status"] is True
        assert result["data"]["home_team"] == "Boston Celtics"
        assert result["data"]["away_team"] == "Los Angeles Lakers"
        assert "espn_odds" in result["data"]

    def test_missing_sport(self):
        result = compare_odds({"params": {"event_id": "123"}})
        assert result["status"] is False

    def test_missing_event_id(self):
        result = compare_odds({"params": {"sport": "nba"}})
        assert result["status"] is False


# ============================================================
# Mocked: Evaluate Market
# ============================================================


class TestEvaluateMarketMocked:
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._load_sport_module")
    def test_evaluate_with_market_search(self, mock_load, mock_poly_search):
        mock_mod = MagicMock()
        mock_mod.get_game_summary.return_value = {
            "status": True,
            "data": {
                "competitors": [
                    {"team": {"name": "Boston Celtics"}, "home_away": "home"},
                    {"team": {"name": "Los Angeles Lakers"}, "home_away": "away"},
                ],
                "odds": {"home_odds": -150, "away_odds": 130},
            },
        }
        mock_load.return_value = mock_mod
        mock_poly_search.return_value = [
            {
                "source": "polymarket",
                "title": "Celtics Game",
                "market_id": "M1",
                "outcomes": [
                    {"token_id": "T1", "outcome": "Yes", "price": 0.52},
                ],
            }
        ]

        result = evaluate_market({"params": {"sport": "nba", "event_id": "123"}})
        assert result["status"] is True
        assert result["data"]["market_prob"] == 0.52
        assert result["data"]["evaluation"] is not None

    @patch("sports_skills.kalshi")
    @patch("sports_skills.markets._connector._load_sport_module")
    def test_evaluate_kalshi_dollars_only_payload(self, mock_load, mock_kalshi):
        # Raw get_market payloads post-migration carry only *_dollars fields;
        # evaluate_market must still derive a usable market probability.
        mock_mod = MagicMock()
        mock_mod.get_game_summary.return_value = {
            "status": True,
            "data": {
                "competitors": [
                    {"team": {"name": "Boston Celtics"}, "home_away": "home"},
                    {"team": {"name": "Los Angeles Lakers"}, "home_away": "away"},
                ],
                "odds": {"home_odds": -150, "away_odds": 130},
            },
        }
        mock_load.return_value = mock_mod
        mock_kalshi.get_market.return_value = {
            "status": True,
            "data": {"yes_bid_dollars": "0.1630", "last_price_dollars": "0.1680"},
        }

        result = evaluate_market({"params": {"sport": "nba", "event_id": "123", "kalshi_ticker": "KX-TEST"}})

        assert result["status"] is True
        assert result["data"]["market_prob"] == 0.16
        assert result["data"]["market_source"] == "kalshi"
        assert result["data"]["evaluation"] is not None

    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.kalshi")
    @patch("sports_skills.markets._connector._load_sport_module")
    def test_evaluate_kalshi_zero_price_falls_through_to_search(self, mock_load, mock_kalshi, mock_poly_search):
        # A zero/missing Kalshi price must leave market_prob as None so the
        # search fallback still runs (previously it was poisoned to 0.0).
        mock_mod = MagicMock()
        mock_mod.get_game_summary.return_value = {
            "status": True,
            "data": {
                "competitors": [
                    {"team": {"name": "Boston Celtics"}, "home_away": "home"},
                    {"team": {"name": "Los Angeles Lakers"}, "home_away": "away"},
                ],
                "odds": {"home_odds": -150, "away_odds": 130},
            },
        }
        mock_load.return_value = mock_mod
        mock_kalshi.get_market.return_value = {
            "status": True,
            "data": {"yes_bid_dollars": "0.0000"},
        }
        mock_poly_search.return_value = [
            {
                "source": "polymarket",
                "title": "Celtics Game",
                "market_id": "M1",
                "outcomes": [{"token_id": "T1", "outcome": "Yes", "price": 0.52}],
            }
        ]

        result = evaluate_market({"params": {"sport": "nba", "event_id": "123", "kalshi_ticker": "KX-TEST"}})

        assert result["status"] is True
        assert result["data"]["market_prob"] == 0.52
        assert result["data"]["market_source"] == "polymarket"

    @patch("sports_skills.markets._connector._load_sport_module")
    def test_evaluate_missing_odds(self, mock_load):
        mock_mod = MagicMock()
        mock_mod.get_game_summary.return_value = {
            "status": True,
            "data": {
                "competitors": [],
                "odds": {},
            },
        }
        mock_load.return_value = mock_mod

        result = evaluate_market({"params": {"sport": "nba", "event_id": "123"}})
        assert result["status"] is False

    def test_missing_sport(self):
        result = evaluate_market({"params": {"event_id": "123"}})
        assert result["status"] is False

    def test_missing_event_id(self):
        result = evaluate_market({"params": {"sport": "nba"}})
        assert result["status"] is False


# ============================================================
# Mocked: Get Sport Markets
# ============================================================


class TestGetSportMarketsMocked:
    def test_missing_sport(self):
        result = get_sport_markets({"params": {}})
        assert result["status"] is False


# ============================================================
# Meta-Sports (football fan-out)
# ============================================================


class TestMetaSports:
    def test_football_in_meta_sports(self):
        assert "football" in META_SPORTS
        spec = META_SPORTS["football"]
        # Each listed league must already be a real key on at least one venue,
        # otherwise the fan-out loop silently drops it.
        for league in spec["leagues"]:
            assert league in KALSHI_SERIES or league in POLYMARKET_SPORTS, league
        assert "FIFA" in spec.get("polymarket_keywords", [])
        # World Cup match markets ride along with the football fan-out.
        assert "worldcup" in spec["leagues"]

    def test_soccer_aliases_to_football(self):
        assert META_SPORT_ALIASES.get("soccer") == "football"


class TestKalshiWorldCupSeries:
    def test_kalshi_module_worldcup_series(self):
        # The kalshi module maps 'worldcup' to the full set of FIFA World Cup
        # 2026 series. Without these, search_markets falls back to a single
        # unfiltered /events page scan and never sees World Cup markets.
        from sports_skills.kalshi._connector import (
            KALSHI_SERIES as KALSHI_MODULE_SERIES,
        )

        tickers = KALSHI_MODULE_SERIES["worldcup"]
        assert "KXMENWORLDCUP" in tickers
        assert "KXWCGAME" in tickers
        assert "KXWCGROUPQUAL" in tickers
        assert all(t.startswith("KX") for t in tickers)


class TestGetSportMarketsMeta:
    """`sport="football"` should fan out across league codes AND surface
    tournament markets (FIFA World Cup) via a polymarket keyword search.
    Before this fix, `get_sport_markets --sport=football` returned 0 markets
    because neither KALSHI_SERIES nor POLYMARKET_SPORTS had a "football" key
    — the per-league EPL/UCL/etc. entries existed but only one sport key
    was consulted per call."""

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_football_fans_out_across_leagues_and_fifa_keyword(self, mock_kalshi, mock_poly):
        # Kalshi returns one market per league lookup.
        mock_kalshi.get_markets.return_value = {
            "status": True,
            "data": {"markets": [{"ticker": "MKT_K", "title": "EPL game"}]},
        }
        # Polymarket returns unique markets per call (use kwargs to vary the id
        # so we exercise the dedupe path). Fixture uses `id` to match the real
        # Polymarket payload shape — `market_id` is the renamed key applied
        # downstream in normalize_market, not present on raw search results.
        poly_call_count = {"n": 0}

        def poly_side_effect(**kwargs):
            poly_call_count["n"] += 1
            return {
                "status": True,
                "data": {"markets": [{"id": f"P{poly_call_count['n']}", "title": "x"}]},
            }

        mock_poly.search_markets.side_effect = poly_side_effect

        result = get_sport_markets({"params": {"sport": "football", "limit": 50}})

        assert result["status"] is True
        assert result["data"]["sport"] == "football"
        # 8 leagues in META_SPORTS["football"]["leagues"] (7 club leagues
        # + worldcup) → 8 kalshi calls.
        assert mock_kalshi.get_markets.call_count == 8
        # 8 league calls + 1 FIFA keyword call = 9 polymarket calls.
        assert mock_poly.search_markets.call_count == 9
        # All 8 kalshi markets surface (one per league).
        assert result["data"]["kalshi_count"] == 8
        # 9 unique polymarket ids (8 leagues + FIFA), all kept by dedupe.
        assert result["data"]["polymarket_count"] == 9

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_soccer_alias_resolves_to_football(self, mock_kalshi, mock_poly):
        mock_kalshi.get_markets.return_value = {"status": True, "data": {"markets": []}}
        mock_poly.search_markets.return_value = {"status": True, "data": {"markets": []}}

        soccer_result = get_sport_markets({"params": {"sport": "soccer"}})
        football_result = get_sport_markets({"params": {"sport": "football"}})

        # Both report the canonical "football" sport in the response.
        assert soccer_result["data"]["sport"] == "football"
        assert football_result["data"]["sport"] == "football"

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_dedupe_collapses_duplicate_polymarket_ids(self, mock_kalshi, mock_poly):
        # Kalshi unused for this assertion.
        mock_kalshi.get_markets.return_value = {"status": True, "data": {"markets": []}}
        # Every polymarket call returns the SAME market id — dedupe should keep
        # only the first occurrence even across 8 fan-out calls.
        mock_poly.search_markets.return_value = {
            "status": True,
            "data": {"markets": [{"id": "DUPE", "title": "x"}]},
        }

        result = get_sport_markets({"params": {"sport": "football"}})

        assert result["data"]["polymarket_count"] == 1

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_meta_sport_tolerates_per_venue_errors(self, mock_kalshi, mock_poly):
        # Kalshi raises on every call; polymarket keeps working.
        mock_kalshi.get_markets.side_effect = Exception("kalshi down")
        mock_poly.search_markets.return_value = {
            "status": True,
            "data": {"markets": [{"id": "P1", "title": "x"}]},
        }

        result = get_sport_markets({"params": {"sport": "football"}})

        # Partial success: status still True, kalshi empty, polymarket populated,
        # warnings list captures the kalshi failures.
        assert result["status"] is True
        assert result["data"]["kalshi_count"] == 0
        assert result["data"]["polymarket_count"] >= 1
        warnings = result["data"].get("warnings", [])
        assert any("kalshi" in w.lower() for w in warnings)


# ============================================================
# Mocked: Get Live Tick (Kalshi)
# ============================================================


def _mlb_summary(event_date="2026-07-17T17:35Z"):
    """Raw ESPN summary header in the REAL MLB shape (locations + date)."""
    return {
        "header": {
            "competitions": [
                {
                    "date": event_date,
                    "status": {"type": {"shortDetail": "Mid 6th", "state": "in"}},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {
                                "abbreviation": "BOS",
                                "displayName": "Boston Red Sox",
                                "location": "Boston",
                            },
                        },
                        {
                            "homeAway": "away",
                            "team": {
                                "abbreviation": "TB",
                                "displayName": "Tampa Bay Rays",
                                "location": "Tampa Bay",
                            },
                        },
                    ],
                }
            ]
        }
    }


def _winner_market(event_tail, suffix, yes_bid, status="active", last_price=0, series="KXMLBGAME"):
    """One side of a Kalshi game-winner market, in the REAL search shape:
    both sides share one location-based title; only the ticker suffix
    identifies the side."""
    return {
        "ticker": f"{series}-{event_tail}-{suffix}",
        "event_ticker": f"{series}-{event_tail}",
        "title": "Tampa Bay vs Boston Winner?",
        "subtitle": "",
        "event_title": "Tampa Bay vs Boston",
        "yes_bid": yes_bid,
        "no_bid": 100 - yes_bid if yes_bid else 0,
        "last_price": last_price,
        "volume": 1000,
        "status": status,
    }


def _game_summary(home_abbr, home_name, home_loc, away_abbr, away_name, away_loc,
                   event_date="2026-07-17T17:35Z", short_detail="Mid 6th"):
    """Raw ESPN summary header, parametrized over sport/teams for cross-sport tests."""
    return {
        "header": {
            "competitions": [
                {
                    "date": event_date,
                    "status": {"type": {"shortDetail": short_detail, "state": "in"}},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {
                                "abbreviation": home_abbr,
                                "displayName": home_name,
                                "location": home_loc,
                            },
                        },
                        {
                            "homeAway": "away",
                            "team": {
                                "abbreviation": away_abbr,
                                "displayName": away_name,
                                "location": away_loc,
                            },
                        },
                    ],
                }
            ]
        }
    }


class TestGetLiveTickMocked:
    """`get_live_tick` fuses the ESPN summary (teams + clock) with a Kalshi home
    price, in the same top-level shape as the mock tick but source-neutral.

    The Kalshi fixtures mirror the venue's REAL payload: location-based event
    titles ("Tampa Bay vs Boston"), an identical title on both sides of the
    winner market, and the matchup encoded only in the ticker
    (date+time ET, AWAYHOME pair, optional Gn doubleheader suffix)."""

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_shape_conversion_and_game_id(self, mock_summary, mock_kalshi):
        mock_summary.return_value = _mlb_summary()
        mock_kalshi.return_value = [
            _winner_market("26JUL171335TBBOSG1", "TB", 37),
            _winner_market("26JUL171335TBBOSG1", "BOS", 63),
        ]

        result = get_live_tick({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        data = result["data"]

        # Same top-level shape as the mock tick, source-neutral price key.
        assert data["sport"] == "mlb"
        assert data["teams"]["home"] == {"abbrev": "BOS", "name": "Boston Red Sox"}
        assert data["teams"]["away"] == {"abbrev": "TB", "name": "Tampa Bay Rays"}
        assert data["game_clock"] == "Mid 6th"
        assert data["price_source"] == "kalshi"
        # HOME side selected by ticker suffix — titles are identical.
        assert data["kalshi_ticker"] == "KXMLBGAME-26JUL171335TBBOSG1-BOS"
        assert data["timestamp"].endswith("Z")
        assert data["home_price_cents"] == 63.0
        # game_id is the ESPN event_id so plays can be fetched for the same game.
        assert data["game_id"] == "401872178"

        # The winner series (KXMLBGAME) was searched, keyed on the home location.
        series, query, status = mock_kalshi.call_args[0][:3]
        assert series == "KXMLBGAME"
        assert query == "boston"
        assert status == "open"

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_doubleheader_picks_game_by_start_time(self, mock_summary, mock_kalshi):
        # ESPN event is game 1 (17:35Z == 13:35 ET); Kalshi lists both games.
        mock_summary.return_value = _mlb_summary("2026-07-17T17:35Z")
        mock_kalshi.return_value = [
            _winner_market("26JUL171910TBBOSG2", "TB", 16),
            _winner_market("26JUL171910TBBOSG2", "BOS", 83),
            _winner_market("26JUL171335TBBOSG1", "TB", 4),
            _winner_market("26JUL171335TBBOSG1", "BOS", 96),
        ]

        result = get_live_tick({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        assert result["data"]["kalshi_ticker"] == "KXMLBGAME-26JUL171335TBBOSG1-BOS"
        assert result["data"]["home_price_cents"] == 96.0

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_zero_bid_falls_back_to_last_price(self, mock_summary, mock_kalshi):
        mock_summary.return_value = _mlb_summary()
        mock_kalshi.return_value = [
            _winner_market("26JUL171335TBBOSG1", "TB", 0, last_price=1),
            _winner_market("26JUL171335TBBOSG1", "BOS", 0, last_price=99),
        ]

        result = get_live_tick({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        assert result["data"]["home_price_cents"] == 99.0

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_no_kalshi_market_errors(self, mock_summary, mock_kalshi):
        mock_summary.return_value = _mlb_summary()
        mock_kalshi.return_value = []

        result = get_live_tick({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is False

    def test_missing_sport(self):
        assert get_live_tick({"params": {"event_id": "1"}})["status"] is False

    def test_missing_event_id(self):
        assert get_live_tick({"params": {"sport": "nfl"}})["status"] is False

    def test_unknown_sport(self):
        assert get_live_tick({"params": {"sport": "cricket", "event_id": "1"}})["status"] is False


class TestParseKalshiEventTail:
    def test_doubleheader_tail(self):
        start, pair, game_num = _parse_kalshi_event_tail("KXMLBGAME-26JUL171335TBBOSG1")
        assert pair == "TBBOS"
        assert game_num == "1"
        # 13:35 ET on 2026-07-17 is 17:35 UTC.
        assert start.isoformat() == "2026-07-17T17:35:00+00:00"

    def test_plain_tail(self):
        start, pair, game_num = _parse_kalshi_event_tail("KXMLBGAME-26JUL181610TBBOS")
        assert pair == "TBBOS"
        assert game_num is None
        assert start.isoformat() == "2026-07-18T20:10:00+00:00"

    def test_unparseable_tail(self):
        assert _parse_kalshi_event_tail("KXMLB-26-BOS") == (None, None, None)

    def test_time_less_tail(self):
        # Real WNBA tickers omit the HHMM segment (observed live 2026-07-18):
        # the pair must still parse for matching; only start time is lost.
        start, pair, game_num = _parse_kalshi_event_tail("KXWNBAGAME-26JUL17SEAIND")
        assert pair == "SEAIND"
        assert start is None
        assert game_num is None


class TestResolveGameMarketMocked:
    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_settled_market_resolves_for_finished_game(self, mock_summary, mock_kalshi):
        mock_summary.return_value = _mlb_summary("2026-07-17T17:35Z")

        # 'any' searches open, settled, closed; game 1 only exists settled.
        def by_status(series, query, status, limit=200):
            if status == "open":
                return [
                    _winner_market("26JUL171910TBBOSG2", "TB", 16),
                    _winner_market("26JUL171910TBBOSG2", "BOS", 83),
                ]
            if status == "settled":
                return [
                    _winner_market("26JUL171335TBBOSG1", "TB", 0, "finalized", last_price=1),
                    _winner_market("26JUL171335TBBOSG1", "BOS", 0, "finalized", last_price=99),
                ]
            return []

        mock_kalshi.side_effect = by_status

        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        data = result["data"]
        # Game 1's settled market wins on start time, not game 2's open one.
        assert data["kalshi_ticker"] == "KXMLBGAME-26JUL171335TBBOSG1-BOS"
        assert data["market_status"] == "finalized"
        assert data["home_yes_cents"] == 99.0
        assert data["market_start"] == "2026-07-17T17:35:00Z"
        assert data["teams"]["home"]["location"] == "Boston"

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_no_match_errors(self, mock_summary, mock_kalshi):
        mock_summary.return_value = _mlb_summary()
        mock_kalshi.return_value = []
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is False

    def test_bad_status_param(self):
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "1", "status": "weird"}})
        assert result["status"] is False

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_rejects_market_from_a_different_date(self, mock_summary, mock_kalshi):
        # Observed live: asking for a FINISHED game returned the same teams'
        # NEXT game (the only market still open), fusing that price with this
        # game's ESPN frame. A lone far-off candidate must be rejected, not
        # accepted for lack of competition.
        mock_summary.return_value = _mlb_summary("2026-07-24T23:15Z")
        mock_kalshi.side_effect = lambda series, query, status, limit=200: (
            [
                _winner_market("26JUL251610TORBOS", "TOR", 50),
                _winner_market("26JUL251610TORBOS", "BOS", 50),
            ]
            if status == "open"
            else []
        )
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is False, "next day's market must not resolve for this game"

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_accepts_same_day_market_despite_start_drift(self, mock_summary, mock_kalshi):
        # A few hours of same-day drift (delay, ESPN/Kalshi disagreeing on the
        # scheduled time) must still resolve.
        mock_summary.return_value = _mlb_summary("2026-07-17T17:35Z")
        mock_kalshi.side_effect = lambda series, query, status, limit=200: (
            [
                _winner_market("26JUL171910TBBOS", "TB", 37),
                _winner_market("26JUL171910TBBOS", "BOS", 63),
            ]
            if status == "open"
            else []
        )
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        assert result["data"]["home_yes_cents"] == 63.0

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_time_less_ticker_survives_the_date_guard(self, mock_summary, mock_kalshi):
        # A tail with no embedded time can't be date-checked; it must NOT be
        # dropped by the guard, or time-less series (real WNBA tickers) would
        # stop resolving entirely.
        mock_summary.return_value = _mlb_summary("2026-07-17T17:35Z")
        mock_kalshi.side_effect = lambda series, query, status, limit=200: (
            [
                _winner_market("26JUL17TBBOS", "TB", 37),
                _winner_market("26JUL17TBBOS", "BOS", 63),
            ]
            if status == "open"
            else []
        )
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        assert result["data"]["home_yes_cents"] == 63.0

    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_one_cent_price_not_rescaled(self, mock_summary, mock_kalshi):
        # A genuine 1c (1% win-prob) home price must stay 1c, not be mistaken
        # for a 0-1 probability and rescaled to 100c. yes_bid is integer cents.
        mock_summary.return_value = _mlb_summary("2026-07-17T17:35Z")
        mock_kalshi.side_effect = lambda series, query, status, limit=200: (
            [
                _winner_market("26JUL171335TBBOS", "TB", 99),
                _winner_market("26JUL171335TBBOS", "BOS", 1),
            ]
            if status == "open"
            else []
        )
        result = resolve_game_market({"params": {"sport": "mlb", "event_id": "401872178"}})
        assert result["status"] is True
        assert result["data"]["home_yes_cents"] == 1.0


# ============================================================
# Cross-sport coverage: get_live_tick / resolve_game_market beyond MLB.
#
# Success-path tests previously only exercised sport="mlb"; these extend the
# same fixtures to the other KALSHI_SERIES/_ESPN_SPORT_PATHS entries the
# markets module already registers (nfl covered via the momentum mock demo).
# Team pairs mirror real ticker shapes we've seen live where possible (WNBA
# SEA@IND matches the actual KXWNBAGAME-26JUL17SEAIND-IND ticker observed
# 2026-07-18).
# ============================================================

CROSS_SPORT_GAMES = [
    pytest.param(
        "nba", "KXNBAGAME",
        "BOS", "Boston Celtics", "Boston",
        "MIA", "Miami Heat", "Miami",
        "MIABOS",
        id="nba",
    ),
    pytest.param(
        "nhl", "KXNHLGAME",
        "TOR", "Toronto Maple Leafs", "Toronto",
        "BOS", "Boston Bruins", "Boston",
        "BOSTOR",
        id="nhl",
    ),
    pytest.param(
        "wnba", "KXWNBAGAME",
        "IND", "Indiana Fever", "Indiana",
        "SEA", "Seattle Storm", "Seattle",
        "SEAIND",
        id="wnba",
    ),
    pytest.param(
        "cfb", "KXCFBGAME",
        "OSU", "Ohio State Buckeyes", "Ohio State",
        "MICH", "Michigan Wolverines", "Michigan",
        "MICHOSU",
        id="cfb",
    ),
    pytest.param(
        "cbb", "KXCBBGAME",
        "DUKE", "Duke Blue Devils", "Duke",
        "UNC", "North Carolina Tar Heels", "North Carolina",
        "UNCDUKE",
        id="cbb",
    ),
]


class TestGetLiveTickCrossSport:
    @pytest.mark.parametrize(
        "sport,series,home_abbr,home_name,home_loc,away_abbr,away_name,away_loc,pair",
        CROSS_SPORT_GAMES,
    )
    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_shape_conversion_per_sport(
        self, mock_summary, mock_kalshi,
        sport, series, home_abbr, home_name, home_loc, away_abbr, away_name, away_loc, pair,
    ):
        mock_summary.return_value = _game_summary(
            home_abbr, home_name, home_loc, away_abbr, away_name, away_loc
        )
        event_tail = f"26JUL171335{pair}"
        mock_kalshi.return_value = [
            _winner_market(event_tail, away_abbr, 37, series=series),
            _winner_market(event_tail, home_abbr, 63, series=series),
        ]

        result = get_live_tick({"params": {"sport": sport, "event_id": "999"}})
        assert result["status"] is True
        data = result["data"]
        assert data["sport"] == sport
        assert data["teams"]["home"]["abbrev"] == home_abbr
        assert data["teams"]["away"]["abbrev"] == away_abbr
        assert data["home_price_cents"] == 63.0
        assert data["kalshi_ticker"] == f"{series}-{event_tail}-{home_abbr}"

        # The sport's own game-market series was searched (KALSHI_SERIES[sport] + "GAME").
        searched_series, query, status = mock_kalshi.call_args[0][:3]
        assert searched_series == series
        assert query == home_loc.lower()
        assert status == "open"


class TestResolveGameMarketCrossSport:
    @pytest.mark.parametrize(
        "sport,series,home_abbr,home_name,home_loc,away_abbr,away_name,away_loc,pair",
        CROSS_SPORT_GAMES,
    )
    @patch("sports_skills.markets._connector._kalshi_game_search")
    @patch("sports_skills._espn_base.espn_summary")
    def test_settled_market_resolves_per_sport(
        self, mock_summary, mock_kalshi,
        sport, series, home_abbr, home_name, home_loc, away_abbr, away_name, away_loc, pair,
    ):
        mock_summary.return_value = _game_summary(
            home_abbr, home_name, home_loc, away_abbr, away_name, away_loc,
            short_detail="Final",
        )
        event_tail = f"26JUL171335{pair}"

        def by_status(series_arg, query, status, limit=200):
            if status == "settled":
                return [
                    _winner_market(event_tail, away_abbr, 0, "finalized", last_price=1, series=series),
                    _winner_market(event_tail, home_abbr, 0, "finalized", last_price=99, series=series),
                ]
            return []

        mock_kalshi.side_effect = by_status

        result = resolve_game_market({"params": {"sport": sport, "event_id": "999"}})
        assert result["status"] is True
        data = result["data"]
        assert data["kalshi_ticker"] == f"{series}-{event_tail}-{home_abbr}"
        assert data["market_status"] == "finalized"
        assert data["home_yes_cents"] == 99.0
        assert data["teams"]["home"]["location"] == home_loc


# ============================================================
# Momentum primitives: mock tick + timestamp-scoped plays
# ============================================================


def _mock_game_file(tmp_path):
    """A minimal mock game JSON matching the demo fixture's shape."""
    import json

    game = {
        "game_id": "mock-mlb-tb-bos-2026",
        "sport": "mlb",
        "teams": {
            "home": {"abbrev": "BOS", "name": "Boston Red Sox"},
            "away": {"abbrev": "TB", "name": "Tampa Bay Rays"},
        },
        "timeline": [
            {
                "timestamp": "2026-07-17T18:00:00Z",
                "game_clock": "Bot 1st",
                "polymarket_home_price_cents": 55,
                "play_by_play": [
                    {
                        "id": "p1",
                        "sequenceNumber": "1",
                        "wallclock": "2026-07-17T17:59:10Z",
                        "text": "Durbin walked.",
                        "type": {"text": "Walk"},
                        "period": {"displayValue": "1st Inning"},
                        "clock": {"displayValue": ""},
                        "homeScore": 0,
                        "awayScore": 0,
                        "scoringPlay": False,
                        "team": {"id": "2"},
                    }
                ],
            },
            {
                "timestamp": "2026-07-17T18:03:00Z",
                "game_clock": "Bot 1st",
                "polymarket_home_price_cents": 71,
                "play_by_play": [
                    {
                        "id": "p1",
                        "sequenceNumber": "1",
                        "wallclock": "2026-07-17T17:59:10Z",
                        "text": "Durbin walked.",
                        "type": {"text": "Walk"},
                        "period": {"displayValue": "1st Inning"},
                        "clock": {"displayValue": ""},
                        "homeScore": 0,
                        "awayScore": 0,
                        "scoringPlay": False,
                        "team": {"id": "2"},
                    },
                    {
                        "id": "p2",
                        "sequenceNumber": "2",
                        "wallclock": "2026-07-17T18:02:43Z",
                        "text": "Narváez singled to center, Yoshida scored.",
                        "type": {"text": "Single"},
                        "period": {"displayValue": "1st Inning"},
                        "clock": {"displayValue": ""},
                        "homeScore": 2,
                        "awayScore": 0,
                        "scoringPlay": True,
                        "team": {"id": "2"},
                    },
                ],
            },
        ],
    }
    path = tmp_path / "mock_game.json"
    path.write_text(json.dumps(game), encoding="utf-8")
    return str(path)


class TestGetMockTick:
    def test_returns_a_timeline_tick(self, tmp_path):
        path = _mock_game_file(tmp_path)
        result = get_mock_tick({"params": {"mock_file_path": path, "interval_seconds": 5}})
        assert result["status"] is True
        data = result["data"]
        assert data["game_id"] == "mock-mlb-tb-bos-2026"
        assert data["total_ticks"] == 2
        assert data["tick_index"] in (0, 1)
        assert data["polymarket_home_price_cents"] in (55, 71)

    def test_missing_file_errors(self):
        result = get_mock_tick({"params": {"mock_file_path": "/nope/missing.json"}})
        assert result["status"] is False


class TestGetPlaysNearTimestampMock:
    """The mock branch: `mock_file_path` selects the plays embedded in the mock
    file's timeline — no network, and the same output shape as the live branch."""

    def test_window_filters_embedded_plays(self, tmp_path):
        path = _mock_game_file(tmp_path)
        result = get_plays_near_timestamp(
            {
                "params": {
                    "sport": "mlb",
                    "mock_file_path": path,
                    "timestamp": "2026-07-17T18:03:00Z",
                    "window_seconds": 60,
                }
            }
        )
        assert result["status"] is True
        data = result["data"]
        assert data["source"] == "mock-file"
        # Only the RBI single is inside [18:02:00, 18:03:00]; the walk
        # (17:59:10) is outside, and the duplicated play is deduped by id.
        assert data["count"] == 1
        assert data["plays"][0]["id"] == "p2"
        assert data["plays"][0]["scoring_play"] is True
        # game_id falls back to the mock file's own id.
        assert data["game_id"] == "mock-mlb-tb-bos-2026"

    def test_wider_window_includes_both_plays_sorted(self, tmp_path):
        path = _mock_game_file(tmp_path)
        result = get_plays_near_timestamp(
            {
                "params": {
                    "sport": "mlb",
                    "mock_file_path": path,
                    "timestamp": "2026-07-17T18:03:00Z",
                    "window_seconds": 600,
                }
            }
        )
        assert result["status"] is True
        plays = result["data"]["plays"]
        assert [p["id"] for p in plays] == ["p1", "p2"]

    def test_missing_mock_file_errors(self):
        result = get_plays_near_timestamp(
            {
                "params": {
                    "sport": "mlb",
                    "mock_file_path": "/nope/missing.json",
                    "timestamp": "2026-07-17T18:03:00Z",
                }
            }
        )
        assert result["status"] is False


class TestGetPlaysNearTimestampLive:
    """The live branch: `game_id` fetches the RAW ESPN summary (wallclocks are
    only present there — the shared normalizer strips them)."""

    def _raw_summary(self):
        return {
            "plays": [
                {
                    "id": "401872178001",
                    "sequenceNumber": "1",
                    "wallclock": "2026-07-17T18:00:21Z",
                    "text": "Duran hit sacrifice fly to center, Durbin scored.",
                    "type": {"text": "Sac Fly"},
                    "period": {"displayValue": "1st Inning"},
                    "clock": {"displayValue": ""},
                    "homeScore": 1,
                    "awayScore": 0,
                    "scoringPlay": True,
                    "team": {"id": "2"},
                },
                {
                    "id": "401872178002",
                    "sequenceNumber": "2",
                    "wallclock": "2026-07-17T18:30:00Z",
                    "text": "Later play, outside the window.",
                    "type": {"text": "Groundout"},
                    "period": {"displayValue": "2nd Inning"},
                    "clock": {"displayValue": ""},
                    "homeScore": 3,
                    "awayScore": 0,
                    "scoringPlay": False,
                    "team": {"id": "2"},
                },
                {
                    "id": "401872178003",
                    "sequenceNumber": "3",
                    # No wallclock — must be skipped, not crash.
                    "text": "Broadcast note.",
                },
            ]
        }

    @patch("sports_skills._espn_base.espn_summary")
    def test_window_filters_raw_espn_plays(self, mock_summary):
        mock_summary.return_value = self._raw_summary()
        result = get_plays_near_timestamp(
            {
                "params": {
                    "sport": "mlb",
                    "game_id": "401872178",
                    "timestamp": "2026-07-17T18:01:00Z",
                    "window_seconds": 120,
                }
            }
        )
        assert result["status"] is True
        data = result["data"]
        assert data["source"] == "espn-live"
        assert data["count"] == 1
        assert data["plays"][0]["id"] == "401872178001"
        assert data["plays"][0]["scoring_play"] is True
        assert data["plays_without_wallclock"] == 1
        # The raw summary path was used (sport path + event id).
        mock_summary.assert_called_once_with("baseball/mlb", "401872178")

    def test_live_branch_requires_game_id(self):
        result = get_plays_near_timestamp({"params": {"sport": "mlb", "timestamp": "2026-07-17T18:01:00Z"}})
        assert result["status"] is False

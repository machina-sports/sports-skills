"""Tests for markets orchestration module."""

from unittest.mock import MagicMock, patch

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
    _success_partial,
    compare_odds,
    evaluate_market,
    get_sport_markets,
    get_sport_schedule,
    get_todays_markets,
    normalize_price,
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
        candidates = [
            {"name": f"Team {i}"} for i in range(20)
        ]
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
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    def test_search_entity_combines_results(self, mock_kalshi, mock_poly):
        mock_kalshi.return_value = [
            {"source": "kalshi", "title": "Lakers vs Celtics", "event_ticker": "EVT1", "markets": []}
        ]
        mock_poly.return_value = [
            {"source": "polymarket", "title": "Lakers Game", "market_id": "MKT1", "outcomes": []}
        ]

        result = search_entity({"params": {"query": "Lakers"}})
        assert result["status"] is True
        assert result["data"]["total_results"] == 2
        assert len(result["data"]["kalshi"]) == 1
        assert len(result["data"]["polymarket"]) == 1

    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    def test_search_entity_partial_failure(self, mock_kalshi, mock_poly):
        mock_kalshi.side_effect = Exception("Kalshi down")
        mock_poly.return_value = [
            {"source": "polymarket", "title": "Lakers Game", "market_id": "MKT1", "outcomes": []}
        ]

        result = search_entity({"params": {"query": "Lakers"}})
        assert result["status"] is True
        assert len(result["data"]["polymarket"]) == 1
        assert "warnings" in result["data"]

    def test_search_entity_missing_query(self):
        result = search_entity({"params": {}})
        assert result["status"] is False


# ============================================================
# Mocked: Get Todays Markets
# ============================================================


class TestGetTodaysMarketsMocked:
    @patch("sports_skills.markets._connector._search_polymarket")
    @patch("sports_skills.markets._connector._search_kalshi")
    @patch("sports_skills.markets._connector._fetch_all_schedules")
    def test_returns_dashboard(self, mock_schedules, mock_kalshi, mock_poly):
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

    def test_soccer_aliases_to_football(self):
        assert META_SPORT_ALIASES.get("soccer") == "football"


class TestGetSportMarketsMeta:
    """`sport="football"` should fan out across league codes AND surface
    tournament markets (FIFA World Cup) via a polymarket keyword search.
    Before this fix, `get_sport_markets --sport=football` returned 0 markets
    because neither KALSHI_SERIES nor POLYMARKET_SPORTS had a "football" key
    — the per-league EPL/UCL/etc. entries existed but only one sport key
    was consulted per call."""

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_football_fans_out_across_leagues_and_fifa_keyword(
        self, mock_kalshi, mock_poly
    ):
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
                "data": {
                    "markets": [
                        {"id": f"P{poly_call_count['n']}", "title": "x"}
                    ]
                },
            }

        mock_poly.search_markets.side_effect = poly_side_effect

        result = get_sport_markets({"params": {"sport": "football", "limit": 50}})

        assert result["status"] is True
        assert result["data"]["sport"] == "football"
        # 7 leagues in META_SPORTS["football"]["leagues"] → 7 kalshi calls.
        assert mock_kalshi.get_markets.call_count == 7
        # 7 league calls + 1 FIFA keyword call = 8 polymarket calls.
        assert mock_poly.search_markets.call_count == 8
        # All 7 kalshi markets surface (one per league).
        assert result["data"]["kalshi_count"] == 7
        # 8 unique polymarket ids (7 leagues + FIFA), all kept by dedupe.
        assert result["data"]["polymarket_count"] == 8

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

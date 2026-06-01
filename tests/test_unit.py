"""Unit tests for pure data transformation and internal logic."""

import time
import urllib.error

from sports_skills._espn_base import (
    ESPN_STATUS_MAP,
    _cache_get,
    _cache_set,
    _is_retryable,
    normalize_odds,
)
from sports_skills._response import error, success, wrap

# ── normalize_odds ─────────────────────────────────────────────


class TestNormalizeOdds:
    """Tests for the shared ESPN odds normalizer."""

    def test_empty_list_returns_none(self):
        assert normalize_odds([]) is None

    def test_none_input_returns_none(self):
        assert normalize_odds(None) is None

    def test_two_way_moneyline(self):
        """Standard US sport odds — home/away only, no draw."""
        odds = [
            {
                "provider": {"name": "Draft Kings"},
                "details": "BOS -6.5",
                "overUnder": 220.5,
                "spread": 6.5,
                "moneyline": {
                    "home": {"close": {"odds": "-280"}},
                    "away": {"close": {"odds": "+220"}},
                },
                "pointSpread": {
                    "home": {"close": {"line": "-6.5", "odds": "-110"}},
                    "away": {"close": {"line": "+6.5", "odds": "-110"}},
                },
                "total": {
                    "over": {"close": {"line": "o220.5", "odds": "-110"}},
                    "under": {"close": {"line": "u220.5", "odds": "-110"}},
                },
                "homeTeamOdds": {"favorite": True},
                "awayTeamOdds": {},
            }
        ]
        result = normalize_odds(odds)

        assert result["provider"] == "Draft Kings"
        assert result["details"] == "BOS -6.5"
        assert result["over_under"] == 220.5
        assert result["favorite"] == "home"
        assert result["moneyline"]["home"] == "-280"
        assert result["moneyline"]["away"] == "+220"
        assert "draw" not in result["moneyline"]
        assert result["spread_line"]["home"]["line"] == "-6.5"
        assert result["total"]["over"]["line"] == "o220.5"

    def test_three_way_moneyline_soccer(self):
        """Soccer odds include draw in moneyline."""
        odds = [
            {
                "provider": {"name": "Draft Kings"},
                "details": "ATH -145",
                "overUnder": 2.5,
                "spread": "",
                "moneyline": {
                    "home": {"open": {"odds": "-170"}, "close": {"odds": "-145"}},
                    "away": {"open": {"odds": "+450"}, "close": {"odds": "+425"}},
                    "draw": {"open": {"odds": "+285"}, "close": {"odds": "+280"}},
                },
                "pointSpread": {},
                "total": {},
                "homeTeamOdds": {},
                "awayTeamOdds": {},
            }
        ]
        result = normalize_odds(odds)

        assert result["moneyline"]["home"] == "-145"
        assert result["moneyline"]["away"] == "+425"
        assert result["moneyline"]["draw"] == "+280"

    def test_opening_lines_included(self):
        """Opening lines should populate the 'open' sub-dict."""
        odds = [
            {
                "provider": {"name": "Draft Kings"},
                "details": "",
                "moneyline": {
                    "home": {"open": {"odds": "-250"}, "close": {"odds": "-280"}},
                    "away": {"open": {"odds": "+200"}, "close": {"odds": "+220"}},
                },
                "pointSpread": {
                    "home": {"open": {"line": "-6.0"}, "close": {"line": "-6.5"}},
                    "away": {"open": {"line": "+6.0"}, "close": {"line": "+6.5"}},
                },
                "total": {
                    "over": {"open": {"line": "o219.5"}, "close": {"line": "o220.5"}},
                    "under": {"close": {"line": "u220.5"}},
                },
                "homeTeamOdds": {},
                "awayTeamOdds": {},
            }
        ]
        result = normalize_odds(odds)

        assert result["open"]["moneyline"]["home"] == "-250"
        assert result["open"]["moneyline"]["away"] == "+200"
        assert result["open"]["spread"]["home"] == "-6.0"
        assert result["open"]["total"] == "o219.5"

    def test_opening_draw_lines(self):
        """Soccer opening lines should include draw when present."""
        odds = [
            {
                "provider": {"name": "Draft Kings"},
                "details": "",
                "moneyline": {
                    "home": {"open": {"odds": "-170"}, "close": {"odds": "-145"}},
                    "away": {"open": {"odds": "+450"}, "close": {"odds": "+425"}},
                    "draw": {"open": {"odds": "+285"}, "close": {"odds": "+280"}},
                },
                "pointSpread": {},
                "total": {},
                "homeTeamOdds": {},
                "awayTeamOdds": {},
            }
        ]
        result = normalize_odds(odds)

        assert result["open"]["moneyline"]["draw"] == "+285"

    def test_away_favorite(self):
        odds = [
            {
                "provider": {"name": "DK"},
                "details": "",
                "moneyline": {},
                "pointSpread": {},
                "total": {},
                "homeTeamOdds": {},
                "awayTeamOdds": {"favorite": True},
            }
        ]
        result = normalize_odds(odds)
        assert result["favorite"] == "away"

    def test_no_favorite(self):
        odds = [
            {
                "provider": {"name": "DK"},
                "details": "",
                "moneyline": {},
                "pointSpread": {},
                "total": {},
                "homeTeamOdds": {},
                "awayTeamOdds": {},
            }
        ]
        result = normalize_odds(odds)
        assert result["favorite"] is None

    def test_missing_nested_keys_default_empty(self):
        """Deeply nested missing keys should not raise — they default to empty strings."""
        odds = [{"provider": {}, "moneyline": {"home": {}}, "pointSpread": {}, "total": {}}]
        result = normalize_odds(odds)
        assert result["provider"] == ""
        assert result["moneyline"]["home"] == ""


# ── _response ──────────────────────────────────────────────────


class TestResponse:
    def test_success_envelope(self):
        r = success({"key": "val"}, message="ok")
        assert r == {"status": True, "data": {"key": "val"}, "message": "ok"}

    def test_error_envelope(self):
        r = error("broke", data={"debug": 1})
        assert r == {"status": False, "data": {"debug": 1}, "message": "broke"}

    def test_wrap_passthrough(self):
        """Already-formatted responses pass through unchanged."""
        envelope = {"status": True, "data": [1, 2], "message": ""}
        assert wrap(envelope) is envelope

    def test_wrap_error_dict(self):
        r = wrap({"error": True, "message": "timeout"})
        assert r["status"] is False
        assert r["message"] == "timeout"

    def test_wrap_plain_dict(self):
        r = wrap({"goals": 3})
        assert r["status"] is True
        assert r["data"] == {"goals": 3}

    def test_wrap_non_dict(self):
        r = wrap([1, 2, 3])
        assert r["status"] is True
        assert r["data"] == [1, 2, 3]


# ── Cache ──────────────────────────────────────────────────────


class TestCache:
    def test_set_and_get(self):
        _cache_set("test_key_1", "hello", ttl=60)
        assert _cache_get("test_key_1") == "hello"

    def test_miss_returns_none(self):
        assert _cache_get("nonexistent_key_xyz") is None

    def test_expired_entry_returns_none(self):
        _cache_set("test_key_expire", "val", ttl=0)
        time.sleep(0.01)
        assert _cache_get("test_key_expire") is None


# ── _is_retryable ─────────────────────────────────────────────


class TestIsRetryable:
    def test_429_is_retryable(self):
        exc = urllib.error.HTTPError("url", 429, "rate limited", {}, None)
        assert _is_retryable(exc) is True

    def test_500_is_retryable(self):
        exc = urllib.error.HTTPError("url", 500, "server error", {}, None)
        assert _is_retryable(exc) is True

    def test_404_is_not_retryable(self):
        exc = urllib.error.HTTPError("url", 404, "not found", {}, None)
        assert _is_retryable(exc) is False

    def test_timeout_is_retryable(self):
        assert _is_retryable(TimeoutError()) is True

    def test_os_error_is_retryable(self):
        assert _is_retryable(OSError("conn reset")) is True

    def test_value_error_is_not_retryable(self):
        assert _is_retryable(ValueError("bad")) is False


# ── ESPN_STATUS_MAP ────────────────────────────────────────────


class TestStatusMap:
    def test_scheduled_maps_to_not_started(self):
        assert ESPN_STATUS_MAP["STATUS_SCHEDULED"] == "not_started"

    def test_final_maps_to_closed(self):
        assert ESPN_STATUS_MAP["STATUS_FINAL"] == "closed"

    def test_in_progress_maps_to_live(self):
        assert ESPN_STATUS_MAP["STATUS_IN_PROGRESS"] == "live"


# ── CLI _parse_value ───────────────────────────────────────────


class TestParseValue:
    def test_int_param(self):
        from sports_skills.cli import _parse_value

        assert _parse_value("limit", "25") == 25
        assert _parse_value("season", "2024") == 2024
        assert _parse_value("week", "3") == 3

    def test_bool_param_string(self):
        from sports_skills.cli import _parse_value

        assert _parse_value("active", "true") is True
        assert _parse_value("active", "false") is False

    def test_bool_param_already_bool(self):
        from sports_skills.cli import _parse_value

        assert _parse_value("active", True) is True

    def test_list_param(self):
        from sports_skills.cli import _parse_value

        result = _parse_value("token_ids", "abc, def, ghi")
        assert result == ["abc", "def", "ghi"]

    def test_plain_string_passthrough(self):
        from sports_skills.cli import _parse_value

        assert _parse_value("team_id", "BOS") == "BOS"


# ── Play-by-Play Normalizers ─────────────────────────────────


class TestNormalizeDrives:
    """Tests for NFL/CFB drive-based play-by-play normalizer."""

    def test_empty_drives(self):
        from sports_skills.nfl._connector import _normalize_drives

        result = _normalize_drives({"drives": {"previous": []}})
        assert result["drives"] == []
        assert result["count"] == 0

    def test_missing_drives_key(self):
        from sports_skills.nfl._connector import _normalize_drives

        result = _normalize_drives({})
        assert result["drives"] == []
        assert result["count"] == 0

    def test_single_drive_with_plays(self):
        from sports_skills.nfl._connector import _normalize_drives

        data = {
            "drives": {
                "previous": [
                    {
                        "id": "1",
                        "description": "3 plays, 75 yards, 1:30",
                        "team": {"id": "1", "displayName": "Test Team", "abbreviation": "TT"},
                        "displayResult": "Touchdown",
                        "isScore": True,
                        "yards": 75,
                        "offensivePlays": 3,
                        "timeElapsed": {"displayValue": "1:30"},
                        "start": {
                            "period": {"number": 1},
                            "clock": {"displayValue": "15:00"},
                            "yardLine": 25,
                            "text": "TT 25",
                        },
                        "end": {
                            "period": {"number": 1},
                            "clock": {"displayValue": "13:30"},
                            "yardLine": 0,
                        },
                        "plays": [
                            {
                                "id": "101",
                                "text": "Rush for 10 yards",
                                "type": {"text": "Rush"},
                                "period": {"number": 1},
                                "clock": {"displayValue": "14:50"},
                                "homeScore": 0,
                                "awayScore": 0,
                                "scoringPlay": False,
                                "statYardage": 10,
                                "isTurnover": False,
                            },
                            {
                                "id": "102",
                                "text": "Pass for 65 yards, TOUCHDOWN",
                                "type": {"text": "Pass Reception"},
                                "period": {"number": 1},
                                "clock": {"displayValue": "13:30"},
                                "homeScore": 7,
                                "awayScore": 0,
                                "scoringPlay": True,
                                "statYardage": 65,
                                "isTurnover": False,
                            },
                        ],
                    }
                ]
            }
        }
        result = _normalize_drives(data)
        assert result["count"] == 1

        drive = result["drives"][0]
        assert drive["result"] == "Touchdown"
        assert drive["is_score"] is True
        assert drive["yards"] == 75
        assert drive["team"]["abbreviation"] == "TT"
        assert drive["start"]["text"] == "TT 25"
        assert len(drive["plays"]) == 2
        assert drive["plays"][1]["scoring_play"] is True
        assert drive["plays"][0]["yards"] == 10


class TestNormalizePlays:
    """Tests for NBA/NHL/CBB flat play-by-play normalizer."""

    def test_empty_plays(self):
        from sports_skills.nba._connector import _normalize_plays

        result = _normalize_plays({"plays": []})
        assert result.get("error") is True

    def test_missing_plays_key(self):
        from sports_skills.nba._connector import _normalize_plays

        result = _normalize_plays({})
        assert result.get("error") is True

    def test_basic_plays(self):
        from sports_skills.nba._connector import _normalize_plays

        data = {
            "plays": [
                {
                    "id": "1",
                    "text": "Jumpball: Player A vs Player B",
                    "type": {"text": "Jumpball"},
                    "period": {"number": 1},
                    "clock": {"displayValue": "12:00"},
                    "homeScore": 0,
                    "awayScore": 0,
                    "scoringPlay": False,
                    "scoreValue": 0,
                    "team": {"id": "5"},
                    "shootingPlay": False,
                },
                {
                    "id": "2",
                    "text": "Player C makes 3-pointer",
                    "type": {"text": "Three Point Jumper"},
                    "period": {"number": 1},
                    "clock": {"displayValue": "11:35"},
                    "homeScore": 3,
                    "awayScore": 0,
                    "scoringPlay": True,
                    "scoreValue": 3,
                    "team": {"id": "5"},
                    "shootingPlay": True,
                    "coordinate": {"x": 25, "y": 40},
                },
            ]
        }
        result = _normalize_plays(data)
        assert result["count"] == 2
        assert result["plays"][0]["scoring_play"] is False
        assert result["plays"][1]["scoring_play"] is True
        assert result["plays"][1]["score_value"] == 3
        assert result["plays"][1]["shooting_play"] is True
        assert result["plays"][1]["coordinate"] == {"x": 25, "y": 40}

    def test_play_without_coordinate(self):
        from sports_skills.nba._connector import _normalize_plays

        data = {
            "plays": [
                {
                    "id": "1",
                    "text": "Timeout",
                    "type": {"text": "Timeout"},
                    "period": {"number": 1},
                    "clock": {"displayValue": "5:00"},
                    "homeScore": 10,
                    "awayScore": 8,
                    "scoringPlay": False,
                    "scoreValue": 0,
                    "team": {},
                    "shootingPlay": False,
                },
            ]
        }
        result = _normalize_plays(data)
        assert "coordinate" not in result["plays"][0]


class TestNormalizeMLBPlays:
    """Tests for MLB play-by-play normalizer with baseball-specific fields."""

    def test_mlb_play_has_outs_and_inning(self):
        from sports_skills.mlb._connector import _normalize_plays

        data = {
            "plays": [
                {
                    "id": "1",
                    "text": "Player grounds out to shortstop",
                    "type": {"text": "At Bat"},
                    "period": {"number": 3, "type": "Top"},
                    "homeScore": 1,
                    "awayScore": 2,
                    "scoringPlay": False,
                    "scoreValue": 0,
                    "outs": 2,
                    "atBatId": "abc123",
                    "team": {"id": "9"},
                },
            ]
        }
        result = _normalize_plays(data)
        assert result["count"] == 1
        play = result["plays"][0]
        assert play["inning"] == 3
        assert play["inning_half"] == "Top"
        assert play["outs"] == 2
        assert play["at_bat_id"] == "abc123"


class TestNormalizeWinProbability:
    """Tests for win probability normalizer."""

    def test_empty_returns_error(self):
        from sports_skills.nfl._connector import _normalize_win_probability

        result = _normalize_win_probability({})
        assert result.get("error") is True

    def test_percentages_converted(self):
        from sports_skills.nfl._connector import _normalize_win_probability

        data = {
            "winprobability": [
                {"playId": "100", "homeWinPercentage": 0.4227, "tiePercentage": 0.0},
                {"playId": "101", "homeWinPercentage": 0.65, "tiePercentage": 0.0},
            ]
        }
        result = _normalize_win_probability(data)
        assert result["count"] == 2
        assert result["timeline"][0]["home_win_pct"] == 42.3
        assert result["timeline"][0]["play_id"] == "100"
        assert result["timeline"][1]["home_win_pct"] == 65.0


# ── Golf: _normalize_player_overview ─────────────────────────


class TestNormalizePlayerOverview:
    """Tests for golf player overview normalizer."""

    def test_empty_data(self):
        from sports_skills.golf._connector import _normalize_player_overview

        result = _normalize_player_overview({})
        assert result["season_stats"]["splits"] == []
        assert result["rankings"] == []
        assert result["recent_tournaments"] == []

    def test_season_stats_parsed(self):
        from sports_skills.golf._connector import _normalize_player_overview

        data = {
            "statistics": {
                "displayName": "2026 Season Overview",
                "labels": ["EVENTS", "CUTS", "TOP10", "WINS", "AVG", "EARNINGS"],
                "names": ["Tournaments Played", "Cuts Made", "Top Ten", "Wins", "Scoring Average", "Earnings"],
                "splits": [
                    {
                        "displayName": "PGA TOUR",
                        "stats": ["3", "4", "0", "0", "68.1", "$475,327"],
                    }
                ],
            }
        }
        result = _normalize_player_overview(data)
        assert result["season_stats"]["display_name"] == "2026 Season Overview"
        assert len(result["season_stats"]["splits"]) == 1
        split = result["season_stats"]["splits"][0]
        assert split["name"] == "PGA TOUR"
        assert split["Tournaments Played"] == "3"
        assert split["Earnings"] == "$475,327"

    def test_rankings_parsed(self):
        from sports_skills.golf._connector import _normalize_player_overview

        data = {
            "seasonRankings": {
                "categories": [
                    {
                        "displayName": "Earnings",
                        "abbreviation": "amount",
                        "displayValue": "$475,327",
                        "rank": 36,
                        "rankDisplayValue": "36th",
                    },
                    {
                        "displayName": "Driving Distance",
                        "name": "yardsPerDrive",
                        "abbreviation": "yardsPerDrive",
                        "value": 312.7,
                        "displayValue": "312.7",
                        "rank": 41,
                    },
                ]
            }
        }
        result = _normalize_player_overview(data)
        assert len(result["rankings"]) == 2
        assert result["rankings"][0]["name"] == "Earnings"
        assert result["rankings"][0]["rank"] == 36
        assert result["rankings"][1]["abbreviation"] == "yardsPerDrive"


# ── Golf: _normalize_scorecard ───────────────────────────────


class TestNormalizeScorecard:
    """Tests for golf scorecard normalizer."""

    def test_empty_linescores(self):
        from sports_skills.golf._connector import _normalize_scorecard

        result = _normalize_scorecard({"athlete": {}, "linescores": []})
        assert result["rounds"] == []

    def test_hole_by_hole_parsed(self):
        from sports_skills.golf._connector import _normalize_scorecard

        competitor = {
            "id": "4686",
            "athlete": {"displayName": "Scottie Scheffler", "flag": {"alt": "USA"}},
            "score": "-6",
            "linescores": [
                {
                    "period": 1,
                    "value": 65.0,
                    "displayValue": "-6",
                    "linescores": [
                        {"period": 1, "value": 3.0, "scoreType": {"displayValue": "-2"}},
                        {"period": 2, "value": 4.0, "scoreType": {"displayValue": "E"}},
                        {"period": 3, "value": 5.0, "scoreType": {"displayValue": "+1"}},
                    ],
                }
            ],
        }
        result = _normalize_scorecard(competitor, "The Genesis Invitational")
        assert result["player"]["name"] == "Scottie Scheffler"
        assert result["player"]["country"] == "USA"
        assert result["tournament"] == "The Genesis Invitational"
        assert result["overall_score"] == "-6"
        assert len(result["rounds"]) == 1
        r1 = result["rounds"][0]
        assert r1["round"] == 1
        assert r1["total_strokes"] == 65
        assert r1["total_score"] == "-6"
        assert len(r1["holes"]) == 3
        assert r1["holes"][0] == {"hole": 1, "strokes": 3, "score": "-2"}
        assert r1["holes"][1] == {"hole": 2, "strokes": 4, "score": "E"}
        assert r1["holes"][2] == {"hole": 3, "strokes": 5, "score": "+1"}

    def test_skips_invalid_periods(self):
        from sports_skills.golf._connector import _normalize_scorecard

        competitor = {
            "athlete": {},
            "linescores": [
                {"period": 0, "value": 0, "linescores": []},
                {"period": 5, "value": 0, "linescores": []},
            ],
        }
        result = _normalize_scorecard(competitor)
        assert result["rounds"] == []


# ── Football: get_player_season_stats normalizer ─────────────


class TestFootballPlayerSeasonStats:
    """Tests for football player season stats overview parsing."""

    def test_empty_gamelog(self):
        """Simulate overview response with no game log stats."""
        from sports_skills.football._connector import get_player_season_stats

        # Patch would be needed for real HTTP, but we test the shape check
        # by verifying the function signature exists and handles empty params
        result = get_player_season_stats({})
        assert result.get("error") is True
        assert "player_id" in result.get("message", "")


# ── Cross-sport normalizers (injuries, transactions, stats, futures, depth charts) ──


class TestNormalizeInjuries:
    """Tests for normalize_injuries shared normalizer."""

    def test_basic(self):
        from sports_skills._espn_base import normalize_injuries

        data = {
            "injuries": [
                {
                    "displayName": "Kansas City Chiefs",
                    "id": 12,
                    "injuries": [
                        {
                            "athlete": {
                                "displayName": "Patrick Mahomes",
                                "position": {"abbreviation": "QB"},
                            },
                            "status": "Questionable",
                            "type": {"description": "Ankle"},
                            "details": {
                                "detail": "Right ankle sprain",
                                "side": "Right",
                                "returnDate": "2026-01-15",
                            },
                        },
                        {
                            "athlete": {
                                "displayName": "Travis Kelce",
                                "position": {"abbreviation": "TE"},
                            },
                            "status": "Out",
                            "type": {"name": "Knee"},
                            "details": {"detail": "Knee surgery"},
                        },
                    ],
                },
            ]
        }
        result = normalize_injuries(data)
        assert result["count"] == 1
        team = result["teams"][0]
        assert team["team"] == "Kansas City Chiefs"
        assert team["team_id"] == "12"
        assert team["count"] == 2
        assert team["injuries"][0]["name"] == "Patrick Mahomes"
        assert team["injuries"][0]["position"] == "QB"
        assert team["injuries"][0]["status"] == "Questionable"
        assert team["injuries"][0]["type"] == "Ankle"
        assert team["injuries"][0]["detail"] == "Right ankle sprain"
        assert team["injuries"][0]["side"] == "Right"
        assert team["injuries"][0]["return_date"] == "2026-01-15"
        assert team["injuries"][1]["name"] == "Travis Kelce"
        assert team["injuries"][1]["type"] == "Knee"
        assert team["injuries"][1]["side"] == ""

    def test_empty(self):
        from sports_skills._espn_base import normalize_injuries

        result = normalize_injuries({})
        assert result == {"teams": [], "count": 0}

    def test_team_with_no_injuries(self):
        from sports_skills._espn_base import normalize_injuries

        data = {"injuries": [{"displayName": "Empty Team", "id": 99, "injuries": []}]}
        result = normalize_injuries(data)
        assert result["teams"][0]["count"] == 0
        assert result["teams"][0]["injuries"] == []


class TestNormalizeTransactions:
    """Tests for normalize_transactions shared normalizer."""

    def test_basic(self):
        from sports_skills._espn_base import normalize_transactions

        data = {
            "transactions": [
                {
                    "date": "2026-02-18T12:00Z",
                    "team": {
                        "displayName": "Los Angeles Lakers",
                        "abbreviation": "LAL",
                    },
                    "description": "Signed G John Doe to a 10-day contract.",
                },
                {
                    "date": "2026-02-17T08:00Z",
                    "team": {
                        "displayName": "Boston Celtics",
                        "abbreviation": "BOS",
                    },
                    "description": "Waived F Jane Smith.",
                },
            ]
        }
        result = normalize_transactions(data)
        assert result["count"] == 2
        assert result["transactions"][0]["date"] == "2026-02-18T12:00Z"
        assert result["transactions"][0]["team"] == "Los Angeles Lakers"
        assert result["transactions"][0]["team_abbreviation"] == "LAL"
        assert "John Doe" in result["transactions"][0]["description"]
        assert result["transactions"][1]["team_abbreviation"] == "BOS"

    def test_empty(self):
        from sports_skills._espn_base import normalize_transactions

        result = normalize_transactions({})
        assert result == {"transactions": [], "count": 0}


class TestNormalizeCoreStats:
    """Tests for normalize_core_stats shared normalizer."""

    def test_basic(self):
        from sports_skills._espn_base import normalize_core_stats

        data = {
            "splits": {
                "categories": [
                    {
                        "displayName": "Passing",
                        "stats": [
                            {
                                "name": "completions",
                                "displayName": "Completions",
                                "abbreviation": "CMP",
                                "value": 401,
                                "displayValue": "401",
                                "rank": 3,
                                "rankDisplayValue": "3rd",
                                "perGameValue": 25.1,
                                "perGameDisplayValue": "25.1",
                            },
                            {
                                "name": "passingYards",
                                "displayName": "Passing Yards",
                                "abbreviation": "YDS",
                                "value": 4839,
                                "displayValue": "4,839",
                            },
                        ],
                    },
                    {
                        "displayName": "Rushing",
                        "stats": [
                            {
                                "name": "rushingAttempts",
                                "displayName": "Rushing Attempts",
                                "abbreviation": "ATT",
                                "value": 66,
                                "displayValue": "66",
                            },
                        ],
                    },
                ]
            }
        }
        result = normalize_core_stats(data)
        assert result["count"] == 2
        passing = result["categories"][0]
        assert passing["name"] == "Passing"
        assert len(passing["stats"]) == 2
        cmp_stat = passing["stats"][0]
        assert cmp_stat["name"] == "completions"
        assert cmp_stat["display_name"] == "Completions"
        assert cmp_stat["abbreviation"] == "CMP"
        assert cmp_stat["value"] == 401
        assert cmp_stat["rank"] == 3
        assert cmp_stat["rank_display"] == "3rd"
        assert cmp_stat["per_game"] == 25.1
        assert cmp_stat["per_game_display"] == "25.1"
        yds_stat = passing["stats"][1]
        assert "rank" not in yds_stat
        assert "per_game" not in yds_stat

    def test_empty_splits(self):
        from sports_skills._espn_base import normalize_core_stats

        result = normalize_core_stats({})
        assert result == {"categories": [], "count": 0}

    def test_category_fallback_name(self):
        from sports_skills._espn_base import normalize_core_stats

        data = {"splits": {"categories": [{"name": "general", "stats": []}]}}
        result = normalize_core_stats(data)
        assert result["categories"][0]["name"] == "general"


class TestNormalizeFutures:
    """Tests for normalize_futures shared normalizer."""

    def test_basic_inline_names(self):
        """Test futures with pre-resolved names (no $ref resolution needed)."""
        from sports_skills._espn_base import normalize_futures

        data = {
            "items": [
                {
                    "id": "101",
                    "displayName": "Super Bowl Winner",
                    "futures": [
                        {
                            "books": [
                                {"athlete": {}, "team": {}, "value": "+450"},
                                {"athlete": {}, "team": {}, "value": "+600"},
                            ]
                        }
                    ],
                },
            ]
        }
        result = normalize_futures(data, limit=10)
        assert result["count"] == 1
        sb = result["futures"][0]
        assert sb["id"] == "101"
        assert sb["name"] == "Super Bowl Winner"
        assert sb["count"] == 2
        assert sb["entries"][0]["value"] == "+450"
        assert sb["entries"][0]["name"] == ""  # no $ref to resolve
        assert sb["entries"][1]["value"] == "+600"

    def test_empty(self):
        from sports_skills._espn_base import normalize_futures

        result = normalize_futures({})
        assert result == {"futures": [], "count": 0}

    def test_limit(self):
        from sports_skills._espn_base import normalize_futures

        books = [{"athlete": {}, "team": {}, "value": f"+{i}"} for i in range(20)]
        data = {"items": [{"id": "1", "name": "MVP", "futures": [{"books": books}]}]}
        result = normalize_futures(data, limit=5)
        assert result["futures"][0]["count"] == 5

    def test_name_fallback(self):
        from sports_skills._espn_base import normalize_futures

        data = {
            "items": [
                {"id": "2", "name": "Cy Young", "futures": [{"books": []}]},
            ]
        }
        result = normalize_futures(data)
        assert result["futures"][0]["name"] == "Cy Young"


class TestNormalizeDepthChart:
    """Tests for normalize_depth_chart shared normalizer."""

    def test_basic(self):
        from sports_skills._espn_base import normalize_depth_chart

        data = {
            "depthchart": [
                {
                    "name": "Offense",
                    "positions": {
                        "qb": {
                            "position": {
                                "displayName": "Quarterback",
                                "abbreviation": "QB",
                            },
                            "athletes": [
                                {"id": 4040715, "displayName": "Patrick Mahomes"},
                                {"id": 3139477, "displayName": "Carson Wentz"},
                            ],
                        },
                        "rb": {
                            "position": {
                                "displayName": "Running Back",
                                "abbreviation": "RB",
                            },
                            "athletes": [
                                {"id": 4241457, "displayName": "Isiah Pacheco"},
                            ],
                        },
                    },
                },
            ]
        }
        result = normalize_depth_chart(data)
        assert result["count"] == 1
        chart = result["charts"][0]
        assert chart["name"] == "Offense"
        assert chart["count"] == 2
        qb = chart["positions"][0]
        assert qb["key"] == "qb"
        assert qb["name"] == "Quarterback"
        assert qb["abbreviation"] == "QB"
        assert len(qb["athletes"]) == 2
        assert qb["athletes"][0]["depth"] == 1
        assert qb["athletes"][0]["name"] == "Patrick Mahomes"
        assert qb["athletes"][0]["id"] == "4040715"
        assert qb["athletes"][1]["depth"] == 2
        assert qb["athletes"][1]["name"] == "Carson Wentz"
        rb = chart["positions"][1]
        assert rb["key"] == "rb"
        assert len(rb["athletes"]) == 1

    def test_empty(self):
        from sports_skills._espn_base import normalize_depth_chart

        result = normalize_depth_chart({})
        assert result == {"charts": [], "count": 0}

    def test_position_fallback_name(self):
        from sports_skills._espn_base import normalize_depth_chart

        data = {
            "depthchart": [
                {
                    "name": "Defense",
                    "positions": {
                        "lt": {
                            "position": {},
                            "athletes": [],
                        },
                    },
                },
            ]
        }
        result = normalize_depth_chart(data)
        pos = result["charts"][0]["positions"][0]
        assert pos["name"] == "lt"
        assert pos["abbreviation"] == "LT"


# ── Schema generation ────────────────────────────────────────────


class TestParamType:
    """Tests for _param_type helper."""

    def test_bool_param(self):
        from sports_skills.cli import _param_type

        assert _param_type("google_news") == "boolean"
        assert _param_type("active") == "boolean"

    def test_int_param(self):
        from sports_skills.cli import _param_type

        assert _param_type("limit") == "integer"
        assert _param_type("season") == "integer"

    def test_string_param(self):
        from sports_skills.cli import _param_type

        assert _param_type("team_id") == "string"
        assert _param_type("query") == "string"

    def test_list_param(self):
        from sports_skills.cli import _param_type

        assert _param_type("tm_player_ids") == "array"
        assert _param_type("token_ids") == "array"


class TestGenerateSchema:
    """Tests for _generate_schema Anthropic tool schema generator."""

    def test_schema_top_level_keys(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        assert schema["sport"] == "nfl"
        assert "tools" in schema
        assert isinstance(schema["tools"], list)

    def test_tool_name_format(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        for tool in schema["tools"]:
            assert tool["name"].startswith("nfl_")

    def test_tool_has_required_fields(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        for tool in schema["tools"]:
            assert "name" in tool
            assert "command" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"
            assert "properties" in tool["parameters"]
            assert "required" in tool["parameters"]

    def test_required_params_listed(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        roster_tool = next(t for t in schema["tools"] if t["name"] == "nfl_get_team_roster")
        assert "team_id" in roster_tool["parameters"]["required"]
        assert "team_id" in roster_tool["parameters"]["properties"]

    def test_optional_params_not_in_required(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        scoreboard = next(t for t in schema["tools"] if t["name"] == "nfl_get_scoreboard")
        assert scoreboard["parameters"]["required"] == []
        assert "date" in scoreboard["parameters"]["properties"]

    def test_param_types_inferred(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        standings = next(t for t in schema["tools"] if t["name"] == "nfl_get_standings")
        assert standings["parameters"]["properties"]["season"]["type"] == "integer"

    def test_bool_param_type(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("polymarket")
        markets = next(t for t in schema["tools"] if t["name"] == "polymarket_get_sports_markets")
        assert markets["parameters"]["properties"]["active"]["type"] == "boolean"

    def test_docstrings_used_as_descriptions(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        teams = next(t for t in schema["tools"] if t["name"] == "nfl_get_teams")
        assert teams["description"] == "Get all 32 NFL teams."

    def test_all_registry_modules_generate_schema(self):
        from sports_skills.cli import _REGISTRY, _generate_schema

        for module_name in _REGISTRY:
            schema = _generate_schema(module_name)
            assert schema["sport"] == module_name
            assert len(schema["tools"]) == len(_REGISTRY[module_name])

    def test_no_params_command(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        injuries = next(t for t in schema["tools"] if t["name"] == "nfl_get_injuries")
        assert injuries["parameters"]["properties"] == {}
        assert injuries["parameters"]["required"] == []

    def test_list_param_has_array_type_and_items(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("polymarket")
        market_prices = next(
            t for t in schema["tools"] if t["name"] == "polymarket_get_market_prices"
        )
        prop = market_prices["parameters"]["properties"]["token_ids"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string"}

    def test_param_descriptions_from_docstrings(self):
        from sports_skills.cli import _generate_schema

        schema = _generate_schema("nfl")
        roster = next(t for t in schema["tools"] if t["name"] == "nfl_get_team_roster")
        team_id_prop = roster["parameters"]["properties"]["team_id"]
        assert "description" in team_id_prop
        assert len(team_id_prop["description"]) > 0


class TestParseDocstringArgs:
    """Tests for _parse_docstring_args helper."""

    def test_simple_args(self):
        from sports_skills.cli import _parse_docstring_args

        doc = """Get team roster.

        Args:
            team_id: ESPN team ID.
        """
        result = _parse_docstring_args(doc)
        assert result["team_id"] == "ESPN team ID."

    def test_multiline_description(self):
        from sports_skills.cli import _parse_docstring_args

        doc = """Get player stats.

        Args:
            player_id: ESPN athlete ID.
            league_slug: ESPN league slug (e.g. "eng.1" for Premier League,
                "esp.1" for La Liga). Defaults to "eng.1".
        """
        result = _parse_docstring_args(doc)
        assert result["player_id"] == "ESPN athlete ID."
        assert "eng.1" in result["league_slug"]
        assert "La Liga" in result["league_slug"]

    def test_no_args_section(self):
        from sports_skills.cli import _parse_docstring_args

        doc = """Get all teams."""
        result = _parse_docstring_args(doc)
        assert result == {}

    def test_empty_docstring(self):
        from sports_skills.cli import _parse_docstring_args

        assert _parse_docstring_args("") == {}
        assert _parse_docstring_args(None) == {}


class TestLoadModuleRaisesExceptions:
    """Tests that _load_module raises clean exceptions instead of sys.exit."""

    def test_unknown_module_raises_value_error(self):
        import pytest

        from sports_skills.cli import _load_module

        with pytest.raises(ValueError, match="Unknown module"):
            _load_module("nonexistent_sport")


class TestCliOptionalDependencyErrors:
    """Structured errors for missing optional deps should be machine-readable."""

    def test_cli_error_includes_optional_dependency_fields(self, capsys):
        import json

        import pytest

        from sports_skills.cli import _cli_error

        with pytest.raises(SystemExit) as exc:
            _cli_error(
                "F1 module dependencies are unavailable in this environment.",
                error_code="MISSING_OPTIONAL_DEPENDENCY",
                hint="python3 -m pip install --upgrade sports-skills",
                dependency="fastf1",
                extra="f1",
            )

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exc.value.code == 1
        assert payload["status"] is False
        assert payload["error_code"] == "MISSING_OPTIONAL_DEPENDENCY"
        assert payload["dependency"] == "fastf1"
        assert payload["extra"] == "f1"
        assert "sports-skills" in payload["hint"]
        assert "Error:" in captured.err

    def test_load_module_f1_raises_structured_optional_dependency(self, monkeypatch):
        import pytest

        import sports_skills
        from sports_skills.cli import OptionalDependencyError, _load_module

        monkeypatch.setattr(sports_skills, "f1", None, raising=False)

        with pytest.raises(OptionalDependencyError) as exc:
            _load_module("f1")

        err = exc.value
        assert err.dependency == "fastf1"
        assert err.extra == "f1"
        assert "sports-skills" in err.hint


class TestNewsQueryDefaults:
    """Query-only news calls should route to Google News automatically."""

    @staticmethod
    def _fake_feed():
        class _Feed:
            status = 200
            bozo = False
            feed = {"title": "Demo Feed"}
            entries = [
                {
                    "title": "Test Item",
                    "link": "https://example.com/item",
                    "published": "Wed, 25 Feb 2026 12:00:00 GMT",
                    "summary": "Summary",
                }
            ]

        return _Feed()

    def test_fetch_items_query_without_url_uses_google_news(self, monkeypatch):
        from sports_skills.news import fetch_items

        captured = {}

        def _fake_parse(url):
            captured["url"] = url
            return self._fake_feed()

        monkeypatch.setattr("sports_skills.news._connector.feedparser.parse", _fake_parse)

        result = fetch_items(query="Corinthians", limit=1)
        assert result["status"] is True
        assert "news.google.com/rss/search" in captured["url"]
        assert result["data"]["url"] == captured["url"]
        assert result["data"]["count"] == 1

    def test_fetch_feed_query_without_url_uses_google_news(self, monkeypatch):
        from sports_skills.news import fetch_feed

        captured = {}

        def _fake_parse(url):
            captured["url"] = url
            return self._fake_feed()

        monkeypatch.setattr("sports_skills.news._connector.feedparser.parse", _fake_parse)

        result = fetch_feed(query="NBA")
        assert result["status"] is True
        assert "news.google.com/rss/search" in captured["url"]
        assert result["data"]["title"] == "Demo Feed"

    def test_fetch_items_without_query_or_url_returns_clear_validation(self):
        from sports_skills.news import fetch_items

        result = fetch_items()
        assert result["status"] is False
        assert "Provide url or use a query for Google News" in result["message"]


class TestNFLverseNormalizers:
    """Tests for pure nflverse normalizers."""

    def test_normalize_schedule_row(self):
        from sports_skills.nfl._nflverse import _normalize_schedule_row

        row = {
            "game_id": "2024_01_KC_BAL",
            "season": 2024,
            "week": 1,
            "game_type": "REG",
            "gameday": "2024-09-05",
            "away_team": "BAL",
            "home_team": "KC",
            "away_score": 20,
            "home_score": 27,
            "location": "GEHA Field",
            "spread_line": -2.5,
        }
        result = _normalize_schedule_row(row)
        assert result["game_id"] == "2024_01_KC_BAL"
        assert result["home_team"] == "KC"
        assert result["away_score"] == 20
        assert result["spread_line"] == -2.5

    def test_normalize_player_stats_row(self):
        from sports_skills.nfl._nflverse import _normalize_player_stats_row

        row = {
            "player_id": "00-0033873",
            "player_name": "Patrick Mahomes",
            "position": "QB",
            "recent_team": "KC",
            "season": 2024,
            "season_type": "REG",
            "passing_yards": 4183,
            "passing_tds": 31,
        }
        result = _normalize_player_stats_row(row)
        assert result["player_id"] == "00-0033873"
        assert result["team"] == "KC"
        assert result["stats"]["passing_yards"] == 4183
        assert result["stats"]["passing_tds"] == 31

    def test_normalize_pbp_row(self):
        from sports_skills.nfl._nflverse import _normalize_pbp_row

        row = {
            "play_id": 55,
            "game_id": "2024_03_BUF_MIA",
            "season": 2024,
            "week": 3,
            "qtr": 4,
            "time": "02:31",
            "posteam": "BUF",
            "defteam": "MIA",
            "down": 3,
            "ydstogo": 7,
            "desc": "(2:31) J.Allen pass short middle to S.Diggs for 9 yards.",
            "epa": 1.21,
            "wpa": 0.08,
        }
        result = _normalize_pbp_row(row)
        assert result["play_id"] == "55"
        assert result["game_id"] == "2024_03_BUF_MIA"
        assert result["quarter"] == 4
        assert result["posteam"] == "BUF"
        assert result["epa"] == 1.21


class TestNFLverseOptionalDependency:
    """Missing nflverse backends should raise a clear install hint."""

    def test_load_provider_error_message(self, monkeypatch):
        import builtins

        from sports_skills.nfl._nflverse import _load_provider

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in {"nflreadpy", "nfl_data_py"}:
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        import pytest

        with pytest.raises(ImportError, match=r"sports-skills\[nfl\]"):
            _load_provider()


class TestParamsContract:
    """Verify _params() returns a wrapped dict in all modules.

    All modules use {"params": {...}} so the Machina connector contract
    is consistent and new modules can copy any pattern safely.
    """

    def test_nfl_params_is_wrapped(self):
        from sports_skills.nfl import _params

        result = _params(date="2026-02-24", week=1)
        assert "params" in result
        assert result["params"]["date"] == "2026-02-24"
        assert result["params"]["week"] == 1

    def test_nba_params_is_wrapped(self):
        from sports_skills.nba import _params

        result = _params(date="2026-02-24")
        assert "params" in result
        assert result["params"]["date"] == "2026-02-24"

    def test_nhl_params_is_wrapped(self):
        from sports_skills.nhl import _params

        result = _params(team_id="1")
        assert "params" in result
        assert result["params"]["team_id"] == "1"

    def test_mlb_params_is_wrapped(self):
        from sports_skills.mlb import _params

        result = _params(season=2025)
        assert "params" in result
        assert result["params"]["season"] == 2025

    def test_wnba_params_is_wrapped(self):
        from sports_skills.wnba import _params

        result = _params(date="2026-02-24")
        assert "params" in result
        assert result["params"]["date"] == "2026-02-24"

    def test_cfb_params_is_wrapped(self):
        from sports_skills.cfb import _params

        result = _params(season=2025, week=8)
        assert "params" in result
        assert result["params"]["season"] == 2025

    def test_cbb_params_is_wrapped(self):
        from sports_skills.cbb import _params

        result = _params(season=2025)
        assert "params" in result
        assert result["params"]["season"] == 2025

    def test_none_values_are_filtered(self):
        """None values should be dropped regardless of module."""
        from sports_skills.nfl import _params

        result = _params(date="2026-02-24", week=None)
        assert "week" not in result["params"]
        assert "date" in result["params"]

    def test_football_and_nfl_params_match_shape(self):
        """football and nfl must return the same shape — the whole point of this fix."""
        from sports_skills.football import _params as football_params
        from sports_skills.nfl import _params as nfl_params

        nfl_result = nfl_params(date="2026-02-24")
        football_result = football_params(date="2026-02-24")
        assert "params" in nfl_result
        assert "params" in football_result
        assert nfl_result["params"]["date"] == "2026-02-24"
        assert football_result["params"]["date"] == "2026-02-24"


class TestXctfParseMeetTable:
    """Tests for the meet result table parser."""

    def test_parses_meet_name_date_and_results(self):
        from sports_skills.xctf._connector import _parse_meet_table

        html = """
        <table>
          <tr><td>Stanford Invitational Mar 15, 2026</td></tr>
          <tr><td>1500</td><td>4:31.80</td><td>1st (F)</td></tr>
          <tr><td>800</td><td>2:10.30</td></tr>
        </table>
        """
        result = _parse_meet_table(html)
        assert result is not None
        assert "Stanford" in result["meet"]
        assert "2026" in result["date"]
        assert len(result["results"]) == 2
        assert result["results"][0]["event"] == "1500"
        assert result["results"][0]["mark"] == "4:31.80"
        assert result["results"][0]["place"] == "1st (F)"

    def test_returns_none_when_no_date_in_header(self):
        from sports_skills.xctf._connector import _parse_meet_table

        html = """
        <table>
          <tr><td>Season Best</td></tr>
          <tr><td>1500</td><td>4:31.80</td></tr>
        </table>
        """
        assert _parse_meet_table(html) is None

    def test_returns_none_for_empty_table(self):
        from sports_skills.xctf._connector import _parse_meet_table

        assert _parse_meet_table("<table></table>") is None


class TestXctfGetNews:
    """Tests for get_news using a mocked feedparser."""

    @staticmethod
    def _fake_feed(entries=None):
        class _Feed:
            bozo = False
            bozo_exception = None

        feed = _Feed()
        feed.entries = entries or [
            {
                "title": "McFarland Runs 3:33",
                "link": "https://www.thestridereport.com/post/mcfarland",
                "published": "Sun, 19 Apr 2026 00:27:30 GMT",
                "summary": "Big performance this weekend.",
                "tags": [{"term": "D1"}, {"term": "OUTDOORS"}],
                "author": "Admin (Garrett Zatlin)",
                "enclosures": [{"href": "https://example.com/image.jpg"}],
            }
        ]
        return feed

    def test_returns_articles_with_correct_fields(self, monkeypatch):
        from sports_skills.xctf._connector import get_news

        monkeypatch.setattr(
            "sports_skills.xctf._connector.feedparser.parse",
            lambda url: self._fake_feed(),
        )

        result = get_news()
        assert result["source"] == "The Stride Report"
        assert result["count"] == 1
        article = result["articles"][0]
        assert article["title"] == "McFarland Runs 3:33"
        assert article["categories"] == ["D1", "OUTDOORS"]
        assert article["image"] == "https://example.com/image.jpg"

    def test_limit_is_respected(self, monkeypatch):
        entries = [
            {
                "title": f"Article {i}",
                "link": f"https://example.com/{i}",
                "published": "Sun, 19 Apr 2026 00:00:00 GMT",
                "summary": "Summary.",
                "tags": [],
                "author": "",
                "enclosures": [],
            }
            for i in range(10)
        ]
        from sports_skills.xctf._connector import get_news

        monkeypatch.setattr(
            "sports_skills.xctf._connector.feedparser.parse",
            lambda url: self._fake_feed(entries=entries),
        )

        result = get_news(limit=3)
        assert result["count"] == 3
        assert len(result["articles"]) == 3

    def test_feed_error_returns_error_dict(self, monkeypatch):
        class _BrokenFeed:
            bozo = True
            bozo_exception = Exception("connection refused")
            entries = []

        from sports_skills.xctf._connector import get_news

        monkeypatch.setattr(
            "sports_skills.xctf._connector.feedparser.parse",
            lambda url: _BrokenFeed(),
        )

        result = get_news()
        assert result["error"] is True
        assert "Stride Report" in result["message"]

    def test_html_entities_unescaped(self, monkeypatch):
        entries = [
            {
                "title": "Elbadra &#38; Engelhardt Clash",
                "link": "https://example.com/1",
                "published": "Sun, 19 Apr 2026 00:00:00 GMT",
                "summary": "A &#38; B",
                "tags": [],
                "author": "",
                "enclosures": [],
            }
        ]
        from sports_skills.xctf._connector import get_news

        monkeypatch.setattr(
            "sports_skills.xctf._connector.feedparser.parse",
            lambda url: self._fake_feed(entries=entries),
        )

        result = get_news()
        assert result["articles"][0]["title"] == "Elbadra & Engelhardt Clash"
        assert result["articles"][0]["summary"] == "A & B"

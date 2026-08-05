"""Tests for the NHL API backend.

No network: `_request` is monkeypatched to serve trimmed real payloads captured
from the live endpoints (tests/fixtures/nhl_stats/), so the normalizers are
exercised against the actual response shapes.
"""

import json
import pathlib
import re

import pytest

from sports_skills.nhl import _stats

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "nhl_stats"


def _key_for(url):
    path = url.split("/v1/")[-1].split("?")[0]
    return re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")


@pytest.fixture
def offline(monkeypatch):
    """Serve every URL from its captured fixture; record what was asked."""
    calls = []

    def fake_request(url, ttl=600):
        calls.append(url)
        return json.loads((FIXTURES / f"{_key_for(url)}.json").read_text())

    monkeypatch.setattr(_stats, "_request", fake_request)
    return calls


# ── season coercion ─────────────────────────────────────────────


class TestSeasonStr:
    def test_start_year(self):
        assert _stats._season_str(2024) == "20242025"

    def test_nhl_form_passthrough(self):
        assert _stats._season_str("20242025") == "20242025"

    def test_original_six_era(self):
        assert _stats._season_str(1962) == "19621963"

    def test_none_is_current(self):
        out = _stats._season_str(None)
        assert re.fullmatch(r"\d{8}", out)
        assert int(out[4:]) == int(out[:4]) + 1

    def test_non_consecutive_halves_rejected(self):
        with pytest.raises(_stats._NhlStatsError, match="consecutive"):
            _stats._season_str("20242026")

    def test_garbage_rejected(self):
        with pytest.raises(_stats._NhlStatsError, match="Invalid season"):
            _stats._season_str("2024-25")


# ── game id validation ─────────────────────────────────────────────


class TestRequireGameId:
    def test_valid_id_passes(self):
        assert _stats._require_game_id(2023030417) == "2023030417"

    def test_missing_is_reported(self):
        with pytest.raises(_stats._NhlStatsError, match="game_id is required"):
            _stats._require_game_id(None)

    def test_espn_event_id_gets_join_guidance(self):
        with pytest.raises(_stats._NhlStatsError, match="looks like an ESPN event id"):
            _stats._require_game_id("401559593")

    def test_other_garbage_gets_the_format(self):
        with pytest.raises(_stats._NhlStatsError, match="Invalid NHL game id"):
            _stats._require_game_id("abc")


# ── team abbreviation translation ─────────────────────────────────────────────


class TestNormalizeTeam:
    @pytest.mark.parametrize(
        ("espn", "nhl"),
        [("LA", "LAK"), ("NJ", "NJD"), ("SJ", "SJS"), ("TB", "TBL"), ("UTAH", "UTA")],
    )
    def test_translates_espn_spellings(self, espn, nhl):
        assert _stats._normalize_team(espn) == nhl

    @pytest.mark.parametrize("abbr", ["TOR", "EDM", "FLA", "BOS"])
    def test_shared_spellings_untouched(self, abbr):
        assert _stats._normalize_team(abbr) == abbr

    def test_none_passes_through(self):
        assert _stats._normalize_team(None) is None

    def test_alias_maps_are_inverses(self):
        for espn, nhl in _stats._ESPN_TO_NHL.items():
            assert _stats._NHL_TO_ESPN[nhl] == espn


# ── localized-string unwrapping ─────────────────────────────────────────────


class TestDefault:
    def test_unwraps_localized(self):
        assert _stats._default({"default": "Panthers"}) == "Panthers"

    def test_plain_value_passes(self):
        assert _stats._default("Panthers") == "Panthers"
        assert _stats._default(None) is None


# ── player search and resolution ─────────────────────────────────────────────


class TestFindPlayer:
    def test_shape_with_both_abbreviations(self, offline):
        out = _stats.find_nhl_player({"params": {"name": "stutzle"}})
        assert out["count"] >= 1
        p = out["players"][0]
        assert {"player_id", "name", "is_active", "position"} <= set(p)
        assert p["team_abbreviation"]
        assert p["team_abbreviation_espn"]

    def test_missing_name_is_reported(self, offline):
        out = _stats.find_nhl_player({"params": {}})
        assert out["error"] is True


class TestResolvePlayer:
    def test_player_id_short_circuits(self, offline):
        assert _stats._resolve_player("8478402", None) == "8478402"
        assert offline == []

    def test_ascii_finds_accented(self, offline):
        """The registry stores 'Tim Stützle'; the ASCII spelling must match."""
        assert _stats._resolve_player(None, "stutzle")

    def test_neither_is_reported(self):
        with pytest.raises(_stats._NhlStatsError, match="player_id or player"):
            _stats._resolve_player(None, None)


# ── schedule ─────────────────────────────────────────────


class TestSchedule:
    def test_date_query_normalizes_games(self, offline):
        out = _stats.get_nhlstats_schedule({"params": {"date": "2024-06-24"}})
        assert out["count"] >= 1
        g = out["games"][0]
        assert {"game_id", "game_date", "away_abbreviation", "home_abbreviation"} <= set(g)
        assert re.fullmatch(r"\d{10}", g["game_id"])

    def test_team_season_rows_carry_both_abbreviations(self, offline):
        out = _stats.get_nhlstats_schedule({"params": {"season": 2024, "team": "TB"}})
        assert out["count"] > 0
        row = out["games"][0]
        assert row["team_abbreviation"] == "TBL"
        assert row["team_abbreviation_espn"] == "TB"

    def test_team_filter_translates_before_the_url(self, offline):
        _stats.get_nhlstats_schedule({"params": {"season": 2024, "team": "TB"}})
        assert "club-schedule-season/TBL/20242025" in offline[-1]

    def test_bad_date_is_reported(self, offline):
        out = _stats.get_nhlstats_schedule({"params": {"date": "June 24"}})
        assert out["error"] is True and "YYYY-MM-DD" in out["message"]


# ── player stats ─────────────────────────────────────────────


class TestPlayerStats:
    def test_seasons_are_labelled_by_league(self, offline):
        """seasonTotals spans junior/European leagues, not just the NHL —
        unlabelled rows would inflate career numbers."""
        out = _stats.get_nhlstats_player_stats({"params": {"player_id": "8478402"}})
        leagues = {s["league"] for s in out["seasons"]}
        assert "NHL" in leagues
        assert all(s.get("league") for s in out["seasons"])

    def test_career_totals_present(self, offline):
        out = _stats.get_nhlstats_player_stats({"params": {"player_id": "8478402"}})
        assert out["career_totals"]["gamesPlayed"] > 0
        assert out["player"].startswith("Connor")


# ── play-by-play ─────────────────────────────────────────────


class TestPlayByPlay:
    def test_events_carry_coordinates(self, offline):
        out = _stats.get_nhlstats_play_by_play({"params": {"game_id": "2023030417"}})
        assert out["count"] > 0
        located = [p for p in out["plays"] if p["x"] is not None]
        assert located, "fixture contains located events"
        assert {"period", "time_in_period", "event", "zone"} <= set(located[0])

    def test_player_names_resolved_from_roster(self, offline):
        """Plays reference player ids; names come from rosterSpots in the
        same payload."""
        out = _stats.get_nhlstats_play_by_play({"params": {"game_id": "2023030417"}})
        named = [p for p in out["plays"] if p.get("player")]
        assert named
        assert all(" " in p["player"] for p in named[:5])

    def test_limit_flags_truncation(self, offline):
        out = _stats.get_nhlstats_play_by_play({"params": {"game_id": "2023030417", "limit": 2}})
        assert out["count"] == 2 and out["truncated"] is True

    def test_espn_id_is_caught(self, offline):
        out = _stats.get_nhlstats_play_by_play({"params": {"game_id": "401559593"}})
        assert out["error"] is True
        assert "looks like an ESPN event id" in out["message"]


# ── boxscore ─────────────────────────────────────────────


class TestBoxscore:
    def test_both_sides_normalized(self, offline):
        out = _stats.get_nhlstats_boxscore({"params": {"game_id": "2023030417"}})
        for side in ("home", "away"):
            team = out[side]
            assert team["team_abbreviation"]
            assert team["team_abbreviation_espn"]
            assert team["skaters"], side
            assert team["goalies"], side

    def test_player_stat_bags(self, offline):
        out = _stats.get_nhlstats_boxscore({"params": {"game_id": "2023030417"}})
        skater = out["home"]["skaters"][0]
        assert skater["player_id"] and skater["name"]
        assert isinstance(skater["stats"], dict) and skater["stats"]


# ── standings ─────────────────────────────────────────────


class TestStandings:
    def test_historical_standings_normalize(self, offline):
        out = _stats.get_nhlstats_standings({"params": {"date": "1967-04-01"}})
        assert out["count"] == 6, "the Original Six"
        row = out["teams"][0]
        assert {"team_name", "wins", "losses", "points"} <= set(row)

    def test_bad_date_is_reported(self, offline):
        out = _stats.get_nhlstats_standings({"params": {"date": "yesterday"}})
        assert out["error"] is True and "YYYY-MM-DD" in out["message"]


# ── leaders ─────────────────────────────────────────────


class TestLeaders:
    def test_season_leaders(self, offline):
        out = _stats.get_nhlstats_leaders(
            {"params": {"category": "goals", "season": 2024, "limit": 3}}
        )
        assert out["count"] == 3
        row = out["leaders"][0]
        assert {"rank", "player", "value"} <= set(row)
        assert row["rank"] == 1

    def test_season_builds_typed_path(self, offline):
        _stats.get_nhlstats_leaders({"params": {"category": "goals", "season": 2024}})
        assert "skater-stats-leaders/20242025/2" in offline[-1]

    def test_goalie_categories_validated(self, offline):
        out = _stats.get_nhlstats_leaders({"params": {"position": "goalie", "category": "points"}})
        assert out["error"] is True
        assert "wins" in out["message"]

    def test_skater_categories_validated(self, offline):
        out = _stats.get_nhlstats_leaders({"params": {"category": "saves"}})
        assert out["error"] is True

    def test_invalid_position_is_reported(self, offline):
        out = _stats.get_nhlstats_leaders({"params": {"position": "defenseman"}})
        assert out["error"] is True

    def test_invalid_season_type_is_reported(self, offline):
        out = _stats.get_nhlstats_leaders(
            {"params": {"category": "goals", "season": 2024, "season_type": "finals"}}
        )
        assert out["error"] is True and "playoffs" in out["message"]


# ── failure behaviour ─────────────────────────────────────────────


class TestGuard:
    def test_unexpected_error_is_reported(self, monkeypatch):
        def boom(url, ttl=600):
            raise RuntimeError("upstream exploded")

        monkeypatch.setattr(_stats, "_request", boom)
        out = _stats.get_nhlstats_standings({"params": {}})
        assert out["error"] is True
        assert "RuntimeError" in out["message"]


class TestUserAgent:
    def test_not_python_urllib_prefixed(self):
        """api-web.nhle.com rejects exactly the Python-urllib prefix, which is
        what the shared ESPN User-Agent starts with — they must not be shared."""
        assert not _stats._NHL_HEADERS["User-Agent"].startswith("Python-urllib")

    def test_identifies_the_project(self):
        assert "sports-skills" in _stats._NHL_HEADERS["User-Agent"]

"""Tests for the MLB Stats API backend.

No network: `_request` is monkeypatched to serve trimmed real payloads captured
from the live endpoints (tests/fixtures/mlb_stats/), so the normalizers are
exercised against the actual response shapes.
"""

import json
import pathlib

import pytest

from sports_skills.mlb import _stats

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "mlb_stats"


def _fixture(path):
    return json.loads((FIXTURES / f"{path.replace('/', '_')}.json").read_text())


@pytest.fixture
def offline(monkeypatch):
    """Serve every endpoint from its captured fixture; record what was asked."""
    calls = []

    def fake_request(path, params=None, ttl=600):
        calls.append((path, params))
        return _fixture(path)

    monkeypatch.setattr(_stats, "_request", fake_request)
    return calls


# ── season coercion ─────────────────────────────────────────────


class TestSeasonStr:
    def test_year_int(self):
        assert _stats._season_str(2024) == "2024"

    def test_year_str(self):
        assert _stats._season_str("1927") == "1927"

    def test_none_is_recent_season(self):
        assert _stats._season_str(None).isdigit()

    def test_nba_style_form_is_rejected(self):
        """MLB seasons are calendar years, not spans."""
        with pytest.raises(_stats._MlbStatsError, match="Invalid season"):
            _stats._season_str("2024-25")


# ── game_pk validation ─────────────────────────────────────────────


class TestRequireGamePk:
    def test_valid_pk_passes(self):
        assert _stats._require_game_pk(775296) == "775296"

    def test_missing_is_reported(self):
        with pytest.raises(_stats._MlbStatsError, match="game_pk is required"):
            _stats._require_game_pk(None)

    def test_espn_event_id_gets_join_guidance(self):
        """The natural mistake: both id systems live in this module."""
        with pytest.raises(_stats._MlbStatsError, match="looks like an ESPN event id"):
            _stats._require_game_pk("401570367")

    def test_other_garbage_gets_the_format(self):
        with pytest.raises(_stats._MlbStatsError, match="Invalid game_pk"):
            _stats._require_game_pk("abc")


# ── team resolution ─────────────────────────────────────────────


class TestResolveTeam:
    @pytest.mark.parametrize(("espn", "mlb"), [("ARI", "AZ"), ("CHW", "CWS")])
    def test_espn_spellings_translate(self, offline, espn, mlb):
        record = _stats._resolve_team(espn)
        assert record["abbreviation"] == mlb
        assert record["team_id"]

    def test_mlb_spelling_passes(self, offline):
        assert _stats._resolve_team("NYY")["name"] == "New York Yankees"

    def test_unknown_team_lists_valid(self, offline):
        with pytest.raises(_stats._MlbStatsError, match="ESPN spellings ARI and CHW"):
            _stats._resolve_team("ZZZ")

    def test_none_passes_through(self):
        assert _stats._resolve_team(None) is None

    def test_alias_maps_are_inverses(self):
        for espn, mlb in _stats._ESPN_TO_MLB.items():
            assert _stats._MLB_TO_ESPN[mlb] == espn


# ── name matching ─────────────────────────────────────────────


class TestFindPlayer:
    def test_ascii_finds_accented(self, offline):
        out = _stats.find_mlb_player({"params": {"name": "acuna"}})
        assert out["count"] >= 1
        assert any("Acu" in p["name"] for p in out["players"])

    def test_shape(self, offline):
        p = _stats.find_mlb_player({"params": {"name": "acuna"}})["players"][0]
        assert {"player_id", "name", "is_active", "position", "team"} <= set(p)

    def test_missing_name_is_reported(self, offline):
        out = _stats.find_mlb_player({"params": {}})
        assert out["error"] is True

    def test_copyright_passthrough(self, offline):
        out = _stats.find_mlb_player({"params": {"name": "acuna"}})
        assert "Copyright" in str(out.get("copyright", ""))


class TestResolvePlayer:
    def test_player_id_short_circuits(self, offline):
        pid, _ = _stats._resolve_player("660271", None)
        assert pid == "660271"
        assert offline == []

    def test_ambiguous_name_lists_candidates(self, offline):
        with pytest.raises(_stats._MlbStatsError, match="matched"):
            _stats._resolve_player(None, "acuna")

    def test_neither_is_reported(self):
        with pytest.raises(_stats._MlbStatsError, match="player_id or player"):
            _stats._resolve_player(None, None)


# ── schedule ─────────────────────────────────────────────


class TestSchedule:
    def test_team_season_rows_carry_both_abbreviations(self, offline):
        out = _stats.get_mlbstats_schedule({"params": {"season": 2024, "team": "CHW"}})
        assert out["count"] > 0
        row = out["games"][0]
        assert row["team_abbreviation"] == "CWS"
        assert row["team_abbreviation_espn"] == "CHW"
        assert row["game_pk"]

    def test_date_query_needs_no_team(self, offline):
        out = _stats.get_mlbstats_schedule({"params": {"date": "2024-10-30"}})
        assert out["count"] > 0

    def test_bad_date_is_reported(self, offline):
        out = _stats.get_mlbstats_schedule({"params": {"date": "Oct 30"}})
        assert out["error"] is True and "YYYY-MM-DD" in out["message"]

    def test_league_wide_season_is_refused(self, offline):
        """~2,430 games; require a narrower ask."""
        out = _stats.get_mlbstats_schedule({"params": {"season": 2024}})
        assert out["error"] is True
        assert "team=" in out["message"]

    def test_game_type_is_sent_upstream(self, offline):
        _stats.get_mlbstats_schedule(
            {"params": {"season": 2024, "team": "NYY", "game_type": "worldseries"}}
        )
        path, params = offline[-1]
        assert path == "schedule"
        assert params["gameType"] == "W"

    def test_invalid_game_type_lists_valid(self, offline):
        out = _stats.get_mlbstats_schedule(
            {"params": {"season": 2024, "team": "NYY", "game_type": "finals"}}
        )
        assert out["error"] is True and "worldseries" in out["message"]


# ── player stats ─────────────────────────────────────────────


class TestPlayerStats:
    def test_season_split_shape(self, offline):
        out = _stats.get_mlbstats_player_stats({"params": {"player_id": "660271", "season": 2024}})
        assert out["count"] >= 1
        split = out["splits"][0]
        assert split["stats"], "stat bag must not be empty"

    def test_season_param_only_sent_for_season_type(self, offline):
        _stats.get_mlbstats_player_stats(
            {"params": {"player_id": "660271", "stat_type": "career", "stat_group": "pitching"}}
        )
        path, params = offline[-1]
        assert "season" not in params
        assert params["stats"] == "career"
        assert params["group"] == "pitching"

    def test_invalid_group_lists_valid(self, offline):
        out = _stats.get_mlbstats_player_stats(
            {"params": {"player_id": "1", "stat_group": "batting"}}
        )
        assert out["error"] is True and "hitting" in out["message"]


# ── play-by-play ─────────────────────────────────────────────


class TestPlayByPlay:
    def test_pitch_level_fields(self, offline):
        out = _stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296"}})
        play = out["plays"][0]
        assert {"inning", "half", "batter", "pitcher", "event", "pitches"} <= set(play)
        pitch = play["pitches"][0]
        assert {"type", "speed_mph", "spin_rpm", "plate_x", "plate_z"} <= set(pitch)

    def test_hit_data_attaches_to_balls_in_play(self, offline):
        out = _stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296"}})
        hits = [
            p["hit"]
            for play in out["plays"]
            for p in play["pitches"]
            if "hit" in p
        ]
        assert hits, "fixture contains balls in play"
        assert {"exit_velocity_mph", "launch_angle", "distance_ft"} <= set(hits[0])

    def test_limit_flags_truncation(self, offline):
        out = _stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296", "limit": 2}})
        assert out["count"] == 2
        assert out["truncated"] is True

    def test_espn_id_is_caught(self, offline):
        out = _stats.get_mlbstats_play_by_play({"params": {"game_pk": "401570367"}})
        assert out["error"] is True
        assert "looks like an ESPN event id" in out["message"]


# ── boxscore ─────────────────────────────────────────────


class TestBoxscore:
    def test_both_sides_normalized(self, offline):
        out = _stats.get_mlbstats_boxscore({"params": {"game_pk": "775296"}})
        for side in ("home", "away"):
            team = out[side]
            assert team["team_name"]
            assert team["team_abbreviation_espn"]
            assert team["stats"]["batting"]
            assert team["players"], side

    def test_players_carry_split_stat_bags(self, offline):
        out = _stats.get_mlbstats_boxscore({"params": {"game_pk": "775296"}})
        player = out["home"]["players"][0]
        assert player["player_id"] and player["name"]
        assert isinstance(player["batting"], dict)
        assert isinstance(player["pitching"], dict)


# ── standings ─────────────────────────────────────────────


class TestStandings:
    def test_division_rows(self, offline):
        out = _stats.get_mlbstats_standings({"params": {"season": 2024}})
        assert out["count"] > 0
        row = out["divisions"][0]["teams"][0]
        assert {"team_name", "wins", "losses", "pct", "games_back"} <= set(row)


# ── leaders ─────────────────────────────────────────────


class TestLeaders:
    def test_rows_are_labelled_by_stat_group(self, offline):
        """homeRuns exists for hitting, catching AND pitching (HRs allowed) —
        flattening without labels would silently mix them."""
        out = _stats.get_mlbstats_leaders({"params": {"category": "homeRuns", "season": 2024}})
        groups = {r["stat_group"] for r in out["leaders"]}
        assert len(groups) > 1
        assert out["warnings"] and "stat_group" in out["warnings"][0]

    def test_leader_shape(self, offline):
        row = _stats.get_mlbstats_leaders(
            {"params": {"category": "homeRuns", "season": 2024}}
        )["leaders"][0]
        assert {"rank", "player", "team", "value", "stat_group"} <= set(row)

    def test_missing_category_shows_examples(self, offline):
        out = _stats.get_mlbstats_leaders({"params": {}})
        assert out["error"] is True and "homeRuns" in out["message"]

    def test_group_is_sent_upstream(self, offline):
        _stats.get_mlbstats_leaders(
            {"params": {"category": "strikeouts", "season": 2024, "stat_group": "pitching"}}
        )
        path, params = offline[-1]
        assert params["statGroup"] == "pitching"


# ── failure behaviour ─────────────────────────────────────────────


class TestGuard:
    def test_unexpected_error_is_reported(self, monkeypatch):
        def boom(path, params=None, ttl=600):
            raise RuntimeError("upstream exploded")

        monkeypatch.setattr(_stats, "_request", boom)
        out = _stats.get_mlbstats_standings({"params": {}})
        assert out["error"] is True
        assert "RuntimeError" in out["message"]

    def test_http_errors_pass_through_summarized(self, monkeypatch):
        def fake_fetch(url, **kw):
            return None, {"error": True, "message": "HTTP 404 from statsapi.mlb.com"}

        monkeypatch.setattr(_stats, "_http_fetch", fake_fetch)
        monkeypatch.setattr(_stats, "_cache_get", lambda k: None)
        with pytest.raises(_stats._MlbStatsError, match="HTTP 404"):
            _stats._request("game/1/boxscore")

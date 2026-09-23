"""sort_by / descending / limit / fields on wide endpoints (issue #143).

Shaping runs on normalized rows after the provider fetch, so the upstream
request and the record/replay key never change, and a call without shaping
params returns exactly what it did before.
"""

import importlib.util
import json
import pathlib

import pandas as pd
import pytest

from sports_skills import _replay, nfl
from sports_skills._shaping import ShapingError, shape_rows
from sports_skills.cli import _parse_value
from sports_skills.mlb import _stats as mlb_stats
from sports_skills.nba import _stats as nba_stats
from sports_skills.nfl import _nflverse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ── helper ─────────────────────────────────────────────


ROWS = [
    {"id": "a", "name": "Zed", "yds": 120, "team": "KC"},
    {"id": "b", "name": "Amy", "yds": "389", "team": "LA"},
    {"id": "c", "name": "Bob", "yds": None, "team": "BUF"},
    {"id": "d", "name": "Cat", "yds": 7.5, "team": "SF"},
    {"id": "e", "name": "Dan", "yds": float("nan"), "team": "NE"},
    {"id": "f", "name": "Eve", "team": "NYJ"},
]


def _ids(rows):
    return [r["id"] for r in rows]


class TestShapeRows:
    def test_no_params_returns_same_object_and_no_meta(self):
        rows, meta = shape_rows(ROWS, {})
        assert rows is ROWS
        assert meta == {}

    def test_descending_alone_is_a_no_op(self):
        rows, meta = shape_rows(ROWS, {"descending": False})
        assert rows is ROWS and meta == {}

    def test_numeric_sort_descending_by_default(self):
        rows, _ = shape_rows(ROWS, {"sort_by": "yds"})
        # "389" is a numeric string and sorts as 389; missing (None, NaN, absent) go last.
        assert _ids(rows) == ["b", "a", "d", "c", "e", "f"]

    def test_ascending_keeps_missing_last(self):
        rows, _ = shape_rows(ROWS, {"sort_by": "yds", "descending": False})
        assert _ids(rows) == ["d", "a", "b", "c", "e", "f"]

    def test_descending_accepts_string_forms(self):
        rows, _ = shape_rows(ROWS, {"sort_by": "yds", "descending": "false"})
        assert _ids(rows)[0] == "d"

    def test_string_sort(self):
        rows, _ = shape_rows(ROWS, {"sort_by": "name", "descending": False})
        assert [r["name"] for r in rows] == ["Amy", "Bob", "Cat", "Dan", "Eve", "Zed"]

    def test_numbers_before_strings_in_both_directions(self):
        mixed = [{"v": "n/a"}, {"v": 3}, {"v": "abc"}, {"v": 10}]
        down, _ = shape_rows(mixed, {"sort_by": "v"})
        up, _ = shape_rows(mixed, {"sort_by": "v", "descending": False})
        assert [r["v"] for r in down] == [10, 3, "n/a", "abc"]
        assert [r["v"] for r in up] == [3, 10, "abc", "n/a"]

    def test_sort_is_stable_for_ties(self):
        rows = [{"k": 1, "i": 0}, {"k": 1, "i": 1}, {"k": 2, "i": 2}]
        out, _ = shape_rows(rows, {"sort_by": "k"})
        assert [r["i"] for r in out] == [2, 0, 1]

    def test_limit_applies_after_sort_and_reports_counts(self):
        rows, meta = shape_rows(ROWS, {"sort_by": "yds", "limit": 2})
        assert _ids(rows) == ["b", "a"]
        assert meta == {"total_rows": 6, "returned_rows": 2}

    def test_limit_alone_keeps_order(self):
        rows, meta = shape_rows(ROWS, {"limit": "3"})
        assert _ids(rows) == ["a", "b", "c"]
        assert meta == {"total_rows": 6, "returned_rows": 3}

    def test_total_rows_override(self):
        _, meta = shape_rows(ROWS[:2], {"limit": 2}, total_rows=50)
        assert meta == {"total_rows": 50, "returned_rows": 2}

    def test_fields_keep_list_plus_identity(self):
        rows, _ = shape_rows(ROWS, {"fields": "yds"}, identity=("id", "name"))
        assert rows[0] == {"id": "a", "name": "Zed", "yds": 120}
        assert rows[5] == {"id": "f", "name": "Eve"}

    def test_fields_accepts_list_and_whitespace(self):
        rows, _ = shape_rows(ROWS, {"fields": [" team ", "yds"]})
        assert rows[0] == {"yds": 120, "team": "KC"}

    def test_fields_always_keeps_sort_column(self):
        rows, _ = shape_rows(ROWS, {"fields": "team", "sort_by": "yds", "limit": 1})
        assert rows == [{"yds": "389", "team": "LA"}]

    def test_fields_does_not_mutate_input(self):
        before = json.dumps(ROWS, default=str)
        shape_rows(ROWS, {"fields": "yds", "sort_by": "yds"})
        assert json.dumps(ROWS, default=str) == before

    def test_nested_columns_are_addressable(self):
        rows = [
            {"player_id": "1", "team": "KC", "stats": {"passing_yards": 200, "attempts": 30, "sacks": 2}},
            {"player_id": "2", "team": "LA", "stats": {"passing_yards": 389, "attempts": 41, "sacks": 1}},
        ]
        out, _ = shape_rows(
            rows, {"sort_by": "passing_yards", "fields": "attempts"}, identity=("player_id",), nested="stats"
        )
        assert out == [
            {"player_id": "2", "stats": {"passing_yards": 389, "attempts": 41}},
            {"player_id": "1", "stats": {"passing_yards": 200, "attempts": 30}},
        ]

    def test_unknown_sort_column_lists_valid_columns(self):
        with pytest.raises(ShapingError) as exc:
            shape_rows(ROWS, {"sort_by": "passing_yds"})
        msg = str(exc.value)
        assert "Unknown sort_by column 'passing_yds'" in msg
        assert "Valid columns: id, name, yds, team" in msg

    def test_unknown_fields_are_all_named(self):
        with pytest.raises(ShapingError, match=r"Unknown fields 'foo', 'bar'\. Valid columns: id, name, yds, team"):
            shape_rows(ROWS, {"fields": "yds,foo,bar"})

    def test_nested_keys_are_listed_as_valid(self):
        rows = [{"player_id": "1", "stats": {"passing_yards": 1}}]
        with pytest.raises(ShapingError, match="Valid columns: player_id, passing_yards"):
            shape_rows(rows, {"sort_by": "nope"}, nested="stats")

    @pytest.mark.parametrize("bad", [0, -1, "x", True, 1.5j])
    def test_invalid_limit(self, bad):
        with pytest.raises(ShapingError, match="must be a positive integer"):
            shape_rows(ROWS, {"limit": bad})

    def test_invalid_descending(self):
        with pytest.raises(ShapingError, match="use true or false"):
            shape_rows(ROWS, {"sort_by": "yds", "descending": "maybe"})

    def test_empty_fields(self):
        with pytest.raises(ShapingError, match="fields is empty"):
            shape_rows(ROWS, {"fields": " , "})

    def test_empty_rows_skip_column_validation(self):
        rows, meta = shape_rows([], {"sort_by": "anything", "fields": "x", "limit": 5})
        assert rows == [] and meta == {"total_rows": 0, "returned_rows": 0}


def test_cli_parses_shaping_params():
    assert _parse_value("descending", "false") is False
    assert _parse_value("descending", "true") is True
    assert _parse_value("limit", "5") == 5
    assert _parse_value("sort_by", "passing_yards") == "passing_yards"
    assert _parse_value("fields", "a,b") == "a,b"


# ── nflverse ─────────────────────────────────────────────


QBS = [
    ("00-0026498", "M.Stafford", "Matthew Stafford", "LA", 389, 41),
    ("00-0034796", "L.Jackson", "Lamar Jackson", "BAL", 250, 30),
    ("00-0036442", "J.Burrow", "Joe Burrow", "CIN", 301, 38),
    ("00-0029263", "R.Wilson", "Russell Wilson", "NYG", 150, 22),
    ("00-0033873", "P.Mahomes", "Patrick Mahomes", "KC", 318, 40),
    ("00-0035228", "K.Murray", "Kyler Murray", "ARI", 220, 33),
    ("00-0039999", "B.Backup", "Bench Backup", "SF", float("nan"), 0),
]


class _FakeNflreadpy:
    def __init__(self):
        self.calls = []

    def load_player_stats(self, seasons, summary_level="reg"):
        self.calls.append(("player_stats", seasons, summary_level))
        rows = [
            {
                "player_id": pid,
                "player_name": short,
                "player_display_name": full,
                "position": "QB",
                "recent_team": team,
                "season": 2025,
                "week": 5,
                "passing_yards": yds,
                "attempts": att,
                "passing_epa": 1.5,
            }
            for pid, short, full, team, yds, att in QBS
        ]
        rows.append({**rows[0], "player_id": "00-1", "player_name": "R.Back", "position": "RB", "passing_yards": 0})
        return pd.DataFrame(rows)

    def load_schedules(self, seasons):
        self.calls.append(("schedules", seasons))
        return pd.DataFrame(
            {
                "game_id": ["2025_05_A_B", "2025_05_C_D"],
                "season": [2025, 2025],
                "week": [5, 5],
                "home_team": ["B", "D"],
                "away_team": ["A", "C"],
                "total": [40.0, 61.0],
            }
        )

    def load_pbp(self, seasons):
        self.calls.append(("pbp", seasons))
        return pd.DataFrame(
            {
                "play_id": [1, 2, 3, 4],
                "game_id": ["G"] * 4,
                "week": [5] * 4,
                "desc": ["run", "pass", "punt", "td"],
                "epa": [0.1, -0.4, float("nan"), 3.2],
            }
        )


@pytest.fixture
def fake_nflverse(monkeypatch):
    fake = _FakeNflreadpy()
    monkeypatch.setattr(_nflverse, "_load_provider", lambda: ("nflreadpy", fake))
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    return fake


class TestNflversePlayerStats:
    def test_week_leader_via_sort_and_limit(self, fake_nflverse):
        out = nfl.get_nflverse_player_stats(season=2025, week=5, position="QB", sort_by="passing_yards", limit=5)
        data = out["data"]
        assert out["status"] is True
        assert data["count"] == data["returned_rows"] == 5
        assert data["total_rows"] == 7
        yards = [p["stats"]["passing_yards"] for p in data["players"]]
        assert yards == [389, 318, 301, 250, 220]
        assert data["players"][0]["player_name"] == "M.Stafford"

    def test_fields_trim_stats_but_keep_identity(self, fake_nflverse):
        out = nfl.get_nflverse_player_stats(
            season=2025, week=5, position="QB", sort_by="passing_yards", limit=1, fields="attempts"
        )
        (row,) = out["data"]["players"]
        assert row == {
            "player_id": "00-0026498",
            "player_name": "M.Stafford",
            "position": "QB",
            "team": "LA",
            "stats": {"week": 5, "passing_yards": 389, "attempts": 41},
        }

    def test_display_name_is_not_a_column_and_error_says_so(self, fake_nflverse):
        out = nfl.get_nflverse_player_stats(season=2025, week=5, fields="player_display_name")
        assert out["status"] is False
        assert "Unknown fields 'player_display_name'" in out["message"]
        assert "player_name" in out["message"] and "passing_yards" in out["message"]

    def test_unknown_sort_column_is_an_error_not_a_crash(self, fake_nflverse):
        out = nfl.get_nflverse_player_stats(season=2025, week=5, sort_by="pass_yds")
        assert out["status"] is False
        assert out["message"].startswith("Unknown sort_by column 'pass_yds'. Valid columns: player_id,")

    def test_no_params_output_is_unchanged(self, fake_nflverse):
        out = nfl.get_nflverse_player_stats(season=2025, week=5, position="QB")
        data = out["data"]
        assert "total_rows" not in data and "returned_rows" not in data
        assert list(data) == [
            "provider", "provider_impl", "season", "summary_level", "week",
            "player_id", "team", "position", "players", "count",
        ]
        assert data["players"][0] == {
            "player_id": "00-0026498",
            "player_name": "M.Stafford",
            "position": "QB",
            "team": "LA",
            "season": 2025,
            "season_type": "REG",
            "stats": {"week": 5, "passing_yards": 389, "attempts": 41, "passing_epa": 1.5},
        }
        # Upstream order preserved; the NaN row carries no passing_yards at all.
        assert [p["player_id"] for p in data["players"]] == [q[0] for q in QBS]
        assert "passing_yards" not in data["players"][-1]["stats"]
        assert data["count"] == 7

    def test_same_upstream_call_with_and_without_shaping(self, fake_nflverse):
        nfl.get_nflverse_player_stats(season=2025, week=5)
        nfl.get_nflverse_player_stats(season=2025, week=5, sort_by="passing_yards", limit=1, fields="attempts")
        assert fake_nflverse.calls == [("player_stats", [2025], "week")] * 2


class TestNflverseOtherTables:
    def test_schedule_sort(self, fake_nflverse):
        out = nfl.get_nflverse_schedule(season=2025, week=5, sort_by="total", limit=1, fields="total")
        assert out["data"]["events"] == [
            {"game_id": "2025_05_C_D", "week": 5, "away_team": "C", "home_team": "D", "total": 61.0}
        ]
        assert out["data"]["total_rows"] == 2

    def test_pbp_limit_without_sort_keeps_existing_truncation(self, fake_nflverse):
        data = nfl.get_nflverse_play_by_play(season=2025, limit=2)["data"]
        assert [p["play_id"] for p in data["plays"]] == ["1", "2"]
        assert data["truncated"] is True
        assert data["total_rows"] == 4 and data["returned_rows"] == 2

    def test_pbp_sort_then_limit(self, fake_nflverse):
        data = nfl.get_nflverse_play_by_play(season=2025, sort_by="epa", limit=2, fields="desc")["data"]
        assert data["plays"] == [
            {"play_id": "4", "game_id": "G", "desc": "td", "epa": 3.2},
            {"play_id": "1", "game_id": "G", "desc": "run", "epa": 0.1},
        ]

    def test_pbp_invalid_limit_is_reported(self, fake_nflverse):
        out = nfl.get_nflverse_play_by_play(season=2025, limit="lots")
        assert out["status"] is False and "positive integer" in out["message"]


needs_parquet = pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None, reason="frame replay stores Parquet and needs pyarrow"
)


class _ExplodingProvider:
    def __getattr__(self, name):
        raise AssertionError(f"nflverse provider called during replay: {name}")


@needs_parquet
def test_replay_entry_serves_shaped_and_unshaped_calls(monkeypatch, tmp_path):
    """One recorded frame answers both calls: shaping never enters the replay key."""
    monkeypatch.setattr(_nflverse, "_load_provider", lambda: ("nflreadpy", _FakeNflreadpy()))
    monkeypatch.setenv(_replay.MODE_ENV, "record")
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    plain = nfl.get_nflverse_player_stats(season=2025, week=5)
    assert len(list(tmp_path.rglob("*.parquet"))) == 1

    monkeypatch.setattr(_nflverse, "_load_provider", lambda: ("nflreadpy", _ExplodingProvider()))
    monkeypatch.setenv(_replay.MODE_ENV, "replay")
    assert nfl.get_nflverse_player_stats(season=2025, week=5) == plain
    shaped = nfl.get_nflverse_player_stats(season=2025, week=5, position="QB", sort_by="passing_yards", limit=1)
    assert shaped["status"] is True
    assert shaped["data"]["players"][0]["stats"]["passing_yards"] == 389
    assert len(list(tmp_path.rglob("*.parquet"))) == 1


# ── NBA / MLB stats ─────────────────────────────────────────────


@pytest.fixture
def nba_offline(monkeypatch):
    calls = []

    def fake_request(endpoint, params, ttl=600):
        calls.append((endpoint, params))
        return json.loads((FIXTURES / "nba_stats" / f"{endpoint}.json").read_text())

    monkeypatch.setattr(nba_stats, "_request", fake_request)
    return calls


class TestNbaStats:
    def test_game_log_sort_limit_fields(self, nba_offline):
        plain = nba_stats.get_nbastats_game_log({"params": {"season": 2024}})
        out = nba_stats.get_nbastats_game_log(
            {"params": {"season": 2024, "sort_by": "pts", "limit": 3, "fields": "wl,pts"}}
        )
        best = sorted((g["pts"] for g in plain["games"]), reverse=True)[:3]
        assert [g["pts"] for g in out["games"]] == best
        assert set(out["games"][0]) == {"game_id", "game_date", "team_abbreviation", "matchup", "wl", "pts"}
        assert out["total_rows"] == plain["count"] and out["returned_rows"] == out["count"] == 3
        # Same upstream request either way: HTTP replay keys are unchanged.
        assert nba_offline[0] == nba_offline[1]

    def test_game_log_no_params_unchanged(self, nba_offline):
        out = nba_stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert list(out) == ["provider", "season", "season_type", "team", "games", "count"]
        assert out["count"] == len(out["games"]) == 40

    def test_game_log_unknown_column(self, nba_offline):
        out = nba_stats.get_nbastats_game_log({"params": {"season": 2024, "sort_by": "points"}})
        assert out["error"] is True
        assert "Unknown sort_by column 'points'" in out["message"] and "pts" in out["message"]

    def test_team_stats_sort(self, nba_offline):
        out = nba_stats.get_nbastats_team_stats({"params": {"season": 2024, "sort_by": "w", "limit": 1}})
        plain = nba_stats.get_nbastats_team_stats({"params": {"season": 2024}})
        assert out["teams"][0]["w"] == max(t["w"] for t in plain["teams"])

    def test_shot_chart_sort_then_limit(self, nba_offline):
        plain = nba_stats.get_nbastats_shot_chart({"params": {"player_id": "203999", "season": 2024}})
        out = nba_stats.get_nbastats_shot_chart(
            {"params": {"player_id": "203999", "season": 2024, "sort_by": "shot_distance", "limit": 2}}
        )
        longest = sorted((s["shot_distance"] for s in plain["shots"]), reverse=True)[:2]
        assert [s["shot_distance"] for s in out["shots"]] == longest
        assert out["truncated"] is True and out["total_rows"] == plain["count"]


@pytest.fixture
def mlb_offline(monkeypatch):
    def fake_request(path, params=None, ttl=600):
        return json.loads((FIXTURES / "mlb_stats" / f"{path.replace('/', '_')}.json").read_text())

    monkeypatch.setattr(mlb_stats, "_request", fake_request)


class TestMlbPlayByPlay:
    def test_fields_drop_pitch_lists(self, mlb_offline):
        out = mlb_stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296", "fields": "event"}})
        assert set(out["plays"][0]) == {"inning", "half", "batter", "pitcher", "event"}
        assert out["total_rows"] == out["returned_rows"] == out["count"]

    def test_sort_by_rbi(self, mlb_offline):
        out = mlb_stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296", "sort_by": "rbi", "limit": 1}})
        plain = mlb_stats.get_mlbstats_play_by_play({"params": {"game_pk": "775296"}})
        assert out["plays"][0]["rbi"] == max(p["rbi"] for p in plain["plays"] if p["rbi"] is not None)
        assert "total_rows" not in plain


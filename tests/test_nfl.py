"""Tests for the nflverse backend and its ESPN interop surface.

No network: the provider module is substituted and the normalizers are driven
with representative rows.
"""

import builtins
import sys
import types

import pytest

from sports_skills.nfl import _nflverse

# ── Team abbreviation normalization ─────────────────────────────────────────────


class TestNormalizeTeam:
    """ESPN and nflverse disagree on how two clubs are spelled."""

    @pytest.mark.parametrize(("espn", "nflverse"), [("LAR", "LA"), ("WSH", "WAS")])
    def test_translates_espn_spellings(self, espn, nflverse):
        assert _nflverse._normalize_team(espn) == nflverse

    @pytest.mark.parametrize("abbr", ["KC", "BAL", "SF", "NE"])
    def test_leaves_shared_spellings_alone(self, abbr):
        assert _nflverse._normalize_team(abbr) == abbr

    def test_uppercases_and_strips(self):
        assert _nflverse._normalize_team(" lar ") == "LA"

    def test_none_passes_through(self):
        assert _nflverse._normalize_team(None) is None

    @pytest.mark.parametrize("abbr", ["OAK", "SD", "STL"])
    def test_relocations_are_not_aliased(self, abbr):
        """nflverse uses era-correct abbreviations; aliasing would corrupt history."""
        assert _nflverse._normalize_team(abbr) == abbr


# ── Identifier coercion ─────────────────────────────────────────────


class TestAsId:
    """Numeric ids arrive as floats from one of the backends."""

    def test_float_loses_the_decimal(self):
        assert _nflverse._as_id(401671789.0) == "401671789"

    def test_int_becomes_str(self):
        assert _nflverse._as_id(401671789) == "401671789"

    def test_str_passes_through(self):
        assert _nflverse._as_id("401671789") == "401671789"

    def test_none_and_empty_are_none(self):
        assert _nflverse._as_id(None) is None
        assert _nflverse._as_id("") is None


# ── Summary level resolution ─────────────────────────────────────────────


class TestResolveSummaryLevel:
    """Season aggregates are the documented default; a week implies weekly rows."""

    def test_defaults_to_regular_season(self):
        assert _nflverse._resolve_summary_level({}) == "reg"

    def test_week_implies_weekly(self):
        assert _nflverse._resolve_summary_level({"week": 1}) == "week"

    @pytest.mark.parametrize("level", ["week", "reg", "post", "reg+post"])
    def test_explicit_levels_accepted(self, level):
        assert _nflverse._resolve_summary_level({"summary_level": level}) == level

    def test_case_insensitive(self):
        assert _nflverse._resolve_summary_level({"summary_level": "REG"}) == "reg"

    def test_invalid_level_is_reported(self):
        with pytest.raises(_nflverse._NflverseUnavailable, match="Invalid summary_level"):
            _nflverse._resolve_summary_level({"summary_level": "season"})

    def test_week_with_aggregate_level_is_reported(self):
        """`reg` has no week column, so the filter would be silently dropped."""
        with pytest.raises(_nflverse._NflverseUnavailable, match="no week column"):
            _nflverse._resolve_summary_level({"week": 1, "summary_level": "reg"})


# ── Season resolution and fallback ─────────────────────────────────────────────


class TestSeasonFallback:
    """nflverse ships the upcoming schedule long before its derived tables."""

    def test_explicit_season_is_flagged(self):
        assert _nflverse._resolve_season({"season": 2024}) == (2024, True)

    def test_absent_season_is_implied(self):
        season, explicit = _nflverse._resolve_season({})
        assert explicit is False and isinstance(season, int)

    def test_implied_season_steps_back(self):
        calls = []

        def loader(year):
            calls.append(year)
            if year == 2025:
                return "frame"
            raise ValueError("Season must be between 1999 and 2025")

        frame, season, note = _nflverse._load_with_season_fallback(loader, 2026, explicit=False)
        assert frame == "frame" and season == 2025
        assert note and "2026" in note and "2025" in note
        assert calls == [2026, 2025]

    def test_explicit_season_raises_instead(self):
        def loader(year):
            raise ValueError("Season must be between 1999 and 2025")

        with pytest.raises(ValueError, match="Season must be between"):
            _nflverse._load_with_season_fallback(loader, 2026, explicit=True)

    def test_both_years_failing_raises_original(self):
        def loader(year):
            raise ValueError(f"no data for {year}")

        with pytest.raises(ValueError, match="no data for 2026"):
            _nflverse._load_with_season_fallback(loader, 2026, explicit=False)

    def test_working_season_is_untouched(self):
        frame, season, note = _nflverse._load_with_season_fallback(
            lambda y: f"frame-{y}", 2024, explicit=False
        )
        assert frame == "frame-2024" and season == 2024 and note is None


# ── Schedule normalization ─────────────────────────────────────────────


class TestNormalizeScheduleRow:
    """The schedule row is the ESPN↔nflverse bridge."""

    ROW = {
        "game_id": "2024_01_BAL_KC",
        "season": 2024,
        "week": 1,
        "away_team": "BAL",
        "home_team": "KC",
        "away_score": 20,
        "home_score": 27,
        "total": 47,
        "total_line": 46.0,
        "spread_line": 3.0,
        "espn": "401671789",
        "pfr": "202409050kan",
        "gsis": 59508,
    }

    def test_exposes_the_espn_event_id(self):
        assert _nflverse._normalize_schedule_row(self.ROW)["espn_event_id"] == "401671789"

    def test_float_espn_id_is_clean(self):
        row = dict(self.ROW, espn=401671789.0)
        assert _nflverse._normalize_schedule_row(row)["espn_event_id"] == "401671789"

    def test_keeps_result_total_and_betting_line_apart(self):
        out = _nflverse._normalize_schedule_row(self.ROW)
        assert out["total"] == 47  # points actually scored
        assert out["total_line"] == 46.0  # betting over/under

    def test_result_total_matches_the_scores(self):
        out = _nflverse._normalize_schedule_row(self.ROW)
        assert out["total"] == out["away_score"] + out["home_score"]

    def test_other_id_bridges_present(self):
        out = _nflverse._normalize_schedule_row(self.ROW)
        assert out["pfr_game_id"] == "202409050kan"
        assert out["gsis_game_id"] == "59508"

    def test_missing_espn_id_is_none(self):
        row = {k: v for k, v in self.ROW.items() if k != "espn"}
        assert _nflverse._normalize_schedule_row(row)["espn_event_id"] is None


# ── Graceful failure ─────────────────────────────────────────────


class TestGuard:
    """Agent-facing functions return errors as data, never as tracebacks."""

    def test_missing_backend_is_reported(self, monkeypatch):
        def boom():
            raise ImportError("NFLverse backend dependencies are unavailable.")

        monkeypatch.setattr(_nflverse, "_load_provider", boom)
        result = _nflverse.get_nflverse_schedule({"params": {"season": 2024}})
        assert result["error"] is True
        assert "unavailable" in result["message"]

    def test_unexpected_error_is_reported(self, monkeypatch):
        def boom():
            raise RuntimeError("upstream exploded")

        monkeypatch.setattr(_nflverse, "_load_provider", boom)
        result = _nflverse.get_nflverse_team_stats({"params": {"season": 2024}})
        assert result["error"] is True
        assert "RuntimeError" in result["message"]
        assert "upstream exploded" in result["message"]

    def test_invalid_summary_level_is_reported_not_raised(self):
        result = _nflverse.get_nflverse_player_stats(
            {"params": {"season": 2024, "summary_level": "bogus"}}
        )
        assert result["error"] is True
        assert "Invalid summary_level" in result["message"]

    def test_nfl_data_py_team_stats_is_reported(self):
        """The old code returned schedule rows relabelled as team stats."""
        with pytest.raises(_nflverse._NflverseUnavailable, match="team-stat table"):
            _nflverse._load_team_stats("nfl_data_py", object(), 2024, "reg")


# ── Empty-filter warnings ─────────────────────────────────────────────


class TestTeamWarnings:
    """An empty team filter must be distinguishable from an empty dataset."""

    def test_no_warning_when_rows_matched(self):
        assert _nflverse._team_warnings("KC", "KC", "team", 98) == []

    def test_no_warning_without_a_team_filter(self):
        assert _nflverse._team_warnings(None, None, None, 0) == []

    def test_unmatched_team_warns(self):
        warnings = _nflverse._team_warnings("ZZZ", "ZZZ", "team", 0)
        assert warnings and "matched no rows" in warnings[0]

    def test_normalization_is_mentioned(self):
        warnings = _nflverse._team_warnings("LA", "LAR", "team", 0)
        assert "LAR" in warnings[0]

    def test_inapplicable_filter_is_distinguished(self):
        warnings = _nflverse._team_warnings("KC", "KC", None, 0)
        assert "not applied" in warnings[0]


# ── Provider selection ─────────────────────────────────────────────


class TestLoadProvider:
    """nflreadpy is preferred; nfl_data_py is the Python 3.9 fallback."""

    @staticmethod
    def _fake(name):
        return types.ModuleType(name)

    @staticmethod
    def _hide(monkeypatch, *names):
        """Make `import <name>` fail for the given modules."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in names:
                raise ImportError(f"{name} absent")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

    def test_prefers_nflreadpy(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "nflreadpy", self._fake("nflreadpy"))
        monkeypatch.setitem(sys.modules, "nfl_data_py", self._fake("nfl_data_py"))
        assert _nflverse._load_provider()[0] == "nflreadpy"

    def test_falls_back_to_nfl_data_py(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "nfl_data_py", self._fake("nfl_data_py"))
        self._hide(monkeypatch, "nflreadpy")
        name, provider = _nflverse._load_provider()
        assert name == "nfl_data_py"
        assert provider is sys.modules["nfl_data_py"]

    def test_neither_available_raises_with_install_hint(self, monkeypatch):
        self._hide(monkeypatch, "nflreadpy", "nfl_data_py")
        with pytest.raises(ImportError, match=r"sports-skills\[nfl\]"):
            _nflverse._load_provider()

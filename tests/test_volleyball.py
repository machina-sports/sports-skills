"""Tests for Nevobo poule path resolution.

Nevobo increments a season counter inside poule paths, so hardcoded paths expire
every season. These tests pin the resolution behaviour that replaces them.
"""

from pathlib import Path

import feedparser
import pytest

from sports_skills import volleyball
from sports_skills.volleyball import LEAGUES, _nevobo


class TestResolvePoulePath:
    COMPETITIONS = {
        "hydra:member": [
            {"@id": "/competitie/competities/nationale-competitie/competitie-eredivisie"},
            {"@id": "/competitie/competities/regio-oost/competitie-iets"},
        ]
    }
    POULES = {
        "hydra:member": [
            {
                "@id": "/competitie/poules/nationale-competitie/"
                "competitie-eredivisie/nationale-competitie-ed-12"
            },
            {
                "@id": "/competitie/poules/nationale-competitie/"
                "competitie-eredivisie/nationale-competitie-eh-12"
            },
        ]
    }

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        _nevobo._cache.clear()
        yield
        _nevobo._cache.clear()

    def _patch(self, monkeypatch, competitions=None, poules=None):
        def fake(path, params=None):
            if path == "/competitie/competities":
                return competitions if competitions is not None else self.COMPETITIONS
            if path == "/competitie/poules":
                return poules if poules is not None else self.POULES
            return {"error": True}

        monkeypatch.setattr(_nevobo, "_hydra_request", fake)

    def test_resolves_current_suffix(self, monkeypatch):
        self._patch(monkeypatch)
        path = _nevobo.resolve_poule_path("competitie-eredivisie", "eh", fallback="old")
        assert path == (
            "nationale-competitie/competitie-eredivisie/nationale-competitie-eh-12"
        )

    def test_distinguishes_codes(self, monkeypatch):
        self._patch(monkeypatch)
        assert _nevobo.resolve_poule_path("competitie-eredivisie", "ed").endswith("ed-12")

    def test_tolerates_competition_season_counter(self, monkeypatch):
        """The competition slug itself may carry a counter."""
        self._patch(
            monkeypatch,
            competitions={
                "hydra:member": [
                    {
                        "@id": "/competitie/competities/nationale-competitie/"
                        "competitie-eredivisie-4"
                    }
                ]
            },
        )
        assert (
            _nevobo.resolve_poule_path("competitie-eredivisie", "eh", fallback="old") != "old"
        )

    def test_ignores_regional_competitions(self, monkeypatch):
        self._patch(
            monkeypatch,
            competitions={
                "hydra:member": [
                    {"@id": "/competitie/competities/regio-oost/competitie-eredivisie"}
                ]
            },
        )
        assert (
            _nevobo.resolve_poule_path("competitie-eredivisie", "eh", fallback="old") == "old"
        )

    def test_unknown_code_falls_back(self, monkeypatch):
        self._patch(monkeypatch)
        assert (
            _nevobo.resolve_poule_path("competitie-eredivisie", "zz", fallback="old") == "old"
        )

    def test_upstream_error_falls_back(self, monkeypatch):
        monkeypatch.setattr(_nevobo, "_hydra_request", lambda p, params=None: {"error": True})
        assert (
            _nevobo.resolve_poule_path("competitie-eredivisie", "eh", fallback="old") == "old"
        )

    def test_result_is_cached(self, monkeypatch):
        calls = []

        def counting(path, params=None):
            calls.append(path)
            if path == "/competitie/competities":
                return self.COMPETITIONS
            return self.POULES

        monkeypatch.setattr(_nevobo, "_hydra_request", counting)
        first = _nevobo.resolve_poule_path("competitie-eredivisie", "eh")
        n = len(calls)
        second = _nevobo.resolve_poule_path("competitie-eredivisie", "eh")
        assert first == second
        assert len(calls) == n, "second lookup should be served from cache"


class TestLeagueConfiguration:
    """Every league needs the keys that make resolution possible."""

    def test_every_league_has_resolution_keys(self):
        for cid, cfg in LEAGUES.items():
            assert cfg.get("competition_family"), f"{cid} missing competition_family"
            assert cfg.get("poule_code"), f"{cid} missing poule_code"

    def test_poule_codes_are_unique(self):
        pairs = [(c["competition_family"], c["poule_code"]) for c in LEAGUES.values()]
        assert len(pairs) == len(set(pairs)), "two leagues resolve to the same poule"

    def test_configured_fallback_paths_still_present(self):
        """The stale path stays as a last resort if the API is unreachable."""
        for cid, cfg in LEAGUES.items():
            assert cfg.get("poule_path"), f"{cid} lost its fallback path"


FIXTURES = Path(__file__).parent / "fixtures" / "nevobo"


def _feed(name):
    return feedparser.parse((FIXTURES / name).read_text())


class TestFeedRows:
    """Recorded Nevobo RSS rows (#164)."""

    def test_unscheduled_match_has_clean_home_team_and_null_date(self, monkeypatch):
        monkeypatch.setattr(_nevobo, "_rss_request", lambda p: _feed("poule_programma_undated.rss"))
        matches = _nevobo.get_poule_schedule("x")["matches"]
        undated = matches[0]
        assert undated["home_team"] == "VCN DS 2"
        assert undated["away_team"] == "Sport Pride US DS 1"
        assert undated["date"] is None
        assert matches[1]["home_team"] == "VV Utrecht DS 2"
        assert matches[1]["date"] == "Sat, 03 Oct 2026 15:30:00 +0200"

    def test_club_results_dedupe_intra_club_matches(self, monkeypatch):
        monkeypatch.setattr(_nevobo, "_rss_request", lambda p: _feed("club_resultaten_dupes.rss"))
        results = _nevobo.get_club_results("CKL5C67")["results"]
        # 5 feed items: two intra-club matches listed twice, one cancelled match.
        assert len(results) == 3
        pairs = [(r["home_team"], r["away_team"]) for r in results]
        assert len(pairs) == len(set(pairs))

    def test_cancelled_match_prefix_is_stripped(self, monkeypatch):
        monkeypatch.setattr(_nevobo, "_rss_request", lambda p: _feed("club_resultaten_dupes.rss"))
        results = _nevobo.get_club_results("CKL5C67")["results"]
        cancelled = [r for r in results if r.get("status") == "vervallen"]
        assert len(cancelled) == 1
        assert cancelled[0]["home_team"] == "Lycurgus L3 2"
        assert cancelled[0]["away_team"] == "LSV L3 1"


class TestSeason:
    COMPETITIONS = {
        "hydra:member": [
            {
                "@id": "/competitie/competities/nationale-competitie/competitie-eredivisie",
                "seizoen": "/seizoenen/2026-2027",
            }
        ]
    }

    @pytest.fixture(autouse=True)
    def _patch(self, monkeypatch):
        _nevobo._cache.clear()
        monkeypatch.setattr(_nevobo, "_hydra_request", lambda p, params=None: self.COMPETITIONS)
        monkeypatch.setattr(_nevobo, "get_poule_standings", lambda p: {"standings": [], "poule_path": p})
        yield
        _nevobo._cache.clear()

    def test_past_season_returns_explicit_error(self):
        for season in ("2025-2026", 2025, "2025"):
            out = volleyball.get_standings(competition_id="nevobo-eredivisie-heren", season=season)
            assert out["status"] is False
            assert "2025-2026" in out["message"] and "2026-2027" in out["message"]

    def test_current_season_is_accepted(self):
        for season in (None, "2026-2027", 2026):
            out = volleyball.get_standings(competition_id="nevobo-eredivisie-heren", season=season)
            assert out["status"] is True, out

    def test_malformed_season_is_rejected(self):
        out = volleyball.get_standings(competition_id="nevobo-eredivisie-heren", season="last year")
        assert out["status"] is False
        assert "Invalid season" in out["message"]

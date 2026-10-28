"""ESPN names NBA, NHL and CBB seasons by the year they end: seasons/2027 is 2026-27."""

import datetime as _dt
import json
import re
from pathlib import Path

import pytest

from sports_skills.cbb import _connector as cbb
from sports_skills.nba import _connector as nba
from sports_skills.nfl import _connector as nfl
from sports_skills.nhl import _connector as nhl

_END_YEAR = [nba, nhl, cbb]
_IDS = ["nba", "nhl", "cbb"]

# (date, season ESPN calls current): opening night, mid-season, and the summer after.
_DATES = [((2026, 10, 27), 2027), ((2027, 2, 1), 2027), ((2027, 8, 1), 2027)]


class _Frozen(_dt.datetime):
    now_value = None

    @classmethod
    def utcnow(cls):
        return cls.now_value

    @classmethod
    def now(cls, tz=None):
        return cls.now_value if tz is None else cls.now_value.replace(tzinfo=tz)


@pytest.fixture
def frozen(monkeypatch):
    def at(y, m, d):
        _Frozen.now_value = _dt.datetime(y, m, d, 12)
        monkeypatch.setattr(_dt, "datetime", _Frozen)

    return at


@pytest.fixture
def core_paths(monkeypatch):
    """Record every ESPN core path a connector asks for; answer with an empty page."""
    asked = []

    def serve(mod):
        monkeypatch.setattr(mod, "espn_core_request", lambda sport, path, *a, **k: asked.append(path) or {"items": []})
        return asked

    return serve


@pytest.fixture
def leader_urls(monkeypatch):
    """Record the leaders URL; answer like ESPN, which sends no season field."""
    urls = []

    def serve(mod):
        monkeypatch.setattr(mod, "_cache_get", lambda key: None)
        monkeypatch.setattr(mod, "_cache_set", lambda *a, **k: None)
        monkeypatch.setattr(
            mod, "_http_fetch", lambda url, **k: (urls.append(url) or json.dumps({"categories": []}).encode(), None)
        )
        return urls

    return serve


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
@pytest.mark.parametrize("date,season", _DATES)
def test_futures_default_to_the_current_season(mod, date, season, frozen, core_paths):
    frozen(*date)
    asked = core_paths(mod)
    mod.get_futures({"params": {}})
    assert asked[0] == f"seasons/{season}/futures"


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
@pytest.mark.parametrize("date,season", _DATES)
def test_team_and_player_stats_default_to_the_current_season(mod, date, season, frozen, core_paths):
    frozen(*date)
    asked = core_paths(mod)
    mod.get_team_stats({"params": {"team_id": "1"}})
    mod.get_player_stats({"params": {"player_id": "2"}})
    assert asked == [
        f"seasons/{season}/types/2/teams/1/statistics",
        f"seasons/{season}/types/2/athletes/2/statistics",
    ]


@pytest.mark.parametrize("mod", [nba, nhl], ids=["nba", "nhl"])
@pytest.mark.parametrize("date,season", _DATES)
def test_leaders_default_to_the_current_season_and_say_which(mod, date, season, frozen, leader_urls):
    frozen(*date)
    urls = leader_urls(mod)
    result = mod.get_leaders({"params": {}})
    assert f"/seasons/{season}/types/2/leaders" in urls[0]
    assert result["season"] == season


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
def test_an_explicit_season_still_wins(mod, frozen, core_paths):
    frozen(2026, 10, 27)
    asked = core_paths(mod)
    mod.get_futures({"params": {"season_year": 2025}})
    mod.get_team_stats({"params": {"team_id": "1", "season_year": 2025}})
    assert asked == ["seasons/2025/futures", "seasons/2025/types/2/teams/1/statistics"]


@pytest.mark.parametrize("mod", [nba, nhl], ids=["nba", "nhl"])
def test_an_explicit_leaders_season_still_wins(mod, frozen, leader_urls):
    frozen(2026, 10, 27)
    urls = leader_urls(mod)
    assert mod.get_leaders({"params": {"season": 2025}})["season"] == 2025
    assert "/seasons/2025/types/2/leaders" in urls[0]


def test_start_year_leagues_are_unchanged(frozen, core_paths):
    # NFL (like CFB, MLB, WNBA) names a season by the year it starts.
    frozen(2026, 10, 27)
    asked = core_paths(nfl)
    nfl.get_futures({"params": {}})
    assert asked[0] == "seasons/2026/futures"


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
@pytest.mark.parametrize("date,season", [((2026, 9, 30), 2026), ((2026, 10, 1), 2027)], ids=["sep30", "oct1"])
def test_the_default_season_turns_over_on_october_first(mod, date, season, frozen, core_paths):
    frozen(*date)
    asked = core_paths(mod)
    mod.get_futures({"params": {}})
    assert asked == [f"seasons/{season}/futures"]


@pytest.fixture
def empty_2027(monkeypatch):
    """ESPN has nothing for 2027 yet; 2026 answers."""
    asked = []

    def serve(mod):
        def core(sport, path, *a, **k):
            asked.append(path)
            return {"error": True, "message": "not found"} if path.startswith("seasons/2027/") else {"items": []}

        monkeypatch.setattr(mod, "espn_core_request", core)
        return asked

    return serve


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
def test_an_implied_season_with_no_data_falls_back_a_year(mod, frozen, empty_2027):
    frozen(2026, 10, 1)
    asked = empty_2027(mod)
    result = mod.get_futures({"params": {}})
    assert asked == ["seasons/2027/futures", "seasons/2026/futures"]
    assert result["season_year"] == 2026
    assert "returned 2026" in result["warnings"][0]


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
def test_an_explicit_season_with_no_data_does_not_fall_back(mod, frozen, empty_2027):
    frozen(2026, 10, 1)
    asked = empty_2027(mod)
    result = mod.get_futures({"params": {"season_year": 2027}})
    assert asked == ["seasons/2027/futures"]
    assert result["error"] is True


@pytest.mark.parametrize("mod", _END_YEAR, ids=_IDS)
def test_an_implied_season_with_an_empty_successful_payload_does_not_fall_back(mod, frozen, core_paths):
    frozen(2026, 10, 1)
    asked = core_paths(mod)
    result = mod.get_futures({"params": {}})
    assert asked == ["seasons/2027/futures"]
    assert result["season_year"] == 2027
    assert "warnings" not in result


# Agent-facing docs: ESPN commands take the ENDING year; the native stats backends keep the starting year.
_SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _skill(sport):
    return (_SKILLS / f"{sport}-data" / "SKILL.md").read_text()


def _choosing_the_season(sport):
    return re.search(r"## Choosing the Season\n(.*?)\n## ", _skill(sport), re.S).group(1)


@pytest.mark.parametrize("sport", ["nba", "nhl"])
def test_skill_doc_names_espn_seasons_by_ending_year(sport):
    section = _choosing_the_season(sport)
    assert "2026-27" in section and "`2027`" in section
    assert re.search(r"February 2026\b.*`2026`", section)
    assert "omit" in section.lower()
    assert "started the previous calendar year" not in section
    assert "matches the current year" not in section


@pytest.mark.parametrize("sport", ["nba", "nhl"])
def test_skill_doc_does_not_tell_agents_to_derive_a_season(sport):
    text = _skill(sport)
    assert "<derived_year>" not in text
    assert "Derive season year from `currentDate`" not in text
    assert "Season year is derived from" not in text


@pytest.mark.parametrize("sport", ["nba", "nhl"])
def test_skill_doc_keeps_starting_year_for_native_stats_commands(sport):
    assert "Pass the starting year (`season=2024` means 2024-25)" in _skill(sport)

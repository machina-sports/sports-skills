"""A past week's college polls come from ESPN's core API (#159)."""

import importlib
import json
from pathlib import Path

import pytest

from sports_skills import _espn_base

# CFB 2025 week 5 from ESPN's core API (poll list, two polls trimmed to three
# ranks) and the site API's team list trimmed to the ranked teams.
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "cfb_rankings_2025_week5.json").read_text())


@pytest.fixture
def served(monkeypatch):
    calls = []

    def fake_core(sport_path, resource_path, ttl=300):
        calls.append(("core", resource_path))
        if resource_path.endswith("/rankings"):
            return FIXTURE["listing"]
        return FIXTURE["polls"][resource_path]

    def fake_site(sport_path, resource="scoreboard", params=None, **kwargs):
        calls.append(("site", resource, params))
        return FIXTURE["teams"]

    monkeypatch.setattr(_espn_base, "espn_core_request", fake_core)
    monkeypatch.setattr(_espn_base, "espn_request", fake_site)
    return calls


@pytest.mark.parametrize("league", ["cfb", "cbb"])
def test_season_and_week_read_that_weeks_polls(served, league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    result = connector.get_rankings({"params": {"season": 2025, "week": 5}})
    assert (result["season"], result["week"]) == (2025, 5)
    ap = result["polls"][0]
    assert ap["name"] == "AP Top 25"
    first = ap["teams"][0]
    assert (first["rank"], first["team"], first["team_id"], first["record"]) == (1, "Ohio State", "194", "3-0")
    assert first["abbreviation"] == "OSU" and first["logo"].endswith("/194.png")
    assert served[0] == ("core", "seasons/2025/types/2/weeks/5/rankings")


def test_week_alone_still_uses_the_site_api(monkeypatch):
    connector = importlib.import_module("sports_skills.cfb._connector")
    calls = []

    def fake_site(sport_path, resource="scoreboard", params=None, **kwargs):
        calls.append(params)
        return {"rankings": []}

    monkeypatch.setattr(connector, "espn_request", fake_site)
    connector.get_rankings({"params": {"week": 3}})
    assert calls == [{"weeks": 3}]


def test_core_failure_is_returned(monkeypatch):
    monkeypatch.setattr(_espn_base, "espn_core_request", lambda *a, **k: {"error": True, "message": "HTTP 404"})
    result = importlib.import_module("sports_skills.cfb._connector").get_rankings({"params": {"season": 1900, "week": 5}})
    assert result == {"error": True, "message": "HTTP 404"}

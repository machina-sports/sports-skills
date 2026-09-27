"""ESPN pro standings come back by division, with clinch and conference record (#147)."""

import importlib
import json
from pathlib import Path

import pytest

# NFL 2025 standings from ESPN's site API with level=3, trimmed to the team
# identity and the stats the normalizer reads.
FIXTURE = Path(__file__).parent / "fixtures" / "nfl_standings_level3_2025.json"

_LEAGUES = ["nfl", "nba", "mlb", "nhl", "wnba"]


def _connector(league):
    return importlib.import_module(f"sports_skills.{league}._connector")


@pytest.mark.parametrize("league", _LEAGUES)
def test_get_standings_requests_division_level(monkeypatch, league):
    connector = _connector(league)
    calls = []

    def fake_web_request(sport_path, resource, params=None):
        calls.append((resource, params))
        return {"children": []}

    monkeypatch.setattr(connector, "espn_web_request", fake_web_request)
    connector.get_standings({"params": {"season": 2025}})
    assert calls == [("standings", {"season": 2025, "level": 3})]


def test_nfl_level3_payload_gives_eight_divisions_of_four():
    groups = _connector("nfl")._normalize_standings(json.loads(FIXTURE.read_text()))
    assert [(g["conference"], g["division"], len(g["entries"])) for g in groups] == [
        ("American Football Conference", "AFC East", 4),
        ("American Football Conference", "AFC North", 4),
        ("American Football Conference", "AFC South", 4),
        ("American Football Conference", "AFC West", 4),
        ("National Football Conference", "NFC East", 4),
        ("National Football Conference", "NFC North", 4),
        ("National Football Conference", "NFC South", 4),
        ("National Football Conference", "NFC West", 4),
    ]
    patriots = groups[0]["entries"][0]
    assert patriots["team"]["abbreviation"] == "NE"
    assert (patriots["wins"], patriots["losses"]) == ("14", "3")
    assert patriots["clinch"] == "z"
    assert patriots["playoff_seed"] == "2"
    assert patriots["conference_record"] == "9-3"


def _entry(*stats):
    return {"entries": [{"team": {"id": "1"}, "stats": [{"name": n, "displayValue": v} for n, v in stats]}]}


@pytest.mark.parametrize("league", _LEAGUES)
def test_clincher_maps_to_clinch(league):
    normalize = _connector(league)._normalize_standings_entries
    (row,) = normalize(_entry(("clincher", "y")))
    assert row["clinch"] == "y"
    (row,) = normalize(_entry(("wins", "3")))
    assert row["clinch"] == ""


@pytest.mark.parametrize("league", ["nfl", "nba", "wnba"])
def test_conference_record_reads_vs_conf(league):
    (row,) = _connector(league)._normalize_standings_entries(_entry(("vs. Conf.", "15-5")))
    assert row["conference_record"] == "15-5"

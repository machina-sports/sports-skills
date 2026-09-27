"""ESPN pro standings name each team's division, with clinch and conference record (#147)."""

import importlib
import json
from pathlib import Path

import pytest

# NFL 2025 standings from ESPN's site API, trimmed to the team identity and the
# stats the normalizer reads: the default (conference-level) payload, and the
# same season with level=3 (conferences -> divisions).
FIXTURES = Path(__file__).parent / "fixtures"
CONFERENCES = json.loads((FIXTURES / "nfl_standings_2025.json").read_text())
DIVISIONS = json.loads((FIXTURES / "nfl_standings_level3_2025.json").read_text())

_LEAGUES = ["nfl", "nba", "mlb", "nhl", "wnba"]
_DIVISION_LEAGUES = ["nfl", "nba", "mlb", "nhl"]


def _connector(league):
    return importlib.import_module(f"sports_skills.{league}._connector")


@pytest.fixture
def nfl_standings(monkeypatch):
    """Serve the default payload, or the level=3 one when asked; record the params."""
    connector = _connector("nfl")
    calls = []

    def fake_web_request(sport_path, resource, params=None):
        calls.append(params)
        return DIVISIONS if (params or {}).get("level") == 3 else CONFERENCES

    monkeypatch.setattr(connector, "espn_web_request", fake_web_request)
    return connector, calls


def test_default_shape_is_conference_groups_as_before(nfl_standings):
    """Two conference groups in ESPN's order, entries in ESPN's order, as on main."""
    connector, calls = nfl_standings
    groups = connector.get_standings({"params": {"season": 2025}})["groups"]
    assert [(g["conference"], g["division"], len(g["entries"])) for g in groups] == [
        ("American Football Conference", "", 16),
        ("National Football Conference", "", 16),
    ]
    expected_order = [[e["team"]["id"] for e in c["standings"]["entries"]] for c in CONFERENCES["children"]]
    assert [[e["team"]["id"] for e in g["entries"]] for g in groups] == expected_order
    # The conference request is the one main sends; level=3 is a second request.
    assert calls == [{"season": 2025}, {"season": 2025, "level": 3}]


def test_every_team_gets_its_division(nfl_standings):
    connector, _ = nfl_standings
    groups = connector.get_standings({"params": {"season": 2025}})["groups"]
    by_team = {e["team"]["abbreviation"]: e["division"] for g in groups for e in g["entries"]}
    assert len(by_team) == 32 and all(by_team.values())
    assert by_team["NE"] == by_team["BUF"] == "AFC East"
    assert by_team["CHI"] == "NFC North"
    assert sorted(set(by_team.values())) == sorted(
        f"{c} {d}" for c in ("AFC", "NFC") for d in ("East", "North", "South", "West")
    )


def test_patriots_row(nfl_standings):
    connector, _ = nfl_standings
    groups = connector.get_standings({"params": {"season": 2025}})["groups"]
    patriots = next(e for e in groups[0]["entries"] if e["team"]["abbreviation"] == "NE")
    assert (patriots["wins"], patriots["losses"]) == ("14", "3")
    assert patriots["division"] == "AFC East"
    assert patriots["clinch"] == "z"
    assert patriots["playoff_seed"] == "2"
    assert patriots["conference_record"] == "9-3"


@pytest.mark.parametrize("league", _DIVISION_LEAGUES)
def test_division_request_failure_keeps_standings(monkeypatch, league):
    connector = _connector(league)

    def fake_web_request(sport_path, resource, params=None):
        if (params or {}).get("level") == 3:
            return {"error": True, "message": "HTTP 503"}
        return CONFERENCES

    monkeypatch.setattr(connector, "espn_web_request", fake_web_request)
    groups = connector.get_standings({"params": {"season": 2025}})["groups"]
    assert [len(g["entries"]) for g in groups] == [16, 16]
    assert {e["division"] for g in groups for e in g["entries"]} == {""}


def test_wnba_sends_one_request(monkeypatch):
    """The WNBA has no divisions, so no level=3 request."""
    connector = _connector("wnba")
    calls = []

    def fake_web_request(sport_path, resource, params=None):
        calls.append(params)
        return {"children": []}

    monkeypatch.setattr(connector, "espn_web_request", fake_web_request)
    connector.get_standings({"params": {"season": 2025}})
    assert calls == [{"season": 2025}]


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

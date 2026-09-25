"""TheSportsDB get_team_info must not return a loosely matched, different team."""

import pytest

from sports_skills.metadata import _connector as md


def _team(name, sport, alternate="", short=""):
    return {"idTeam": name, "strTeam": name, "strSport": sport, "strTeamAlternate": alternate, "strTeamShort": short}


@pytest.fixture
def search(monkeypatch):
    results = {}
    monkeypatch.setattr(md, "_http_fetch", lambda url, retries=2: {"teams": results.get("teams")})
    return results


def test_loose_match_is_rejected(search):
    """Live free-key response for "St. Louis Cardinals" (2026-09)."""
    search["teams"] = [_team("Louisville", "American Football", "Louisville Cardinals")]
    result = md.get_team_info({"params": {"team_name": "St. Louis Cardinals"}})
    assert result["error"] is True
    assert "Louisville" in result["message"] and "St. Louis Cardinals" in result["message"]


def test_exact_name_beats_earlier_loose_result(search):
    search["teams"] = [
        _team("Louisville", "American Football", "Louisville Cardinals"),
        _team("St. Louis Cardinals", "Baseball", "Cardinals", "STL"),
    ]
    result = md.get_team_info({"params": {"team_name": "St Louis Cardinals"}})
    assert result["name"] == "St. Louis Cardinals"


@pytest.mark.parametrize(
    ("query", "team"),
    [
        ("Arsenal", _team("Arsenal", "Soccer", "Arsenal Football Club, AFC, Arsenal FC")),
        ("Real Madrid CF", _team("Real Madrid", "Soccer", "Real Madrid", "MAD")),
        ("Inter", _team("Inter Milan", "Soccer", "Inter, Internazionale Milano")),
        ("Yankees", _team("New York Yankees", "Baseball", "Yankees")),
        ("Saint Louis Blues", _team("St. Louis Blues", "Ice Hockey", "Blues")),
    ],
)
def test_close_names_still_match(search, query, team):
    search["teams"] = [team]
    assert md.get_team_info({"params": {"team_name": query}})["name"] == team["strTeam"]

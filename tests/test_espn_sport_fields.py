"""Per-sport fields ESPN moved (checked live 2026-11-16)."""

import pytest

from sports_skills.cbb import _connector as cbb
from sports_skills.football import _connector as football
from sports_skills.golf import _connector as golf
from sports_skills.nba import _connector as nba
from sports_skills.wnba import _connector as wnba

PLACEHOLDER = {"x": -214748340, "y": -214748365}


@pytest.mark.parametrize("connector", [nba, wnba, cbb])
def test_placeholder_coordinates_are_dropped(connector):
    """ESPN fills non-shot plays (jump balls, substitutions) with a placeholder spot."""
    summary = {
        "plays": [
            {"id": "1", "text": "Jump ball", "coordinate": PLACEHOLDER},
            {"id": "2", "text": "Made shot", "coordinate": {"x": 25, "y": 6}},
        ]
    }
    plays = connector._normalize_plays(summary)["plays"]
    assert "coordinate" not in plays[0]
    assert plays[1]["coordinate"] == {"x": 25, "y": 6}


def test_nba_summary_event_fills_name_venue_and_odds():
    summary = {
        "header": {
            "id": "1",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Boston Celtics", "abbreviation": "BOS"}},
                        {"homeAway": "away", "team": {"displayName": "Orlando Magic", "abbreviation": "ORL"}},
                    ],
                    "odds": [],
                }
            ],
        },
        "gameInfo": {"venue": {"fullName": "TD Garden", "address": {"city": "Boston", "state": "MA"}}},
        "pickcenter": [{"provider": {"name": "ESPN BET"}, "details": "BOS -7.5", "overUnder": 221.5}],
    }
    header = nba._summary_event(summary)
    assert (header["name"], header["shortName"]) == ("Orlando Magic at Boston Celtics", "ORL @ BOS")
    comp = header["competitions"][0]
    assert comp["venue"]["fullName"] == "TD Garden"
    assert comp["odds"] == summary["pickcenter"]
    assert summary["header"]["competitions"][0]["odds"] == []  # the summary itself is not changed


def test_football_lineup_formation_reads_the_roster():
    """ESPN now sends boxscore.form as null and the formation on each roster."""
    summary = {
        "boxscore": {"teams": [], "form": None},
        "rosters": [
            {
                "team": {"id": "359"},
                "homeAway": "home",
                "formation": "4-2-3-1",
                "roster": [{"starter": True, "athlete": {"id": "1", "displayName": "Keeper"}}],
            }
        ],
    }
    (lineup,) = football._normalize_espn_summary_lineups(summary)
    assert lineup["formation"] == "4-2-3-1"


def test_golf_player_info_reads_display_dob_status_name_and_trims_birthplace(monkeypatch):
    athlete = {
        "id": "10057",
        "displayName": "Test Player",
        "dateOfBirth": None,
        "displayDOB": "3/8/1992",
        "birthPlace": {"city": "Fulton", "state": "Mississippi              "},
        "status": {"id": "1", "name": "Active", "type": "active", "abbreviation": "Active"},
    }
    monkeypatch.setattr(golf, "_cache_get", lambda key: None)
    monkeypatch.setattr(golf, "_cache_set", lambda *a, **k: None)
    monkeypatch.setattr(golf, "_fetch_player", lambda player_id, tour: ({"athlete": athlete}, None))
    result = golf.get_player_info({"params": {"player_id": "10057"}})
    data = result.get("data", result)
    assert (data["date_of_birth"], data["status"], data["birthplace"]) == ("3/8/1992", "Active", "Fulton, Mississippi")

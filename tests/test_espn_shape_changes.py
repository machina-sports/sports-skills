"""Connectors read ESPN's current response shapes (checked live 2026-11-16)."""

import json

import pytest

from sports_skills import _espn_base
from sports_skills.cbb import _connector as cbb
from sports_skills.cfb import _connector as cfb
from sports_skills.cricket import _espn as cricket
from sports_skills.tennis import _connector as tennis
from sports_skills.wnba import _connector as wnba


def test_mlb_team_totals_are_read_from_their_groups():
    """MLB groups team totals: {"name": "fielding", "stats": [{name, abbreviation, displayValue}]}."""
    boxscore = {
        "teams": [
            {
                "team": {"id": "10"},
                "statistics": [
                    {
                        "name": "fielding",
                        "displayName": "Fielding",
                        "stats": [
                            {"name": "pickoffs", "abbreviation": "PO", "displayValue": "0"},
                            {"name": "putouts", "abbreviation": "PO", "displayValue": "27"},
                        ],
                    },
                    {"name": "records", "displayName": "Records", "stats": []},
                ],
            }
        ],
        "players": [
            {
                "team": {"id": "10"},
                "statistics": [{"type": "batting", "labels": ["AB", "H"], "keys": ["atBats", "hits"], "athletes": []}],
            }
        ],
    }
    (team,) = _espn_base.normalize_boxscore(boxscore)
    assert team["team_stats"] == {"fielding": {"pickoffs": "0", "putouts": "27"}, "records": {}}
    assert team["statistics"][0]["category"] == "batting"


def test_flat_team_totals_still_read():
    boxscore = {
        "teams": [{"team": {"id": "1"}, "statistics": [{"name": "hits", "label": "Hits", "displayValue": "13"}]}]
    }
    (team,) = _espn_base.normalize_boxscore(boxscore)
    assert team["team_stats"] == {"Hits": "13"}


def test_nhl_shootout_goals_is_not_labelled_shots_on_goal():
    """ESPN labels shootoutGoals "SOG"; shots are the "S" column."""
    boxscore = {
        "teams": [{"team": {"id": "1"}, "statistics": []}],
        "players": [
            {
                "team": {"id": "1"},
                "statistics": [
                    {
                        "name": "forwards",
                        "labels": ["G", "S", "SOG"],
                        "keys": ["goals", "shotsTotal", "shootoutGoals"],
                        "athletes": [{"athlete": {"displayName": "A"}, "stats": ["1", "4", "0"]}],
                        "totals": ["1", "4", "0"],
                    }
                ],
            }
        ],
    }
    (group,) = _espn_base.normalize_boxscore(boxscore)[0]["statistics"]
    assert group["labels"] == ["G", "S", "shootoutGoals"]
    assert group["athletes"][0]["stats"] == {"G": "1", "S": "4", "shootoutGoals": "0"}


def test_bpi_fifth_column_is_the_conference_title_chance():
    """ESPN's bpi columns: ..., bpidefense, chancewinconfortie, sosremrank, wins, losses, ..."""
    entry = {
        "team": {"id": "150", "displayName": "Duke Blue Devils"},
        "categories": [
            {
                "name": "bpi",
                "values": [
                    24.1644,
                    1.0,
                    0.0,
                    10.8953,
                    13.2691,
                    90.15,
                    26.0,
                    3.0,
                    1.0,
                    27.453,
                    4.547,
                    0.0,
                    0.0,
                    16.2,
                    1.8,
                ],
            }
        ],
    }
    bpi = cbb._normalize_bpi_team(entry)["bpi"]
    assert bpi["conf_title_pct"] == 90.15
    assert "win_pct" not in bpi
    assert (bpi["sos_rank"], bpi["wins"], bpi["losses"]) == (26, 3, 1)


def test_wnba_season_schedule_asks_for_every_game(monkeypatch):
    """ESPN returns 100 events for dates=<season> unless a limit is sent (2026: 374 games)."""
    sent = []
    monkeypatch.setattr(wnba, "espn_request", lambda path, resource, params=None: sent.append(params) or {"events": []})
    wnba.get_schedule({"params": {"season": 2026}})
    assert sent == [{"dates": "2026", "limit": 1000}]


@pytest.mark.parametrize(
    ("connector", "params"),
    [(cfb, {"season": 2026}), (cbb, {"season": 2027})],
)
def test_college_whole_season_schedule_is_refused(monkeypatch, connector, params):
    """ESPN truncates a whole college season (CFB to 300 games, CBB to 200)."""
    monkeypatch.setattr(connector, "espn_request", lambda *a, **k: pytest.fail("ESPN was called"))
    result = connector.get_schedule({"params": params})
    assert result["error"] is True
    assert "get_team_schedule" in result["message"]


def test_tennis_previous_winners_read_the_top_level_name():
    event = {
        "id": "1",
        "previousWinners": [{"displayName": "Jannik Sinner", "type": {"id": "1", "text": "Men's Singles"}}],
    }
    winners = tennis._normalize_tournament(event, include_matches=False)["previous_winners"]
    assert winners == [{"year": "", "name": "Jannik Sinner", "draw": "Men's Singles"}]


def test_tennis_player_country_falls_back_to_citizenship(monkeypatch):
    payload = {
        "id": "1",
        "displayName": "Alexander Zverev",
        "birthPlace": {"summary": "Hamburg"},
        "citizenshipCountry": {"name": "Germany"},
    }
    monkeypatch.setattr(tennis, "_http_fetch", lambda url, **kw: (json.dumps(payload).encode(), None))
    result = tennis.get_player_info({"params": {"player_id": "1"}})
    data = result.get("data", result)
    assert data["country"] == "Germany"


def test_cricket_status_and_note_without_status_name():
    """A day's close of play: no ``type.name`` and no notes; the situation is in ``status.summary``."""
    event = {
        "id": "1555690",
        "competitions": [
            {
                "status": {
                    "summary": "Mymensingh lead by 142 runs",
                    "type": {
                        "id": "112",
                        "description": "Stumps",
                        "detail": "Live",
                        "shortDetail": "Live",
                        "state": "in",
                    },
                },
                "notes": [],
                "competitors": [],
            }
        ],
    }
    row = cricket._normalize_event(event)
    assert (row["status"], row["note"]) == ("live", "Mymensingh lead by 142 runs")


def test_injuries_leave_out_players_cleared_as_active():
    data = {
        "injuries": [
            {
                "injuries": [
                    {"status": "Active", "athlete": {"displayName": "Cleared Player"}},
                    {"status": "Out", "athlete": {"displayName": "Injured Player"}, "details": {"type": "Ankle"}},
                ]
            }
        ]
    }
    result = _espn_base.normalize_injuries(data)
    teams = result["teams"] if isinstance(result, dict) else result
    names = [i["name"] for team in teams for i in team["injuries"]]
    assert names == ["Injured Player"]

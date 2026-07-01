"""Regression tests for game-summary box-score and scoring-play normalization.

These guard against the ESPN payload-shape bug where ``get_game_summary``
returned a hollow box score (empty ``athletes``) and empty ``scoring_plays``:

- Player rows live under ``boxscore["players"]``, not ``boxscore["teams"]``.
- ESPN omits the top-level ``scoringPlays`` key for NBA/NHL/MLB; scoring plays
  must be derived from the ``plays`` array.

Fixtures are real (trimmed) ESPN summary payloads saved under ``tests/fixtures``
so the tests are fully hermetic — no network access.
"""

import json
from pathlib import Path

import pytest

from sports_skills._espn_base import normalize_boxscore, normalize_scoring_plays
from sports_skills.mlb._connector import _normalize_game_summary as mlb_summary
from sports_skills.nba._connector import _normalize_game_summary as nba_summary
from sports_skills.nhl._connector import _normalize_game_summary as nhl_summary
from sports_skills.wnba._connector import _normalize_game_summary as wnba_summary

FIXTURES = Path(__file__).parent / "fixtures"

CASES = [
    ("nba_summary_401859967.json", nba_summary),
    ("nhl_summary_401874176.json", nhl_summary),
    ("mlb_summary_401815943.json", mlb_summary),
    ("wnba_summary_401857321.json", wnba_summary),
]


def _load(name):
    with open(FIXTURES / name) as f:
        return json.load(f)


@pytest.mark.parametrize("fixture,normalize", CASES)
def test_boxscore_has_player_rows(fixture, normalize):
    """The box score must contain populated player ``athletes`` for both teams."""
    result = normalize(_load(fixture))
    box = result["boxscore"]
    assert len(box) == 2, "expected two teams in the box score"

    total_athletes = 0
    for team in box:
        # Player stat groups come from boxscore["players"] and carry athletes.
        for group in team["statistics"]:
            total_athletes += len(group["athletes"])
        # Team-aggregate stats (from boxscore["teams"]) must be preserved too.
        assert team["team_stats"], f"missing team_stats for {team['team']['name']}"

    assert total_athletes > 0, "box score returned zero player rows (regression!)"


@pytest.mark.parametrize("fixture,normalize", CASES)
def test_scoring_plays_non_empty(fixture, normalize):
    """Scoring plays must be derived from plays[] even when scoringPlays is absent."""
    result = normalize(_load(fixture))
    plays = result["scoring_plays"]
    assert plays, "scoring_plays was empty (regression!)"
    first = plays[0]
    # Shape contract every consumer relies on.
    for key in ("period", "clock", "text", "team", "home_score", "away_score"):
        assert key in first
    assert first["team"]["id"], "scoring play missing team id"


def test_boxscore_reads_players_not_teams():
    """Directly exercise the helper: a teams-only box score yields no athletes,
    a players sub-tree yields athletes — proving we read the right array."""
    teams_only = {
        "teams": [
            {
                "team": {"id": "1", "displayName": "Test", "abbreviation": "TST"},
                "statistics": [{"name": "fg", "label": "FG", "displayValue": "31-87"}],
            }
        ],
    }
    out = normalize_boxscore(teams_only)
    assert out[0]["team_stats"] == {"FG": "31-87"}
    assert out[0]["statistics"] == []  # no players array -> no athletes

    with_players = dict(teams_only)
    with_players["players"] = [
        {
            "team": {"id": "1"},
            "statistics": [
                {
                    "labels": ["PTS", "REB"],
                    "athletes": [
                        {
                            "athlete": {"displayName": "A. Player", "position": {"abbreviation": "G"}},
                            "stats": ["25", "5"],
                            "starter": True,
                        }
                    ],
                }
            ],
        }
    ]
    out = normalize_boxscore(with_players)
    athletes = out[0]["statistics"][0]["athletes"]
    assert athletes[0]["name"] == "A. Player"
    assert athletes[0]["stats"] == {"PTS": "25", "REB": "5"}


def test_scoring_plays_prefers_curated_over_derived():
    """When ESPN provides a curated scoringPlays array, use it verbatim and do
    not fall back to plays[]."""
    data = {
        "scoringPlays": [
            {
                "period": {"number": 1},
                "clock": {"displayValue": "9:44"},
                "type": {"text": "Goal"},
                "text": "Curated play",
                "team": {"id": "7", "displayName": "Curated FC"},
                "homeScore": 1,
                "awayScore": 0,
            }
        ],
        "plays": [{"scoringPlay": True, "text": "Should be ignored", "team": {"id": "9"}}],
    }
    out = normalize_scoring_plays(data)
    assert len(out) == 1
    assert out[0]["text"] == "Curated play"
    assert out[0]["team"]["name"] == "Curated FC"


def test_scoring_plays_derives_with_team_lookup():
    """When scoringPlays is absent, derive from plays[] and backfill team name."""
    data = {
        "plays": [
            {"scoringPlay": False, "text": "not scoring", "team": {"id": "1"}},
            {
                "scoringPlay": True,
                "text": "Player makes shot",
                "team": {"id": "1"},
                "period": {"number": 2},
                "clock": {"displayValue": "5:00"},
                "homeScore": 2,
                "awayScore": 0,
            },
        ],
    }
    out = normalize_scoring_plays(data, {"1": {"name": "Home Team", "abbreviation": "HOM"}})
    assert len(out) == 1
    assert out[0]["text"] == "Player makes shot"
    assert out[0]["team"]["name"] == "Home Team"
    assert out[0]["team"]["abbreviation"] == "HOM"

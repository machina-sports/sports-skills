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
from sports_skills.cbb._connector import _normalize_game_summary as cbb_summary
from sports_skills.cfb._connector import _normalize_game_summary as cfb_summary
from sports_skills.mlb._connector import _normalize_game_summary as mlb_summary
from sports_skills.nba._connector import _normalize_game_summary as nba_summary
from sports_skills.nfl._connector import _normalize_game_summary as nfl_summary
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
    # The starter / did_not_play flags must be mapped through, not dropped.
    assert athletes[0]["starter"] is True
    assert athletes[0]["did_not_play"] is False


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


def test_scoring_plays_derives_with_competitors_backfill():
    """When scoringPlays is absent, derive from plays[] and backfill team identity
    from the connector's competitors list (plays carry only team.id)."""
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
    competitors = [{"team": {"id": "1", "name": "Home Team", "abbreviation": "HOM"}}]
    out = normalize_scoring_plays(data, competitors)
    assert len(out) == 1
    assert out[0]["text"] == "Player makes shot"
    assert out[0]["team"]["name"] == "Home Team"
    assert out[0]["team"]["abbreviation"] == "HOM"


def test_normalizers_tolerate_null_payloads():
    """ESPN can send null boxscore/plays (e.g. not-started games) — the helpers
    must degrade to empty, not raise (agents rely on graceful failure)."""
    assert normalize_boxscore(None) == []
    assert normalize_boxscore({}) == []
    assert normalize_scoring_plays(None) == []
    assert normalize_scoring_plays({"plays": None}) == []
    assert normalize_scoring_plays({"scoringPlays": None, "plays": None}) == []


# ---------------------------------------------------------------------------
# Extended-sports migration (PR #86 follow-up): NFL / CFB / CBB now route
# through the shared normalize_boxscore / normalize_scoring_plays helpers, so
# their box score and scoring plays populate instead of silently returning
# empty. Hermetic synthetic payloads (no fixtures/network) prove the wiring.
# ---------------------------------------------------------------------------


def _synthetic_summary(*, curated_scoring):
    """Minimal ESPN summary payload exercising box score + scoring plays.

    curated_scoring=True mimics football (top-level scoringPlays); False mimics
    basketball (no scoringPlays — must derive from plays[]).
    """
    teams = [
        {
            "team": {"id": "1", "displayName": "Team One", "abbreviation": "ON1"},
            "statistics": [{"label": "Total Yards", "displayValue": "350"}],
        },
        {
            "team": {"id": "2", "displayName": "Team Two", "abbreviation": "TW2"},
            "statistics": [{"label": "Total Yards", "displayValue": "420"}],
        },
    ]
    players = [
        {
            "team": {"id": "1"},
            "statistics": [
                {
                    "name": "leaders",
                    "labels": ["YDS", "TD"],
                    "athletes": [
                        {
                            "athlete": {"displayName": "Star One", "position": {"abbreviation": "X"}},
                            "stats": ["300", "2"],
                            "starter": True,
                        }
                    ],
                }
            ],
        },
        {
            "team": {"id": "2"},
            "statistics": [
                {
                    "name": "leaders",
                    "labels": ["YDS", "TD"],
                    "athletes": [
                        {
                            "athlete": {"displayName": "Star Two", "position": {"abbreviation": "X"}},
                            "stats": ["280", "1"],
                            "starter": True,
                        }
                    ],
                }
            ],
        },
    ]
    data = {
        "header": {
            "id": "999",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"id": "1", "displayName": "Team One", "abbreviation": "ON1"}},
                        {"homeAway": "away", "team": {"id": "2", "displayName": "Team Two", "abbreviation": "TW2"}},
                    ]
                }
            ],
        },
        "boxscore": {"teams": teams, "players": players},
    }
    if curated_scoring:
        data["scoringPlays"] = [
            {
                "period": {"number": 1},
                "clock": {"displayValue": "10:00"},
                "type": {"text": "Touchdown"},
                "text": "Scoring play",
                "team": {"id": "1", "displayName": "Team One"},
                "homeScore": 7,
                "awayScore": 0,
            }
        ]
    else:
        data["plays"] = [
            {
                "scoringPlay": True,
                "text": "Made basket",
                "team": {"id": "1"},
                "period": {"number": 1},
                "clock": {"displayValue": "5:00"},
                "homeScore": 2,
                "awayScore": 0,
            }
        ]
    return data


@pytest.mark.parametrize(
    "normalize,curated",
    [
        (nfl_summary, True),  # football: curated scoringPlays
        (cfb_summary, True),  # football: curated scoringPlays
        (cbb_summary, False),  # basketball: derive scoring plays from plays[]
    ],
)
def test_extended_sports_populate_boxscore_and_scoring(normalize, curated):
    result = normalize(_synthetic_summary(curated_scoring=curated))

    box = result["boxscore"]
    assert len(box) == 2, "expected two teams in the box score"
    total_athletes = sum(len(group["athletes"]) for team in box for group in team["statistics"])
    assert total_athletes > 0, "extended-sport box score returned zero player rows"
    for team in box:
        assert team["team_stats"], "team_stats missing (team-aggregate stats dropped)"

    plays = result["scoring_plays"]
    assert plays, "extended-sport scoring_plays was empty (still on the old buggy path?)"
    assert plays[0]["team"]["id"], "scoring play missing team id"

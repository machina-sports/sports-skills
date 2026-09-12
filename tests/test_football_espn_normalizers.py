"""ESPN soccer normalizers: team statistics names, penalty event type, league slug."""

from __future__ import annotations

import json

import pytest

from sports_skills.football import _connector as c

# Statistic names exactly as ESPN's soccer boxscore emits them (identical for bra.1 and eng.1).
ESPN_BOXSCORE = {
    "boxscore": {
        "teams": [
            {
                "team": {"id": "819", "displayName": "Flamengo", "abbreviation": "FLA"},
                "statistics": [
                    {"name": "possessionPct", "displayValue": "58"},
                    {"name": "totalShots", "displayValue": "14"},
                    {"name": "shotsOnTarget", "displayValue": "6"},
                    {"name": "blockedShots", "displayValue": "3"},
                    {"name": "wonCorners", "displayValue": "7"},
                    {"name": "foulsCommitted", "displayValue": "12"},
                    {"name": "offsides", "displayValue": "2"},
                    {"name": "yellowCards", "displayValue": "1"},
                    {"name": "redCards", "displayValue": "0"},
                    {"name": "totalPasses", "displayValue": "512"},
                    {"name": "accuratePasses", "displayValue": "448"},
                    {"name": "passPct", "displayValue": "87.5"},
                    {"name": "totalTackles", "displayValue": "19"},
                    {"name": "effectiveTackles", "displayValue": "13"},
                    {"name": "tacklePct", "displayValue": "68.4"},
                    {"name": "interceptions", "displayValue": "9"},
                    {"name": "totalClearance", "displayValue": "21"},
                    {"name": "effectiveClearance", "displayValue": "18"},
                    {"name": "totalCrosses", "displayValue": "17"},
                    {"name": "accurateCrosses", "displayValue": "5"},
                    {"name": "totalLongBalls", "displayValue": "40"},
                    {"name": "accurateLongBalls", "displayValue": "22"},
                    {"name": "penaltyKickShots", "displayValue": "1"},
                    {"name": "penaltyKickGoals", "displayValue": "1"},
                    {"name": "saves", "displayValue": "4"},
                ],
            }
        ]
    },
    "header": {"competitions": [{"competitors": [{"id": "819", "homeAway": "home"}]}]},
}


def test_team_statistics_use_the_names_espn_actually_emits():
    teams = c._normalize_espn_summary_statistics(ESPN_BOXSCORE)
    assert len(teams) == 1
    st = teams[0]["statistics"]
    assert st["shots_total"] == "14"
    assert st["shots_on_target"] == "6"
    assert st["shots_off_target"] == "5"  # derived: 14 total - 6 on target - 3 blocked (ESPN has no shotsOffTarget)
    assert st["shots_blocked"] == "3"
    assert st["passes_total"] == "512"
    assert st["passes_accurate"] == "448"
    assert st["tackles"] == "19"
    assert st["tackles_effective"] == "13"
    assert st["interceptions"] == "9"
    assert st["clearances"] == "21"
    assert st["crosses"] == "17"
    assert st["crosses_accurate"] == "5"
    assert st["long_balls_total"] == "40"
    assert st["penalty_kick_goals"] == "1"
    assert st["goalkeeper_saves"] == "4"
    assert st["ball_possession"] == "58"
    assert st["corner_kicks"] == "7"


def test_team_statistics_negative_control_old_aliases_still_read():
    legacy = json.loads(json.dumps(ESPN_BOXSCORE))
    for stat in legacy["boxscore"]["teams"][0]["statistics"]:
        stat["name"] = {
            "totalShots": "shotsTotal",
            "accuratePasses": "completedPasses",
            "totalTackles": "tackles",
            "blockedShots": "shotsBlocked",
        }.get(stat["name"], stat["name"])
    st = c._normalize_espn_summary_statistics(legacy)[0]["statistics"]
    assert (
        st["shots_total"] == "14"
        and st["passes_accurate"] == "448"
        and st["tackles"] == "19"
        and st["shots_blocked"] == "3"
    )
    empty = c._normalize_espn_summary_statistics({"boxscore": {"teams": [{"team": {"id": "1"}, "statistics": []}]}})
    assert empty[0]["statistics"]["shots_total"] == "0" and empty[0]["statistics"]["shots_off_target"] == "0"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Goal", "goal"),
        ("Goal - Header", "goal"),
        ("Goal - Free-kick", "goal"),
        ("Own Goal", "own_goal"),
        ("Penalty - Scored", "penalty_goal"),
        ("Penalty - Missed", "penalty_missed"),
        ("Penalty - Saved", "penalty_missed"),
        ("Yellow Card", "yellow_card"),
        ("Red Card", "red_card"),
        ("Substitution", "substitution"),
    ],
)
def test_event_type_mapping_covers_the_penalty_texts_espn_uses(text, expected):
    assert c._map_espn_event_type(text) == expected


def test_league_code_accepts_sports_skills_slug_and_espn_code():
    assert c._espn_league_code("serie-a-brazil") == "bra.1"
    assert c._espn_league_code("premier-league") == "eng.1"
    assert c._espn_league_code("bra.1") == "bra.1"
    assert c._espn_league_code("") == "eng.1"


def test_player_season_stats_builds_the_espn_url_from_the_slug(monkeypatch):
    seen = {}

    def fake_fetch(url, headers=None, rate_limiter=None, **kwargs):
        seen["url"] = url
        return json.dumps({"gameLog": {"statistics": []}}).encode(), None

    monkeypatch.setattr(c, "_http_fetch", fake_fetch)
    monkeypatch.setattr(c, "_cache_get", lambda key: None)
    monkeypatch.setattr(c, "_cache_set", lambda *a, **k: None)
    out = c.get_player_season_stats({"params": {"player_id": "192226", "league_slug": "serie-a-brazil"}})
    assert "/soccer/bra.1/athletes/192226/overview" in seen["url"]
    assert out.get("matches") == [] or out.get("player_id") == "192226"


def test_shots_off_target_subtracts_blocked_shots_too():
    # eng.1 event 740629, Newcastle: 16 total, 4 on target, 5 blocked -> 7 off target (not 12)
    summary = {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "361", "displayName": "Newcastle United", "abbreviation": "NEW"},
                    "statistics": [
                        {"name": "totalShots", "displayValue": "16"},
                        {"name": "shotsOnTarget", "displayValue": "4"},
                        {"name": "blockedShots", "displayValue": "5"},
                    ],
                }
            ]
        },
        "header": {"competitions": [{"competitors": [{"id": "361", "homeAway": "away"}]}]},
    }
    st = c._normalize_espn_summary_statistics(summary)[0]["statistics"]
    assert st["shots_off_target"] == "7"
    assert st["shots_blocked"] == "5"


def test_null_display_values_do_not_raise_and_derive_zero():
    # a present stat with ``displayValue: null`` used to make ``int(None)`` raise TypeError
    summary = {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "819", "displayName": "Flamengo", "abbreviation": "FLA"},
                    "statistics": [
                        {"name": "totalShots", "displayValue": None},
                        {"name": "shotsOnTarget", "displayValue": None},
                        {"name": "blockedShots", "displayValue": None},
                        {"name": "possessionPct", "displayValue": None},
                    ],
                }
            ]
        },
        "header": {"competitions": [{"competitors": [{"id": "819", "homeAway": "home"}]}]},
    }
    st = c._normalize_espn_summary_statistics(summary)[0]["statistics"]
    assert st["shots_total"] == "0" and st["shots_on_target"] == "0"
    assert st["shots_off_target"] == "0" and st["ball_possession"] == "0"

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


# --- #163: league probe fetches the summary once; stoppage time kept ---

LA_LIGA_SUMMARY = {
    "header": {
        "league": {"slug": "esp.1"},
        "season": {"year": 2026},
        "competitions": [{"date": "2026-09-20T19:00Z", "competitors": []}],
    },
    "keyEvents": [
        {"id": "1", "type": {"text": "Halftime"}, "clock": {"displayValue": "45'+3'"}},
        {"id": "2", "type": {"text": "Goal"}, "clock": {"displayValue": "59'"}},
        {"id": "3", "type": {"text": "End Regular Time"}, "clock": {"displayValue": "90'+7'"}},
    ],
}


def test_event_summary_probe_fetches_real_league_once(monkeypatch):
    calls = []

    def fake_fetch(url, **kw):
        calls.append(url)
        return json.dumps(LA_LIGA_SUMMARY).encode(), None

    monkeypatch.setattr(c, "_http_fetch", fake_fetch)
    out = c.get_event_summary({"params": {"event_id": "163000001"}})
    assert out["event"]["competition"]["id"] == "la-liga"
    # ESPN answered the eng.1 probe with the La Liga summary; it is not fetched again under esp.1
    assert len(calls) == 1, calls


def test_timeline_keeps_stoppage_time_as_added_time():
    tl = c._normalize_espn_summary_timeline(LA_LIGA_SUMMARY)
    assert [(e["minute"], e["added_time"]) for e in tl] == [(45, 3), (59, 0), (90, 7)]


def test_timeline_reads_period_and_wallclock():
    summary = {
        "keyEvents": [
            {
                "id": "1",
                "type": {"text": "Yellow Card"},
                "period": {"number": 1},
                "clock": {"displayValue": "24'"},
                "wallclock": "2026-11-08T14:24:44Z",
            },
            {
                "id": "2",
                "type": {"text": "Goal"},
                "period": {"number": 2},
                "clock": {"displayValue": "70'"},
                "wallclock": "2026-11-08T15:31:02Z",
            },
        ]
    }
    tl = c._normalize_espn_summary_timeline(summary)
    assert [(e["period"], e["datetime"]) for e in tl] == [
        (1, "2026-11-08T14:24:44Z"),
        (2, "2026-11-08T15:31:02Z"),
    ]


def test_timeline_without_period_or_wallclock_keeps_empty_strings():
    tl = c._normalize_espn_summary_timeline(LA_LIGA_SUMMARY)
    assert {(e["period"], e["datetime"]) for e in tl} == {("", "")}


def test_timeline_scalar_period_yields_empty_string():
    # ESPN (e.g. eng.1 event 740705) sends ``period`` as an object; a bare scalar is not
    # a shape we read, so it must degrade to "" instead of raising on ``.get``.
    summary = {
        "keyEvents": [
            {
                "id": "1",
                "type": {"text": "Goal"},
                "period": 2,
                "clock": {"displayValue": "70'"},
                "wallclock": "2026-11-08T15:31:02Z",
            }
        ]
    }
    (event,) = c._normalize_espn_summary_timeline(summary)
    assert event["period"] == ""
    assert event["datetime"] == "2026-11-08T15:31:02Z"


def _roster_player(pid, *, subbed_in=False, subbed_out=False, sub_clock=None):
    plays = []
    if sub_clock:
        plays.append({"clock": {"displayValue": sub_clock}, "substitution": True})
    return {
        "athlete": {"id": pid, "displayName": pid},
        "starter": not subbed_in,
        "subbedIn": subbed_in,
        "subbedOut": subbed_out,
        "plays": plays,
    }


def test_sub_minute_comes_from_the_substitution_play():
    summary = {
        "rosters": [
            {
                "team": {"id": "364", "displayName": "Liverpool"},
                "roster": [
                    _roster_player("out", subbed_out=True, sub_clock="60'"),
                    _roster_player("in", subbed_in=True, sub_clock="60'"),
                    _roster_player("late", subbed_in=True, sub_clock="90'+2'"),
                    _roster_player("starter"),
                ],
            }
        ]
    }
    (team,) = c._normalize_espn_summary_players(summary)
    minutes = {p["id"]: p["sub_minute"] for p in team["players"]}
    assert minutes == {"out": 60, "in": 60, "late": 90, "starter": None}


def _players_by_id(roster):
    summary = {"rosters": [{"team": {"id": "364", "displayName": "Liverpool"}, "roster": roster}]}
    (team,) = c._normalize_espn_summary_players(summary)
    return {p["id"]: p for p in team["players"]}


def test_sub_minute_skips_null_or_unreadable_clock_and_uses_next_valid_play():
    entry = {
        "athlete": {"id": "in", "displayName": "in"},
        "starter": False,
        "subbedIn": True,
        "subbedOut": False,
        "plays": [
            {"clock": {"displayValue": None}, "substitution": True},
            {"clock": {"displayValue": "--"}, "substitution": True},
            {"clock": None, "substitution": True},
            {"clock": {"displayValue": "67'"}, "substitution": True},
        ],
    }
    assert _players_by_id([entry])["in"]["sub_minute"] == 67


def test_sub_minute_preserves_explicit_zero_sub_minute():
    entry = _roster_player("in", subbed_in=True, sub_clock="60'")
    entry["subMinute"] = 0
    assert _players_by_id([entry])["in"]["sub_minute"] == 0


def test_sub_minute_subbed_in_and_out_uses_first_valid_substitution_in_provider_order():
    # Convention: a player both subbed in and out gets the minute of the first valid
    # substitution play as ESPN orders them (here: the entry). No extra fields are added.
    entry = {
        "athlete": {"id": "both", "displayName": "both"},
        "starter": False,
        "subbedIn": True,
        "subbedOut": True,
        "plays": [
            {"clock": {"displayValue": None}, "substitution": True},
            {"clock": {"displayValue": "46'"}, "substitution": True},
            {"clock": {"displayValue": "80'"}, "substitution": True},
        ],
    }
    player = _players_by_id([entry])["both"]
    assert player["sub_minute"] == 46
    assert player["subbed_in"] is True and player["subbed_out"] is True
    assert not {"sub_in_minute", "sub_out_minute"} & set(player)


def test_serie_b_is_wired_like_serie_a():
    serie_a = c.LEAGUES["serie-a"]
    serie_b = c.LEAGUES["serie-b"]
    assert serie_b["espn"] == "ita.2"
    assert serie_b["fduk"] == "I2"
    assert serie_b["clubelo"] == serie_a["clubelo"] == "ITA"
    assert serie_b["openfootball"]["file"] == "it.2"
    assert serie_b["openfootball"]["timezone"] == serie_a["openfootball"]["timezone"]
    assert serie_b["country"] == "Italy"
    # No Understat or FPL data exists for Serie B.
    assert serie_b["understat"] is None
    assert serie_b["fpl"] is None
    assert c.ESPN_TO_SLUG["ita.2"] == "serie-b"
    assert c._espn_league_code("serie-b") == "ita.2"
    assert c._espn_league_code("ita.2") == "ita.2"

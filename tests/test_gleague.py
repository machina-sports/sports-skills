"""NBA G League (ESPN ``basketball/nba-development``): public API, CLI registration, isolation from NBA.

Captured payloads live in tests/fixtures/gleague/ (see PROVENANCE.md). Payloads
named SYNTHETIC below are small hand-built edge cases, not captured data; where
they carry teams or scores, those come from the captured fixtures.

No network: ``_espn_base._http_fetch`` is replaced by a transport that serves
G League payloads by resource and records every URL, and ``urlopen`` records
any request that slips past it.
"""

import datetime as dt
import importlib
import importlib.util
import inspect
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from sports_skills import _espn_base
from sports_skills.cli import _REGISTRY
from sports_skills.nba import _connector as nba_connector

FIXTURES = Path(__file__).parent / "fixtures" / "gleague"
SCOREBOARD = json.loads((FIXTURES / "scoreboard_20260410.json").read_text())
ROSTER_2026 = json.loads((FIXTURES / "roster_team2_season2026.json").read_text())
ROSTER_CURRENT = json.loads((FIXTURES / "roster_team2_current.json").read_text())
TEAMS = json.loads((FIXTURES / "teams_excerpt.json").read_text())
TOURNAMENT_2026 = json.loads((FIXTURES / "schedule_team2_2026_tournament_excerpt.json").read_text())
STANDINGS_2026 = json.loads((FIXTURES / "standings_2026_east_excerpt.json").read_text())
NEWS = json.loads((FIXTURES / "news_excerpt.json").read_text())

G_LEAGUE_PATH = "/sports/basketball/nba-development/"
FINALS_EVENT = "401867657"  # G League Finals Game 2, GBO 119 @ STO 104, 2026-04-11T02:00Z
FINALS_START_TS = int(dt.datetime(2026, 4, 11, 2, tzinfo=dt.timezone.utc).timestamp())

EXPECTED_COMMANDS = {
    "get_teams": {},
    "get_scoreboard": {"optional": ["date"]},
    "get_schedule": {"optional": ["date", "season"]},
    "get_standings": {"optional": ["season"]},
    "get_team_roster": {"required": ["team_id"]},
    "get_team_schedule": {"required": ["team_id"], "optional": ["season", "season_type"]},
    "get_game_summary": {"required": ["event_id"]},
    "get_play_by_play": {"required": ["event_id"]},
    "get_news": {"optional": ["limit"]},
    # Official sources (NBA Stats LeagueID 20, cdn-gleague.nba.com); see test_gleague_official.py.
    "get_live_boxscore": {"required": ["game_id"]},
    "get_live_playbyplay": {"required": ["game_id"], "optional": ["limit", "scoring_only"]},
    "find_nba_player": {"required": ["name"]},
    "get_nbastats_game_log": {
        "optional": ["season", "team", "season_type", "player_or_team", "player", "sort_by", "descending", "limit", "fields"]
    },
    "get_nbastats_player_career": {"optional": ["player_id", "player", "per_mode"]},
    "get_nbastats_team_stats": {
        "optional": ["season", "team", "measure", "per_mode", "season_type", "sort_by", "descending", "limit", "fields"]
    },
    "get_nbastats_shot_chart": {
        "optional": ["player_id", "player", "season", "season_type", "sort_by", "descending", "limit", "fields"]
    },
    "get_nbastats_play_by_play": {"required": ["game_id"], "optional": ["limit"]},
    "get_nbastats_advanced_boxscore": {"required": ["game_id"]},
    "get_nbastats_leaders": {
        "optional": ["season", "season_type", "per_mode", "stat_category", "sort_by", "descending", "limit", "fields"]
    },
}

# NBA commands with no verified G League source: teams/{id}/statistics is HTTP 404,
# the summary has no winprobability block, cdn-gleague.nba.com's schedule answered 403,
# and the rest were not probed.
UNSUPPORTED = [
    "get_team_stats",
    "get_player_stats",
    "get_leaders",
    "get_injuries",
    "get_transactions",
    "get_futures",
    "get_depth_chart",
    "get_win_probability",
    "get_live_scoreboard",
    "get_player_live_stats",
    "get_nba_game_matchup",
]


def _gleague():
    assert importlib.util.find_spec("sports_skills.gleague") is not None, "sports_skills.gleague does not exist"
    return importlib.import_module("sports_skills.gleague")


def _ok(result):
    assert result["status"] is True, result
    return result["data"]


# ── SYNTHETIC payloads ─────────────────────────────────────────────

AUS = {"id": "2", "displayName": "Austin Spurs", "abbreviation": "AUS"}
STO = {"id": "23", "displayName": "Stockton Kings", "abbreviation": "STO"}
GBO = {"id": "9", "displayName": "Greensboro Swarm", "abbreviation": "GBO"}

# SYNTHETIC: a game day with no games.
EMPTY_SCOREBOARD = {"events": []}


def _schedule_event(event_id, date, season_type, home_score, away_score):
    """SYNTHETIC team-schedule row: scores arrive as objects, as teams/{id}/schedule sends them."""
    return {
        "id": event_id,
        "date": date,
        "name": f"SYNTHETIC {event_id}",
        "seasonType": {"id": season_type},
        "competitions": [
            {
                "date": date,
                "status": {"type": {"name": "STATUS_FINAL", "shortDetail": "Final"}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": AUS,
                        "score": {"value": float(home_score), "displayValue": str(home_score)},
                    },
                    {
                        "homeAway": "away",
                        "team": STO,
                        "score": {"value": float(away_score), "displayValue": str(away_score)},
                    },
                ],
            }
        ],
    }


REGULAR_GAME = _schedule_event("synthetic-regular", "2025-12-27T01:00Z", "2", 98, 104)
POSTSEASON_GAME = _schedule_event("synthetic-postseason", "2026-04-01T00:00Z", "3", 120, 117)
SCHEDULE_BY_TYPE = {None: [REGULAR_GAME], "2": [REGULAR_GAME], "3": [POSTSEASON_GAME]}


def _team_schedule(seasontype):
    """Type 5 is the captured 2025-26 Tip-Off Tournament excerpt; the other phases are SYNTHETIC."""
    if seasontype == "5":
        return TOURNAMENT_2026
    # SYNTHETIC envelope: ESPN reports its *current* season here, whatever was asked.
    return {"season": {"year": 2027}, "team": AUS, "events": list(SCHEDULE_BY_TYPE.get(seasontype, []))}


def _standings_entry(team, wins, losses):
    return {
        "team": team,
        "stats": [
            {"name": "wins", "value": float(wins), "displayValue": str(wins)},
            {"name": "losses", "value": float(losses), "displayValue": str(losses)},
        ],
    }


# SYNTHETIC: the upcoming season's table before opening night, every record 0-0.
STANDINGS_2027_ZEROS = {
    "name": "NBA G League",
    "children": [
        {
            "name": "Eastern Conference",
            "standings": {
                "season": 2027,
                "seasonType": 2,
                "entries": [_standings_entry({"id": "27", "abbreviation": "WIS"}, 0, 0)],
            },
        }
    ],
}

# SYNTHETIC: one league-wide table on the root (no conference children), in the tournament phase.
STANDINGS_LEAGUE_WIDE = {
    "name": "NBA G League",
    "standings": {
        "season": 2027,
        "seasonType": 5,
        "entries": [_standings_entry(AUS, 3, 1), _standings_entry(STO, 1, 3)],
    },
}

# SYNTHETIC: conference -> group -> table nesting.
STANDINGS_NESTED = {
    "name": "NBA G League",
    "children": [
        {
            "name": "Western Conference",
            "children": [
                {
                    "name": "SYNTHETIC Group A",
                    "standings": {"season": 2027, "seasonType": 2, "entries": [_standings_entry(AUS, 2, 0)]},
                },
                {
                    "name": "SYNTHETIC Group B",
                    "standings": {"season": 2027, "seasonType": 2, "entries": [_standings_entry(STO, 0, 2)]},
                },
            ],
        }
    ],
}

# SYNTHETIC summary: header values from the captured scoreboard; the two plays are made up.
SUMMARY = {
    "header": {
        "id": FINALS_EVENT,
        "season": {"year": 2026, "type": 3},
        "competitions": [
            {
                "date": "2026-04-11T02:00Z",
                "status": {"type": {"name": "STATUS_FINAL", "state": "post", "shortDetail": "Final"}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "104",
                        "winner": False,
                        "team": STO,
                        "linescores": [{"displayValue": v} for v in ("19", "31", "33", "21")],
                    },
                    {
                        "homeAway": "away",
                        "score": "119",
                        "winner": True,
                        "team": GBO,
                        "linescores": [{"displayValue": v} for v in ("25", "37", "27", "30")],
                    },
                ],
            }
        ],
    },
    "boxscore": {
        "teams": [
            {"team": STO, "statistics": [{"label": "PTS", "displayValue": "104"}]},
            {"team": GBO, "statistics": [{"label": "PTS", "displayValue": "119"}]},
        ],
        "players": [],
    },
    "plays": [
        {
            "id": "synthetic-1",
            "text": "SYNTHETIC jump ball",
            "type": {"text": "Jumpball"},
            "period": {"number": 1},
            "clock": {"displayValue": "12:00"},
            "homeScore": 0,
            "awayScore": 0,
            "scoringPlay": False,
            "scoreValue": 0,
            "team": {"id": "23"},
        },
        {
            "id": "synthetic-2",
            "text": "SYNTHETIC three point jumper",
            "type": {"text": "Jump Shot"},
            "period": {"number": 1},
            "clock": {"displayValue": "11:40"},
            "homeScore": 0,
            "awayScore": 3,
            "scoringPlay": True,
            "scoreValue": 3,
            "team": {"id": "9"},
            "shootingPlay": True,
        },
    ],
}


# ── Transport ─────────────────────────────────────────────


class _Transport:
    """Stands in for ``_espn_base._http_fetch``: serves G League payloads by resource, records each URL.

    Anything outside ``basketball/nba-development`` is a 404, so a fallback to
    another league can never succeed by accident. A handler returning an int
    answers with that HTTP status.
    """

    def __init__(self):
        self.urls = []
        self.escaped = []
        self.routes = {
            "teams": lambda q: TEAMS,
            "scoreboard": lambda q: SCOREBOARD if q.get("dates") == "20260410" else EMPTY_SCOREBOARD,
            "teams/2/roster": lambda q: ROSTER_CURRENT,
            "teams/2/schedule": lambda q: _team_schedule(q.get("seasontype")),
            "standings": lambda q: STANDINGS_2026 if q.get("season") == "2026" else STANDINGS_2027_ZEROS,
            "news": lambda q: NEWS,
            "summary": lambda q: SUMMARY if q.get("event") == FINALS_EVENT else 404,
        }

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        _, found, resource = parts.path.partition("/nba-development/")
        handler = self.routes.get(resource) if found else None
        payload = handler(query) if handler else 404
        if isinstance(payload, int):
            return None, {"error": True, "status_code": payload, "message": f"HTTP {payload} from {parts.netloc}"}
        return json.dumps(payload).encode(), None

    def queries(self, resource):
        """Query params of every request for ``resource``, in order."""
        found = []
        for url in self.urls:
            parts = urllib.parse.urlsplit(url)
            if parts.path.endswith(f"/nba-development/{resource}"):
                found.append(dict(urllib.parse.parse_qsl(parts.query)))
        return found


@pytest.fixture
def espn(monkeypatch):
    transport = _Transport()
    monkeypatch.setattr(_espn_base, "_http_fetch", transport)
    monkeypatch.setattr(_espn_base, "_cache", {})

    def no_network(request, *args, **kwargs):
        # Recorded as well as raised: a caller that swallows exceptions must still fail the test.
        transport.escaped.append(getattr(request, "full_url", request))
        raise AssertionError(f"unexpected network call: {transport.escaped[-1]}")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return transport


# ── Registration: CLI, package, schema ─────────────────────────────────────────────


def test_cli_registers_only_source_backed_commands():
    assert "gleague" in _REGISTRY, "sports-skills gleague is not registered"
    assert _REGISTRY["gleague"] == EXPECTED_COMMANDS


def test_commands_without_a_verified_g_league_source_are_not_advertised():
    assert "gleague" in _REGISTRY, "sports-skills gleague is not registered"
    assert sorted(set(UNSUPPORTED) & set(_REGISTRY["gleague"])) == []


def test_public_functions_take_exactly_the_registered_params():
    gl = _gleague()
    for command, spec in EXPECTED_COMMANDS.items():
        params = inspect.signature(getattr(gl, command)).parameters
        assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values()), command
        assert set(params) == set(spec.get("required", []) + spec.get("optional", [])), command
        for name in spec.get("required", []):
            assert params[name].default is inspect.Parameter.empty, (command, name)


def test_package_exports_gleague():
    import sports_skills

    assert "gleague" in sports_skills.__all__
    assert sports_skills.gleague is _gleague()


def test_cli_loads_the_module_and_every_tool_has_a_docstring():
    from sports_skills.cli import _generate_schema, _load_module

    assert "gleague" in _REGISTRY, "sports-skills gleague is not registered"
    assert _load_module("gleague") is _gleague()
    tools = {t["command"]: t for t in _generate_schema("gleague")["tools"]}
    assert set(tools) == set(EXPECTED_COMMANDS)
    for command, tool in tools.items():
        assert tool["name"] == f"gleague_{command}"
        assert tool["description"] != f"{command} command for gleague", f"{command} has no docstring"


def test_cli_missing_team_id_is_a_structured_error(monkeypatch, capsys):
    from sports_skills import cli

    monkeypatch.setattr(sys, "argv", ["sports-skills", "gleague", "get_team_roster"])
    with pytest.raises(SystemExit):
        cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] is False
    assert "--team_id" in payload["message"]


# ── Isolation: G League IDs overlap NBA IDs, so nothing may reach an NBA source ──


def test_every_command_stays_on_the_g_league_espn_path(espn):
    gl = _gleague()
    gl.get_teams()
    gl.get_scoreboard()
    gl.get_scoreboard(date="2026-04-10")
    gl.get_schedule(date="2026-04-10")
    gl.get_standings()
    gl.get_standings(season=2026)
    gl.get_team_roster(team_id="2")
    gl.get_team_schedule(team_id="2", season_type="all")
    gl.get_game_summary(event_id=FINALS_EVENT)
    gl.get_play_by_play(event_id=FINALS_EVENT)
    gl.get_news()

    assert espn.escaped == [], "a request bypassed the shared ESPN transport (NBA CDN / stats.nba.com?)"
    assert espn.urls
    off_path = [u for u in espn.urls if G_LEAGUE_PATH not in u]
    assert off_path == []
    assert [u for u in espn.urls if "/sports/basketball/nba/" in u or "nba.com" in u] == []
    # The NBA connector's own sport path is untouched (no shared mutable state).
    assert nba_connector.SPORT_PATH == "basketball/nba"


def test_overlapping_team_id_returns_the_g_league_team(espn):
    # ESPN team id 2 is the Boston Celtics in the NBA and the Austin Spurs in the G League.
    data = _ok(_gleague().get_team_roster(team_id="2"))
    assert data["team"] == {"id": "2", "name": "Austin Spurs", "abbreviation": "AUS"}


# ── Scoreboard / schedule ─────────────────────────────────────────────


def test_scoreboard_normalizes_the_captured_finals_game(espn):
    data = _ok(_gleague().get_scoreboard(date="2026-04-10"))
    assert espn.queries("scoreboard") == [{"dates": "20260410"}]
    assert data["count"] == 1
    (event,) = data["events"]
    assert event["id"] == FINALS_EVENT
    assert event["name"] == "Greensboro Swarm at Stockton Kings"
    assert event["status"] == "closed"
    assert event["season_type"] == "postseason"
    assert event["start_time"] == "2026-04-11T02:00Z"
    assert event["start_ts"] == FINALS_START_TS
    assert event["venue"]["name"] == "Adventist Health Arena"
    assert event["broadcasts"] == ["ESPNU"]
    sides = {c["home_away"]: c for c in event["competitors"]}
    assert (sides["home"]["team"]["abbreviation"], sides["home"]["score"]) == ("STO", "104")
    assert (sides["away"]["team"]["abbreviation"], sides["away"]["score"]) == ("GBO", "119")
    assert sides["away"]["winner"] is True
    assert sides["home"]["period_scores"] == [19, 31, 33, 21]


def test_scoreboard_without_a_date_asks_espn_for_its_default_day(espn):
    _ok(_gleague().get_scoreboard())
    assert espn.queries("scoreboard") == [{}]


def test_a_day_without_games_is_empty_not_an_error(espn):
    data = _ok(_gleague().get_scoreboard(date="2026-07-04"))
    assert (data["events"], data["count"]) == ([], 0)


def test_scoreboard_upstream_failure_is_an_error(espn):
    espn.routes["scoreboard"] = lambda q: 503
    result = _gleague().get_scoreboard(date="2026-04-10")
    assert result["status"] is False
    assert result["status_code"] == 503
    assert all(G_LEAGUE_PATH in u for u in espn.urls)


def test_schedule_for_a_date_reads_the_g_league_scoreboard(espn):
    data = _ok(_gleague().get_schedule(date="2026-04-10"))
    assert [e["id"] for e in data["events"]] == [FINALS_EVENT]


def test_schedule_season_without_a_date_is_an_error_without_a_request(espn):
    # ESPN's scoreboard has no season filter; it would answer with the next game day.
    result = _gleague().get_schedule(season=2026)
    assert result["status"] is False
    assert "get_team_schedule" in result["message"]
    assert espn.urls == []


# ── Standings ─────────────────────────────────────────────


def test_standings_for_a_requested_season(espn):
    data = _ok(_gleague().get_standings(season=2026))
    assert {q.get("season") for q in espn.queries("standings")} == {"2026"}
    assert (data["season"], data["season_type"]) == (2026, "regular")
    entries = {e["team"]["abbreviation"]: e for g in data["groups"] for e in g["entries"]}
    assert set(entries) == {"WIS", "LIN"}
    assert {g["conference"] for g in data["groups"]} == {"Eastern Conference"}
    wis = entries["WIS"]
    assert (wis["wins"], wis["losses"], wis["win_pct"]) == ("10", "26", ".278")
    assert (wis["home_record"], wis["away_record"]) == ("4-14", "6-12")
    assert wis["conference_record"] == "7-21"
    assert wis["last_ten"] == "2-8"  # ESPN names this stat "Last Ten Games" for the G League, not "L10"
    assert (wis["playoff_seed"], wis["streak"]) == ("16", "L1")


def test_omitted_season_skips_an_upcoming_season_with_no_games(espn):
    data = _ok(_gleague().get_standings())
    assert data["season"] == 2026
    assert data["defaulted_from"] == 2027
    assert "season=2027" in data["note"]
    assert {e["team"]["abbreviation"] for g in data["groups"] for e in g["entries"]} == {"WIS", "LIN"}


def test_explicit_season_error_is_not_replaced_by_another_season(espn):
    espn.routes["standings"] = lambda q: 404 if q.get("season") == "2027" else STANDINGS_2026
    result = _gleague().get_standings(season=2027)
    assert result["status"] is False
    assert {q.get("season") for q in espn.queries("standings")} == {"2027"}


def test_league_wide_table_is_kept(espn):
    espn.routes["standings"] = lambda q: STANDINGS_LEAGUE_WIDE
    data = _ok(_gleague().get_standings(season=2027))
    teams = [e["team"]["id"] for g in data["groups"] for e in g["entries"]]
    assert teams == ["2", "23"]


def test_tournament_phase_is_not_labelled_play_in(espn):
    # ESPN season type 5 is the NBA play-in but the G League tournament/Showcase phase.
    espn.routes["standings"] = lambda q: STANDINGS_LEAGUE_WIDE
    data = _ok(_gleague().get_standings(season=2027))
    assert data["season_type"] == "tournament"


def test_nested_group_tables_are_all_kept(espn):
    espn.routes["standings"] = lambda q: STANDINGS_NESTED
    data = _ok(_gleague().get_standings(season=2027))
    by_team = {e["team"]["id"]: g for g in data["groups"] for e in g["entries"]}
    assert set(by_team) == {"2", "23"}
    assert {g["conference"] for g in by_team.values()} == {"Western Conference"}


# ── Roster ─────────────────────────────────────────────


def test_empty_roster_is_a_successful_empty_list(espn):
    # Captured: ESPN answered teams/2/roster?season=2026 with athletes: [] (served here for the plain request).
    espn.routes["teams/2/roster"] = lambda q: ROSTER_2026
    data = _ok(_gleague().get_team_roster(team_id="2"))
    assert (data["athletes"], data["count"]) == ([], 0)


def test_current_flat_roster_is_normalized(espn):
    data = _ok(_gleague().get_team_roster(team_id="2"))
    assert espn.queries("teams/2/roster") == [{}]  # current roster only; no season is sent
    assert data["season"] == 2027
    assert data["count"] == 2
    bader, banks = data["athletes"]
    assert (bader["id"], bader["name"], bader["jersey"], bader["position"], bader["college"]) == (
        "2490244",
        "Travis Bader",
        "3",
        "F",
        "",
    )
    assert (banks["position"], banks["height"], banks["weight"], banks["college"], banks["status"]) == (
        "C",
        "6' 10\"",
        "250 lbs",
        "Georgia Tech",
        "active",
    )


def test_roster_upstream_failure_is_an_error(espn):
    result = _gleague().get_team_roster(team_id="999")
    assert result["status"] is False
    assert result["status_code"] == 404


# ── Team schedule ─────────────────────────────────────────────


def test_team_schedule_without_a_season_uses_espns_default(espn):
    data = _ok(_gleague().get_team_schedule(team_id="2"))
    assert espn.queries("teams/2/schedule") == [{}]
    assert data["season"] == 2027
    assert [e["id"] for e in data["events"]] == ["synthetic-regular"]


def test_team_schedule_echoes_the_requested_season(espn):
    data = _ok(_gleague().get_team_schedule(team_id="2", season=2026))
    assert espn.queries("teams/2/schedule") == [{"season": "2026"}]
    assert data["season"] == 2026


@pytest.mark.parametrize("value", ["tournament", "showcase", "5", 5])
def test_tournament_season_type_requests_espn_type_5(espn, value):
    data = _ok(_gleague().get_team_schedule(team_id="2", season=2026, season_type=value))
    assert espn.queries("teams/2/schedule") == [{"season": "2026", "seasontype": "5"}]
    assert [e["id"] for e in data["events"]] == ["401818725", "401818801"]
    assert {e["season_type"] for e in data["events"]} == {"tournament"}


def test_omitted_season_reports_espns_requested_season_not_its_envelope(espn):
    # Captured payload (requested with season=2026): envelope season 2027, requestedSeason 2026.
    data = _ok(_gleague().get_team_schedule(team_id="2", season_type="tournament"))
    assert espn.queries("teams/2/schedule") == [{"seasontype": "5"}]
    assert data["season"] == 2026


def test_all_merges_tournament_regular_and_postseason_in_date_order(espn):
    data = _ok(_gleague().get_team_schedule(team_id="2", season=2026, season_type="all"))
    assert {q.get("seasontype") for q in espn.queries("teams/2/schedule")} == {"2", "3", "5"}
    assert [e["id"] for e in data["events"]] == ["401818725", "401818801", "synthetic-regular", "synthetic-postseason"]
    assert [e["season_type"] for e in data["events"]] == ["tournament", "tournament", "regular", "postseason"]
    assert data["count"] == 4


def test_play_in_is_not_a_g_league_season_type(espn):
    result = _gleague().get_team_schedule(team_id="2", season_type="playin")
    assert result["status"] is False
    assert "tournament" in result["message"]
    assert espn.urls == []


def test_team_schedule_scores_are_strings_and_rows_carry_start_ts(espn):
    # Captured: teams/{id}/schedule sends each score as {"value": 89.0, "displayValue": "89"}.
    data = _ok(_gleague().get_team_schedule(team_id="2", season=2026, season_type="tournament"))
    event = data["events"][0]
    sides = {c["home_away"]: (c["team"]["abbreviation"], c["score"], c["winner"]) for c in event["competitors"]}
    assert sides == {"home": ("LAK", "89", False), "away": ("AUS", "101", True)}
    assert event["start_time"] == "2025-11-08T01:00Z"
    assert event["start_ts"] == int(dt.datetime(2025, 11, 8, 1, tzinfo=dt.timezone.utc).timestamp())
    assert event["venue"]["name"] == "Legacy Arena at BJCC"


def test_one_failing_phase_fails_the_whole_all_request(espn):
    espn.routes["teams/2/schedule"] = lambda q: (
        500 if q.get("seasontype") == "3" else _team_schedule(q.get("seasontype"))
    )
    result = _gleague().get_team_schedule(team_id="2", season=2026, season_type="all")
    assert result["status"] is False
    assert result["status_code"] == 500


# ── Game summary / play-by-play ─────────────────────────────────────────────


def test_game_summary_is_normalized(espn):
    data = _ok(_gleague().get_game_summary(event_id=FINALS_EVENT))
    assert espn.queries("summary") == [{"event": FINALS_EVENT}]
    info = data["game_info"]
    assert info["id"] == FINALS_EVENT
    assert (info["start_time"], info["start_ts"]) == ("2026-04-11T02:00Z", FINALS_START_TS)
    assert info["season_type"] == "postseason"
    assert {c["team"]["abbreviation"]: c["score"] for c in data["competitors"]} == {"STO": "104", "GBO": "119"}
    assert [t["team"]["id"] for t in data["boxscore"]] == ["23", "9"]
    assert [(p["team"]["abbreviation"], p["away_score"]) for p in data["scoring_plays"]] == [("GBO", 3)]


SUMMARY_CAPTURED = json.loads((FIXTURES / "summary_401867657_excerpt.json").read_text())


def test_captured_finals_summary_is_normalized(espn):
    espn.routes["summary"] = lambda q: SUMMARY_CAPTURED
    data = _ok(_gleague().get_game_summary(event_id=FINALS_EVENT))
    info = data["game_info"]
    assert (info["id"], info["start_ts"], info["season_type"]) == (FINALS_EVENT, FINALS_START_TS, "postseason")
    assert info["venue"]["name"] == "Adventist Health Arena"
    sides = {c["team"]["abbreviation"]: (c["home_away"], c["score"], c["linescores"]) for c in data["competitors"]}
    assert sides == {
        "STO": ("home", "104", ["19", "31", "33", "21"]),
        "GBO": ("away", "119", ["25", "37", "27", "30"]),
    }
    box = {t["team"]["id"]: t for t in data["boxscore"]}
    assert set(box) == {"9", "23"}
    assert (box["9"]["team_stats"]["FG"], box["9"]["team_stats"]["Rebounds"]) == ("42-91", "51")
    (table,) = box["23"]["statistics"]
    points = table["labels"][1]  # ESPN's second column is points ("Points" in the captured descriptions)
    assert [(a["name"], a["stats"][points]) for a in table["athletes"]] == [
        ("Gabe Levin", "6"),
        ("Patrick Baldwin Jr.", "20"),
    ]
    assert table["totals"][points] == "104"
    # The excerpt keeps the first three plays, none of which scored.
    assert data["scoring_plays"] == []


def test_captured_finals_play_by_play_rows(espn):
    espn.routes["summary"] = lambda q: SUMMARY_CAPTURED
    data = _ok(_gleague().get_play_by_play(event_id=FINALS_EVENT))
    assert data["count"] == 3
    rows = [(p["id"], p["type"], p["clock"], p["team_id"], p["shooting_play"]) for p in data["plays"]]
    assert rows == [
        ("4018676574", "Jumpball", "12:00", "9", False),
        ("4018676577", "Driving Layup", "11:34", "9", True),
        ("4018676578", "Defensive Rebound", "11:33", "23", False),
    ]
    assert data["plays"][1]["coordinate"] == {"x": 27, "y": 4}


def test_game_summary_upstream_failure_is_an_error(espn):
    result = _gleague().get_game_summary(event_id="401000000")
    assert result["status"] is False
    assert "401000000" in result["message"]


def test_play_by_play_is_normalized(espn):
    data = _ok(_gleague().get_play_by_play(event_id=FINALS_EVENT))
    assert data["count"] == 2
    play = data["plays"][1]
    assert (play["id"], play["period"], play["clock"]) == ("synthetic-2", 1, "11:40")
    assert (play["scoring_play"], play["score_value"], play["team_id"]) == (True, 3, "9")


def test_play_by_play_without_plays_is_empty_not_an_error(espn):
    espn.routes["summary"] = lambda q: {**SUMMARY, "plays": []}
    data = _ok(_gleague().get_play_by_play(event_id=FINALS_EVENT))
    assert (data["plays"], data["count"]) == ([], 0)


def test_play_by_play_upstream_failure_is_an_error(espn):
    result = _gleague().get_play_by_play(event_id="401000000")
    assert result["status"] is False


# ── Teams / news ─────────────────────────────────────────────


def test_teams_are_normalized(espn):
    data = _ok(_gleague().get_teams())
    assert data["count"] == 2
    assert [(t["id"], t["name"], t["abbreviation"]) for t in data["teams"]] == [
        ("2", "Austin Spurs", "AUS"),
        ("4", "Capital City Go-Go", "CAP"),
    ]
    assert data["teams"][0]["logo"] == "https://a.espncdn.com/i/teamlogos/nba-development/500/aus.png"


def test_news_is_normalized_with_a_coverage_caveat(espn):
    data = _ok(_gleague().get_news())
    assert data["count"] == 2
    assert [a["link"] for a in data["articles"]] == [
        "https://www.espn.com/video/clip/_/id/50307102/davis-hot-starts-puts-wildcats",
        "http://www.espn.com/nba-g-league/recap?gameId=401819373",
    ]
    # Captured: ESPN's G League feed carries other leagues' stories (the first is an NBL clip).
    assert data["caveats"] and all(isinstance(c, str) and c for c in data["caveats"])


def test_news_limit_caps_the_articles(espn):
    data = _ok(_gleague().get_news(limit=1))
    assert data["count"] == 1
    assert data["articles"][0]["headline"] == "Davis hot starts puts out Wildcats"


# ── Missing params fail before any request ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("command", "kwargs"),
    [
        ("get_team_roster", {"team_id": ""}),
        ("get_team_schedule", {"team_id": ""}),
        ("get_game_summary", {"event_id": ""}),
        ("get_play_by_play", {"event_id": ""}),
    ],
)
def test_missing_required_param_is_an_error_without_a_request(espn, command, kwargs):
    result = getattr(_gleague(), command)(**kwargs)
    assert result["status"] is False
    assert "required" in result["message"]
    assert espn.urls == []


@pytest.mark.parametrize(
    "command,param",
    [
        ("get_team_roster", "team_id"),
        ("get_team_schedule", "team_id"),
        ("get_game_summary", "event_id"),
        ("get_play_by_play", "event_id"),
    ],
)
@pytest.mark.parametrize("bad_id", ["../../nba/teams/2", "2?season=2026", "2#nba", "2/roster", True, 2.5])
def test_rejects_malformed_identifiers_before_transport(espn, command, param, bad_id):
    result = getattr(_gleague(), command)(**{param: bad_id})
    assert result["status"] is False
    assert espn.urls == []


@pytest.mark.parametrize("command", ["get_game_summary", "get_play_by_play"])
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"error": {"message": "No game found", "code": 404}},
        {"header": {"id": "999"}},
        {"header": {"id": FINALS_EVENT, "competitions": [{"id": "999"}]}},
        {"header": {"id": FINALS_EVENT, "competitions": [{"status": None}]}},
        {"header": {"id": FINALS_EVENT, "competitions": [{**SUMMARY["header"]["competitions"][0], "status": None}]}},
        {
            "header": {
                "id": FINALS_EVENT,
                "competitions": [{**SUMMARY["header"]["competitions"][0], "competitors": None}],
            }
        },
        {"header": {"id": FINALS_EVENT, "competitions": [{**SUMMARY["header"]["competitions"][0], "id": "999"}]}},
        {**SUMMARY, "error": {"message": "Invalid game"}},
    ],
)
def test_rejects_missing_game_summary_payload(monkeypatch, command, payload):
    monkeypatch.setattr(_espn_base, "_cache", {})
    monkeypatch.setattr(_espn_base, "_http_fetch", lambda *a, **kw: (json.dumps(payload).encode(), None))
    result = getattr(_gleague(), command)(event_id="401867657")
    assert result["status"] is False


@pytest.mark.parametrize("command", ["get_scoreboard", "get_schedule"])
@pytest.mark.parametrize("date", [20260410, "2026-02-30", "../nba", "20260410"])
def test_invalid_dates_fail_before_transport(espn, command, date):
    result = getattr(_gleague(), command)(date=date)
    assert result["status"] is False
    assert espn.urls == []

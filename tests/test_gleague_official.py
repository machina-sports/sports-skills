"""NBA G League via the official NBA sources: NBA Stats (``LeagueID=20``) and the G League live CDN.

Payloads are unmodified excerpts of captured responses in tests/fixtures/gleague/official/
(see PROVENANCE.md there). Payloads marked SYNTHETIC are hand-built from those captures.

No network: ``nba._stats._http_fetch`` (the stats.nba.com transport) and
``_espn_base._http_fetch`` (the shared transport the CDN adapter uses) are replaced by one
recording transport, and ``urlopen`` records and refuses anything that slips past it.
"""

import copy
import importlib
import inspect
import json
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from sports_skills import _espn_base
from sports_skills.cli import _REGISTRY
from sports_skills.nba import _cdn as nba_cdn
from sports_skills.nba import _stats as nba_stats

ROOT = Path(__file__).parent.parent
OFFICIAL_DIR = Path(__file__).parent / "fixtures" / "gleague" / "official"
OFFICIAL = {p.stem: json.loads(p.read_text()) for p in OFFICIAL_DIR.glob("*.json")}

STATS_HOST = "stats.nba.com"
CDN_HOST = "cdn-gleague.nba.com"
CDN_GAME = "2052500034"  # Tip-Off Tournament game, Maine Celtics @ Raptors 905, 2025-11-12
STATS_GAME = "2022500001"  # Stockton Kings @ Austin Spurs, 2025-12-19
MAC = "1630644"  # Mac McClung's NBA.com person id

# stats.nba.com endpoint -> captured excerpt
STATS_ROUTES = {
    "commonallplayers": "commonallplayers",
    "leaguegamelog": "leaguegamelog",
    "leaguedashteamstats": "leaguedashteamstats",
    "playercareerstats": "playercareerstats",
    "shotchartdetail": "shotchartdetail",
    "playbyplayv3": "playbyplayv3",
    "boxscoreadvancedv3": "boxscoreadvancedv3",
    "playergamelog": "playergamelog",
    "leagueleaders": "leaders",
}

NBA_SHAPED = [
    "find_nba_player",
    "get_nbastats_game_log",
    "get_nbastats_player_career",
    "get_nbastats_team_stats",
    "get_nbastats_shot_chart",
    "get_nbastats_play_by_play",
    "get_nbastats_advanced_boxscore",
    "get_live_boxscore",
    "get_live_playbyplay",
]

BAD_GAME_IDS = [
    "0022400061",  # NBA
    "1022400061",  # WNBA
    "401867657",  # ESPN event
    "20225000011",
    "202250000",
    "../2022500001",
    "2022500001/../x",
    "2022500001?x=1",
    "２０２２５０００01",  # full-width digits
    "",
    True,
    2.5,
]


def _gl():
    return importlib.import_module("sports_skills.gleague")


def _fn(name):
    gl = _gl()
    assert hasattr(gl, name), f"sports_skills.gleague.{name} does not exist"
    return getattr(gl, name)


def _ok(result):
    assert result["status"] is True, result
    return result["data"]


def _err(result):
    assert result["status"] is False, result
    return result["message"]


# ── Transport ─────────────────────────────────────────────


class _Transport:
    """Serves the captured official payloads by endpoint and records every request.

    A stats request naming any LeagueID other than "20" is a 404, so an NBA request can
    never succeed by accident. A handler may return a dict (JSON), bytes (raw body), an
    int (HTTP status), or "timeout".
    """

    def __init__(self):
        self.calls = []
        self.escaped = []
        self.routes = {name: (lambda q, f=fixture: OFFICIAL[f]) for name, fixture in STATS_ROUTES.items()}
        self.routes["boxscore"] = lambda q: OFFICIAL[f"boxscore_{CDN_GAME}_gleague"]
        self.routes["playbyplay"] = lambda q: OFFICIAL[f"playbyplay_{CDN_GAME}_gleague"]

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        handler = None
        if parts.netloc == STATS_HOST and query.get("LeagueID", "20") == "20":
            handler = self.routes.get(parts.path.rsplit("/", 1)[-1])
        elif parts.netloc == CDN_HOST:
            prefix = "/static/json/liveData/"
            kind = parts.path[len(prefix) :].split("/")[0] if parts.path.startswith(prefix) else ""
            if parts.path == f"{prefix}{kind}/{kind}_{CDN_GAME}.json":
                handler = self.routes.get(kind)
        payload = handler(query) if handler else 404
        if payload == "timeout":
            return None, {"error": True, "message": "The read operation timed out"}
        if isinstance(payload, int):
            return None, {"error": True, "status_code": payload, "message": f"HTTP {payload} from {parts.netloc}"}
        if isinstance(payload, bytes):
            return payload, None
        return json.dumps(payload).encode(), None

    @property
    def urls(self):
        return [u for u, _ in self.calls]

    def queries(self, endpoint):
        return [
            dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query, keep_blank_values=True))
            for u in self.urls
            if urllib.parse.urlsplit(u).path.endswith(f"/{endpoint}")
        ]


@pytest.fixture
def official(monkeypatch):
    transport = _Transport()
    monkeypatch.setattr(nba_stats, "_http_fetch", transport)
    monkeypatch.setattr(_espn_base, "_http_fetch", transport)
    monkeypatch.setattr(_espn_base, "_cache", {})

    def no_network(request, *args, **kwargs):
        transport.escaped.append(getattr(request, "full_url", request))
        raise AssertionError(f"unexpected network call: {transport.escaped[-1]}")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    yield transport
    assert transport.escaped == []
    assert [u for u in transport.urls if urllib.parse.urlsplit(u).netloc not in (STATS_HOST, CDN_HOST)] == []


def _with_table(endpoint, table_name, **changes):
    """Deep copy of a captured payload with one result set's fields replaced."""
    data = copy.deepcopy(OFFICIAL[STATS_ROUTES[endpoint]])
    for table in data["resultSets"]:
        if table["name"] == table_name:
            table.update(changes)
    return data


# ── Registration and signatures ─────────────────────────────────────────────


def test_cli_registers_the_official_commands_with_nba_params():
    commands = _REGISTRY["gleague"]
    for command in NBA_SHAPED:
        assert commands.get(command) == _REGISTRY["nba"][command], command
    assert commands.get("get_nbastats_leaders") == {
        "optional": ["season", "season_type", "per_mode", "stat_category", "sort_by", "descending", "limit", "fields"]
    }
    # No verified G League scoreboard source.
    assert "get_live_scoreboard" not in commands
    assert "get_player_live_stats" not in commands


@pytest.mark.parametrize("command", NBA_SHAPED)
def test_public_signature_matches_nba(command):
    nba = importlib.import_module("sports_skills.nba")

    def shape(fn):
        return [(p.name, p.kind, p.default) for p in inspect.signature(fn).parameters.values()]

    assert shape(_fn(command)) == shape(getattr(nba, command))


def test_schema_describes_every_official_command():
    from sports_skills.cli import _generate_schema

    tools = {t["command"]: t for t in _generate_schema("gleague")["tools"]}
    for command in [*NBA_SHAPED, "get_nbastats_leaders"]:
        assert command in tools, command
        assert tools[command]["description"] != f"{command} command for gleague", command


def test_every_official_command_requests_the_g_league_only(official):
    _ok(_fn("find_nba_player")(name="mcclung"))
    _ok(_fn("get_nbastats_game_log")(season=2025))
    _ok(_fn("get_nbastats_game_log")(season=2025, player="Mac McClung"))
    _ok(_fn("get_nbastats_player_career")(player="Mac McClung"))
    _ok(_fn("get_nbastats_team_stats")(season=2025))
    _ok(_fn("get_nbastats_shot_chart")(player="Mac McClung", season=2025))
    _ok(_fn("get_nbastats_play_by_play")(game_id=STATS_GAME))
    _ok(_fn("get_nbastats_advanced_boxscore")(game_id=STATS_GAME))
    _ok(_fn("get_nbastats_leaders")(season=2025))
    _ok(_fn("get_live_boxscore")(game_id=CDN_GAME))
    _ok(_fn("get_live_playbyplay")(game_id=CDN_GAME))
    queries = [dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query)) for u in official.urls]
    assert {q["LeagueID"] for q in queries if "LeagueID" in q} == {"20"}
    assert {q["GameID"][:2] for q in queries if "GameID" in q and q["GameID"]} == {"20"}
    assert {urllib.parse.urlsplit(u).netloc for u in official.urls} == {STATS_HOST, CDN_HOST}


# ── Player registry ─────────────────────────────────────────────


def test_find_player_searches_the_g_league_registry(official):
    data = _ok(_fn("find_nba_player")(name="mcclung"))
    (query,) = official.queries("commonallplayers")
    assert query["LeagueID"] == "20"
    assert (data["provider"], data["league_id"], data["count"]) == ("nba-stats", "20", 1)
    assert data["players"] == [
        {
            "player_id": MAC,
            "name": "Mac McClung",
            "is_active": True,
            "team": "WCB",
            "from_year": "2021",
            "to_year": "2025",
        }
    ]


def test_find_player_without_a_match_is_an_empty_success(official):
    data = _ok(_fn("find_nba_player")(name="Nobody Here"))
    assert (data["players"], data["count"]) == ([], 0)


def test_find_player_requires_a_name(official):
    _err(_fn("find_nba_player")(name=""))
    assert official.calls == []


def test_registry_without_its_named_table_is_an_error(official):
    official.routes["commonallplayers"] = lambda q: _with_table("commonallplayers", "CommonAllPlayers", name="Other")
    assert "CommonAllPlayers" in _err(_fn("find_nba_player")(name="mcclung"))


# ── Game log ─────────────────────────────────────────────


def test_team_game_log_rows(official):
    data = _ok(_fn("get_nbastats_game_log")(season=2025))
    (query,) = official.queries("leaguegamelog")
    assert (query["LeagueID"], query["PlayerOrTeam"], query["Season"], query["SeasonType"]) == (
        "20",
        "T",
        "2025-26",
        "Regular Season",
    )
    assert (data["provider"], data["league_id"], data["season"], data["season_type"], data["team"]) == (
        "nba-stats",
        "20",
        "2025-26",
        "Regular Season",
        None,
    )
    assert data["count"] == 3
    first = data["games"][0]
    assert (first["game_id"], first["team_abbreviation"], first["team_name"], first["matchup"], first["pts"]) == (
        STATS_GAME,
        "STO",
        "Stockton Kings",
        "STO @ AUS",
        119,
    )
    # G League abbreviations have no verified ESPN spelling.
    assert all("team_abbreviation_espn" not in row for row in data["games"])


def test_game_log_team_filter_uses_g_league_abbreviations(official):
    data = _ok(_fn("get_nbastats_game_log")(season="2025-26", team="sto"))
    assert (data["team"], [g["team_abbreviation"] for g in data["games"]]) == ("STO", ["STO"])


def test_game_log_team_filter_never_maps_nba_spellings(official):
    # "GS" is the ESPN spelling of the NBA's GSW; nothing translates it here.
    data = _ok(_fn("get_nbastats_game_log")(season=2025, team="GS"))
    assert (data["team"], data["games"], data["count"]) == ("GS", [], 0)
    assert data["warnings"] == ["team 'GS' matched no rows"]


def test_game_log_shaping_keeps_identity_columns(official):
    data = _ok(_fn("get_nbastats_game_log")(season=2025, sort_by="pts", descending=False, limit=1, fields="pts"))
    (row,) = data["games"]
    assert row == {
        "game_id": "2022500005",
        "game_date": "2025-12-19",
        "team_abbreviation": "MHU",
        "matchup": "MHU vs. CLC",
        "pts": 107,
    }
    assert (data["total_rows"], data["returned_rows"]) == (3, 1)


def test_player_game_log_by_name(official):
    data = _ok(_fn("get_nbastats_game_log")(season=2025, player="Mac McClung"))
    assert official.queries("commonallplayers")[0]["LeagueID"] == "20"
    (query,) = official.queries("playergamelog")
    assert (query["LeagueID"], query["PlayerID"], query["Season"]) == ("20", MAC, "2025-26")
    assert (data["player_or_team"], data["player_id"], data["player"], data["league_id"]) == (
        "player",
        MAC,
        "Mac McClung",
        "20",
    )
    assert [g["game_date"] for g in data["games"]] == ["2026-03-20", "2026-03-22", "2026-03-24"]
    last = data["games"][-1]
    assert (last["game_id"], last["team_abbreviation"], last["opponent"], last["home_away"], last["pts"]) == (
        "2022500525",
        "WCB",
        "BHM",
        "away",
        59,
    )


def test_player_game_log_preserves_zero_stats(official):
    data = _ok(_fn("get_nbastats_game_log")(season=2025, player=MAC))
    first = data["games"][0]
    assert (first["oreb"], first["plus_minus"], first["blk"]) == (0, 0, 0)


def test_player_game_log_by_id_skips_the_registry(official):
    data = _ok(_fn("get_nbastats_game_log")(season=2025, player=MAC))
    assert official.queries("commonallplayers") == []
    assert (data["player_id"], data["count"]) == (MAC, 3)


def test_league_wide_player_rows_use_verified_g_league_source(official):
    official.routes["leaguegamelog"] = lambda q: OFFICIAL["leaguegamelog_players"]
    data = _ok(_fn("get_nbastats_game_log")(season=2025, player_or_team="player", team="AUS"))
    assert official.queries("leaguegamelog")[0]["PlayerOrTeam"] == "P"
    assert data["player_or_team"] == "player"
    assert data["count"] == 1
    assert data["games"][0]["player_name"] == "Trey McGowens"
    assert data["games"][0]["opponent"] == "STO"
    assert data["games"][0]["fg3_pct"] is None
    assert "player_id" not in data


def test_unknown_player_is_an_error(official):
    assert "No G League player" in _err(_fn("get_nbastats_game_log")(season=2025, player="Nobody Here"))
    assert official.queries("playergamelog") == []


def test_empty_game_log_is_a_success(official):
    official.routes["leaguegamelog"] = lambda q: _with_table("leaguegamelog", "LeagueGameLog", rowSet=[])
    data = _ok(_fn("get_nbastats_game_log")(season=2025))
    assert (data["games"], data["count"]) == ([], 0)


def test_game_log_rows_from_another_league_are_an_error(official):
    rows = copy.deepcopy(OFFICIAL["leaguegamelog"]["resultSets"][0]["rowSet"])
    rows[0][4] = "0022500001"
    official.routes["leaguegamelog"] = lambda q: _with_table("leaguegamelog", "LeagueGameLog", rowSet=rows)
    assert "0022500001" in _err(_fn("get_nbastats_game_log")(season=2025))


# ── Seasons and phases ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("season", "expected"), [(2025, "2025-26"), ("2025", "2025-26"), ("2025-26", "2025-26"), (1999, "1999-00")]
)
def test_season_is_the_starting_year(official, season, expected):
    assert _ok(_fn("get_nbastats_game_log")(season=season))["season"] == expected
    assert official.queries("leaguegamelog")[0]["Season"] == expected


@pytest.mark.parametrize("season", ["2025-27", "2026-25", "1999-2000", "next", True, 2025.5, "../2025"])
def test_malformed_season_is_an_error_without_a_request(official, season):
    assert "season" in _err(_fn("get_nbastats_game_log")(season=season)).lower()
    assert official.calls == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("regular", "Regular Season"),
        ("2", "Regular Season"),
        ("playoffs", "Playoffs"),
        ("4", "Playoffs"),
        ("Pre Season", "Pre Season"),
    ],
)
def test_season_types_follow_nba(official, value, expected):
    assert _ok(_fn("get_nbastats_game_log")(season=2025, season_type=value))["season_type"] == expected
    assert official.queries("leaguegamelog")[0]["SeasonType"] == expected


@pytest.mark.parametrize("value", ["playin", "PlayIn", "play-in", "5", 5])
def test_play_in_is_not_a_g_league_phase(official, value):
    _err(_fn("get_nbastats_game_log")(season=2025, season_type=value))
    assert official.calls == []


@pytest.mark.parametrize("value", ["showcase", "Showcase Cup", "tournament"])
def test_showcase_stats_use_verified_api_enum(official, value):
    official.routes["leaguegamelog"] = lambda q: OFFICIAL["leaguegamelog_showcase"]
    data = _ok(_fn("get_nbastats_game_log")(season=2025, season_type=value))
    assert official.queries("leaguegamelog")[0]["SeasonType"] == "Showcase"
    assert data["season_type"] == "Showcase"
    assert data["games"][0]["game_id"] == "2052500009"


# ── Player career ─────────────────────────────────────────────


def test_player_career_is_regular_season_g_league_only(official):
    data = _ok(_fn("get_nbastats_player_career")(player="McClung", per_mode="per_game"))
    (query,) = official.queries("playercareerstats")
    assert (query["LeagueID"], query["PlayerID"], query["PerMode"]) == ("20", MAC, "PerGame")
    assert (data["provider"], data["league_id"], data["player_id"], data["player"], data["per_mode"]) == (
        "nba-stats",
        "20",
        MAC,
        "Mac McClung",
        "PerGame",
    )
    assert [(s["season_id"], s["team_abbreviation"], s["gp"]) for s in data["seasons"]] == [
        ("2021-22", "WCB", 1),
        ("2021-22", "SBL", 26),
        ("2021-22", "TOT", 27),
    ]
    assert {s["league_id"] for s in data["seasons"]} == {"20"}
    # Career regular-season totals, not the college (14.7) or Showcase (20.3) tables.
    assert (data["career_totals"]["gp"], data["career_totals"]["pts"]) == (144, 24.9)
    assert all("school_name" not in s for s in data["seasons"])
    assert data["count"] == 3


def test_player_career_by_id(official):
    data = _ok(_fn("get_nbastats_player_career")(player_id=MAC))
    assert official.queries("commonallplayers") == []
    assert official.queries("playercareerstats")[0]["PerMode"] == "Totals"
    assert data["player_id"] == MAC


def test_player_career_row_from_another_league_is_an_error(official):
    rows = copy.deepcopy(OFFICIAL["playercareerstats"]["resultSets"][0]["rowSet"])
    rows[1][2] = "00"
    official.routes["playercareerstats"] = lambda q: _with_table(
        "playercareerstats", "SeasonTotalsRegularSeason", rowSet=rows
    )
    _err(_fn("get_nbastats_player_career")(player_id=MAC))


def test_player_career_without_the_regular_season_table_is_an_error(official):
    # NBA's reader would silently fall back to the first table; here that is an error.
    official.routes["playercareerstats"] = lambda q: _with_table(
        "playercareerstats", "SeasonTotalsRegularSeason", name="Renamed"
    )
    assert "SeasonTotalsRegularSeason" in _err(_fn("get_nbastats_player_career")(player_id=MAC))


def test_player_career_with_no_games_is_an_empty_success(official):
    data = copy.deepcopy(OFFICIAL["playercareerstats"])
    for table in data["resultSets"]:
        table["rowSet"] = []
    official.routes["playercareerstats"] = lambda q: data
    result = _ok(_fn("get_nbastats_player_career")(player_id=MAC))
    assert (result["seasons"], result["career_totals"], result["count"]) == ([], None, 0)


@pytest.mark.parametrize("player_id", ["16306../44", "1630644?x", True, "abc"])
def test_malformed_player_id_is_an_error_without_a_request(official, player_id):
    _err(_fn("get_nbastats_player_career")(player_id=player_id))
    assert official.calls == []


# ── Team stats ─────────────────────────────────────────────


def _game_log_with_austin():
    """SYNTHETIC composition: the captured game log plus one row carrying the Austin Spurs'
    identity (team id, tricode, name) from the captured boxscoreadvancedv3; its stats are the
    captured STO row's."""
    data = copy.deepcopy(OFFICIAL["leaguegamelog"])
    row = list(data["resultSets"][0]["rowSet"][0])
    row[1:4] = [1612709890, "AUS", "Austin Spurs"]
    data["resultSets"][0]["rowSet"].append(row)
    return data


def test_team_stats_rows(official):
    data = _ok(_fn("get_nbastats_team_stats")(season=2025, per_mode="per_game"))
    (query,) = official.queries("leaguedashteamstats")
    assert (query["LeagueID"], query["MeasureType"], query["PerMode"], query["Season"]) == (
        "20",
        "Base",
        "PerGame",
        "2025-26",
    )
    # Abbreviations come from the same season's G League game log, never an NBA table.
    (log_query,) = official.queries("leaguegamelog")
    assert (log_query["LeagueID"], log_query["Season"], log_query["SeasonType"]) == ("20", "2025-26", "Regular Season")
    assert (data["provider"], data["league_id"], data["measure"], data["per_mode"], data["count"]) == (
        "nba-stats",
        "20",
        "Base",
        "PerGame",
        3,
    )
    austin = data["teams"][0]
    assert (austin["team_id"], austin["team_name"], austin["pts"], austin["gp_rank"]) == (
        1612709890,
        "Austin Spurs",
        112.1,
        1,
    )
    # The captured game-log excerpt has no Austin row, so its abbreviation is unknown.
    assert austin["team_abbreviation"] is None
    assert all("team_abbreviation_espn" not in row for row in data["teams"])


def test_team_stats_filter_by_g_league_abbreviation(official):
    official.routes["leaguegamelog"] = lambda q: _game_log_with_austin()
    data = _ok(_fn("get_nbastats_team_stats")(season=2025, team="aus"))
    assert data["team"] == "AUS"
    assert [(t["team_name"], t["team_abbreviation"]) for t in data["teams"]] == [("Austin Spurs", "AUS")]


@pytest.mark.parametrize("team", ["Austin Spurs", "austin spurs", "1612709890"])
def test_team_stats_filter_by_official_name_or_id(official, team):
    data = _ok(_fn("get_nbastats_team_stats")(season=2025, team=team))
    assert [t["team_name"] for t in data["teams"]] == ["Austin Spurs"]


def test_team_stats_never_maps_nba_abbreviations(official):
    official.routes["leaguegamelog"] = lambda q: _game_log_with_austin()
    data = _ok(_fn("get_nbastats_team_stats")(season=2025, team="SA"))
    assert (data["teams"], data["warnings"]) == ([], ["team 'SA' matched no rows"])


def test_team_stats_shaping(official):
    data = _ok(_fn("get_nbastats_team_stats")(season=2025, sort_by="pts", limit=1, fields="pts"))
    assert data["teams"] == [
        {"team_id": 1612709928, "team_name": "Capital City Go-Go", "team_abbreviation": None, "pts": 117.9}
    ]


def test_team_stats_game_log_failure_is_an_error(official):
    official.routes["leaguegamelog"] = lambda q: 500
    assert "HTTP 500" in _err(_fn("get_nbastats_team_stats")(season=2025))


# ── Shot chart ─────────────────────────────────────────────


@pytest.mark.parametrize("wrong_player", [999999, None])
def test_shot_chart_rejects_missing_or_mismatched_player(official, wrong_player):
    payload = copy.deepcopy(OFFICIAL["shotchartdetail"])
    table = payload["resultSets"][0]
    table["rowSet"][0][table["headers"].index("PLAYER_ID")] = wrong_player
    official.routes["shotchartdetail"] = lambda q: payload
    _err(_fn("get_nbastats_shot_chart")(player_id=MAC, season=2025, limit=1))


def test_shot_chart_rows(official):
    data = _ok(_fn("get_nbastats_shot_chart")(player="Mac McClung", season=2025))
    (query,) = official.queries("shotchartdetail")
    assert (query["LeagueID"], query["PlayerID"], query["Season"], query["SeasonType"]) == (
        "20",
        MAC,
        "2025-26",
        "Regular Season",
    )
    assert (data["provider"], data["league_id"], data["player_id"], data["count"]) == ("nba-stats", "20", MAC, 3)
    first = data["shots"][0]
    assert first == {
        "game_id": "2022500014",
        "game_date": "2025-12-20",
        "period": 1,
        "minutes_remaining": 9,
        "seconds_remaining": 8,
        "action_type": "Jump Shot",
        "shot_type": "3PT Field Goal",
        "shot_zone": "Above the Break 3",
        "shot_area": "Right Side Center(RC)",
        "shot_distance": 25,
        "loc_x": 110,
        "loc_y": 225,
        "made": True,
    }
    assert data["shots"][2]["made"] is False


def test_shot_chart_limit_flags_truncation(official):
    data = _ok(_fn("get_nbastats_shot_chart")(player_id=MAC, season=2025, limit=2))
    assert (data["count"], data["truncated"], data["total_rows"]) == (2, True, 3)


# ── Play-by-play v3 / advanced box score ─────────────────────────────────────────────


def test_stats_play_by_play_rows(official):
    data = _ok(_fn("get_nbastats_play_by_play")(game_id=STATS_GAME))
    (query,) = official.queries("playbyplayv3")
    assert query["GameID"] == STATS_GAME
    assert (data["provider"], data["league_id"], data["game_id"], data["count"]) == ("nba-stats", "20", STATS_GAME, 3)
    start, jump, miss = data["plays"]
    assert (start["team"], start["score_home"], start["loc_x"]) == (None, "0", 0)
    assert (jump["team"], jump["player"], jump["action_type"]) == ("AUS", "M. Potter", "Jump Ball")
    assert (miss["shot_value"], miss["loc_x"], miss["loc_y"], miss["sub_type"]) == (
        2,
        22,
        19,
        "Driving Reverse Layup Shot",
    )


def test_stats_play_by_play_limit(official):
    data = _ok(_fn("get_nbastats_play_by_play")(game_id=STATS_GAME, limit=1))
    assert (data["count"], data["truncated"]) == (1, True)


def test_stats_play_by_play_without_actions_is_empty(official):
    payload = copy.deepcopy(OFFICIAL["playbyplayv3"])
    payload["game"]["actions"] = []
    official.routes["playbyplayv3"] = lambda q: payload
    data = _ok(_fn("get_nbastats_play_by_play")(game_id=STATS_GAME))
    assert (data["plays"], data["count"]) == ([], 0)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["game"].update(gameId="2022500002"),
        lambda d: d.pop("game"),
        lambda d: d["game"].pop("actions"),
        lambda d: d["game"].update(actions={"0": {}}),
    ],
)
def test_stats_play_by_play_for_another_or_no_game_is_an_error(official, mutate):
    payload = copy.deepcopy(OFFICIAL["playbyplayv3"])
    mutate(payload)
    official.routes["playbyplayv3"] = lambda q: payload
    _err(_fn("get_nbastats_play_by_play")(game_id=STATS_GAME))


def test_advanced_boxscore(official):
    data = _ok(_fn("get_nbastats_advanced_boxscore")(game_id=STATS_GAME))
    assert official.queries("boxscoreadvancedv3")[0]["GameID"] == STATS_GAME
    assert (data["provider"], data["league_id"], data["game_id"]) == ("nba-stats", "20", STATS_GAME)
    home, away = data["home"], data["away"]
    assert (home["team_id"], home["team"], home["team_name"]) == ("1612709890", "AUS", "Austin Spurs")
    assert (away["team"], away["team_name"]) == ("STO", "Stockton Kings")
    assert "team_abbreviation_espn" not in home
    osifo, potter = home["players"]
    assert (potter["player_id"], potter["name"], potter["position"], potter["minutes"]) == (
        "1630695",
        "Micah Potter",
        "F",
        "30:37",
    )
    assert potter["stats"]["offensiveRating"] == 106.1
    assert osifo["stats"]["assistPercentage"] == 0.0
    assert home["stats"]["pace"] == 100.65


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["boxScoreAdvanced"].update(gameId="2022500002"),
        lambda d: d.pop("boxScoreAdvanced"),
        lambda d: d["boxScoreAdvanced"].pop("homeTeam"),
        lambda d: d["boxScoreAdvanced"]["awayTeam"].update(players=None),
    ],
)
def test_advanced_boxscore_for_another_or_no_game_is_an_error(official, mutate):
    payload = copy.deepcopy(OFFICIAL["boxscoreadvancedv3"])
    mutate(payload)
    official.routes["boxscoreadvancedv3"] = lambda q: payload
    _err(_fn("get_nbastats_advanced_boxscore")(game_id=STATS_GAME))


# ── Leaders ─────────────────────────────────────────────


def test_leaders_default_request_and_rows(official):
    data = _ok(_fn("get_nbastats_leaders")(season=2025))
    (query,) = official.queries("leagueleaders")
    assert (query["LeagueID"], query["PerMode"], query["StatCategory"], query["Season"], query["SeasonType"]) == (
        "20",
        "PerGame",
        "PTS",
        "2025-26",
        "Regular Season",
    )
    assert (data["provider"], data["league_id"], data["stat_category"], data["per_mode"], data["count"]) == (
        "nba-stats",
        "20",
        "PTS",
        "PerGame",
        3,
    )
    first = data["leaders"][0]
    assert (first["player_id"], first["rank"], first["player"], first["team"], first["pts"]) == (
        1630644,
        1,
        "Mac McClung",
        "WCB",
        31.8,
    )


def test_leaders_shaping(official):
    data = _ok(_fn("get_nbastats_leaders")(season=2025, stat_category="pts", sort_by="ast", limit=1, fields="ast"))
    assert data["leaders"] == [{"player_id": 1642443, "rank": 2, "player": "Jahmir Young", "team": "SXF", "ast": 8.9}]
    assert (data["total_rows"], data["returned_rows"]) == (3, 1)


def test_leaders_empty_table_is_a_success(official):
    payload = copy.deepcopy(OFFICIAL["leaders"])
    payload["resultSet"]["rowSet"] = []
    official.routes["leagueleaders"] = lambda q: payload
    data = _ok(_fn("get_nbastats_leaders")(season=2025))
    assert (data["leaders"], data["count"]) == ([], 0)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["resultSet"].update(name="Other"),
        lambda d: d.pop("resultSet"),
        lambda d: d["resultSet"].update(headers=None),
        lambda d: d["resultSet"].update(headers=[], rowSet=[[]]),
        lambda d: d["resultSet"].update(headers=["PLAYER_ID", "PLAYER_ID"], rowSet=[[1, 2]]),
        lambda d: d["resultSet"]["rowSet"][0].pop(),
    ],
)
def test_leaders_malformed_table_is_an_error(official, mutate):
    payload = copy.deepcopy(OFFICIAL["leaders"])
    mutate(payload)
    official.routes["leagueleaders"] = lambda q: payload
    _err(_fn("get_nbastats_leaders")(season=2025))


def test_leaders_unknown_stat_category_is_an_error_without_a_request(official):
    _err(_fn("get_nbastats_leaders")(stat_category="DUNKS"))
    assert official.calls == []


# ── Upstream failures ─────────────────────────────────────────────


@pytest.mark.parametrize("status", [403, 429, 500])
def test_stats_http_errors_are_reported(official, status):
    official.routes["leaguegamelog"] = lambda q: status
    assert f"HTTP {status}" in _err(_fn("get_nbastats_game_log")(season=2025))


def test_stats_timeout_is_reported_as_throttling(official):
    official.routes["leaguegamelog"] = lambda q: "timeout"
    assert "did not answer" in _err(_fn("get_nbastats_game_log")(season=2025))


def test_stats_invalid_json_is_an_error(official):
    official.routes["leaguegamelog"] = lambda q: b"<html>not json"
    assert "invalid JSON" in _err(_fn("get_nbastats_game_log")(season=2025))


@pytest.mark.parametrize(
    "payload",
    [
        {**OFFICIAL["leaguegamelog"], "parameters": {**OFFICIAL["leaguegamelog"]["parameters"], "LeagueID": "00"}},
        {k: v for k, v in OFFICIAL["leaguegamelog"].items() if k != "parameters"},
        {**OFFICIAL["leaguegamelog"], "resultSets": None},
        [],
        _with_table("leaguegamelog", "LeagueGameLog", headers="GAME_ID"),
        _with_table("leaguegamelog", "LeagueGameLog", rowSet=[[1, 2]]),
    ],
)
def test_stats_payload_for_another_league_or_malformed_is_an_error(official, payload):
    official.routes["leaguegamelog"] = lambda q: payload
    _err(_fn("get_nbastats_game_log")(season=2025))


@pytest.mark.parametrize(
    ("command", "kwargs"),
    [
        ("get_nbastats_play_by_play", {}),
        ("get_nbastats_advanced_boxscore", {}),
        ("get_live_boxscore", {}),
        ("get_live_playbyplay", {}),
    ],
)
@pytest.mark.parametrize("game_id", BAD_GAME_IDS)
def test_non_g_league_game_ids_fail_before_transport(official, command, kwargs, game_id):
    _err(_fn(command)(game_id=game_id, **kwargs))
    assert official.calls == []


# ── Live CDN ─────────────────────────────────────────────


def test_live_boxscore_from_the_g_league_cdn(official):
    data = _ok(_fn("get_live_boxscore")(game_id=CDN_GAME))
    ((url, kwargs),) = official.calls
    assert url == f"https://{CDN_HOST}/static/json/liveData/boxscore/boxscore_{CDN_GAME}.json"
    assert kwargs["headers"] == nba_cdn._CDN_HEADERS
    assert kwargs["max_retries"] == 0
    assert (data["provider"], data["league_id"]) == ("nba-cdn", "20")
    info = data["game_info"]
    assert (info["id"], info["status"], info["game_code"], info["period"]) == (CDN_GAME, "closed", "20251112/MNERAP", 4)
    home, away = data["teams"]
    assert (home["home_away"], home["team"], home["score"], home["period_scores"]) == (
        "home",
        {"id": "1612709920", "name": "Raptors 905", "abbreviation": "RAP"},
        "111",
        [36, 20, 24, 31],
    )
    assert (away["team"]["abbreviation"], away["score"]) == ("MNE", "75")
    lawson = home["players"][0]
    assert (lawson["name"], lawson["points"], lawson["minutes"], lawson["field_goals"], lawson["plus_minus"]) == (
        "A.J. Lawson",
        35,
        "30:07",
        "12-20",
        32.0,
    )
    # The CDN sends "0"/"1" strings; "0" must not read as true.
    assert (lawson["starter"], lawson["on_court"]) == (True, False)
    assert home["players"][1]["three_pointers"] == "0-1"


def test_live_playbyplay_most_recent_first(official):
    data = _ok(_fn("get_live_playbyplay")(game_id=CDN_GAME))
    assert official.urls == [f"https://{CDN_HOST}/static/json/liveData/playbyplay/playbyplay_{CDN_GAME}.json"]
    assert (data["provider"], data["league_id"], data["game_id"], data["order"]) == (
        "nba-cdn",
        "20",
        CDN_GAME,
        "most_recent_first",
    )
    assert [a["action_number"] for a in data["actions"]] == [7, 4, 2]
    miss = data["actions"][0]
    assert (miss["team_tricode"], miss["player_name"], miss["shot_result"], miss["scoring_play"]) == (
        "MNE",
        "J. Bridges",
        "Missed",
        False,
    )


def test_live_playbyplay_limit_and_scoring_only(official):
    assert [a["action_number"] for a in _ok(_fn("get_live_playbyplay")(game_id=CDN_GAME, limit=1))["actions"]] == [7]
    data = _ok(_fn("get_live_playbyplay")(game_id=CDN_GAME, scoring_only=True))
    assert (data["actions"], data["count"]) == ([], 0)


def test_live_playbyplay_rejects_a_bad_limit(official):
    _err(_fn("get_live_playbyplay")(game_id=CDN_GAME, limit=0))
    assert official.calls == []


@pytest.mark.parametrize("command", ["get_live_boxscore", "get_live_playbyplay"])
@pytest.mark.parametrize("status", [403, 429])
def test_live_refusal_propagates_without_a_fallback(official, command, status):
    official.routes["boxscore"] = official.routes["playbyplay"] = lambda q: status
    result = _fn(command)(game_id=CDN_GAME)
    _err(result)
    assert result["status_code"] == status
    assert len(official.calls) == 1  # no retry, no ESPN or NBA fallback


@pytest.mark.parametrize("command", ["get_live_boxscore", "get_live_playbyplay"])
def test_live_invalid_json_is_an_error(official, command):
    official.routes["boxscore"] = official.routes["playbyplay"] = lambda q: b"<html>"
    assert "invalid JSON" in _err(_fn(command)(game_id=CDN_GAME))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["game"].update(gameId="2052500035"),
        lambda d: d.pop("game"),
        lambda d: d.update(game={}),
        lambda d: d["game"].update(homeTeam=None),
        lambda d: d["game"]["awayTeam"].update(players="x"),
        lambda d: d["game"]["homeTeam"].update(periods=None),
        lambda d: d["game"]["homeTeam"]["players"][0].pop("statistics"),
        lambda d: d["game"]["homeTeam"]["players"][0].update(statistics={}),
        lambda d: d["game"]["homeTeam"]["players"][0]["statistics"].pop("points"),
        lambda d: d["game"]["homeTeam"]["players"][0].pop("personId"),
    ],
)
def test_live_boxscore_for_another_or_no_game_is_an_error(official, mutate):
    payload = copy.deepcopy(OFFICIAL[f"boxscore_{CDN_GAME}_gleague"])
    mutate(payload)
    official.routes["boxscore"] = lambda q: payload
    _err(_fn("get_live_boxscore")(game_id=CDN_GAME))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["game"].update(gameId="2052500035"),
        lambda d: d.pop("game"),
        lambda d: d["game"].update(actions=None),
    ],
)
def test_live_playbyplay_for_another_or_no_game_is_an_error(official, mutate):
    payload = copy.deepcopy(OFFICIAL[f"playbyplay_{CDN_GAME}_gleague"])
    mutate(payload)
    official.routes["playbyplay"] = lambda q: payload
    _err(_fn("get_live_playbyplay")(game_id=CDN_GAME))


# ── Cache isolation from the NBA ─────────────────────────────────────────────


def test_live_cache_is_separate_from_the_nba_cdn(official):
    _ok(_fn("get_live_boxscore")(game_id=CDN_GAME))
    _ok(_fn("get_live_boxscore")(game_id=CDN_GAME))
    assert len(official.calls) == 1  # second call served from cache
    assert _espn_base._cache_get(f"nba_cdn:boxscore:{CDN_GAME}") is None


def test_stats_cache_is_separate_from_the_nba_league(official):
    _ok(_fn("get_nbastats_game_log")(season=2025))
    nba_result = nba_stats.get_nbastats_game_log({"params": {"season": 2025}})
    # The NBA request (LeagueID 00) is not answered from the G League cache entry.
    assert nba_result.get("error") is True
    assert [q["LeagueID"] for q in official.queries("leaguegamelog")] == ["20", "00"]


# ── Docs and provenance ─────────────────────────────────────────────


def test_discovery_docs_describe_the_official_sources():
    skill = (ROOT / "skills" / "gleague-data" / "SKILL.md").read_text()
    reference = (ROOT / "skills" / "gleague-data" / "references" / "api-reference.md").read_text()
    catalog = json.loads((ROOT / "skills" / "catalog.json").read_text())["skills"]["gleague-data"]["description"]
    for command in [*NBA_SHAPED, "get_nbastats_leaders"]:
        assert f"`{command}`" in skill, command
        assert f"### {command}" in reference, command
    for text in (skill, reference, catalog):
        assert "NBA Stats" in text and "cdn-gleague.nba.com" in text
        assert "no G League equivalent" not in text
        assert "No parity with the NBA live CDN or NBA Stats" not in text
    assert "~~`get_live_scoreboard`~~" in skill


def test_official_fixture_provenance_names_the_public_sources():
    provenance = (OFFICIAL_DIR / "PROVENANCE.md").read_text()
    for name in OFFICIAL:
        assert f"{name}.json" in provenance, name
    assert "sportsdataverse/hoopR" in provenance
    assert f"https://{CDN_HOST}/static/json/liveData/boxscore/boxscore_{CDN_GAME}.json" in provenance

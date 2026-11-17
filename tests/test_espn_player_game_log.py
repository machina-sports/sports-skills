"""Player game logs for WNBA, CFB, CBB and NBA from ESPN's athlete gamelog (issue 241).

Fixtures are ESPN's responses (links and logos stripped) for Jonquel Jones'
2025 WNBA season, C.J. Stroud's 2022 Ohio State season, Cooper Flagg's
2024-25 Duke season, and Dyson Daniels' (play-in) and Anthony Edwards'
(playoffs) 2024-25 NBA seasons.
"""

import json
from pathlib import Path

import pytest

from sports_skills import _espn_base, cbb, cfb, nba, wnba
from sports_skills.cli import _REGISTRY

FIXTURES = Path(__file__).parent / "fixtures" / "espn_gamelog"


@pytest.fixture
def espn(monkeypatch):
    """Serve one fixture (or an error) and record the URLs requested."""
    calls = []
    state = {"payload": None, "error": None}

    def fetch(url, **kwargs):
        calls.append(url)
        if state["error"]:
            return None, state["error"]
        return state["payload"], None

    def serve(name=None, payload=None, error=None):
        if name:
            payload = (FIXTURES / f"{name}.json").read_bytes()
        state["payload"] = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        state["error"] = error

    monkeypatch.setattr(_espn_base, "_http_fetch", fetch)
    monkeypatch.setattr(_espn_base, "_cache", {})
    serve.calls = calls
    return serve


def test_wnba_regular_season_rows_oldest_first(espn):
    espn("wnba_2999101_2025")
    result = wnba.get_player_game_log(player_id="2999101", season=2025)

    assert espn.calls == [
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/2999101/gamelog?season=2025"
    ]
    data = result["data"]
    assert (data["player_id"], data["season"], data["season_type"], data["count"]) == ("2999101", 2025, "regular", 31)
    dates = [g["game_date"] for g in data["games"]]
    assert dates == sorted(dates)
    first = data["games"][0]
    assert {k: v for k, v in first.items() if k != "stats"} == {
        "game_id": "401736116",
        "game_date": "2025-05-17T17:00:00.000+00:00",
        "team_abbreviation": "NY",
        "opponent": "LV",
        "opponent_id": "17",
        "opponent_name": "Las Vegas Aces",
        "home_away": "home",
        "result": "W",
        "team_score": "92",
        "opponent_score": "78",
        "season_type": "regular",
        "note": "",
    }
    assert (first["stats"]["minutes"], first["stats"]["points"], first["stats"]["totalRebounds"]) == ("30", "17", "10")
    assert "warnings" not in data


def test_cfb_postseason_row_is_from_the_players_side(espn):
    espn("cfb_4432577_2022")
    data = cfb.get_player_game_log(player_id="4432577", season=2022, season_type="all")["data"]

    assert data["count"] == 13
    bowl = data["games"][-1]
    # Ohio State were the away side; ESPN's `score` is winner-first ("42-41").
    assert (bowl["opponent"], bowl["home_away"], bowl["result"]) == ("UGA", "away", "L")
    assert (bowl["team_score"], bowl["opponent_score"]) == ("41", "42")
    assert bowl["season_type"] == "postseason"
    assert bowl["note"] == "CFP Semifinal at the Chick-fil-A Peach Bowl"
    # Passing and rushing both have a YDS column; stat names keep them apart.
    assert (bowl["stats"]["passingYards"], bowl["stats"]["rushingYards"]) == ("348", "34")


def test_cfb_season_type_filters(espn):
    espn("cfb_4432577_2022")
    regular = cfb.get_player_game_log(player_id="4432577", season=2022)["data"]
    post = cfb.get_player_game_log(player_id="4432577", season=2022, season_type="postseason")["data"]
    assert (regular["count"], post["count"]) == (12, 1)
    assert {g["season_type"] for g in regular["games"]} == {"regular"}


def test_cbb_season_names_and_home_side(espn):
    espn("cbb_5041939_2025")
    data = cbb.get_player_game_log(player_id="5041939", season=2025, season_type="all")["data"]

    # "2024-25 Season" is the regular season, "2024-25 Postseason" the tournament.
    assert [g["season_type"] for g in data["games"]].count("regular") == 32
    assert [g["season_type"] for g in data["games"]].count("postseason") == 5
    final_four = data["games"][-1]
    assert (final_four["opponent"], final_four["home_away"], final_four["result"]) == ("HOU", "home", "L")
    assert (final_four["team_score"], final_four["opponent_score"]) == ("67", "70")


def test_shaping_sorts_limits_and_keeps_identity(espn):
    espn("cbb_5041939_2025")
    data = cbb.get_player_game_log(
        player_id="5041939", season=2025, season_type="postseason", sort_by="points", limit=2, fields="points"
    )["data"]

    assert (data["total_rows"], data["returned_rows"], data["count"]) == (5, 2, 2)
    assert [g["stats"] for g in data["games"]] == [{"points": "30"}, {"points": "27"}]
    assert set(data["games"][0]) == {"game_id", "game_date", "team_abbreviation", "opponent", "stats"}


def test_default_season_reads_espns_season(espn):
    espn("wnba_2999101_2025")
    data = wnba.get_player_game_log(player_id="2999101")["data"]
    assert espn.calls == [
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/2999101/gamelog"
    ]
    assert data["season"] == "2025"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"player_id": ""}, "player_id is required"),
        ({"player_id": "abc"}, "player_id is required"),
        ({"player_id": "2999101", "season": "next"}, "Invalid season 'next'"),
        ({"player_id": "2999101", "season_type": "playoffs"}, "Invalid season_type 'playoffs'"),
    ],
)
def test_invalid_arguments_are_text_errors_without_a_request(espn, kwargs, message):
    result = wnba.get_player_game_log(**kwargs)
    assert result["status"] is False and message in result["message"]
    assert espn.calls == []


def test_unknown_player_and_unknown_field_are_text_errors(espn):
    espn(error={"error": True, "status_code": 404, "message": "HTTP 404"})
    result = wnba.get_player_game_log(player_id="999999999")
    assert result["status"] is False
    assert result["message"] == "ESPN has no player 999999999 here. Get ids from get_team_roster."

    espn("cfb_4432577_2022")
    result = cfb.get_player_game_log(player_id="4432577", season=2022, fields="bogus")
    assert result["status"] is False and "Unknown fields 'bogus'" in result["message"]


def test_season_with_no_games_warns(espn):
    espn(payload={"filters": [{"name": "league", "value": "wnba"}]})
    data = wnba.get_player_game_log(player_id="2999101", season=1990)["data"]
    assert (data["games"], data["count"]) == ([], 0)
    assert data["warnings"] == ["no regular games for player 2999101 in this season"]


@pytest.mark.parametrize("league", ["wnba", "cfb", "cbb", "nba"])
def test_cli_registers_the_command(league):
    assert _REGISTRY[league]["get_player_game_log"] == {
        "required": ["player_id"],
        "optional": ["season", "season_type", "sort_by", "descending", "limit", "fields"],
    }


def test_nba_reads_espn_by_espn_id_not_stats_nba_com(espn):
    espn("nba_4594268_2025")
    data = nba.get_player_game_log(player_id="4594268", season=2025, season_type="postseason")["data"]

    assert espn.calls == [
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/4594268/gamelog?season=2025"
    ]
    assert (data["season"], data["count"]) == (2025, 15)
    assert {g["season_type"] for g in data["games"]} == {"postseason"}
    dates = [g["game_date"] for g in data["games"]]
    assert dates == sorted(dates)
    assert set(data["games"][0]["stats"]) >= {"minutes", "points", "totalRebounds", "assists"}


def test_nba_play_in_is_its_own_season_type(espn):
    espn("nba_4869342_2025")
    regular = nba.get_player_game_log(player_id="4869342", season=2025)["data"]
    play_in = nba.get_player_game_log(player_id="4869342", season=2025, season_type="playin")["data"]
    every = nba.get_player_game_log(player_id="4869342", season=2025, season_type="all")["data"]

    # ESPN names the group "2024-25 Play In Regular Season"; it must not count as regular season.
    assert (regular["count"], play_in["count"]) == (76, 2)
    assert {g["season_type"] for g in regular["games"]} == {"regular"}
    assert {g["season_type"] for g in play_in["games"]} == {"playin"}
    assert sorted({g["season_type"] for g in every["games"]}) == ["playin", "preseason", "regular"]
    assert every["count"] == 76 + 2 + 4


def test_nba_newest_first_shaping(espn):
    espn("nba_4869342_2025")
    data = nba.get_player_game_log(
        player_id="4869342", season=2025, season_type="all", sort_by="game_date", descending=True, limit=3
    )["data"]
    assert (data["total_rows"], data["returned_rows"]) == (82, 3)
    assert [g["season_type"] for g in data["games"]] == ["playin", "playin", "regular"]

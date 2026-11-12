"""ESPN team schedules can include postseason games (NBA playoffs, bowls, NCAA tournament)."""

import importlib

import pytest

from sports_skills import _espn_base, cbb, cfb, nba, wnba


def _event(event_id, date, season_type):
    return {
        "id": event_id,
        "date": date,
        "name": f"game {event_id}",
        "seasonType": {"id": season_type},
        "competitions": [{"competitors": [], "status": {"type": {}}}],
    }


_BY_TYPE = {
    None: [_event("1", "2025-11-01T00:00Z", "2")],
    "2": [_event("1", "2025-11-01T00:00Z", "2")],
    "3": [_event("3", "2026-01-01T00:00Z", "3")],
    "5": [_event("5", "2025-12-15T00:00Z", "5")],
}


@pytest.fixture
def fake_espn(monkeypatch):
    calls = []

    def fake_request(sport_path, resource="scoreboard", params=None, max_retries=3):
        calls.append((sport_path, resource, params))
        code = (params or {}).get("seasontype")
        return {"team": {"id": "9", "displayName": "Team"}, "events": list(_BY_TYPE[code])}

    monkeypatch.setattr(_espn_base, "espn_request", fake_request)
    return calls


def _ids(result):
    assert result["status"] is True, result
    return [e["id"] for e in result["data"]["events"]]


@pytest.mark.parametrize("module", [nba, wnba, cfb, cbb])
def test_default_request_is_unchanged(fake_espn, module):
    assert _ids(module.get_team_schedule(team_id="9", season=2025)) == ["1"]
    assert fake_espn[-1][2] == {"season": 2025}


@pytest.mark.parametrize("module", [nba, wnba, cfb, cbb])
@pytest.mark.parametrize("value", ["postseason", "playoffs", "3", 3])
def test_postseason_sends_seasontype_3(fake_espn, module, value):
    assert _ids(module.get_team_schedule(team_id="9", season=2025, season_type=value)) == ["3"]
    assert fake_espn[-1][2] == {"season": 2025, "seasontype": "3"}


@pytest.mark.parametrize("module", [wnba, cfb, cbb])
def test_all_merges_regular_and_postseason(fake_espn, module):
    result = module.get_team_schedule(team_id="9", season=2025, season_type="all")
    assert _ids(result) == ["1", "3"]
    assert result["data"]["count"] == 2


def test_nba_all_includes_play_in_in_date_order(fake_espn):
    result = nba.get_team_schedule(team_id="9", season=2025, season_type="all")
    assert _ids(result) == ["1", "5", "3"]


def test_unknown_season_type_is_an_error(fake_espn):
    result = nba.get_team_schedule(team_id="9", season_type="bogus")
    assert result["status"] is False
    assert "season_type" in result["message"]
    assert fake_espn == []


# teams/{id}/schedule sends each competitor's score as an object, the
# scoreboard as a string (#151).
def _schedule_event(home_score, away_score):
    return {
        "id": "401772971",
        "date": "2025-09-07T17:00Z",
        "name": "Las Vegas Raiders at New England Patriots",
        "competitions": [
            {
                "date": "2025-09-07T17:00Z",
                "status": {"type": {"name": "STATUS_FINAL", "shortDetail": "Final"}},
                "competitors": [
                    {"homeAway": "home", "team": {"id": "17"}, "score": home_score, "winner": False},
                    {"homeAway": "away", "team": {"id": "13"}, "score": away_score, "winner": True},
                ],
            }
        ],
    }


_ESPN_LEAGUES = ["nfl", "nba", "wnba", "mlb", "nhl", "cfb", "cbb"]


@pytest.mark.parametrize("league", _ESPN_LEAGUES)
def test_schedule_score_object_is_unwrapped_to_string(league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    event = _schedule_event(
        {"value": 13.0, "displayValue": "13"},
        {"value": 20.0, "displayValue": "20"},
    )
    scores = [c["score"] for c in connector._normalize_event(event)["competitors"]]
    assert scores == ["13", "20"]


@pytest.mark.parametrize("league", _ESPN_LEAGUES)
def test_scoreboard_score_string_is_unchanged(league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    scores = [c["score"] for c in connector._normalize_event(_schedule_event("13", "20"))["competitors"]]
    assert scores == ["13", "20"]


# Each row says which part of the season it is from (#159): team schedules
# carry ``seasonType``, scoreboards ``season.type``.
@pytest.mark.parametrize("league", _ESPN_LEAGUES)
@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"seasonType": {"id": "1"}}, "preseason"),
        ({"seasonType": {"id": "2"}}, "regular"),
        ({"seasonType": {"id": "3"}}, "postseason"),
        ({"seasonType": {"id": "5"}}, "playin"),
        ({"season": {"year": 2025, "type": 3}}, "postseason"),
        ({}, ""),
    ],
)
def test_rows_carry_season_type(league, event, expected):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    row = connector._normalize_event({**_schedule_event("13", "20"), **event})
    assert row["season_type"] == expected


@pytest.mark.parametrize("event", [{"seasonType": "2"}, {"season": 2025}, {"seasonType": None, "season": None}])
def test_season_type_tolerates_non_dict_values(event):
    from sports_skills._espn_base import event_season_type

    assert event_season_type(event) in ("regular", "")


# teams/{id}/schedule also shapes broadcasts and records unlike the scoreboard:
# ``broadcasts[].media.shortName`` instead of ``names``, and ``record`` (a list
# of ``{type, displayValue}``) instead of ``records[].summary``.
def _with(competitor_extra, comp_extra):
    event = _schedule_event("13", "20")
    comp = event["competitions"][0]
    comp.update(comp_extra)
    for c in comp["competitors"]:
        c.update(competitor_extra)
    return event


@pytest.mark.parametrize("league", _ESPN_LEAGUES)
def test_schedule_broadcasts_and_record_are_read(league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    event = _with(
        {"record": [{"type": "total", "displayValue": "1-0"}, {"type": "vsconf", "displayValue": "1-0"}]},
        {"broadcasts": [{"type": {"shortName": "TV"}, "media": {"shortName": "ESPN"}}]},
    )
    row = connector._normalize_event(event)
    assert row["broadcasts"] == ["ESPN"]
    assert [c["record"] for c in row["competitors"]] == ["1-0", "1-0"]


@pytest.mark.parametrize("league", _ESPN_LEAGUES)
def test_scoreboard_broadcasts_and_records_are_unchanged(league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    event = _with({"records": [{"type": "total", "summary": "9-3"}]}, {"broadcasts": [{"names": ["MNMT"]}]})
    row = connector._normalize_event(event)
    assert row["broadcasts"] == ["MNMT"]
    assert [c["record"] for c in row["competitors"]] == ["9-3", "9-3"]


@pytest.mark.parametrize("league", _ESPN_LEAGUES)
def test_no_broadcasts_or_records(league):
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    row = connector._normalize_event(_schedule_event("13", "20"))
    assert row["broadcasts"] == []
    assert [c["record"] for c in row["competitors"]] == ["", ""]

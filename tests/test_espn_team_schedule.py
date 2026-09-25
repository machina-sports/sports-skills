"""ESPN team schedules can include postseason games (NBA playoffs, bowls, NCAA tournament)."""

import pytest

from sports_skills import _espn_base, cbb, cfb, nba


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


@pytest.mark.parametrize("module", [nba, cfb, cbb])
def test_default_request_is_unchanged(fake_espn, module):
    assert _ids(module.get_team_schedule(team_id="9", season=2025)) == ["1"]
    assert fake_espn[-1][2] == {"season": 2025}


@pytest.mark.parametrize("module", [nba, cfb, cbb])
@pytest.mark.parametrize("value", ["postseason", "playoffs", "3", 3])
def test_postseason_sends_seasontype_3(fake_espn, module, value):
    assert _ids(module.get_team_schedule(team_id="9", season=2025, season_type=value)) == ["3"]
    assert fake_espn[-1][2] == {"season": 2025, "seasontype": "3"}


@pytest.mark.parametrize("module", [cfb, cbb])
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

"""Fields ESPN moved: logos, summary records, scoreboard season, leader rank, rankings envelope (2026-11-16)."""

import pytest

from sports_skills import _espn_base
from sports_skills.cbb import _connector as cbb
from sports_skills.cfb import _connector as cfb
from sports_skills.mlb import _connector as mlb
from sports_skills.nba import _connector as nba
from sports_skills.nfl import _connector as nfl
from sports_skills.nhl import _connector as nhl
from sports_skills.wnba import _connector as wnba

LOGOS = {
    "id": "6",
    "displayName": "Dallas Cowboys",
    "logos": [{"href": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png"}],
}


def test_team_logo_reads_logo_or_logos():
    assert _espn_base.team_logo({"logo": "https://x/a.png"}) == "https://x/a.png"
    assert _espn_base.team_logo(LOGOS) == "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png"
    assert _espn_base.team_logo({}) == ""


@pytest.mark.parametrize("connector", [nfl, nba, wnba, nhl, mlb, cfb, cbb])
def test_summary_competitor_has_logo_and_record_string(connector):
    """The summary header's team has ``logos`` (no ``logo``) and ``record`` is a list."""
    competitor = {
        "id": "6",
        "homeAway": "home",
        "team": LOGOS,
        "score": "20",
        "record": [{"type": "total", "summary": "11-3"}, {"type": "home", "summary": "6-1"}],
    }
    summary = {"header": {"id": "1", "competitions": [{"competitors": [competitor], "status": {"type": {}}}]}}
    result = connector._normalize_game_summary(summary)
    (row,) = result["competitors"] if "competitors" in result else result["header"]["competitors"]
    assert row["team"]["logo"] == LOGOS["logos"][0]["href"]
    assert row["record"] == "11-3"


@pytest.mark.parametrize("connector", [nfl, nba, wnba, nhl, mlb, cfb, cbb])
def test_schedule_event_competitor_has_logo(connector):
    event = {
        "id": "1",
        "competitions": [{"competitors": [{"id": "6", "homeAway": "home", "team": LOGOS}], "status": {"type": {}}}],
    }
    (row,) = connector._normalize_event(event)["competitors"]
    assert row["team"]["logo"] == LOGOS["logos"][0]["href"]


def test_scoreboard_season_for_an_explicit_date():
    """With ``dates`` ESPN sends no top-level season; it is in leagues[0].season."""
    data = {"leagues": [{"season": {"year": 2026, "type": {"id": "2", "type": 2, "name": "Regular Season"}}}]}
    assert _espn_base.scoreboard_season(data) == {"year": 2026, "type": 2}
    assert _espn_base.scoreboard_season({"season": {"year": 2026, "type": 2}}) == {"year": 2026, "type": 2}
    assert _espn_base.scoreboard_season({}) == {"year": "", "type": ""}


@pytest.mark.parametrize(("connector", "date"), [(cfb, "2026-11-14"), (cbb, "2026-11-14")])
def test_dated_college_scoreboard_reports_its_season(monkeypatch, connector, date):
    data = {"events": [], "leagues": [{"season": {"year": 2026, "type": {"type": 2}}}]}
    monkeypatch.setattr(connector, "espn_request", lambda *a, **k: data)
    params = {"date": date} if connector is cbb else {"season": 2026, "week": 12}
    result = (
        connector.get_scoreboard({"params": params}) if connector is cbb else connector.get_schedule({"params": params})
    )
    assert result["season"] == {"year": 2026, "type": 2}


@pytest.mark.parametrize("connector", [nhl, wnba, nba, mlb])
def test_dated_schedule_reports_its_day(monkeypatch, connector):
    """ESPN leaves out ``day`` for an explicit date."""
    monkeypatch.setattr(connector, "espn_request", lambda *a, **k: {"events": []})
    assert connector.get_schedule({"params": {"date": "2026-11-15"}})["day"] == "2026-11-15"


def test_leader_rank_is_the_list_position():
    """ESPN's core leader entries have no ``rank``; the list is in rank order."""
    categories = [
        {
            "displayName": "Points",
            "leaders": [
                {"athlete": {"id": "1", "displayName": "First"}, "value": 30.0},
                {"athlete": {"id": "2", "displayName": "Second"}, "value": 28.0},
            ],
        }
    ]
    (category,) = _espn_base._resolve_leaders(categories)
    assert [row["rank"] for row in category["leaders"]] == [1, 2]


@pytest.mark.parametrize("connector", [cfb, cbb])
def test_current_rankings_report_season_and_week(monkeypatch, connector):
    """Without arguments ESPN sends latestSeason/latestWeek, not season/week."""
    data = {"rankings": [], "latestSeason": {"year": 2026}, "latestWeek": {"number": 12}}
    monkeypatch.setattr(connector, "espn_request", lambda *a, **k: data)
    result = connector.get_rankings({"params": {}})
    assert (result["season"], result["week"]) == (2026, 12)

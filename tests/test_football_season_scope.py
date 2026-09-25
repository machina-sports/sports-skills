"""football: season-scoped commands must not answer with another season's data."""

from sports_skills.football import _connector as fc


def _espn_event(event_id, date, season_year):
    return {
        "id": event_id,
        "date": date,
        "season": {"year": season_year},
        "competitions": [{"competitors": [], "status": {"type": {}}}],
    }


def _fake_schedule(monkeypatch):
    """ESPN eng.1 Arsenal (359) as observed 2026-09: fixture=true ignores `season`."""

    def fake(league_slug, resource="scoreboard", params=None, max_retries=3):
        params = params or {}
        if params.get("fixture") == "true":
            return {
                "requestedSeason": {"year": 2026},
                "events": [_espn_event("f1", "2027-05-30T15:00Z", 2026)],
            }
        year = int(params.get("season", 2026))
        return {
            "requestedSeason": {"year": year},
            "events": [_espn_event(f"r{year}", f"{year}-08-17T15:00Z", year)],
        }

    monkeypatch.setattr(fc, "_espn_request", fake)


def test_past_season_schedule_excludes_current_fixtures(monkeypatch):
    _fake_schedule(monkeypatch)
    result = fc.get_team_schedule(
        {"params": {"team_id": "359", "league_slug": "premier-league", "season_year": 2024}}
    )
    assert [e["id"] for e in result["events"]] == ["r2024"]


def test_current_season_schedule_keeps_fixtures(monkeypatch):
    _fake_schedule(monkeypatch)
    result = fc.get_team_schedule(
        {"params": {"team_id": "359", "league_slug": "premier-league", "season_year": 2026}}
    )
    assert [e["id"] for e in result["events"]] == ["r2026", "f1"]
    # Without season_year, behaviour is unchanged (results + fixtures).
    result = fc.get_team_schedule({"params": {"team_id": "359", "league_slug": "premier-league"}})
    assert [e["id"] for e in result["events"]] == ["r2026", "f1"]


def _bootstrap():
    return {
        "events": [{"deadline_time": "2026-08-21T17:30:00Z"}],
        "teams": [{"id": 1, "code": 3, "name": "Arsenal", "short_name": "ARS"}],
        "elements": [
            {"id": 7, "code": 7, "first_name": "Bukayo", "second_name": "Saka", "team": 1,
             "goals_scored": 4, "assists": 2, "starts": 5, "element_type": 3},
        ],
    }


def test_season_leaders_refuse_a_season_fpl_does_not_have(monkeypatch):
    monkeypatch.setattr(fc, "_get_fpl_bootstrap", _bootstrap)
    result = fc.get_season_leaders({"params": {"season_id": "premier-league-2024"}})
    assert result["leaders"] == []
    assert "premier-league-2026" in result["message"]
    assert "premier-league-2024" in result["message"]


def test_season_leaders_for_current_season(monkeypatch):
    monkeypatch.setattr(fc, "_get_fpl_bootstrap", _bootstrap)
    result = fc.get_season_leaders({"params": {"season_id": "premier-league-2026"}})
    assert result["leaders"][0]["goals"] == 4

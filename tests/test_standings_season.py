"""ESPN standings say which season they describe, and skip an unstarted one (#153)."""

import importlib

import pytest

from sports_skills import _espn_base

_LEAGUES = ["nba", "nfl", "mlb", "nhl", "wnba", "cfb", "cbb"]

# 2026-09-25, between the NBA's 2025-26 and 2026-27 seasons.
OFFSEASON = 1790294400


def _season(year, reg_start, reg_end):
    """An ESPN ``seasons[]`` entry with preseason and regular-season dates."""
    return {
        "year": year,
        "types": [
            {"id": "1", "startDate": "2026-09-30T07:00Z", "endDate": reg_start},
            {"id": "2", "startDate": reg_start, "endDate": reg_end},
        ],
    }


def _payload(year, season_type, wins, losses, seasons=None, envelope_year=None):
    """An ESPN standings payload with one table of two teams."""
    stats = [{"name": "wins", "value": wins, "displayValue": str(wins)}]
    stats += [{"name": "losses", "value": losses, "displayValue": str(losses)}]
    return {
        "season": {"year": envelope_year or year},
        "seasons": seasons or [],
        "children": [
            {
                "name": "Eastern Conference",
                "standings": {
                    "season": year,
                    "seasonType": season_type,
                    "entries": [
                        {"team": {"id": str(i), "abbreviation": f"T{i}"}, "stats": stats} for i in (1, 2)
                    ],
                },
            }
        ],
    }


UPCOMING = _payload(2027, 2, 0, 0, [_season(2027, "2026-10-20T07:00Z", "2027-04-12T06:59Z")])
FINISHED = _payload(2026, 2, 60, 22, [_season(2026, "2025-10-21T07:00Z", "2026-04-13T06:59Z")])


def _serve(monkeypatch, league, by_season):
    """Serve payloads by requested season (None = ESPN's default); record the params."""
    connector = importlib.import_module(f"sports_skills.{league}._connector")
    calls = []

    def fake_web_request(sport_path, resource, params=None, **kwargs):
        calls.append(params)
        if (params or {}).get("level") == 3:
            return {"children": []}
        return by_season[(params or {}).get("season")]

    monkeypatch.setattr(connector, "espn_web_request", fake_web_request)
    monkeypatch.setattr(_espn_base, "_now", lambda: OFFSEASON)
    return connector, calls


@pytest.mark.parametrize("league", _LEAGUES)
def test_unstarted_default_season_falls_back_to_the_last_one(monkeypatch, league):
    connector, calls = _serve(monkeypatch, league, {None: UPCOMING, 2026: FINISHED})
    result = connector.get_standings({"params": {}})
    assert result["groups"][0]["entries"][0]["wins"] == "60"
    assert result["season"] == 2026
    assert result["season_type"] == "regular"
    assert result["season_status"] == "complete"
    assert result["defaulted_from"] == 2027
    assert "season=2027" in result["note"]
    assert calls[:2] == [None, {"season": 2026}]
    # The division request (pro leagues) asks for the season that was returned.
    assert all(c == {"season": 2026, "level": 3} for c in calls[2:])


@pytest.mark.parametrize("league", ["nba", "nhl"])
def test_explicit_season_is_never_replaced(monkeypatch, league):
    connector, calls = _serve(monkeypatch, league, {2027: UPCOMING})
    result = connector.get_standings({"params": {"season": 2027}})
    assert result["season"] == 2027
    assert result["season_status"] == "not_started"
    assert "defaulted_from" not in result
    assert calls[0] == {"season": 2027}


def test_preseason_table_falls_back(monkeypatch):
    """NHL on 2026-09-25: preseason records under a started-looking season."""
    preseason = _payload(2027, 1, 3, 0, [_season(2027, "2026-09-28T07:00Z", "2027-04-11T06:59Z")])
    connector, _ = _serve(monkeypatch, "nhl", {None: preseason, 2026: FINISHED})
    result = connector.get_standings({"params": {}})
    assert (result["season"], result["defaulted_from"]) == (2026, 2027)


def test_zero_table_after_the_start_date_falls_back(monkeypatch):
    """ESPN's start date has passed but no team has a win or a loss yet."""
    started = _payload(2027, 2, 0, 0, [_season(2027, "2026-09-20T07:00Z", "2027-04-11T06:59Z")])
    connector, _ = _serve(monkeypatch, "nhl", {None: started, 2026: FINISHED})
    assert connector.get_standings({"params": {}})["defaulted_from"] == 2027


def test_season_in_progress_is_unchanged(monkeypatch):
    playing = _payload(2026, 2, 3, 0, [_season(2026, "2026-09-10T07:00Z", "2027-01-05T07:59Z")])
    connector, calls = _serve(monkeypatch, "nfl", {None: playing})
    result = connector.get_standings({"params": {}})
    assert (result["season"], result["season_type"], result["season_status"]) == (2026, "regular", "in_progress")
    assert "defaulted_from" not in result
    assert calls[0] is None


def test_season_is_the_tables_not_the_envelopes(monkeypatch):
    """MLB in the offseason: the envelope says 2027 over the finished 2026 tables."""
    mlb = _payload(2026, 2, 93, 68, [_season(2026, "2026-03-26T07:00Z", "2026-09-21T06:59Z")], envelope_year=2027)
    connector, calls = _serve(monkeypatch, "mlb", {None: mlb})
    result = connector.get_standings({"params": {}})
    assert (result["season"], result["season_status"]) == (2026, "complete")
    assert "defaulted_from" not in result


def test_failed_fallback_keeps_the_default_table(monkeypatch):
    connector, _ = _serve(monkeypatch, "nba", {None: UPCOMING, 2026: {"error": True, "message": "HTTP 503"}})
    result = connector.get_standings({"params": {}})
    assert result["season"] == 2027
    assert result["season_status"] == "not_started"
    assert "defaulted_from" not in result


def test_no_dates_means_no_status():
    assert _espn_base.standings_season(_payload(2026, 2, 1, 1))["season_status"] == ""


def test_fallback_is_dropped_when_espn_ignores_the_prior_season(monkeypatch):
    """A 'prior' load that is the same upcoming table is not a fallback."""
    connector, _ = _serve(monkeypatch, "nba", {None: UPCOMING, 2026: UPCOMING})
    result = connector.get_standings({"params": {}})
    assert result["season"] == 2027
    assert "defaulted_from" not in result


def test_group_filtered_college_table_with_overall_records(monkeypatch):
    """cfb group=: the root is the conference table, and rows have no ``losses`` stat."""
    stats = [{"name": "wins", "value": 0}, {"name": "overall", "displayValue": "0-0"}]
    root = {
        "season": {"year": 2027},
        "standings": {"season": 2027, "seasonType": 2, "entries": [{"team": {"id": "1"}, "stats": stats}]},
    }
    prior = {
        "standings": {
            "season": 2026,
            "seasonType": 2,
            "entries": [{"team": {"id": "1"}, "stats": [{"name": "overall", "displayValue": "12-2"}]}],
        }
    }
    calls = []

    def load(year):
        calls.append(year)
        return prior

    data, defaulted_from = _espn_base.default_standings_season(root, None, load)
    assert (data, defaulted_from, calls) == (prior, 2027, [2026])


def test_malformed_payloads_do_not_raise():
    assert _espn_base.standings_season({"children": [None, {"standings": {"entries": [{"stats": None}]}}]})
    assert _espn_base._no_games_played({"children": [None, {"standings": {"entries": [None, {"stats": None}]}}]}) is False

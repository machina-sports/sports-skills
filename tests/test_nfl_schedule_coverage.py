"""NFL schedules say what they cover and never claim a complete season.

``get_schedule(season=...)`` alone sent ``dates=<year>`` to the scoreboard and
got ~100 events from mixed seasons. Season-only is refused (like NBA/NHL/MLB);
season+week keeps ESPN's week query; no params is ESPN's current window. Every
schedule reports an additive ``coverage`` block.

All fixtures are synthetic and minimal; ``espn_request`` is mocked, no network.
"""

import pytest

from sports_skills.nfl import _connector as nfl

_COVERAGE_KEYS = {
    "requested",
    "completeness",
    "reason",
    "warnings",
    "returned_count",
    "seasons_returned",
    "weeks_returned",
}


def _event(event_id, week, year=2026, season_type=2):
    return {
        "id": event_id,
        "season": {"year": year, "type": season_type},
        "week": {"number": week},
        "competitions": [{"date": "2026-09-13T17:00Z", "competitors": []}],
    }


def _mock(monkeypatch, respond):
    """Replace the ESPN boundary; ``respond(resource, params)`` builds the reply."""
    calls = []

    def fake(sport_path, resource="scoreboard", params=None, max_retries=2):
        calls.append({"resource": resource, "params": params, "max_retries": max_retries})
        return respond(resource, params or {})

    monkeypatch.setattr(nfl, "espn_request", fake)
    return calls


# ── get_schedule: refusal and validation (before any request) ──


@pytest.mark.parametrize("season", [2026, "2026"])
def test_season_only_is_refused_before_network(monkeypatch, season):
    calls = _mock(monkeypatch, lambda r, p: {"events": [_event("1", 1)]})
    result = nfl.get_schedule({"params": {"season": season}})
    assert result["error"] is True
    assert "get_team_schedule" in result["message"]
    assert "week" in result["message"]
    assert calls == []


@pytest.mark.parametrize(
    "params",
    [
        {"season": "abc", "week": 5},
        {"season": "20x6"},
        {"season": 2026, "week": 0},
        {"season": 2026, "week": 24},
        {"season": 2026, "week": "abc"},
        {"week": -1},
        {"season": True, "week": 5},
        {"season": 2026.0, "week": 5},
        {"season": 2026, "week": True},
        {"season": 2026, "week": 5.0},
        {"season": 2026, "week": "5.0"},
    ],
)
def test_invalid_season_or_week_is_a_graceful_error(monkeypatch, params):
    calls = _mock(monkeypatch, lambda r, p: {"events": []})
    result = nfl.get_schedule({"params": params})
    assert result["error"] is True
    assert isinstance(result["message"], str) and result["message"]
    assert calls == []


# ── get_schedule: season + week query semantics ──


@pytest.mark.parametrize("week", [5, "5"])
def test_regular_season_week_query(monkeypatch, week):
    calls = _mock(monkeypatch, lambda r, p: {"events": []})
    nfl.get_schedule({"params": {"season": 2026, "week": week}})
    assert calls[0]["resource"] == "scoreboard"
    # Explicit seasontype: ESPN's default may be the current postseason.
    assert calls[0]["params"] == {"dates": "2026", "seasontype": 2, "week": 5}


@pytest.mark.parametrize("week, espn_week", [(19, 1), ("20", 2), (23, 5)])
def test_postseason_week_query(monkeypatch, week, espn_week):
    calls = _mock(monkeypatch, lambda r, p: {"events": []})
    nfl.get_schedule({"params": {"season": 2026, "week": week}})
    assert calls[0]["params"] == {"dates": "2026", "seasontype": 3, "week": espn_week}


# ── get_schedule: coverage ──


def test_season_week_coverage_is_unknown_not_complete(monkeypatch):
    _mock(monkeypatch, lambda r, p: {
        "events": [_event("1", 5), _event("2", 5)],
        "season": {"year": 2026, "type": 2},
        "week": {"number": 5, "text": "Week 5"},
    })
    result = nfl.get_schedule({"params": {"season": 2026, "week": 5}})

    # Existing shape is untouched.
    assert result["count"] == 2
    assert [e["id"] for e in result["events"]] == ["1", "2"]
    assert result["season"] == {"year": 2026, "type": 2}
    assert result["week"] == {"number": 5, "text": "Week 5"}

    coverage = result["coverage"]
    assert set(coverage) == _COVERAGE_KEYS
    assert coverage["requested"] == {"season": 2026, "week": 5, "team_id": None}
    # An HTTP 200 does not prove every game of the week was returned.
    assert coverage["completeness"] == "unknown"
    assert coverage["reason"]
    assert isinstance(coverage["warnings"], list)
    assert coverage["returned_count"] == 2
    assert coverage["seasons_returned"] == [2026]
    assert coverage["weeks_returned"] == [5]


@pytest.mark.parametrize("malformed", ["2026", [2026], True])
def test_malformed_event_coverage_metadata_does_not_crash(monkeypatch, malformed):
    event = _event("1", 5)
    event.update(season=malformed, week=malformed)
    _mock(monkeypatch, lambda r, p: {"events": [event]})
    result = nfl.get_schedule({"params": {"season": 2026, "week": 5}})
    assert result["count"] == 1
    assert result["coverage"]["seasons_returned"] == []
    assert result["coverage"]["weeks_returned"] == []
    assert result["coverage"]["completeness"] == "unknown"


def test_empty_week_is_not_inferred_complete(monkeypatch):
    """No events is not proof of a bye week or an empty slate."""
    _mock(monkeypatch, lambda r, p: {"events": []})
    coverage = nfl.get_schedule({"params": {"season": 2026, "week": 7}})["coverage"]
    assert coverage["completeness"] == "unknown"
    assert coverage["returned_count"] == 0
    assert coverage["weeks_returned"] == []


def test_no_params_is_the_current_window_not_a_season(monkeypatch):
    calls = _mock(monkeypatch, lambda r, p: {
        "events": [_event("1", 18, year=2025), _event("2", 1, year=2026)],
    })
    result = nfl.get_schedule({"params": {}})
    assert not calls[0]["params"]

    coverage = result["coverage"]
    assert coverage["requested"] == {"season": None, "week": None, "team_id": None}
    assert coverage["completeness"] == "unknown"
    assert "current" in coverage["reason"].lower()
    assert coverage["returned_count"] == 2
    assert coverage["seasons_returned"] == [2025, 2026]


def test_week_without_season_is_the_current_seasons_week(monkeypatch):
    calls = _mock(monkeypatch, lambda r, p: {"events": [_event("1", 3)]})
    result = nfl.get_schedule({"params": {"week": 3}})
    assert calls[0]["params"] == {"seasontype": 2, "week": 3}

    coverage = result["coverage"]
    assert coverage["requested"] == {"season": None, "week": 3, "team_id": None}
    assert coverage["completeness"] == "unknown"
    assert coverage["weeks_returned"] == [3]


# ── get_team_schedule: coverage ──


def _team_responder(post):
    def respond(resource, params):
        if params.get("seasontype") == 3:
            return post
        return {
            "team": {"id": "12", "displayName": "Kansas City Chiefs", "abbreviation": "KC"},
            "events": [_event("1", 1, year=2025), _event("2", 2, year=2025)],
        }

    return respond


def test_team_schedule_with_postseason_is_unknown_not_complete(monkeypatch):
    post = {"events": [_event("3", 1, year=2025, season_type=3)]}
    _mock(monkeypatch, _team_responder(post))
    result = nfl.get_team_schedule({"params": {"team_id": 12, "season": 2025}})

    assert result["count"] == 3
    assert result["season"] == 2025
    coverage = result["coverage"]
    assert set(coverage) == _COVERAGE_KEYS
    assert coverage["requested"] == {"season": 2025, "week": None, "team_id": "12"}
    assert coverage["completeness"] == "unknown"
    assert coverage["returned_count"] == 3
    assert coverage["seasons_returned"] == [2025]


def test_team_postseason_failure_is_partial(monkeypatch):
    post = {"error": True, "status_code": 503, "message": "HTTP 503 from site.api.espn.com"}
    _mock(monkeypatch, _team_responder(post))
    result = nfl.get_team_schedule({"params": {"team_id": "12", "season": 2025}})

    assert not result.get("error")
    assert [e["id"] for e in result["events"]] == ["1", "2"]
    coverage = result["coverage"]
    assert coverage["completeness"] == "partial"
    assert coverage["reason"]
    assert any("postseason" in w.lower() for w in coverage["warnings"])
    assert coverage["returned_count"] == 2

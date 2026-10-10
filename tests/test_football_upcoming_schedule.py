"""get_season_schedule must include upcoming fixtures, not only played results.

ESPN's team schedule endpoint returns completed matches by default; upcoming
matches need a separate ``fixture=true`` call, which ignores ``season`` and
always answers for the current season. All ESPN calls are faked here (offline).
"""

import pytest

from sports_skills.football import _connector as fc


def _event(eid, date, home, away, status, season=2026, score=None):
    sides = []
    for qualifier, (tid, name), goals in (
        ("home", home, score[0] if score else None),
        ("away", away, score[1] if score else None),
    ):
        side = {"id": tid, "homeAway": qualifier, "team": {"id": tid, "displayName": name}}
        if goals is not None:
            side["score"] = {"value": float(goals), "displayValue": str(goals)}
        sides.append(side)
    comp = {"id": eid, "date": date, "competitors": sides, "status": {"type": {"name": status}}}
    return {"id": eid, "date": date, "season": {"year": season}, "competitions": [comp]}


ARS, LEE, BHA = ("359", "Arsenal"), ("357", "Leeds United"), ("331", "Brighton & Hove Albion")

# Captured subset of real ESPN eng.1 payloads for Arsenal, fetched 2026-10-10:
# teams/359/schedule?season=2026 (completed) and ...&fixture=true (upcoming).
BHA_ARS = _event("401879274", "2026-09-19T14:00Z", BHA, ARS, "STATUS_FULL_TIME", score=(3, 0))
ARS_LEE = _event("401879268", "2026-10-10T11:30Z", ARS, LEE, "STATUS_SCHEDULED")

FEED_DOWN = {"error": True, "message": "HTTP 503"}


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch):
    monkeypatch.setattr(fc, "_cache", {})


def _install(monkeypatch, teams, default, fixtures, current=2026):
    """Fake ESPN. ``default``/``fixtures`` map team id -> events list or error dict."""

    def web(league_slug, resource, params=None):
        entries = [{"team": {"id": t}} for t in teams]
        return {"children": [{"standings": {"entries": entries}}]}

    def site(league_slug, resource="scoreboard", params=None, max_retries=None):
        params = params or {}
        if not resource.startswith("teams/"):
            season = {"year": current, "startDate": f"{current}-08-01T00:00Z"}
            return {"leagues": [{"season": season}], "events": []}
        tid = resource.split("/")[1]
        is_fixture = params.get("fixture") == "true"
        feed = (fixtures if is_fixture else default).get(tid, [])
        if isinstance(feed, dict):
            return feed
        # fixture=true ignores `season`; the default feed honours it.
        year = current if is_fixture else int(params.get("season", current))
        return {"events": list(feed), "requestedSeason": {"year": year}}

    monkeypatch.setattr(fc, "_espn_web_request", web)
    monkeypatch.setattr(fc, "_espn_request", site)
    monkeypatch.setattr(fc, "_openfootball_fetch", lambda slug, year: None)


def _schedule(season_id):
    return fc.get_season_schedule({"params": {"season_id": season_id}})


def _ids(result):
    return [e["id"] for e in result["schedules"]]


def test_current_season_includes_completed_and_upcoming_real_payload(monkeypatch):
    _install(
        monkeypatch,
        teams=["359", "357"],
        default={"359": [BHA_ARS], "357": []},
        fixtures={"359": [ARS_LEE], "357": [ARS_LEE]},
    )
    result = _schedule("premier-league-2026")

    assert _ids(result) == ["401879274", "401879268"]
    played, upcoming = result["schedules"]
    assert played["status"] == "closed"
    assert played["scores"] == {"home": 3, "away": 0}
    assert upcoming["status"] == "not_started"
    assert upcoming["start_time"] == "2026-10-10T11:30Z"
    assert [c["team"]["id"] for c in upcoming["competitors"]] == ["359", "357"]
    assert result.get("source") != "openfootball"


def test_dedupes_across_teams_and_feeds_with_result_precedence(monkeypatch):
    # Synthetic: 900001 shows as a stale scheduled copy in Arsenal's fixture
    # feed (seen first) and as a played 2-1 result in Leeds' default feed.
    stale = _event("900001", "2026-10-04T14:00Z", ARS, LEE, "STATUS_SCHEDULED")
    final = _event("900001", "2026-10-04T14:00Z", ARS, LEE, "STATUS_FULL_TIME", score=(2, 1))
    _install(
        monkeypatch,
        teams=["359", "357", "331"],
        default={"359": [BHA_ARS], "357": [final], "331": [BHA_ARS]},
        fixtures={"359": [stale, ARS_LEE], "357": [ARS_LEE], "331": []},
    )
    result = _schedule("premier-league-2026")

    assert sorted(_ids(result)) == ["401879268", "401879274", "900001"]
    starts = [e["start_time"] for e in result["schedules"]]
    assert starts == sorted(starts)
    merged = next(e for e in result["schedules"] if e["id"] == "900001")
    assert merged["status"] == "closed"
    assert merged["scores"] == {"home": 2, "away": 1}


def test_past_season_rejects_current_fixture_feed_leak(monkeypatch):
    # Synthetic 2025 result; the fixture feed still answers with the real
    # current-season (2026) Leeds fixture because ESPN ignores `season`.
    old = _event("900010", "2026-03-01T15:00Z", ARS, LEE, "STATUS_FULL_TIME", 2025, (1, 1))
    _install(
        monkeypatch,
        teams=["359", "357"],
        default={"359": [old], "357": [old]},
        fixtures={"359": [ARS_LEE], "357": [ARS_LEE]},
    )
    result = _schedule("premier-league-2025")

    assert _ids(result) == ["900010"]


def test_excludes_event_whose_own_season_is_wrong(monkeypatch):
    # Synthetic: the fixture feed reports the right requestedSeason but carries
    # an event that ESPN itself labels as the previous season.
    stray = _event("900020", "2026-10-17T14:00Z", ARS, BHA, "STATUS_SCHEDULED", season=2025)
    _install(
        monkeypatch,
        teams=["359", "357"],
        default={"359": [BHA_ARS], "357": []},
        fixtures={"359": [ARS_LEE, stray], "357": [ARS_LEE]},
    )
    result = _schedule("premier-league-2026")

    assert "900020" not in _ids(result)
    assert sorted(_ids(result)) == ["401879268", "401879274"]


def test_fixture_feed_failure_keeps_returned_results(monkeypatch):
    _install(
        monkeypatch,
        teams=["359", "357"],
        default={"359": [BHA_ARS], "357": []},
        fixtures={"359": FEED_DOWN, "357": FEED_DOWN},
    )
    result = _schedule("premier-league-2026")

    assert _ids(result) == ["401879274"]
    assert result.get("source") != "openfootball"
    assert not result.get("error")


def test_fixtures_only_season(monkeypatch):
    # Synthetic: no match played yet, so only the fixture feed has events.
    _install(
        monkeypatch,
        teams=["359", "357"],
        default={"359": [], "357": []},
        fixtures={"359": [ARS_LEE], "357": [ARS_LEE]},
    )
    result = _schedule("premier-league-2026")

    assert _ids(result) == ["401879268"]
    assert result["schedules"][0]["status"] == "not_started"
    assert result.get("source") != "openfootball"

"""Golf connector (#163): past events by id/date, light schedule, round rows, overview order.

Payloads are trimmed from live ESPN responses (PGA 2026: Arnold Palmer Invitational
and Puerto Rico Open ran the same week; Collin Morikawa withdrew after one hole of
THE PLAYERS).
"""

from __future__ import annotations

import json

from sports_skills.golf import _connector as g


def _golfer(pid, name, linescores, order=1):
    return {"id": pid, "order": order, "athlete": {"displayName": name}, "score": "-5",
            "linescores": linescores}


def _event(eid, name, competitors):
    return {"id": eid, "name": name, "competitions": [{"competitors": competitors, "status": {}}]}


HOLES_18 = [{"period": h, "value": 4.0, "scoreType": {"displayValue": "E"}} for h in range(1, 19)]

WEEK_SCOREBOARD = {
    "events": [
        _event("401811935", "Arnold Palmer Invitational", [
            _golfer("1", "A. Player", [{"period": 1, "value": 72.0, "displayValue": "E",
                                        "linescores": HOLES_18}]),
        ]),
        _event("401811936", "Puerto Rico Open", [
            _golfer("10592", "Collin Morikawa", [
                {"period": 1, "value": 4.0, "displayValue": "E"},
                {"period": 2, "value": 0.0, "displayValue": "-"},
            ]),
        ]),
    ]
}


def _fake_espn(calls, payload):
    def fake(sport_path, resource="scoreboard", params=None, **kw):
        calls.append(params)
        return payload
    return fake


def test_leaderboard_event_id_reaches_a_past_event(monkeypatch):
    scoreboard_calls, core_calls = [], []
    monkeypatch.setattr(g, "espn_request", _fake_espn(scoreboard_calls, WEEK_SCOREBOARD))

    def fake_fetch(url, **kw):
        core_calls.append(url)
        return json.dumps({"date": "2026-03-05T05:00Z"}).encode(), None

    monkeypatch.setattr(g, "_http_fetch", fake_fetch)
    out = g.get_leaderboard({"params": {"tour": "pga", "event_id": "401811936"}})
    assert out["tournament"]["id"] == "401811936"
    assert out["tournament"]["name"] == "Puerto Rico Open"
    assert scoreboard_calls == [{"dates": "20260305"}]
    assert core_calls[0].endswith("/golf/leagues/pga/events/401811936")


def test_leaderboard_date_and_bad_date(monkeypatch):
    calls = []
    monkeypatch.setattr(g, "espn_request", _fake_espn(calls, WEEK_SCOREBOARD))
    out = g.get_leaderboard({"params": {"tour": "pga", "date": "2026-03-06"}})
    assert out["tournament"]["name"] == "Arnold Palmer Invitational"
    assert calls == [{"dates": "20260306"}]
    bad = g.get_leaderboard({"params": {"tour": "pga", "date": "March 6"}})
    assert bad["error"] is True and "YYYY-MM-DD" in bad["message"]


def test_leaderboard_unknown_event_is_an_error(monkeypatch):
    monkeypatch.setattr(g, "espn_request", _fake_espn([], WEEK_SCOREBOARD))
    out = g.get_leaderboard({"params": {"tour": "pga", "event_id": "1", "date": "2026-03-06"}})
    assert out["error"] is True and "get_schedule" in out["message"]


def test_scorecard_event_id_and_round_rows(monkeypatch):
    monkeypatch.setattr(g, "espn_request", _fake_espn([], WEEK_SCOREBOARD))
    out = g.get_scorecard({"params": {"tour": "pga", "player_id": "10592",
                                      "event_id": "401811936", "date": "2026-03-05"}})
    assert out["tournament"] == "Puerto Rico Open"
    r1, r2 = out["rounds"]
    # a withdrawal after one hole: 4 strokes, no hole detail from ESPN
    assert (r1["total_strokes"], r1["total_score"], r1["holes_played"]) == (4, "E", None)
    # the unplayed round is "-", not 0 strokes
    assert r2["total_strokes"] is None and r2["total_score"] == "-"


def test_leaderboard_round_rows_carry_holes_played():
    t = g._normalize_tournament(WEEK_SCOREBOARD["events"][0])
    assert t["leaderboard"][0]["rounds"] == [
        {"round": 1, "strokes": 72, "score": "E", "holes_played": 18}
    ]
    t = g._normalize_tournament(WEEK_SCOREBOARD["events"][1])
    assert t["leaderboard"][0]["rounds"][1]["strokes"] is None


def test_schedule_asks_for_the_calendar_only(monkeypatch):
    calls = []
    payload = {"season": {"year": 2026}, "events": [{"id": "x"}], "leagues": [{"calendar": [
        {"id": "401811941", "label": "Masters Tournament", "startDate": "2026-04-09T07:00Z",
         "endDate": "2026-04-12T07:00Z"},
    ]}]}
    monkeypatch.setattr(g, "espn_request", _fake_espn(calls, payload))
    out = g.get_schedule({"params": {"tour": "pga", "year": 2026}})
    assert out["count"] == 1 and out["tournaments"][0]["name"] == "Masters Tournament"
    assert calls == [{"dates": "2026", "limit": 1}]


def test_recent_tournaments_newest_first():
    data = {"recentTournaments": [
        {"name": "PGA TOUR", "eventsStats": [
            {"name": "TOUR Championship", "date": "2026-08-27T04:00:00.000+00:00"},
            {"name": "The Open", "date": "2026-07-16T04:00:00.000+00:00"},
        ]},
        {"name": "DP World Tour", "eventsStats": [
            {"name": "BMW PGA Championship", "date": "2026-09-17T04:00:00.000+00:00"},
            {"name": "Crown Australian Open", "date": "2025-12-04T05:00:00.000+00:00"},
        ]},
    ]}
    names = [t["name"] for t in g._normalize_player_overview(data)["recent_tournaments"]]
    assert names == ["BMW PGA Championship", "TOUR Championship", "The Open",
                     "Crown Australian Open"]

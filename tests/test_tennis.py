"""Tennis connector (#163): the full-year calendar body is fetched once, then cached."""

from __future__ import annotations

from sports_skills.tennis import _connector as t


def test_calendar_is_cached_after_the_first_fetch(monkeypatch):
    calls = []

    def fake(sport_path, resource="scoreboard", params=None, **kw):
        calls.append(params)
        return {"events": [{"id": "188-2026", "name": "Wimbledon", "groupings": [{}]}]}

    monkeypatch.setattr(t, "espn_request", fake)
    first = t.get_calendar({"params": {"tour": "atp", "year": 1999}})
    second = t.get_calendar({"params": {"tour": "atp", "year": 1999}})
    assert first == second and first["tournaments"][0]["name"] == "Wimbledon"
    assert "draws" not in first["tournaments"][0]
    assert calls == [{"dates": "1999"}]

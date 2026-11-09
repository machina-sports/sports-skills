"""NFL get_leaders with no season reads the current season's leaders.

ESPN's unscoped ``leagues/nfl/leaders`` is all-time career leaders (Adam
Vinatieri's 2673 points first), not the current season.
"""

import json

import pytest

from sports_skills.nfl import _connector as nfl

CAREER = "leagues/nfl/leaders"


@pytest.fixture
def served(monkeypatch):
    calls = []
    available = {2026}

    def fake_fetch(url, headers=None, **kw):
        calls.append(url)
        if url.endswith(CAREER):
            year = "career"
        else:
            year = int(url.split("/seasons/")[1].split("/")[0])
            if year not in available:
                return None, {"error": True, "message": "HTTP 404"}
        body = {"season": {"year": year if year != "career" else ""}, "categories": [{"name": str(year)}]}
        return json.dumps(body).encode(), None

    monkeypatch.setattr(nfl, "_http_fetch", fake_fetch)
    monkeypatch.setattr(nfl, "_resolve_leaders", lambda cats: [c["name"] for c in cats])
    monkeypatch.setattr(nfl, "_cache_get", lambda key: None)
    monkeypatch.setattr(nfl, "_cache_set", lambda *a, **kw: None)
    return calls


def test_no_season_reads_the_current_season(served, monkeypatch):
    monkeypatch.setattr(nfl, "_current_year", lambda: 2026)

    result = nfl.get_leaders({"params": {}})

    assert result["categories"] == ["2026"]
    assert result["season"] == 2026
    assert not any(url.endswith(CAREER) for url in served)


def test_no_season_before_espn_serves_it_steps_back_a_year(served, monkeypatch):
    # January 2027: the 2026 season is still being played.
    monkeypatch.setattr(nfl, "_current_year", lambda: 2027)

    result = nfl.get_leaders({"params": {}})

    assert result["categories"] == ["2026"]
    assert result["season"] == 2026


def test_named_season_is_not_substituted(served):
    result = nfl.get_leaders({"params": {"season": 2027}})

    assert result.get("error") is True

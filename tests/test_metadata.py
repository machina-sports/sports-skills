"""TheSportsDB get_team_info must not return a loosely matched, different team."""

import pytest

from sports_skills.metadata import _connector as md


def _team(name, sport, alternate="", short=""):
    return {"idTeam": name, "strTeam": name, "strSport": sport, "strTeamAlternate": alternate, "strTeamShort": short}


@pytest.fixture
def search(monkeypatch):
    results = {}
    monkeypatch.setattr(md, "_http_fetch", lambda url, retries=2: {"teams": results.get("teams")})
    return results


def test_loose_match_is_rejected(search):
    """Live free-key response for "St. Louis Cardinals" (2026-09)."""
    search["teams"] = [_team("Louisville", "American Football", "Louisville Cardinals")]
    result = md.get_team_info({"params": {"team_name": "St. Louis Cardinals"}})
    assert result["error"] is True
    assert "Louisville" in result["message"] and "St. Louis Cardinals" in result["message"]


def test_exact_name_beats_earlier_loose_result(search):
    search["teams"] = [
        _team("Louisville", "American Football", "Louisville Cardinals"),
        _team("St. Louis Cardinals", "Baseball", "Cardinals", "STL"),
    ]
    result = md.get_team_info({"params": {"team_name": "St Louis Cardinals"}})
    assert result["name"] == "St. Louis Cardinals"


@pytest.mark.parametrize(
    ("query", "team"),
    [
        ("Arsenal", _team("Arsenal", "Soccer", "Arsenal Football Club, AFC, Arsenal FC")),
        ("Real Madrid CF", _team("Real Madrid", "Soccer", "Real Madrid", "MAD")),
        ("Inter", _team("Inter Milan", "Soccer", "Inter, Internazionale Milano")),
        ("Yankees", _team("New York Yankees", "Baseball", "Yankees")),
        ("Saint Louis Blues", _team("St. Louis Blues", "Ice Hockey", "Blues")),
    ],
)
def test_close_names_still_match(search, query, team):
    search["teams"] = [team]
    assert md.get_team_info({"params": {"team_name": query}})["name"] == team["strTeam"]


def test_team_logo_rejects_loose_match(search):
    search["teams"] = [_team("Louisville", "American Football", "Louisville Cardinals")]
    result = md.get_team_logo({"params": {"team_name": "St. Louis Cardinals", "sport": "Baseball"}})
    assert result["error"] is True
    assert "Louisville" in result["message"] and "St. Louis Cardinals" in result["message"]


def test_team_logo_prefers_close_match_in_sport(search):
    search["teams"] = [
        _team("Louisville", "American Football", "Louisville Cardinals"),
        _team("Arizona Cardinals", "American Football", "Cardinals", "ARI"),
        _team("St. Louis Cardinals", "Baseball", "Cardinals", "STL"),
    ]
    result = md.get_team_logo({"params": {"team_name": "St Louis Cardinals", "sport": "Baseball"}})
    assert result["team_name"] == "St. Louis Cardinals"


def test_team_logo_close_match_in_other_sport_still_returned(search):
    search["teams"] = [_team("Arsenal", "Soccer", "Arsenal FC")]
    result = md.get_team_logo({"params": {"team_name": "Arsenal", "sport": "Basketball"}})
    assert result["team_name"] == "Arsenal"


# ── rate limiting (#165) ─────────────────────────────────────────────
# Live free key (2026-09): 30 quick searchteams calls succeed, the 31st gets
# HTTP 429 with Retry-After: 119.


def _raise_429(calls):
    import email.message
    import urllib.error

    def urlopen(req, timeout=None):
        calls.append(req.full_url)
        headers = email.message.Message()
        headers["Retry-After"] = "119"
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", headers, None)

    return urlopen


@pytest.fixture
def no_cache(monkeypatch):
    monkeypatch.setattr(md, "_cache", {})
    monkeypatch.setattr(md.time, "sleep", lambda s: None)


def test_limiter_stays_under_the_free_key_limit():
    """Burst plus one minute of refill must not exceed 30 requests."""
    assert md._limiter.max_tokens + 60 * md._limiter.refill_rate <= 30


def test_429_is_not_retried_and_says_why(monkeypatch, no_cache):
    calls = []
    monkeypatch.setattr(md.urllib.request, "urlopen", _raise_429(calls))
    raw, err = md._live_http_fetch(f"{md.BASE_URL}/searchteams.php?t=Arsenal", retries=2)
    assert raw is None and len(calls) == 1
    assert err["status_code"] == 429
    assert "30 requests" in err["message"] and "119" in err["message"]


def test_429_reaches_the_caller_with_an_upgrade_hint(monkeypatch, no_cache):
    from sports_skills import metadata

    monkeypatch.delenv("SPORTS_SKILLS_NO_UPGRADE_HINTS", raising=False)
    monkeypatch.setattr(md.urllib.request, "urlopen", _raise_429([]))
    monkeypatch.setattr(md._limiter, "acquire", lambda timeout=10.0: True)
    out = metadata.get_team_logo(team_name="Arsenal")
    assert out["status"] is False
    assert out["status_code"] == 429
    assert out["upgrade"]["trigger"] == "rate_limited"


def test_exhausted_limiter_refuses_instead_of_calling_upstream(monkeypatch, no_cache):
    calls = []
    monkeypatch.setattr(md.urllib.request, "urlopen", _raise_429(calls))
    monkeypatch.setattr(md._limiter, "acquire", lambda timeout=10.0: False)
    out = md._http_fetch(f"{md.BASE_URL}/searchteams.php?t=Arsenal")
    assert calls == []
    assert out["error"] is True and out["status_code"] == 429
    assert "30 requests" in out["message"]


def test_cache_hits_do_not_spend_rate_limit_tokens(monkeypatch, no_cache):
    url = f"{md.BASE_URL}/searchteams.php?t=Arsenal"
    md._cache_set(url, {"teams": []})

    def acquire(timeout=10.0):
        raise AssertionError("cache hit must not wait on the limiter")

    monkeypatch.setattr(md._limiter, "acquire", acquire)
    assert md._http_fetch(url) == {"teams": []}

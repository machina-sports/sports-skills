"""get_leaders and get_futures keep ESPN lookups bounded (one request per athlete or team ref)."""

import json

import pytest

from sports_skills import _espn_base
from sports_skills.mlb import _connector as mlb
from sports_skills.nba import _connector as nba
from sports_skills.nfl import _connector as nfl
from sports_skills.nhl import _connector as nhl
from sports_skills.wnba import _connector as wnba

REF = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/{}?lang=en&region=us"


@pytest.fixture
def athlete_lookups(monkeypatch):
    looked_up = []

    def resolve(ref_url):
        looked_up.append(ref_url)
        return {"name": f"Athlete {len(looked_up)}", "id": ref_url.split("/athletes/")[1].split("?")[0]}

    monkeypatch.setattr(_espn_base, "_resolve_athlete_ref", resolve)
    return looked_up


def _category(size):
    return {
        "displayName": "Passing Yards",
        "leaders": [{"athlete": {"$ref": REF.format(i)}, "value": 100 - i} for i in range(size)],
    }


def test_leaders_limit_resolves_only_the_kept_leaders(athlete_lookups):
    (category,) = _espn_base._resolve_leaders([_category(50)], limit=10)
    assert len(category["leaders"]) == 10
    assert len(athlete_lookups) == 10
    assert [row["rank"] for row in category["leaders"]][-1] == 10


def test_leaders_without_a_limit_keep_every_leader(athlete_lookups):
    (category,) = _espn_base._resolve_leaders([_category(25)])
    assert len(category["leaders"]) == 25


@pytest.mark.parametrize(
    ("params", "expected"),
    [({}, (10, None)), ({"limit": "25"}, (25, None)), ({"limit": None}, (10, None))],
)
def test_leaders_limit_defaults_to_ten(params, expected):
    assert _espn_base.leaders_limit(params) == expected


@pytest.mark.parametrize("bad", ["0", "-3", "ten"])
def test_leaders_limit_rejects_non_positive_values(bad):
    limit, error = _espn_base.leaders_limit({"limit": bad})
    assert limit is None and error["error"] is True


@pytest.mark.parametrize("connector", [nfl, nba, wnba, nhl, mlb])
def test_get_leaders_applies_the_limit(monkeypatch, athlete_lookups, connector):
    payload = json.dumps({"categories": [_category(40)], "season": {"year": 2026}}).encode()
    monkeypatch.setattr(connector, "_http_fetch", lambda url, **kw: (payload, None))
    monkeypatch.setattr(connector, "_cache_get", lambda key: None)
    monkeypatch.setattr(connector, "_cache_set", lambda *a, **k: None)
    result = connector.get_leaders({"params": {"season": 2026, "limit": 5}})
    data = result.get("data", result)
    assert len(data["categories"][0]["leaders"]) == 5
    assert len(athlete_lookups) == 5


def test_futures_team_names_come_from_one_team_list(monkeypatch):
    """A futures market lists every team; one league team list names them all."""
    fetched = []
    teams = {
        "sports": [
            {"leagues": [{"teams": [{"team": {"id": str(i), "displayName": f"Team {i}"}} for i in range(1, 33)]}]}
        ]
    }

    def fetch(url, **kw):
        fetched.append(url)
        return json.dumps(teams).encode(), None

    monkeypatch.setattr(_espn_base, "_http_fetch", fetch)
    store = {}
    monkeypatch.setattr(_espn_base, "_cache_get", store.get)
    monkeypatch.setattr(_espn_base, "_cache_set", lambda key, value, ttl=None: store.__setitem__(key, value))
    team_ref = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/{}?lang=en&region=us"
    data = {
        "items": [
            {
                "id": "1",
                "displayName": "Super Bowl Winner",
                "futures": [
                    {
                        "provider": {"name": "ESPN BET"},
                        "books": [{"team": {"$ref": team_ref.format(i)}, "value": f"+{i}00"} for i in range(1, 33)],
                    }
                ],
            }
        ]
    }
    (market,) = _espn_base.normalize_futures(data, limit=32)["futures"]
    assert [entry["name"] for entry in market["entries"]][:3] == ["Team 1", "Team 2", "Team 3"]
    assert fetched == ["https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=1000"]

"""Team news reads ESPN's league feed filtered by team, not ``teams/<id>/news``.

``teams/<id>/news`` answers ``{}`` for every ESPN league, which normalized to
"0 articles". The league feed takes ``?team=<id>`` and tags each article with
the teams it covers, the way NFL ``get_news`` already reads it.
"""

import pytest

from sports_skills.cbb import _connector as cbb
from sports_skills.cfb import _connector as cfb
from sports_skills.mlb import _connector as mlb
from sports_skills.nba import _connector as nba
from sports_skills.nhl import _connector as nhl
from sports_skills.wnba import _connector as wnba

# (connector, ESPN sportId on team tags, team id) as served live
LEAGUES = [
    (nba, 46, "13"),
    (nhl, 90, "13"),
    (mlb, 10, "10"),
    (wnba, 59, "14"),
    (cfb, 23, "333"),
    (cbb, 41, "150"),
]


def _article(headline, sport_id, *team_ids):
    return {
        "headline": headline,
        "published": "2026-11-09T12:00:00Z",
        "links": {"web": {"href": f"https://www.espn.com/{headline}"}},
        "categories": [
            {"type": "team", "sportId": sport_id, "teamId": int(t), "team": {"id": int(t)}} for t in team_ids
        ],
    }


def _serve(monkeypatch, connector, sport_id, team_id):
    calls = []

    def fake_request(sport_path, resource="scoreboard", params=None, **kw):
        calls.append((resource, params))
        if resource.startswith("teams/"):
            return {}
        return {
            "articles": [
                _article("ours", sport_id, team_id, "99"),
                _article("league-wide", sport_id, "98", "99"),
                _article("same-id-other-sport", 9999, team_id),
            ]
        }

    monkeypatch.setattr(connector, "espn_request", fake_request)
    import sports_skills._espn_base as base

    monkeypatch.setattr(base, "espn_request", fake_request)
    return calls


@pytest.mark.parametrize("connector,sport_id,team_id", LEAGUES, ids=lambda v: getattr(v, "__name__", str(v)))
def test_team_news_returns_the_teams_articles(monkeypatch, connector, sport_id, team_id):
    calls = _serve(monkeypatch, connector, sport_id, team_id)

    result = connector.get_news({"params": {"team_id": team_id}})

    assert calls == [("news", {"team": team_id})]
    assert [a["headline"] for a in result["articles"]] == ["ours"]
    assert result["count"] == 1


@pytest.mark.parametrize("connector,sport_id,team_id", LEAGUES, ids=lambda v: getattr(v, "__name__", str(v)))
def test_league_news_is_unfiltered(monkeypatch, connector, sport_id, team_id):
    calls = _serve(monkeypatch, connector, sport_id, team_id)

    result = connector.get_news({"params": {}})

    assert result["count"] == 3
    assert calls == [("news", None)]

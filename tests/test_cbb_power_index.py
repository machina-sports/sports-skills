"""CBB BPI reads follow ESPN's powerindex pagination past the first page.

ESPN reports the page count as ``pagination.pages`` (365 teams, 50 per page,
pages=8). Reading a key ESPN doesn't send stopped every loop after page one.
"""

import pytest

from sports_skills.cbb import _connector as cbb

PAGE_SIZE = 50
TEAM_COUNT = 120


def _entry(rank):
    return {
        "team": {"id": str(1000 + rank), "displayName": f"Team {rank}", "abbreviation": f"T{rank}"},
        "categories": [],
    }


@pytest.fixture
def served(monkeypatch):
    calls = []

    def fake_fitt(sport_path, resource, params=None):
        calls.append(params["page"])
        limit, page = params["limit"], params["page"]
        start = (page - 1) * limit
        ranks = range(start + 1, min(start + limit, TEAM_COUNT) + 1)
        return {
            "teams": [_entry(r) for r in ranks],
            "pagination": {
                "count": TEAM_COUNT,
                "limit": limit,
                "page": page,
                "pages": -(-TEAM_COUNT // limit),
            },
        }

    monkeypatch.setattr(cbb, "espn_fitt_request", fake_fitt)
    return calls


def test_team_lookup_finds_a_team_past_the_first_page(served):
    result = cbb.get_power_index({"params": {"team_id": "1110"}})

    assert result.get("error") is not True
    assert result["teams"][0]["team"]["id"] == "1110"
    assert served == [1, 2, 3]


def test_page_count_comes_from_espn_pages(served):
    result = cbb.get_power_index({"params": {"limit": PAGE_SIZE, "page": 1}})

    assert result["page_count"] == 3

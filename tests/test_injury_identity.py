"""Injury records carry ESPN's athlete id when ESPN sends one, and say so when not.

No name hashing or fuzzy joins: a record without ``athlete.id`` is
``unresolved``. Fixtures are synthetic and minimal; no network.
"""

import pytest

from sports_skills._espn_base import normalize_injuries
from sports_skills.nfl import _connector as nfl

_FIELDS = {"name", "position", "status", "type", "detail", "side", "return_date"}


def _payload():
    return {
        "injuries": [
            {
                "id": "12",
                "displayName": "Kansas City Chiefs",
                "injuries": [
                    {
                        "athlete": {"id": 3139477, "displayName": "Player A", "position": {"abbreviation": "QB"}},
                        "status": "Questionable",
                        "type": {"description": "Ankle"},
                        "details": {"detail": "Sprain", "side": "Left", "returnDate": "2026-10-12"},
                    },
                    {
                        "athlete": {"displayName": "Player B", "position": {"abbreviation": "WR"}},
                        "status": "Out",
                        "type": {"name": "Knee"},
                        "details": {},
                    },
                ],
            },
            {
                "id": "1",
                "displayName": "Atlanta Falcons",
                "injuries": [
                    {"athlete": {"id": "", "displayName": "Player C"}, "status": "Out"},
                ],
            },
        ]
    }


def _records(result):
    return [inj for team in result["teams"] for inj in team["injuries"]]


def test_provider_id_is_preserved_as_string():
    record = normalize_injuries(_payload())["teams"][0]["injuries"][0]
    assert record["athlete_id"] == "3139477"
    assert record["identity_status"] == "provider-native"
    assert record["id_namespace"] == "espn"


def test_missing_or_empty_id_is_unresolved_not_hashed():
    records = _records(normalize_injuries(_payload()))
    for record in records[1:]:
        assert record["athlete_id"] is None
        assert record["identity_status"] == "unresolved"
        assert record["id_namespace"] is None


def test_existing_fields_are_unchanged():
    result = normalize_injuries(_payload())
    assert result["count"] == 2  # still the team count
    team = result["teams"][0]
    assert team["team"] == "Kansas City Chiefs"
    assert team["team_id"] == "12"
    assert team["count"] == 2
    first = team["injuries"][0]
    assert {k: first[k] for k in _FIELDS} == {
        "name": "Player A",
        "position": "QB",
        "status": "Questionable",
        "type": "Ankle",
        "detail": "Sprain",
        "side": "Left",
        "return_date": "2026-10-12",
    }
    assert team["injuries"][1]["type"] == "Knee"


def test_identity_summary_accounts_for_every_record():
    result = normalize_injuries(_payload())
    assert result["identity_summary"] == {"records": 3, "provider_native": 1, "unresolved": 2}
    assert any("healthy" in caveat.lower() for caveat in result["caveats"])


def test_null_and_malformed_optional_fields_do_not_crash():
    payload = {
        "injuries": [
            {
                "id": "12",
                "displayName": "Kansas City Chiefs",
                "injuries": [
                    {"athlete": None, "details": None, "type": None, "status": "Out"},
                    {"athlete": {"id": 42, "position": None}, "status": "Out"},
                    {"athlete": "Player D", "details": [], "type": "Ankle", "status": "Out"},
                ],
            }
        ]
    }
    result = normalize_injuries(payload)
    records = _records(result)
    assert len(records) == 3
    for record in records:
        assert set(record) >= _FIELDS
    assert records[1]["athlete_id"] == "42"
    assert [r["identity_status"] for r in records] == ["unresolved", "provider-native", "unresolved"]
    assert result["identity_summary"] == {"records": 3, "provider_native": 1, "unresolved": 2}


@pytest.mark.parametrize("collection", [None, "invalid", 42, {}])
def test_malformed_injury_collections_do_not_crash(collection):
    outer = normalize_injuries({"injuries": collection})
    assert outer["teams"] == []
    nested = normalize_injuries({"injuries": [{"injuries": collection}]})
    assert nested["teams"][0]["injuries"] == []
    assert nested["identity_summary"]["records"] == 0


@pytest.mark.parametrize("athlete_id", [True, False, {}, [], 3.5, " ", " 42 "])
def test_malformed_ids_are_unresolved(athlete_id):
    payload = _payload()
    payload["injuries"][0]["injuries"][0]["athlete"]["id"] = athlete_id
    record = _records(normalize_injuries(payload))[0]
    assert record["athlete_id"] is None
    assert record["identity_status"] == "unresolved"


def test_null_team_and_injury_entries_are_not_fabricated_records():
    result = normalize_injuries({"injuries": [None, {"injuries": [None]}]})
    assert result["count"] == 1
    assert result["teams"][0]["injuries"] == []
    assert result["identity_summary"] == {"records": 0, "provider_native": 0, "unresolved": 0}


def test_nfl_get_injuries_carries_identity(monkeypatch):
    monkeypatch.setattr(nfl, "espn_request", lambda *a, **k: _payload())
    result = nfl.get_injuries()
    assert result["teams"][0]["injuries"][0]["athlete_id"] == "3139477"
    assert result["identity_summary"]["unresolved"] == 2

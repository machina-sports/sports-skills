"""ESPN schedule and scoreboard rows carry the start instant as epoch seconds (#152)."""

import importlib

import pytest

_LEAGUES = ["nba", "nfl", "mlb", "nhl", "wnba", "cfb", "cbb"]


@pytest.mark.parametrize("league", _LEAGUES)
def test_start_ts_is_the_start_time_in_epoch_seconds(league):
    normalize = importlib.import_module(f"sports_skills.{league}._connector")._normalize_event
    # ESPN's minute-precision UTC form: Chiefs @ Packers, 2026-09-25 00:15 UTC.
    row = normalize({"id": "1", "competitions": [{"date": "2026-09-25T00:15Z", "competitors": []}]})
    assert row["start_time"] == "2026-09-25T00:15Z"
    assert row["start_ts"] == 1790295300


@pytest.mark.parametrize("league", _LEAGUES)
def test_start_ts_is_none_without_a_date(league):
    normalize = importlib.import_module(f"sports_skills.{league}._connector")._normalize_event
    assert normalize({"id": "1", "competitions": [{"competitors": []}]})["start_ts"] is None

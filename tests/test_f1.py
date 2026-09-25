"""FastF1 connector: sprint points in season totals, pit in/out laps."""

import pandas as pd
import pytest

fastf1 = pytest.importorskip("fastf1")

from sports_skills.f1 import _connector as f1  # noqa: E402


def _schedule():
    return fastf1.events.EventSchedule(
        pd.DataFrame(
            {
                "RoundNumber": [1, 2],
                "EventName": ["Chinese Grand Prix", "Japanese Grand Prix"],
                "EventDate": pd.to_datetime(["2026-03-15", "2026-03-29"]),
                "EventFormat": ["sprint_qualifying", "conventional"],
            }
        )
    )


def _results(points):
    return fastf1.core.SessionResults(
        pd.DataFrame(
            {
                "Abbreviation": ["NOR", "PIA"],
                "FullName": ["Lando Norris", "Oscar Piastri"],
                "TeamName": ["McLaren", "McLaren"],
                "Position": [1.0, 2.0],
                "GridPosition": [1.0, 2.0],
                "Status": ["Finished", "Finished"],
                "Points": points,
            },
            index=["4", "81"],
        )
    )


_RACE_POINTS = {"R": [25.0, 18.0], "S": [8.0, 7.0]}


class _Session:
    def __init__(self, session_type):
        self.session_type = session_type

    def load(self, laps=True, **kwargs):
        self.results = _results(_RACE_POINTS[self.session_type])
        self.laps = fastf1.core.Laps(
            pd.DataFrame(
                {
                    "Driver": ["NOR", "NOR", "NOR"],
                    "DriverNumber": ["4", "4", "4"],
                    "Team": ["McLaren"] * 3,
                    "LapNumber": [10.0, 11.0, 12.0],
                    "LapTime": pd.to_timedelta(["0:01:40", "0:01:55", "0:01:36"]),
                    "IsAccurate": [True, True, True],
                    "PitInTime": pd.to_timedelta(["0:20:00", None, None]),
                    "PitOutTime": pd.to_timedelta([None, "0:20:22", None]),
                }
            )
        )


@pytest.fixture
def fake_fastf1(monkeypatch):
    calls = []

    def get_session(year, event, session_type):
        calls.append((event, session_type))
        return _Session(session_type)

    monkeypatch.setattr(fastf1, "get_event_schedule", lambda year: _schedule())
    monkeypatch.setattr(fastf1, "get_session", get_session)
    return calls


def test_championship_standings_include_sprint_points(fake_fastf1):
    result = f1.get_championship_standings({"params": {"year": 2026}})
    assert result["status"] is True, result
    drivers = {d["driver_code"]: d for d in result["data"]["driver_standings"]}
    # Two races (25 + 25) plus one sprint (8).
    assert drivers["NOR"]["points"] == 58
    assert drivers["NOR"]["sprint_points"] == 8
    assert drivers["NOR"]["races"] == 2
    assert drivers["NOR"]["wins"] == 2
    teams = {t["team"]: t["points"] for t in result["data"]["constructor_standings"]}
    assert teams["McLaren"] == 25 + 18 + 25 + 18 + 8 + 7
    # Only the sprint weekend loads the sprint session.
    assert ("Chinese Grand Prix", "S") in fake_fastf1
    assert ("Japanese Grand Prix", "S") not in fake_fastf1


def test_season_stats_include_sprint_points(fake_fastf1):
    result = f1.get_season_stats({"params": {"year": 2026}})
    assert result["status"] is True, result
    drivers = {d["driver_code"]: d for d in result["data"]["drivers"]}
    assert drivers["PIA"]["points"] == 18 + 18 + 7
    assert drivers["PIA"]["sprint_points"] == 7


def test_pit_in_and_out_laps_are_not_accurate(fake_fastf1):
    result = f1.get_lap_data({"params": {"year": 2026, "event": "Japanese Grand Prix", "driver": "NOR"}})
    assert result["status"] is True, result
    laps = {lap["lap_number"]: lap for lap in result["data"]}
    assert laps[10]["is_pit_in_lap"] is True and laps[10]["is_accurate"] is False
    assert laps[11]["is_pit_out_lap"] is True and laps[11]["is_accurate"] is False
    assert laps[12]["is_accurate"] is True
    assert laps[12]["is_pit_in_lap"] is False and laps[12]["is_pit_out_lap"] is False

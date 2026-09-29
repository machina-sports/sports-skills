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
                "Location": ["Shanghai", "Suzuka"],
                "Session1": ["Practice 1", "Practice 1"],
                "Session1Date": pd.to_datetime(["2026-03-13 11:30", "2026-03-27 11:30"]),
                "Session2": ["Sprint Qualifying", "Practice 2"],
                "Session2Date": pd.to_datetime(["2026-03-13 15:30", "2026-03-27 15:00"]),
                "Session3": ["Sprint", "Practice 3"],
                "Session3Date": pd.to_datetime(["2026-03-14 11:00", "2026-03-28 11:30"]),
                "Session4": ["Qualifying", "Qualifying"],
                "Session4Date": pd.to_datetime(["2026-03-14 15:00", "2026-03-28 15:00"]),
                "Session5": ["Race", "Race"],
                "Session5Date": pd.to_datetime(["2026-03-15 15:00", "2026-03-29 14:00"]),
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
    def __init__(self, session_type, event):
        self.session_type = session_type
        self.name = {"R": "Race", "S": "Sprint"}[session_type]
        self.event = _schedule().get_event_by_name(event)

    def load(self, laps=True, **kwargs):
        self.results = _results(_RACE_POINTS[self.session_type])
        self.laps = fastf1.core.Laps(
            pd.DataFrame(
                {
                    "Driver": ["NOR", "NOR", "NOR"] + ["PIA"] * 5,
                    "DriverNumber": ["4", "4", "4"] + ["81"] * 5,
                    "Team": ["McLaren"] * 8,
                    "LapNumber": [10.0, 11.0, 12.0, 3.0, 4.0, 20.0, 21.0, 30.0],
                    "LapTime": pd.to_timedelta(
                        ["0:01:40", "0:01:55", "0:01:36", None, None, "0:01:41", "0:02:30", "0:01:39"]
                    ),
                    "IsAccurate": [True, True, True, False, False, False, False, True],
                    # PIA: tyre change under a red flag (lap 3), a slow 65 s stop
                    # (lap 20), then retires into the pits (lap 30, no out lap).
                    "TrackStatus": ["1", "1", "1", "1245", "1", "1", "1", "1"],
                    "PitInTime": pd.to_timedelta(
                        ["0:20:00", None, None, "0:10:00", None, "0:40:00", None, "0:55:00"]
                    ),
                    "PitOutTime": pd.to_timedelta(
                        [None, "0:20:22", None, None, "0:40:40", None, "0:41:05", None]
                    ),
                }
            )
        )


@pytest.fixture
def fake_fastf1(monkeypatch):
    calls = []

    def get_session(year, event, session_type):
        calls.append((event, session_type))
        return _Session(session_type, event)

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


def test_team_comparison_includes_sprint_points(fake_fastf1):
    result = f1.get_team_comparison({"params": {"year": 2026, "team1": "McLaren", "team2": "Ferrari"}})
    assert result["status"] is True, result
    mclaren = result["data"]["team1"]
    assert mclaren["points"] == 25 + 18 + 25 + 18 + 8 + 7
    assert mclaren["sprint_points"] == 8 + 7
    assert result["data"]["team2"]["sprint_points"] == 0


def test_driver_comparison_includes_sprint_points(fake_fastf1):
    result = f1.get_driver_comparison({"params": {"year": 2026, "driver1": "NOR", "driver2": "PIA"}})
    assert result["status"] is True, result
    drivers = {d["driver_code"]: d for d in result["data"]["drivers"]}
    assert drivers["NOR"]["points"] == 25 + 25 + 8
    assert drivers["NOR"]["sprint_points"] == 8
    assert drivers["PIA"]["sprint_points"] == 7
    assert drivers["NOR"]["races"] == 2


def test_single_event_comparison_counts_only_that_weekends_sprint(fake_fastf1):
    result = f1.get_driver_comparison(
        {"params": {"year": 2026, "driver1": "NOR", "driver2": "PIA", "event": "Japanese Grand Prix"}}
    )
    assert result["status"] is True, result
    drivers = {d["driver_code"]: d for d in result["data"]["drivers"]}
    assert drivers["NOR"]["points"] == 25
    assert drivers["NOR"]["sprint_points"] == 0


def test_pit_stops_keep_long_and_red_flag_stops(fake_fastf1):
    result = f1.get_pit_stops({"params": {"year": 2026, "event": "Japanese Grand Prix"}})
    assert result["status"] is True, result
    data = result["data"]
    stops = {(p["driver"], p["lap"]): p for p in data["pit_stops"]}
    # The 65 s stop and the red-flag tyre change are real stint changes; the
    # lap-30 pit entry has no out lap (retirement), so it is not a stop.
    assert set(stops) == {("NOR", 10), ("PIA", 20), ("PIA", 3)}
    assert stops[("NOR", 10)]["duration_seconds"] == 22.0
    assert stops[("PIA", 20)]["duration_seconds"] == 65.0
    assert stops[("PIA", 3)]["red_flag"] is True
    assert stops[("PIA", 20)]["red_flag"] is False
    assert data["total_stops"] == 3
    assert data["duration_type"] == "pit_lane_time"
    # Team averages leave out red-flag stops (the car waited in the pit lane).
    mclaren = data["team_summary"][0]
    assert mclaren["total_stops"] == 2
    assert mclaren["average_seconds"] == 43.5
    assert mclaren["best_seconds"] == 22.0


def test_race_results_fastest_lap_from_laps(fake_fastf1):
    result = f1.get_race_results({"params": {"year": 2026, "event": "Japanese Grand Prix"}})
    assert result["status"] is True, result
    rows = {r["driver"]: r for r in result["data"]}
    assert rows["NOR"]["fastest_lap"] is True
    assert rows["NOR"]["fastest_lap_time"] == "1:36.000"
    assert rows["PIA"]["fastest_lap"] is False
    assert rows["PIA"]["fastest_lap_time"] == "1:39.000"


@pytest.mark.parametrize(
    ("event", "session_type", "name", "round_number", "event_date", "session_date", "track"),
    [
        ("Japanese Grand Prix", "R", "Race", 2, "2026-03-29", "2026-03-29T14:00:00", "Suzuka"),
        ("Chinese Grand Prix", "S", "Sprint", 1, "2026-03-15", "2026-03-14T11:00:00", "Shanghai"),
    ],
)
def test_session_data_metadata(fake_fastf1, event, session_type, name, round_number, event_date, session_date, track):
    result = f1.get_session_data(
        {"params": {"session_year": 2026, "session_name": event, "session_type": session_type}}
    )
    assert result["status"] is True, result
    data = result["data"]
    assert data["event_name"] == event
    assert data["round"] == round_number
    assert data["event_date"] == event_date
    assert data["session_date"] == session_date
    assert data["session_type"] == name
    assert data["track_name"] == track


def test_championship_standings_after_round(fake_fastf1):
    result = f1.get_championship_standings({"params": {"year": 2026, "round": 1}})
    assert result["status"] is True, result
    drivers = {d["driver_code"]: d for d in result["data"]["driver_standings"]}
    # Round 1 race (25) plus its sprint (8); round 2 is not counted.
    assert drivers["NOR"]["points"] == 33
    assert drivers["NOR"]["sprint_points"] == 8
    assert drivers["NOR"]["races"] == 1
    assert result["data"]["races_counted"] == 1
    assert result["data"]["after_round"] == 1
    assert ("Japanese Grand Prix", "R") not in fake_fastf1


def test_championship_standings_bad_round_is_text_error(fake_fastf1):
    result = f1.get_championship_standings({"params": {"year": 2026, "round": "abc"}})
    assert result["status"] is False
    assert "round" in result["message"].lower()

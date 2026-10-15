"""Regression tests for NFL/CFB drive-by-drive play-by-play.

The bug: the drive normalizer read ``drives.previous`` and ignored
``drives.current``, so a live game showed no plays from the drive being played
until it ended. ``espn_summary`` also cached a live game for five minutes,
longer than many drives last.

``nfl_summary_401872994_drives.json`` is a real ESPN summary (LAR vs BUF, Final/OT),
trimmed to the header and the first four drives, with the ``teamParticipants``
$ref links removed. Live shapes are derived from it the way ESPN serves a game in
progress: ``drives.current`` is one drive object, present only while the game is
on, and the drive in progress may sit in ``current`` alone or also be repeated as
the last entry of ``previous``.
"""

import copy
import json
from pathlib import Path

import pytest

from sports_skills import _espn_base
from sports_skills._espn_base import normalize_football_drives
from sports_skills.cfb._connector import _normalize_drives as cfb_drives
from sports_skills.nfl._connector import _normalize_drives as nfl_drives

FIXTURE = Path(__file__).parent / "fixtures" / "nfl_summary_401872994_drives.json"


@pytest.fixture
def final():
    with open(FIXTURE) as f:
        return json.load(f)


def _live(summary):
    """The same summary, marked as a game in progress."""
    summary["header"]["competitions"][0]["status"]["type"]["state"] = "in"
    return summary


def _play_ids(result):
    return [p["id"] for d in result["drives"] for p in d["plays"]]


def _current_only(final, keep_plays=5):
    """Two finished drives, plus the third in progress under ``current`` only."""
    live = _live(copy.deepcopy(final))
    in_progress = copy.deepcopy(live["drives"]["previous"][2])
    in_progress["plays"] = in_progress["plays"][:keep_plays]
    live["drives"] = {"previous": live["drives"]["previous"][:2], "current": in_progress}
    return live


class TestFinishedGame:
    def test_every_drive_and_play_is_kept_in_order(self, final):
        result = nfl_drives(final)
        assert result["count"] == 4
        assert [len(d["plays"]) for d in result["drives"]] == [6, 17, 12, 19]
        raw_ids = [str(p["id"]) for d in final["drives"]["previous"] for p in d["plays"]]
        assert _play_ids(result) == raw_ids
        assert result["current_drive_id"] is None
        assert not any(d["is_current"] for d in result["drives"])
        assert result["game_state"] == "post"

    def test_existing_fields_are_unchanged(self, final):
        drive = nfl_drives(final)["drives"][0]
        assert drive["result"] == "Field Goal"
        assert set(drive) >= {
            "id",
            "description",
            "team",
            "result",
            "is_score",
            "yards",
            "plays_count",
            "time_elapsed",
            "start",
            "end",
            "plays",
        }
        play = drive["plays"][0]
        assert set(play) >= {
            "id",
            "text",
            "type",
            "period",
            "clock",
            "home_score",
            "away_score",
            "scoring_play",
            "yards",
            "is_turnover",
        }

    def test_play_carries_situation_and_espn_times(self, final):
        play = nfl_drives(final)["drives"][0]["plays"][1]
        assert play["id"] == "40187299468"
        assert play["sequence_number"] == 6800
        assert play["start"] == {
            "down": 1,
            "distance": 10,
            "yard_line": 26,
            "yards_to_endzone": 26,
            "down_distance_text": "1st & 10 at LAR 26",
            "possession_text": "LAR 26",
            "team_id": "2",
        }
        assert play["end"]["down"] == 2 and play["end"]["distance"] == 7
        assert play["wallclock"] == "2026-10-13T00:16:48Z"
        assert play["modified"] == "2026-10-13T04:18Z"
        assert play["is_penalty"] is False

    def test_cfb_uses_the_same_normalizer(self, final):
        live = _current_only(final)
        assert cfb_drives(live) == nfl_drives(live) == normalize_football_drives(live)


class TestDriveInProgress:
    def test_current_only_drive_is_returned_before_it_ends(self, final):
        live = _current_only(final, keep_plays=5)
        result = nfl_drives(live)
        assert result["count"] == 3
        current = result["drives"][-1]
        assert current["is_current"] is True
        assert result["current_drive_id"] == current["id"] == str(final["drives"]["previous"][2]["id"])
        assert len(current["plays"]) == 5
        assert result["game_state"] == "in"

    def test_drive_repeated_in_previous_and_current_is_merged_once(self, final):
        live = _live(copy.deepcopy(final))
        repeated = copy.deepcopy(live["drives"]["previous"][3])
        live["drives"]["current"] = repeated
        result = nfl_drives(live)
        assert result["count"] == 4
        ids = _play_ids(result)
        assert len(ids) == len(set(ids)) == 54
        assert result["drives"][-1]["is_current"] is True
        assert [d["is_current"] for d in result["drives"]] == [False, False, False, True]

    def test_fresher_copy_of_a_revised_play_wins(self, final):
        live = _live(copy.deepcopy(final))
        repeated = copy.deepcopy(live["drives"]["previous"][3])
        revised = repeated["plays"][2]
        revised["text"] += " (revised)"
        revised["modified"] = "2099-01-01T00:00Z"
        stale = live["drives"]["previous"][3]["plays"][3]
        stale["text"] += " (newer)"
        stale["modified"] = "2099-01-01T00:00Z"
        live["drives"]["current"] = repeated
        plays = nfl_drives(live)["drives"][-1]["plays"]
        by_id = {p["id"]: p for p in plays}
        assert by_id[str(revised["id"])]["text"].endswith("(revised)")
        # The copy in ``previous`` is the newer one here, so it stays.
        assert by_id[str(stale["id"])]["text"].endswith("(newer)")

    def test_current_copy_adds_plays_the_previous_copy_has_not_seen(self, final):
        live = _live(copy.deepcopy(final))
        tail = live["drives"]["previous"][3]
        repeated = copy.deepcopy(tail)
        tail["plays"] = tail["plays"][:10]  # previous lags behind current
        live["drives"]["current"] = repeated
        assert len(nfl_drives(live)["drives"][-1]["plays"]) == 19

    def test_live_drive_totals_come_from_the_current_object(self, final):
        live = _live(copy.deepcopy(final))
        repeated = copy.deepcopy(live["drives"]["previous"][3])
        repeated["yards"] = 999
        live["drives"]["current"] = repeated
        assert nfl_drives(live)["drives"][-1]["yards"] == 999

    def test_drive_moving_from_current_to_previous_keeps_its_plays(self, final):
        """Two polls: the drive in progress, then the same drive finished."""
        before = nfl_drives(_current_only(final, keep_plays=5))
        after_summary = _live(copy.deepcopy(final))
        after_summary["drives"] = {
            "previous": after_summary["drives"]["previous"][:3],
            "current": copy.deepcopy(final["drives"]["previous"][3]),
        }
        after = nfl_drives(after_summary)
        assert set(_play_ids(before)) <= set(_play_ids(after))
        assert len(_play_ids(after)) == len(set(_play_ids(after)))
        finished = after["drives"][2]
        assert finished["is_current"] is False and len(finished["plays"]) == 12

    def test_play_listed_under_two_drives_stays_in_the_later_one(self, final):
        live = _live(copy.deepcopy(final))
        moved = copy.deepcopy(live["drives"]["previous"][2]["plays"][-1])
        current = copy.deepcopy(live["drives"]["previous"][3])
        current["plays"].insert(0, moved)
        live["drives"]["current"] = current
        live["drives"]["previous"] = live["drives"]["previous"][:3]
        result = nfl_drives(live)
        ids = _play_ids(result)
        assert len(ids) == len(set(ids))
        assert str(moved["id"]) in {p["id"] for p in result["drives"][-1]["plays"]}
        assert str(moved["id"]) not in {p["id"] for p in result["drives"][2]["plays"]}

    def test_plays_are_ordered_by_sequence_number(self, final):
        live = _current_only(final, keep_plays=6)
        live["drives"]["current"]["plays"].reverse()
        plays = nfl_drives(live)["drives"][-1]["plays"]
        sequence = [p["sequence_number"] for p in plays]
        assert sequence == sorted(sequence)


class TestDegradedInput:
    @pytest.mark.parametrize(
        "drives",
        [
            None,
            {},
            {"previous": None},
            {"previous": [], "current": None},
            {"current": {}},
            {"previous": "oops", "current": []},
            {"previous": [None, 7]},
        ],
    )
    def test_malformed_drives_degrade_to_empty(self, drives):
        result = nfl_drives({"drives": drives})
        assert result["drives"] == [] and result["count"] == 0
        assert result["current_drive_id"] is None

    def test_none_summary(self):
        result = normalize_football_drives(None)
        assert result["count"] == 0 and result["game_state"] is None and result["retrieved_at"] is None

    def test_drives_and_plays_without_ids_are_not_merged(self):
        play = {"text": "same text", "clock": {"displayValue": "10:00"}}
        drives = {"previous": [{"plays": [play, dict(play)]}, {"plays": [dict(play)]}]}
        result = nfl_drives({"drives": drives})
        assert result["count"] == 2
        assert [len(d["plays"]) for d in result["drives"]] == [2, 1]

    def test_missing_situation_stays_unknown_and_zero_is_kept(self):
        plays = [
            {"id": "1", "sequenceNumber": "1"},
            {"id": "2", "sequenceNumber": "2", "start": {"down": 0, "distance": 0, "yardLine": 0}},
        ]
        no_situation, kickoff = nfl_drives({"drives": {"current": {"id": "9", "plays": plays}}})["drives"][0]["plays"]
        assert no_situation["start"] is None and no_situation["end"] is None
        assert no_situation["wallclock"] is None and no_situation["modified"] is None
        assert no_situation["is_penalty"] is None
        assert kickoff["start"]["down"] == 0 and kickoff["start"]["distance"] == 0
        assert kickoff["start"]["team_id"] is None and kickoff["start"]["possession_text"] is None


class TestPublicApi:
    def test_get_play_by_play_returns_the_drive_in_progress(self, final, monkeypatch):
        from sports_skills import nfl
        from sports_skills.nfl import _connector

        live = _current_only(final, keep_plays=5)
        live[_espn_base.SUMMARY_RETRIEVED_AT_KEY] = "2026-10-15T00:20:00Z"
        monkeypatch.setattr(_connector, "espn_summary", lambda *a, **kw: live)
        response = nfl.get_play_by_play(event_id="401872994")
        data = response["data"]
        assert data["drives"][-1]["is_current"] is True
        assert len(data["drives"][-1]["plays"]) == 5
        assert data["retrieved_at"] == "2026-10-15T00:20:00Z"


class TestLiveSummaryCache:
    @pytest.fixture(autouse=True)
    def _isolated_cache(self, monkeypatch):
        monkeypatch.setattr(_espn_base, "_cache", {})

    def _serve(self, monkeypatch, payload):
        calls = []

        def fake_fetch(url, **kwargs):
            calls.append(url)
            return json.dumps(payload).encode(), None

        monkeypatch.setattr(_espn_base, "_http_fetch", fake_fetch)
        return calls

    def _ttl(self, key):
        _, expiry = _espn_base._cache[key]
        return expiry - _espn_base.time.monotonic()

    def test_live_game_expires_fast(self, final, monkeypatch):
        self._serve(monkeypatch, _live(copy.deepcopy(final)))
        data = _espn_base.espn_summary("football/nfl", "401872994")
        assert data[_espn_base.SUMMARY_RETRIEVED_AT_KEY].endswith("Z")
        assert self._ttl("espn_summary:football/nfl:401872994") <= _espn_base._LIVE_SUMMARY_TTL

    def test_finished_game_keeps_the_long_ttl(self, final, monkeypatch):
        self._serve(monkeypatch, final)
        _espn_base.espn_summary("football/nfl", "401872994")
        assert self._ttl("espn_summary:football/nfl:401872994") > 200

    def test_cached_summary_is_served_without_refetching(self, final, monkeypatch):
        calls = self._serve(monkeypatch, _live(copy.deepcopy(final)))
        first = _espn_base.espn_summary("football/nfl", "401872994")
        second = _espn_base.espn_summary("football/nfl", "401872994")
        assert len(calls) == 1
        assert first[_espn_base.SUMMARY_RETRIEVED_AT_KEY] == second[_espn_base.SUMMARY_RETRIEVED_AT_KEY]

    def test_non_object_json_is_a_failure(self, monkeypatch):
        self._serve(monkeypatch, ["not", "a", "summary"])
        assert _espn_base.espn_summary("football/nfl", "1") is None

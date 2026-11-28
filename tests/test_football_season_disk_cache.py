"""Season detection is cached on disk, so separate CLI processes share one ESPN scan.

``XDG_CACHE_HOME`` points at a per-test temporary directory (see conftest), so the
disk cache never touches the real home directory.
"""

import json
import os
import time

import pytest

from sports_skills import _replay
from sports_skills.football import _connector

SCOREBOARD = {
    "leagues": [
        {
            "season": {
                "year": 2026,
                "startDate": "2026-01-28T03:00Z",
                "endDate": "2026-12-03T02:59Z",
                "displayName": "2026 Brasileirão",
            },
            "calendar": [],
        }
    ]
}


@pytest.fixture
def espn_calls(monkeypatch):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    _connector._cache.clear()
    calls = []

    def fake_request(espn_slug, *args, **kwargs):
        calls.append(espn_slug)
        return SCOREBOARD

    monkeypatch.setattr(_connector, "_espn_request", fake_request)
    yield calls
    _connector._cache.clear()


def _new_process():
    """A new CLI process starts with an empty in-memory cache."""
    _connector._cache.clear()


def test_new_process_reads_the_season_from_disk(espn_calls):
    first = _connector._detect_current_season("serie-a-brazil", "bra.1")
    _new_process()
    assert _connector._detect_current_season("serie-a-brazil", "bra.1") == first
    assert first["year"] == 2026
    assert espn_calls == ["bra.1"]


@pytest.mark.parametrize("fetched_at", [-2 * _connector._SEASON_DISK_TTL, 600, "yesterday"])
def test_expired_future_or_corrupt_entries_are_refetched(espn_calls, fetched_at):
    _connector._detect_current_season("serie-a-brazil", "bra.1")
    path = _connector._season_cache_path("bra.1")
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    record["fetched_at"] = time.time() + fetched_at if isinstance(fetched_at, int) else fetched_at
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f)
    _new_process()
    _connector._detect_current_season("serie-a-brazil", "bra.1")
    assert espn_calls == ["bra.1", "bra.1"]


def test_unreadable_file_is_a_miss(espn_calls):
    path = _connector._season_cache_path("bra.1")
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert _connector._detect_current_season("serie-a-brazil", "bra.1")["year"] == 2026
    assert espn_calls == ["bra.1"]


def test_estimated_fallback_is_not_written(monkeypatch, espn_calls):
    monkeypatch.setattr(_connector, "_espn_request", lambda *args, **kwargs: {"error": "ESPN down"})
    season = _connector._detect_current_season("serie-a-brazil", "bra.1")
    assert season["estimated"] is True
    assert not os.path.exists(_connector._season_cache_path("bra.1"))


def test_replay_modes_skip_the_disk(monkeypatch, espn_calls):
    monkeypatch.setattr(_replay, "mode", lambda: _replay.REPLAY)
    _connector._detect_current_season("serie-a-brazil", "bra.1")
    assert not os.path.exists(_connector._season_cache_path("bra.1"))

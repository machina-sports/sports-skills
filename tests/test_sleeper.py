"""Tests for the Sleeper fantasy trending connector (``nfl.get_fantasy_trending``).

No network: ``_sleeper._http_fetch`` is substituted, except in the replay and
retry tests, which drive the shared ``_http_fetch`` against a fake ``urlopen``.
``XDG_CACHE_HOME`` points at a per-test temporary directory, so the disk
catalog cache never touches the real home directory.
Player IDs, names and counts below are synthetic.
"""

import datetime
import io
import json
import sys
import urllib.error
import urllib.request

import pytest

from sports_skills import _espn_base, _replay, nfl
from sports_skills.cli import _REGISTRY, _generate_schema, main
from sports_skills.nfl import _sleeper

CATALOG = {
    "90001": {"full_name": "Test Runner", "first_name": "Test", "last_name": "Runner", "team": "AAA", "position": "RB"},
    "90002": {"full_name": "Sample Catcher", "team": "BBB", "position": "WR"},
    "90003": {"full_name": "Free Agent", "team": None, "position": "TE"},
    # Team defenses carry first/last name but no full_name.
    "ZZZ": {"first_name": "Test City", "last_name": "Testers", "team": "ZZZ", "position": "DEF"},
    "90004": {"team": "CCC", "position": "QB"},
}

TRENDING = [
    {"player_id": "90001", "count": 5000},
    {"player_id": "90002", "count": 4000},
]


class FakeSleeper:
    """Stands in for ``_http_fetch``: routes trending vs catalog URLs."""

    def __init__(self, trending=TRENDING, catalog=CATALOG, trending_err=None, catalog_err=None):
        self.trending = trending
        self.catalog = catalog
        self.trending_err = trending_err
        self.catalog_err = catalog_err
        self.calls = []

    @staticmethod
    def _body(value):
        return value if isinstance(value, bytes) else json.dumps(value).encode()

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        if "/trending/" in url:
            if self.trending_err:
                return None, dict(self.trending_err)
            return self._body(self.trending), None
        if self.catalog_err:
            return None, dict(self.catalog_err)
        return self._body(self.catalog), None

    def trending_calls(self):
        return [u for u in self.calls if "/trending/" in u]

    def catalog_calls(self):
        return [u for u in self.calls if "/trending/" not in u]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


START = datetime.datetime(2026, 10, 5, 12, 0, tzinfo=datetime.timezone.utc)


class Clocks:
    """Moves the in-memory cache clock and ``_sleeper._utcnow`` together, as real time does."""

    def __init__(self, monkeypatch):
        self.mono = 1000.0
        self.utc = START
        monkeypatch.setattr(_espn_base.time, "monotonic", lambda: self.mono)
        monkeypatch.setattr(_sleeper, "_utcnow", lambda: self.utc)

    def advance(self, seconds):
        self.mono += seconds
        self.utc += datetime.timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def cache_home(monkeypatch, tmp_path_factory):
    """A private XDG cache home, kept apart from ``tmp_path`` (the replay tests count files there)."""
    home = tmp_path_factory.mktemp("xdg-cache")
    monkeypatch.setenv("XDG_CACHE_HOME", str(home))
    return home


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    monkeypatch.delenv(_replay.DIR_ENV, raising=False)
    monkeypatch.setattr(_espn_base.RateLimiter, "acquire", lambda self: None)
    _espn_base._cache.clear()
    yield
    _espn_base._cache.clear()


@pytest.fixture
def fake(monkeypatch):
    fetch = FakeSleeper()
    monkeypatch.setattr(_sleeper, "_http_fetch", fetch)
    return fetch


@pytest.fixture
def stamps(monkeypatch):
    """``_utcnow`` advancing one minute per call, so a re-fetch shows a new timestamp."""
    state = {"t": datetime.datetime(2026, 10, 5, 12, 0, tzinfo=datetime.timezone.utc)}

    def tick():
        value = state["t"]
        state["t"] = value + datetime.timedelta(minutes=1)
        return value

    monkeypatch.setattr(_sleeper, "_utcnow", tick)


@pytest.fixture
def clocks(monkeypatch):
    return Clocks(monkeypatch)


def _sleeper_cache_keys():
    return [k for k in _espn_base._cache if str(k).startswith("sleeper:")]


def _disk_path(cache_home):
    return cache_home / "sports-skills" / "sleeper" / "players-nfl.json"


def _disk_record(fetched_at="2026-10-05T11:00:00Z", index=None, schema=1):
    if index is None:
        index = {"90001": {"name": "Disk Name", "team": "DSK", "position": "RB"}}
    return {"schema": schema, "fetched_at": fetched_at, "index": index}


def _write_disk(cache_home, record):
    path = _disk_path(cache_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(record if isinstance(record, bytes) else json.dumps(record).encode())
    return path


# ── Happy paths ────────────────────────────────────────────────────────────────


class TestTrending:
    def test_adds_resolve_names_and_keep_sleeper_ids(self, fake, stamps):
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        data = result["data"]
        assert data["provider"] == "sleeper"
        assert data["trend_type"] == "add"
        assert data["lookback_hours"] == 24
        assert data["limit"] == 10
        assert data["count"] == 2
        assert data["unresolved_count"] == 0
        assert data["catalog_status"] == "loaded"
        assert "warnings" not in data
        assert data["players"][0] == {
            "rank": 1,
            "sleeper_player_id": "90001",
            "name": "Test Runner",
            "name_resolved": True,
            "team": "AAA",
            "position": "RB",
            "count": 5000,
        }
        assert data["players"][1]["sleeper_player_id"] == "90002"
        assert data["players"][1]["rank"] == 2

    def test_no_espn_mapping_is_attached(self, fake):
        player = nfl.get_fantasy_trending()["data"]["players"][0]
        assert not any("espn" in key for key in player)
        assert "player_id" not in player

    def test_requests_the_documented_urls(self, fake):
        nfl.get_fantasy_trending()
        assert fake.trending_calls() == [
            "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=10"
        ]
        assert fake.catalog_calls() == ["https://api.sleeper.app/v1/players/nfl"]

    def test_drops(self, fake):
        fake.trending = [{"player_id": "90003", "count": 77}]
        result = nfl.get_fantasy_trending(trend_type=" DROP ", lookback_hours=48, limit=5)
        data = result["data"]
        assert data["trend_type"] == "drop"
        assert fake.trending_calls() == [
            "https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours=48&limit=5"
        ]
        assert data["players"][0]["name"] == "Free Agent"
        assert data["players"][0]["team"] is None
        assert data["players"][0]["count"] == 77

    def test_provenance_and_popularity_note(self, fake, stamps):
        data = nfl.get_fantasy_trending()["data"]
        source = data["source"]
        assert source["trending_url"].endswith("/trending/add?lookback_hours=24&limit=10")
        assert source["trending_fetched_at"] == "2026-10-05T12:00:00Z"
        assert source["players_url"] == "https://api.sleeper.app/v1/players/nfl"
        assert source["players_fetched_at"] == "2026-10-05T12:01:00Z"
        assert "popularity" in data["note"]
        assert "not a projection" in data["note"]

    def test_valid_empty_list_is_success_without_catalog_fetch(self, fake):
        fake.trending = []
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        data = result["data"]
        assert data["players"] == []
        assert data["count"] == 0
        assert data["catalog_status"] == "not_needed"
        assert data["source"]["players_url"] is None
        assert data["source"]["players_fetched_at"] is None
        assert fake.catalog_calls() == []

    def test_rows_beyond_limit_are_dropped(self, fake):
        fake.trending = [{"player_id": "90001", "count": 3}, {"player_id": "90002", "count": 2}]
        data = nfl.get_fantasy_trending(limit=1)["data"]
        assert [p["sleeper_player_id"] for p in data["players"]] == ["90001"]

    def test_integer_player_id_is_kept_as_string(self, fake):
        fake.trending = [{"player_id": 90001, "count": 3}]
        player = nfl.get_fantasy_trending()["data"]["players"][0]
        assert player["sleeper_player_id"] == "90001"
        assert player["name"] == "Test Runner"


# ── Name resolution ────────────────────────────────────────────────────────────


class TestResolution:
    def test_unknown_player_is_flagged_unresolved(self, fake):
        fake.trending = [{"player_id": "90001", "count": 9}, {"player_id": "99999", "count": 8}]
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        data = result["data"]
        unknown = data["players"][1]
        assert unknown == {
            "rank": 2,
            "sleeper_player_id": "99999",
            "name": None,
            "name_resolved": False,
            "team": None,
            "position": None,
            "count": 8,
        }
        assert data["unresolved_count"] == 1
        assert data["catalog_status"] == "loaded"
        assert any("99999" in w for w in data["warnings"])

    def test_catalog_entry_without_any_name_is_unresolved(self, fake):
        fake.trending = [{"player_id": "90004", "count": 1}]
        player = nfl.get_fantasy_trending()["data"]["players"][0]
        assert player["name"] is None
        assert player["name_resolved"] is False
        # What the catalog does know is still reported.
        assert player["team"] == "CCC"
        assert player["position"] == "QB"

    def test_team_defense_name_is_built_from_first_and_last(self, fake):
        fake.trending = [{"player_id": "ZZZ", "count": 1}]
        player = nfl.get_fantasy_trending()["data"]["players"][0]
        assert player["name"] == "Test City Testers"
        assert player["position"] == "DEF"

    def test_non_object_catalog_entries_are_skipped(self, fake):
        fake.catalog = {"90001": CATALOG["90001"], "90002": "garbage"}
        data = nfl.get_fantasy_trending()["data"]
        assert data["catalog_status"] == "loaded"
        assert data["players"][0]["name_resolved"] is True
        assert data["players"][1]["name_resolved"] is False

    def test_nameless_record_with_null_team_and_position_keeps_the_catalog(self, fake):
        fake.catalog = {
            "ZZZ": CATALOG["ZZZ"],
            "90005": {"full_name": None, "first_name": None, "last_name": None, "team": None, "position": None},
        }
        fake.trending = [{"player_id": "ZZZ", "count": 2}, {"player_id": "90005", "count": 1}]
        data = nfl.get_fantasy_trending()["data"]
        assert data["catalog_status"] == "loaded"
        assert data["players"][0]["name"] == "Test City Testers"
        assert data["players"][1]["name_resolved"] is False
        assert (data["players"][1]["team"], data["players"][1]["position"]) == (None, None)
        assert set(_espn_base._cache_get(_sleeper._CATALOG_KEY)["index"]) == {"ZZZ"}


class TestCatalogFailure:
    """Counts survive a catalog failure, but the result never claims to be complete."""

    @pytest.mark.parametrize(
        ("catalog", "catalog_err", "reason"),
        [
            (None, {"error": True, "status_code": 500, "message": "HTTP 500 from api.sleeper.app"}, "HTTP 500"),
            (None, {"error": True, "message": "timed out"}, "timed out"),
            (b"<html>nope</html>", None, "not valid JSON"),
            ([], None, "non-empty object"),
            ({}, None, "non-empty object"),
            ({"90001": "x", "90002": 3}, None, "no player objects"),
            ({"error": {"message": "temporarily unavailable"}}, None, "'error' is not a player record"),
            ({"players": CATALOG}, None, "'players' is not a player record"),
            ({**CATALOG, "meta": {"version": 2}}, None, "'meta' is not a player record"),
            ({"90001": {"full_name": {"first": "Test"}, "team": "AAA"}}, None, "'90001' is not a player record"),
        ],
    )
    def test_marks_catalog_unavailable(self, fake, catalog, catalog_err, reason):
        fake.catalog = catalog
        fake.catalog_err = catalog_err
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        data = result["data"]
        assert data["catalog_status"] == "unavailable"
        assert data["unresolved_count"] == 2
        assert all(p["name_resolved"] is False and p["name"] is None for p in data["players"])
        assert [p["count"] for p in data["players"]] == [5000, 4000]
        assert data["source"]["players_fetched_at"] is None
        assert len(data["warnings"]) == 1
        assert "catalog unavailable" in data["warnings"][0]
        assert reason in data["warnings"][0]

    def test_failure_is_not_cached(self, fake):
        fake.catalog_err = {"error": True, "status_code": 503, "message": "HTTP 503"}
        nfl.get_fantasy_trending()
        fake.catalog_err = None
        data = nfl.get_fantasy_trending(trend_type="drop")["data"]
        assert data["catalog_status"] == "loaded"
        assert len(fake.catalog_calls()) == 2

    def test_rejected_payload_is_cached_nowhere(self, fake, cache_home):
        fake.catalog = {"error": {"message": "temporarily unavailable"}}
        assert nfl.get_fantasy_trending()["data"]["catalog_status"] == "unavailable"
        assert _espn_base._cache_get(_sleeper._CATALOG_KEY) is None
        assert not _disk_path(cache_home).exists()


# ── Bad trending shapes ────────────────────────────────────────────────────────


class TestTrendingShape:
    @pytest.mark.parametrize(
        ("payload", "fragment"),
        [
            (b"not json", "not valid JSON"),
            (b"\xff\xfe", "not valid JSON"),
            ({"player_id": "90001", "count": 1}, "expected a list"),
            ("a string", "expected a list"),
            (None, "expected a list"),
            ([1], "item 0 is not an object"),
            ([{"player_id": "90001", "count": 1}, ["x"]], "item 1 is not an object"),
            ([{"count": 1}], "player_id"),
            ([{"player_id": "", "count": 1}], "player_id"),
            ([{"player_id": "  ", "count": 1}], "player_id"),
            ([{"player_id": None, "count": 1}], "player_id"),
            ([{"player_id": True, "count": 1}], "player_id"),
            ([{"player_id": 1.5, "count": 1}], "player_id"),
            ([{"player_id": {"id": 1}, "count": 1}], "player_id"),
            ([{"player_id": "90001"}], "count"),
            ([{"player_id": "90001", "count": None}], "count"),
            ([{"player_id": "90001", "count": -1}], "count"),
            ([{"player_id": "90001", "count": "5"}], "count"),
            ([{"player_id": "90001", "count": 1.5}], "count"),
            ([{"player_id": "90001", "count": True}], "count"),
        ],
    )
    def test_schema_drift_is_a_structured_error(self, fake, payload, fragment):
        fake.trending = payload
        result = nfl.get_fantasy_trending()
        assert result["status"] is False
        assert result["data"] is None
        assert "Sleeper trending" in result["message"]
        assert fragment in result["message"]
        assert fake.catalog_calls() == []

    def test_bad_shape_is_not_cached(self, fake):
        fake.trending = {"oops": True}
        assert nfl.get_fantasy_trending()["status"] is False
        fake.trending = TRENDING
        assert nfl.get_fantasy_trending()["status"] is True
        assert len(fake.trending_calls()) == 2

    def test_unexpected_exception_is_contained(self, monkeypatch):
        def boom(url, **kwargs):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(_sleeper, "_http_fetch", boom)
        result = nfl.get_fantasy_trending()
        assert result["status"] is False
        assert "RuntimeError" in result["message"]
        assert "kaboom" in result["message"]


# ── Network errors ─────────────────────────────────────────────────────────────


class TestNetworkErrors:
    @pytest.mark.parametrize(
        "err",
        [
            {"error": True, "status_code": 429, "message": "HTTP 429 from api.sleeper.app"},
            {"error": True, "status_code": 404, "message": "HTTP 404 from api.sleeper.app"},
            {"error": True, "status_code": 503, "message": "HTTP 503 from api.sleeper.app"},
            {"error": True, "message": "<urlopen error [Errno 8] nodename nor servname provided>"},
        ],
    )
    def test_trending_failure_is_an_error(self, fake, err):
        fake.trending_err = err
        result = nfl.get_fantasy_trending()
        assert result["status"] is False
        assert result["message"].startswith("Sleeper trending request failed: ")
        assert err["message"] in result["message"]
        if "status_code" in err:
            assert result["status_code"] == err["status_code"]
        else:
            assert "status_code" not in result
        assert fake.catalog_calls() == []
        assert _sleeper_cache_keys() == []

    def test_429_is_retried_then_reported(self, monkeypatch):
        """Through the shared ``_http_fetch``: retried with backoff, then a 429 error."""
        attempts = []

        def throttled(req, timeout=None, context=None):
            attempts.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b""))

        sleeps = []
        monkeypatch.setattr(urllib.request, "urlopen", throttled)
        monkeypatch.setattr(_espn_base.time, "sleep", sleeps.append)
        result = nfl.get_fantasy_trending()
        assert result["status"] is False
        assert result["status_code"] == 429
        assert "Sleeper trending request failed" in result["message"]
        assert len(attempts) == 1 + _espn_base._MAX_RETRIES
        assert len(sleeps) == _espn_base._MAX_RETRIES


# ── Caching ────────────────────────────────────────────────────────────────────


class TestCache:
    def test_repeat_call_is_served_from_cache_with_original_timestamps(self, fake, stamps):
        first = nfl.get_fantasy_trending()["data"]
        second = nfl.get_fantasy_trending()["data"]
        assert len(fake.trending_calls()) == 1
        assert len(fake.catalog_calls()) == 1
        assert second == first
        assert second["source"]["trending_fetched_at"] == "2026-10-05T12:00:00Z"
        assert second["source"]["players_fetched_at"] == "2026-10-05T12:01:00Z"

    def test_different_params_use_different_trending_entries(self, fake):
        nfl.get_fantasy_trending()
        nfl.get_fantasy_trending(limit=5)
        nfl.get_fantasy_trending(trend_type="drop")
        nfl.get_fantasy_trending(lookback_hours=12)
        assert len(fake.trending_calls()) == 4
        # The catalog is fetched once and shared.
        assert len(fake.catalog_calls()) == 1

    def test_trending_expires_after_five_minutes(self, fake, stamps, monkeypatch):
        clock = Clock()
        monkeypatch.setattr(_espn_base.time, "monotonic", clock)
        first = nfl.get_fantasy_trending()["data"]
        clock.now += 299
        nfl.get_fantasy_trending()
        assert len(fake.trending_calls()) == 1
        clock.now += 2
        refreshed = nfl.get_fantasy_trending()["data"]
        assert len(fake.trending_calls()) == 2
        assert len(fake.catalog_calls()) == 1
        assert refreshed["source"]["trending_fetched_at"] != first["source"]["trending_fetched_at"]
        assert refreshed["source"]["players_fetched_at"] == first["source"]["players_fetched_at"]

    def test_catalog_expires_after_a_day(self, fake, clocks):
        first = nfl.get_fantasy_trending()["data"]
        clocks.advance(86399)
        nfl.get_fantasy_trending()
        assert len(fake.catalog_calls()) == 1
        clocks.advance(2)
        refreshed = nfl.get_fantasy_trending()["data"]
        assert len(fake.catalog_calls()) == 2
        assert refreshed["source"]["players_fetched_at"] != first["source"]["players_fetched_at"]

    def test_cached_catalog_holds_only_resolved_fields(self, fake):
        nfl.get_fantasy_trending()
        catalog = _espn_base._cache_get(_sleeper._CATALOG_KEY)
        assert catalog["index"]["90001"] == {"name": "Test Runner", "team": "AAA", "position": "RB"}


class TestDiskCache:
    """The trimmed catalog persists across processes; trending does not."""

    def test_new_process_reads_catalog_from_disk(self, fake, clocks):
        first = nfl.get_fantasy_trending()["data"]
        _espn_base._cache.clear()  # a fresh CLI process starts with an empty memory cache
        second = nfl.get_fantasy_trending()["data"]
        assert len(fake.catalog_calls()) == 1
        assert second["players"] == first["players"]
        assert second["source"]["players_fetched_at"] == first["source"]["players_fetched_at"]

    def test_trending_is_not_persisted(self, fake, clocks):
        nfl.get_fantasy_trending()
        _espn_base._cache.clear()
        nfl.get_fantasy_trending()
        assert len(fake.trending_calls()) == 2

    def test_disk_file_holds_only_trimmed_fields(self, fake, clocks, cache_home):
        nfl.get_fantasy_trending()
        path = _disk_path(cache_home)
        record = json.loads(path.read_text())
        assert set(record) == {"schema", "fetched_at", "index"}
        assert record["schema"] == _sleeper._CATALOG_CACHE_SCHEMA
        assert record["fetched_at"] == "2026-10-05T12:00:00Z"
        assert record["index"]["90001"] == {"name": "Test Runner", "team": "AAA", "position": "RB"}
        assert "first_name" not in path.read_text()
        assert [p.name for p in path.parent.iterdir()] == [path.name]  # no temp file left behind

    def test_fresh_disk_catalog_is_served_without_a_fetch(self, fake, clocks, cache_home):
        _write_disk(cache_home, _disk_record(fetched_at="2026-10-05T11:00:00Z"))
        data = nfl.get_fantasy_trending()["data"]
        assert fake.catalog_calls() == []
        assert data["catalog_status"] == "loaded"
        assert data["players"][0]["name"] == "Disk Name"
        assert data["players"][1]["name_resolved"] is False
        assert data["source"]["players_fetched_at"] == "2026-10-05T11:00:00Z"

    def test_hydrated_memory_keeps_the_original_expiry(self, fake, clocks):
        nfl.get_fantasy_trending()
        clocks.advance(86000)
        _espn_base._cache.clear()
        nfl.get_fantasy_trending()  # disk hit, 400 s of life left
        clocks.advance(399)
        nfl.get_fantasy_trending()  # memory hit
        assert len(fake.catalog_calls()) == 1
        clocks.advance(2)  # 86401 s after the fetch: memory and disk are both stale
        refreshed = nfl.get_fantasy_trending()["data"]
        assert len(fake.catalog_calls()) == 2
        assert refreshed["source"]["players_fetched_at"] == "2026-10-06T12:00:01Z"

    @pytest.mark.parametrize(
        "record",
        [
            b"not json",
            b"\xff\xfe",
            b'{"schema": 1, "fetched_at": "2026-10-05T11:00:00Z", "index": {"90001"',
            [],
            _disk_record(schema=2),
            _disk_record(schema=True),
            {"fetched_at": "2026-10-05T11:00:00Z", "index": _disk_record()["index"]},
            _disk_record(fetched_at="2026-10-04T12:00:00Z"),  # exactly 24 h old: expired
            _disk_record(fetched_at="2026-10-01T00:00:00Z"),
            _disk_record(fetched_at="2026-10-05T12:00:01Z"),  # in the future
            _disk_record(fetched_at="yesterday"),
            _disk_record(fetched_at=1790000000),
            _disk_record(fetched_at=None),
            _disk_record(index={}),
            _disk_record(index=[]),
            _disk_record(index={"90001": "Disk Name"}),
            _disk_record(index={"90001": {"name": "Disk Name", "team": "DSK"}}),
            _disk_record(index={"90001": {"name": "Disk Name", "team": "DSK", "position": "RB", "age": 30}}),
            _disk_record(index={"90001": {"name": 7, "team": "DSK", "position": "RB"}}),
            _disk_record(index={"90001": {"name": "", "team": "DSK", "position": "RB"}}),
            _disk_record(index={"90001": {"name": " Disk Name ", "team": "DSK", "position": "RB"}}),
            _disk_record(index={"error": {"name": None, "team": None, "position": None}}),
        ],
    )
    def test_unusable_disk_cache_is_a_miss(self, fake, clocks, cache_home, record):
        path = _write_disk(cache_home, record)
        data = nfl.get_fantasy_trending()["data"]
        assert len(fake.catalog_calls()) == 1
        assert data["players"][0]["name"] == "Test Runner"
        assert data["source"]["players_fetched_at"] == "2026-10-05T12:00:00Z"
        # The fresh fetch replaced the bad file.
        assert json.loads(path.read_text())["fetched_at"] == "2026-10-05T12:00:00Z"

    def test_unreadable_disk_cache_is_a_miss(self, fake, clocks, cache_home):
        _disk_path(cache_home).mkdir(parents=True)  # a directory where the file should be
        data = nfl.get_fantasy_trending()["data"]
        assert data["catalog_status"] == "loaded"
        assert len(fake.catalog_calls()) == 1

    def test_failed_atomic_write_keeps_the_read_and_claims_no_cache(self, fake, clocks, cache_home, monkeypatch):
        def refuse(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(_sleeper.os, "replace", refuse)
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        assert result["data"]["catalog_status"] == "loaded"
        assert "warnings" not in result["data"]
        cache_dir = _disk_path(cache_home).parent
        assert list(cache_dir.iterdir()) == []  # neither the file nor a stray temp file
        # Nothing was cached on disk, so a new process fetches again.
        _espn_base._cache.clear()
        nfl.get_fantasy_trending()
        assert len(fake.catalog_calls()) == 2

    def test_unwritable_cache_home_keeps_the_read(self, fake, clocks, monkeypatch, tmp_path):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("")
        monkeypatch.setenv("XDG_CACHE_HOME", str(blocker))
        result = nfl.get_fantasy_trending()
        assert result["status"] is True
        assert result["data"]["catalog_status"] == "loaded"

    def test_failed_fetch_leaves_no_disk_cache(self, fake, cache_home):
        fake.catalog_err = {"error": True, "status_code": 503, "message": "HTTP 503"}
        nfl.get_fantasy_trending()
        assert not _disk_path(cache_home).exists()

    def test_cache_path_follows_xdg_then_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        assert _sleeper._catalog_cache_path() == str(tmp_path / "xdg" / "sports-skills" / "sleeper" / "players-nfl.json")
        # An empty XDG_CACHE_HOME falls back to ~/.cache, never a relative path.
        monkeypatch.setenv("XDG_CACHE_HOME", "")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        assert _sleeper._catalog_cache_path() == str(tmp_path / "home" / ".cache" / "sports-skills" / "sleeper" / "players-nfl.json")


# ── Record / replay ────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, body):
        self._body = body
        self.headers = {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeNetwork:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None, context=None):
        self.calls.append(req.full_url)
        if "/trending/" in req.full_url:
            return _FakeResponse(json.dumps(TRENDING).encode())
        return _FakeResponse(json.dumps(CATALOG).encode())


def _no_urlopen(req, timeout=None, context=None):
    raise AssertionError(f"network access during replay: {req.full_url}")


class TestReplay:
    def test_record_bypasses_a_warm_cache_and_replay_needs_no_network(self, monkeypatch, tmp_path):
        net = _FakeNetwork()
        monkeypatch.setattr(urllib.request, "urlopen", net)
        live = nfl.get_fantasy_trending()
        assert len(net.calls) == 2
        assert _sleeper_cache_keys()

        # Record mode must hit the network (and record) despite the warm cache.
        monkeypatch.setenv(_replay.MODE_ENV, "record")
        monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
        recorded = nfl.get_fantasy_trending()
        assert len(net.calls) == 4
        assert recorded["data"]["players"] == live["data"]["players"]
        assert len(list(tmp_path.rglob("*.json"))) == 2

        # Replay must read the recordings, not the warm in-process cache.
        monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
        monkeypatch.setenv(_replay.MODE_ENV, "replay")
        replayed = nfl.get_fantasy_trending()
        assert replayed["status"] is True
        assert replayed["data"]["players"] == live["data"]["players"]
        assert any(_replay.MODE_ENV in w for w in replayed["data"]["warnings"])

    def test_record_mode_does_not_populate_the_cache(self, monkeypatch, tmp_path):
        monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork())
        monkeypatch.setenv(_replay.MODE_ENV, "record")
        monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
        assert nfl.get_fantasy_trending()["status"] is True
        assert _sleeper_cache_keys() == []

    def test_record_and_replay_neither_read_nor_write_the_disk_cache(self, monkeypatch, tmp_path, cache_home):
        disk = _write_disk(cache_home, _disk_record(fetched_at=_sleeper._timestamp()))
        before = disk.read_bytes()
        net = _FakeNetwork()
        monkeypatch.setattr(urllib.request, "urlopen", net)
        monkeypatch.setenv(_replay.MODE_ENV, "record")
        monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
        recorded = nfl.get_fantasy_trending()
        assert len(net.calls) == 2  # the fresh disk catalog was not used
        assert recorded["data"]["players"][0]["name"] == "Test Runner"

        monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
        monkeypatch.setenv(_replay.MODE_ENV, "replay")
        replayed = nfl.get_fantasy_trending()
        assert replayed["data"]["players"][0]["name"] == "Test Runner"
        assert disk.read_bytes() == before
        assert [p.name for p in disk.parent.iterdir()] == [disk.name]

    def test_record_mode_writes_no_disk_cache(self, monkeypatch, tmp_path, cache_home):
        monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork())
        monkeypatch.setenv(_replay.MODE_ENV, "record")
        monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
        assert nfl.get_fantasy_trending()["status"] is True
        assert list(cache_home.iterdir()) == []

    def test_replay_miss_is_reported_not_served_from_cache(self, monkeypatch, tmp_path):
        monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork())
        assert nfl.get_fantasy_trending()["status"] is True  # warms the live cache

        monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
        monkeypatch.setenv(_replay.MODE_ENV, "replay")
        monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
        result = nfl.get_fantasy_trending()
        assert result["status"] is False
        assert result.get("replay_miss") is True
        assert "Sleeper trending request failed" in result["message"]


# ── Parameter validation ───────────────────────────────────────────────────────


class TestValidation:
    @pytest.mark.parametrize(
        ("kwargs", "param"),
        [
            ({"trend_type": "trade"}, "trend_type"),
            ({"trend_type": ""}, "trend_type"),
            ({"trend_type": 1}, "trend_type"),
            ({"trend_type": ["add"]}, "trend_type"),
            ({"lookback_hours": True}, "lookback_hours"),
            ({"lookback_hours": False}, "lookback_hours"),
            ({"lookback_hours": 24.0}, "lookback_hours"),
            ({"lookback_hours": 1.5}, "lookback_hours"),
            ({"lookback_hours": float("inf")}, "lookback_hours"),
            ({"lookback_hours": float("nan")}, "lookback_hours"),
            ({"lookback_hours": 0}, "lookback_hours"),
            ({"lookback_hours": -1}, "lookback_hours"),
            ({"lookback_hours": 169}, "lookback_hours"),
            ({"lookback_hours": "24.0"}, "lookback_hours"),
            ({"lookback_hours": "-5"}, "lookback_hours"),
            ({"lookback_hours": "abc"}, "lookback_hours"),
            ({"lookback_hours": ""}, "lookback_hours"),
            ({"lookback_hours": [24]}, "lookback_hours"),
            ({"limit": True}, "limit"),
            ({"limit": 10.0}, "limit"),
            ({"limit": 0}, "limit"),
            ({"limit": 101}, "limit"),
            ({"limit": "1e2"}, "limit"),
            ({"limit": 10**20}, "limit"),
        ],
    )
    def test_invalid_params_fail_before_any_request(self, fake, kwargs, param):
        result = nfl.get_fantasy_trending(**kwargs)
        assert result["status"] is False
        assert result["data"] is None
        assert result["message"].startswith(param)
        assert fake.calls == []

    def test_bounds_are_inclusive(self, fake):
        assert nfl.get_fantasy_trending(lookback_hours=1, limit=1)["status"] is True
        assert nfl.get_fantasy_trending(lookback_hours=168, limit=100)["status"] is True

    def test_digit_strings_are_accepted(self, fake):
        data = nfl.get_fantasy_trending(lookback_hours=" 48 ", limit="5")["data"]
        assert data["lookback_hours"] == 48
        assert data["limit"] == 5
        assert fake.trending_calls()[0].endswith("lookback_hours=48&limit=5")

    def test_none_means_default(self, fake):
        data = nfl.get_fantasy_trending(trend_type=None, lookback_hours=None, limit=None)["data"]
        assert (data["trend_type"], data["lookback_hours"], data["limit"]) == ("add", 24, 10)


# ── CLI and discovery ──────────────────────────────────────────────────────────


class TestCli:
    def test_registered_with_optional_params(self):
        entry = _REGISTRY["nfl"]["get_fantasy_trending"]
        assert entry.get("required", []) == []
        assert set(entry["optional"]) == {"trend_type", "lookback_hours", "limit"}

    def test_schema_describes_every_param(self):
        tools = {t["name"]: t for t in _generate_schema("nfl")["tools"]}
        tool = tools["nfl_get_fantasy_trending"]
        assert "Sleeper" in tool["description"]
        props = tool["parameters"]["properties"]
        assert set(props) == {"trend_type", "lookback_hours", "limit"}
        assert all(prop.get("description") for prop in props.values())
        assert props["lookback_hours"]["type"] == "integer"

    def test_cli_invocation(self, fake, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            ["sports-skills", "nfl", "get_fantasy_trending", "--trend_type=drop", "--lookback_hours=48", "--limit=5"],
        )
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is True
        assert payload["data"]["trend_type"] == "drop"
        assert payload["data"]["lookback_hours"] == 48
        assert payload["data"]["limit"] == 5
        assert fake.trending_calls() == [
            "https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours=48&limit=5"
        ]

    def test_cli_invalid_value_is_structured(self, fake, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["sports-skills", "nfl", "get_fantasy_trending", "--lookback_hours=1.5"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is False
        assert "lookback_hours" in payload["message"]
        assert fake.calls == []

    def test_module_listing_shows_command(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["sports-skills", "nfl"])
        main()
        assert "get_fantasy_trending [--trend_type=<value>]" in capsys.readouterr().out

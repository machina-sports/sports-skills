"""Record/replay for providers that bypass the shared ``_http_fetch``.

nflverse, FastF1, Kalshi, Polymarket, OpenDota/Leaguepedia, Cricsheet, Nevobo,
TFRRS/The Stride Report, TheSportsDB, ProphetX, openfootball and Google News.

Each provider is recorded against a fake upstream, then replayed with sockets
blocked; the public tool function must return the identical result.
"""

import importlib.util
import inspect
import io
import json
import os
import pathlib
import socket
import sys
import urllib.error
import urllib.request
import zipfile

import feedparser
import pandas as pd
import pytest

from sports_skills import (
    _espn_base,
    _replay,
    cricket,
    esports,
    football,
    kalshi,
    metadata,
    news,
    nfl,
    polymarket,
    prophetx,
    volleyball,
    xctf,
)
from sports_skills.esports import _connector as esports_conn
from sports_skills.football import _connector as football_conn
from sports_skills.kalshi import _connector as kalshi_conn
from sports_skills.metadata import _connector as metadata_conn
from sports_skills.nfl import _nflverse
from sports_skills.polymarket import _connector as polymarket_conn
from sports_skills.prophetx import _connector as prophetx_conn
from sports_skills.volleyball import _nevobo
from sports_skills.xctf import _connector as xctf_conn

_CACHES = (
    kalshi_conn._cache,
    polymarket_conn._cache,
    esports_conn._cache,
    metadata_conn._cache,
    prophetx_conn._cache,
    _nevobo._cache,
    xctf_conn._cache,
    football_conn._cache,
    _espn_base._cache,
)


def _clear_caches():
    for cache in _CACHES:
        cache.clear()


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
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None, context=None):
        url = req.full_url
        self.calls.append(url)
        for fragment, outcome in self.routes.items():
            if fragment in url:
                if isinstance(outcome, int):
                    raise urllib.error.HTTPError(url, outcome, "err", {}, io.BytesIO(b"upstream says no"))
                return _FakeResponse(outcome)
        raise urllib.error.HTTPError(url, 404, "not found", {}, io.BytesIO(b""))


def _no_urlopen(req, timeout=None, context=None):
    raise AssertionError(f"network access during replay: {req.full_url}")


@pytest.fixture
def no_sockets(monkeypatch):
    """Fail any attempt to open a network connection, whatever library makes it."""

    def refuse(*args, **kwargs):
        raise AssertionError(f"network access during replay: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path_factory):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    monkeypatch.delenv(_replay.DIR_ENV, raising=False)
    # Cricsheet keeps an on-disk cache; never share the user's.
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("xdg")))
    _allow_waits(monkeypatch)
    _clear_caches()
    yield
    _clear_caches()


_WAITS = (
    (kalshi_conn._RateLimiter, "acquire"),
    (polymarket_conn._RateLimiter, "acquire"),
    (esports_conn._RateLimiter, "acquire"),
    (metadata_conn._RateLimiter, "acquire"),
    (prophetx_conn._RateLimiter, "acquire"),
    (football_conn._RateLimiter, "acquire"),
    (_espn_base.RateLimiter, "acquire"),
    (_nevobo, "_throttle"),
    (xctf_conn, "_throttle"),
)


def _allow_waits(monkeypatch):
    for owner, name in _WAITS:
        monkeypatch.setattr(owner, name, lambda *a, **k: None)


def _refuse_waits(monkeypatch):
    """Replay must not wait on a rate limiter or throttle."""

    def refuse(*args, **kwargs):
        raise AssertionError("rate-limit wait during replay")

    for owner, name in _WAITS:
        monkeypatch.setattr(owner, name, refuse)


def _set_mode(monkeypatch, mode, directory=None):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    if directory is not None:
        monkeypatch.setenv(_replay.DIR_ENV, str(directory))


def _replay_mode(monkeypatch, directory):
    """Switch to replay and drop the in-process caches, as a fresh run would."""
    _clear_caches()
    _set_mode(monkeypatch, "replay", directory)


needs_parquet = pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None, reason="frame replay stores Parquet and needs pyarrow"
)


# ============================================================
# Generic frame layer
# ============================================================


def _frame():
    return pd.DataFrame(
        {
            "game_id": ["2024_05_A", "2024_05_B"],
            "week": [5, 5],
            "spread_line": [3.5, float("nan")],
            "kickoff": pd.to_datetime(["2024-10-06 13:00", "2024-10-06 16:25"]),
        }
    )


@needs_parquet
def test_frame_off_mode_calls_live_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    df = _frame()

    assert _replay.frame("ns", "loader", {"season": 2024}, lambda: df) is df
    assert list(tmp_path.iterdir()) == []


@needs_parquet
def test_frame_record_then_replay_round_trips(monkeypatch, tmp_path, no_sockets):
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = _replay.frame("ns", "loader", {"season": 2024}, _frame, provider="pandas")

    _set_mode(monkeypatch, "replay", tmp_path)
    replayed = _replay.frame("ns", "loader", {"season": 2024}, lambda: pytest.fail("live load in replay"))

    pd.testing.assert_frame_equal(replayed, recorded)
    parquet_path, sidecar_path = _replay.frame_paths(str(tmp_path), _replay.frame_key("ns", "loader", {"season": 2024}))
    with open(sidecar_path, encoding="utf-8") as handle:
        sidecar = json.load(handle)
    assert sidecar["schema_version"] == _replay.FRAME_SCHEMA_VERSION
    assert (sidecar["namespace"], sidecar["loader"], sidecar["args"]) == ("ns", "loader", {"season": 2024})
    assert (sidecar["rows"], sidecar["columns"]) == (2, 4)
    assert sidecar["provider"] == "pandas" and sidecar["provider_version"] == pd.__version__
    assert sidecar["inexact_columns"] == []
    assert sidecar["recorded_at"].endswith("Z") and len(sidecar["parquet_sha256"]) == 64


def test_frame_key_ignores_arg_order():
    assert _replay.frame_key("ns", "l", {"a": 1, "b": 2}) == _replay.frame_key("ns", "l", {"b": 2, "a": 1})
    assert _replay.frame_key("ns", "l", {"a": 1}) != _replay.frame_key("ns", "l", {"a": 2})


@needs_parquet
def test_frame_miss_raises_replay_miss(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "replay", tmp_path)
    with pytest.raises(_replay.ReplayFailure) as info:
        _replay.frame("ns", "loader", {"season": 1999}, lambda: pytest.fail("live load in replay"))
    assert info.value.error["replay_miss"] is True
    assert "ns.loader" in info.value.error["message"]


@needs_parquet
def test_frame_loader_exception_is_not_recorded(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "record", tmp_path)

    def boom():
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError):
        _replay.frame("ns", "loader", {}, boom)
    assert not any(tmp_path.rglob("*.json"))


@needs_parquet
def test_frame_missing_parquet_is_replay_error(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "record", tmp_path)
    _replay.frame("ns", "loader", {}, _frame)
    parquet_path, _ = _replay.frame_paths(str(tmp_path), _replay.frame_key("ns", "loader", {}))
    os.unlink(parquet_path)

    _set_mode(monkeypatch, "replay", tmp_path)
    with pytest.raises(_replay.ReplayFailure) as info:
        _replay.frame("ns", "loader", {}, lambda: pytest.fail("live load in replay"))
    assert info.value.error["replay_error"] is True


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_frame_without_pyarrow_is_a_clear_error_before_any_load(monkeypatch, tmp_path, mode):
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    _set_mode(monkeypatch, mode, tmp_path)
    with pytest.raises(_replay.ReplayFailure) as info:
        _replay.frame("ns", "loader", {}, lambda: pytest.fail("loaded without a way to store it"))
    assert info.value.error["replay_error"] is True
    assert "pyarrow" in info.value.error["message"]


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_frame_missing_directory_is_a_config_error(monkeypatch, mode):
    _set_mode(monkeypatch, mode)
    with pytest.raises(_replay.ReplayFailure) as info:
        _replay.frame("ns", "loader", {}, lambda: pytest.fail("live load without a directory"))
    assert _replay.DIR_ENV in info.value.error["message"]


# ============================================================
# nflverse
# ============================================================


class _FakeNflreadpy:
    """nflreadpy stand-in returning pandas frames and counting loads."""

    def __init__(self):
        self.calls = []

    def load_schedules(self, seasons):
        self.calls.append(("schedules", seasons))
        return pd.DataFrame(
            {
                "game_id": ["2024_05_BAL_CIN", "2024_05_NYG_SEA", "2024_06_X_Y"],
                "season": [2024, 2024, 2024],
                "week": [5, 5, 6],
                "home_team": ["CIN", "SEA", "Y"],
                "away_team": ["BAL", "NYG", "X"],
                "home_score": [38.0, 20.0, float("nan")],
                "away_score": [41.0, 29.0, float("nan")],
                "espn": [401671789.0, 401671790.0, None],
                "gameday": ["2024-10-06", "2024-10-06", "2024-10-13"],
            }
        )

    def load_player_stats(self, seasons, summary_level="reg"):
        self.calls.append(("player_stats", seasons, summary_level))
        return pd.DataFrame(
            {
                "player_id": ["00-1", "00-2"],
                "player_name": ["L.Jackson", "J.Burrow"],
                "position": ["QB", "QB"],
                "recent_team": ["BAL", "CIN"],
                "season": [2024, 2024],
                "week": [5, 5],
                "passing_yards": [348, 392],
                "passing_epa": [12.5, float("nan")],
            }
        )


class _ExplodingProvider:
    def __getattr__(self, name):
        raise AssertionError(f"nflverse provider called during replay: {name}")


def _use_provider(monkeypatch, provider):
    monkeypatch.setattr(_nflverse, "_load_provider", lambda: ("nflreadpy", provider))


@needs_parquet
@pytest.mark.parametrize(
    ("fn", "params"),
    [
        (nfl.get_nflverse_schedule, {"season": 2024, "week": 5}),
        (nfl.get_nflverse_player_stats, {"season": 2024, "week": 5, "team": "BAL"}),
    ],
)
def test_nflverse_replays_public_call_without_network(monkeypatch, tmp_path, no_sockets, fn, params):
    fake = _FakeNflreadpy()
    _use_provider(monkeypatch, fake)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = fn(**params)
    assert recorded["status"] is True and recorded["data"]["count"] > 0
    assert len(fake.calls) == 1
    assert len(list(tmp_path.rglob("*.parquet"))) == 1

    _use_provider(monkeypatch, _ExplodingProvider())
    _set_mode(monkeypatch, "replay", tmp_path)

    assert fn(**params) == recorded


@needs_parquet
def test_nflverse_off_mode_is_unchanged(monkeypatch, tmp_path):
    fake = _FakeNflreadpy()
    _use_provider(monkeypatch, fake)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    params = {"season": 2024, "week": 5}

    off = nfl.get_nflverse_schedule(**params)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = nfl.get_nflverse_schedule(**params)

    assert off == recorded
    assert off["data"]["events"][0]["espn_event_id"] == "401671789"


@needs_parquet
def test_nflverse_keys_by_data_arguments(monkeypatch, tmp_path):
    """Season and summary level both select a different frame."""
    _use_provider(monkeypatch, _FakeNflreadpy())
    _set_mode(monkeypatch, "record", tmp_path)
    nfl.get_nflverse_player_stats(season=2024, week=5)

    _use_provider(monkeypatch, _ExplodingProvider())
    _set_mode(monkeypatch, "replay", tmp_path)
    season_level = nfl.get_nflverse_player_stats(season=2024)
    other_season = nfl.get_nflverse_player_stats(season=2023, week=5)

    assert season_level["replay_miss"] is True
    assert other_season["replay_miss"] is True
    assert "player_stats" in season_level["message"] and '"summary_level": "reg"' in season_level["message"]


@needs_parquet
def test_nflverse_replay_miss_fails_closed_in_normal_error_shape(monkeypatch, tmp_path, no_sockets):
    _use_provider(monkeypatch, _ExplodingProvider())
    _set_mode(monkeypatch, "replay", tmp_path)

    result = nfl.get_nflverse_schedule(season=2024)

    assert result["status"] is False and result["replay_miss"] is True
    assert "nflverse.schedules" in result["message"]


@needs_parquet
def test_nflverse_tampered_parquet_fails_integrity(monkeypatch, tmp_path, no_sockets):
    _use_provider(monkeypatch, _FakeNflreadpy())
    _set_mode(monkeypatch, "record", tmp_path)
    nfl.get_nflverse_schedule(season=2024)
    (parquet,) = tmp_path.rglob("*.parquet")
    data = bytearray(parquet.read_bytes())
    data[len(data) // 2] ^= 0xFF
    parquet.write_bytes(bytes(data))

    _use_provider(monkeypatch, _ExplodingProvider())
    _set_mode(monkeypatch, "replay", tmp_path)
    result = nfl.get_nflverse_schedule(season=2024)

    assert result["status"] is False and result["replay_error"] is True
    assert "integrity" in result["message"]


def test_nflverse_loaders_keep_their_signatures():
    """The replay wrapper binds loader arguments by name; it must not hide them."""
    params = list(inspect.signature(_nflverse._load_player_stats).parameters)
    assert params == ["provider_name", "provider", "season", "summary_level"]


# ============================================================
# FastF1
# ============================================================


if importlib.util.find_spec("fastf1") is not None:
    from sports_skills import f1 as f1_api
    from sports_skills.f1 import _connector as f1

    fastf1 = f1.fastf1
    needs_fastf1 = pytest.mark.skipif(False, reason="")
else:  # pragma: no cover - fastf1 is a dev dependency
    needs_fastf1 = pytest.mark.skip(reason="fastf1 not installed")


def _schedule():
    return fastf1.events.EventSchedule(
        pd.DataFrame(
            {
                "RoundNumber": [0, 1, 2],
                "Country": ["Bahrain", "Bahrain", "Monaco"],
                "Location": ["Sakhir", "Sakhir", "Monaco"],
                "EventName": ["Pre-Season Testing", "Bahrain Grand Prix", "Monaco Grand Prix"],
                "EventDate": pd.to_datetime(["2024-02-23", "2024-03-02", "2024-05-26"]),
                "EventFormat": ["testing", "conventional", "conventional"],
            }
        )
    )


def _results():
    return fastf1.core.SessionResults(
        pd.DataFrame(
            {
                "DriverNumber": ["16", "81"],
                "Abbreviation": ["LEC", "PIA"],
                "FullName": ["Charles Leclerc", "Oscar Piastri"],
                "TeamName": ["Ferrari", "McLaren"],
                "TeamId": ["ferrari", "mclaren"],
                "Position": [1.0, 2.0],
                "GridPosition": [1.0, 2.0],
                "Status": ["Finished", "Finished"],
                "Points": [25.0, 18.0],
                "Time": pd.to_timedelta(["2:23:15.554", "0:00:07.152"]),
                "Q1": pd.to_timedelta(["0:01:11.584", None]),
            },
            index=["16", "81"],
        )
    )


def _laps():
    return fastf1.core.Laps(
        pd.DataFrame(
            {
                "Driver": ["LEC", "LEC", "PIA", "PIA"],
                "DriverNumber": ["16", "16", "81", "81"],
                "Team": ["Ferrari", "Ferrari", "McLaren", "McLaren"],
                "LapNumber": [1.0, 2.0, 1.0, 2.0],
                "LapTime": pd.to_timedelta(["0:01:20.1", "0:01:15.2", None, "0:01:15.9"]),
                "Sector1Time": pd.to_timedelta(["0:00:20", "0:00:19", "0:00:21", "0:00:19.5"]),
                "Sector2Time": pd.to_timedelta(["0:00:35", "0:00:34", "0:00:36", "0:00:34.4"]),
                "Sector3Time": pd.to_timedelta(["0:00:25.1", "0:00:22.2", "0:00:23", "0:00:22"]),
                "Compound": ["MEDIUM", "MEDIUM", "HARD", "HARD"],
                "TyreLife": [1.0, 2.0, 1.0, 2.0],
                "IsPersonalBest": [False, True, False, True],
                "Position": [1.0, 1.0, 2.0, 2.0],
                "PitInTime": pd.to_timedelta([None, None, "0:10:00", None]),
                "PitOutTime": pd.to_timedelta([None, None, None, "0:10:22"]),
            }
        )
    )


class _FakeSession:
    def __init__(self, year, event, session_type):
        self.year, self.event_name, self.session_type_arg = year, event, session_type
        self.event = pd.Series({"EventName": event}, name=8)
        self.loaded_laps = None

    def load(self, laps=True, telemetry=True, weather=True, messages=True):
        self.loaded_laps = laps
        self.results = _results()
        if laps:
            self.laps = _laps()

    def __str__(self):
        return f"{self.year} Season Round 8: {self.event_name} - {self.session_type_arg}"


class _FakeFastF1:
    def __init__(self):
        self.calls = []

    def get_event_schedule(self, year):
        self.calls.append(("schedule", year))
        return _schedule()

    def get_session(self, year, event, session_type):
        self.calls.append(("session", year, event, session_type))
        return _FakeSession(year, event, session_type)


def _use_fastf1(monkeypatch, fake):
    monkeypatch.setattr(fastf1, "get_event_schedule", fake.get_event_schedule)
    monkeypatch.setattr(fastf1, "get_session", fake.get_session)


def _refuse_fastf1(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"FastF1 called during replay: {args!r}")

    monkeypatch.setattr(fastf1, "get_event_schedule", refuse)
    monkeypatch.setattr(fastf1, "get_session", refuse)


_F1_CALLS = [
    ("get_race_results", {"year": 2024, "event": "Monaco"}),
    ("get_lap_data", {"year": 2024, "event": "Monaco Grand Prix", "driver": "LEC"}),
    ("get_session_data", {"session_year": 2024, "session_name": "Monaco Grand Prix", "session_type": "Q"}),
    ("get_race_schedule", {"year": 2024}),
    ("get_team_info", {"year": 2024}),
    ("get_pit_stops", {"year": 2024, "event": "Monaco Grand Prix"}),
]


@needs_fastf1
@needs_parquet
@pytest.mark.parametrize(("name", "params"), _F1_CALLS)
def test_fastf1_replays_public_call_without_network(monkeypatch, tmp_path, no_sockets, name, params):
    fn = getattr(f1_api, name)
    fake = _FakeFastF1()
    _use_fastf1(monkeypatch, fake)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = fn(**params)
    assert recorded["status"] is True, recorded
    assert fake.calls

    _refuse_fastf1(monkeypatch)
    _set_mode(monkeypatch, "replay", tmp_path)

    assert fn(**params) == recorded


@needs_fastf1
@needs_parquet
@pytest.mark.parametrize(("name", "params"), _F1_CALLS)
def test_fastf1_off_mode_matches_record_mode(monkeypatch, tmp_path, name, params):
    fn = getattr(f1_api, name)
    _use_fastf1(monkeypatch, _FakeFastF1())
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    off = fn(**params)
    assert list(tmp_path.iterdir()) == []

    _set_mode(monkeypatch, "record", tmp_path)
    assert fn(**params) == off


@needs_fastf1
@needs_parquet
def test_fastf1_replay_miss_fails_closed(monkeypatch, tmp_path, no_sockets):
    _refuse_fastf1(monkeypatch)
    _set_mode(monkeypatch, "replay", tmp_path)

    result = f1_api.get_race_results(year=2024, event="Monaco")

    assert result["status"] is False and result["replay_miss"] is True
    assert "fastf1.event_schedule" in result["message"]


@needs_fastf1
@needs_parquet
def test_fastf1_season_loop_does_not_skip_a_missing_race(monkeypatch, tmp_path, no_sockets):
    """Per-race loops swallow load errors; a replay miss must not be one of them,
    or a season aggregate would silently come back short."""
    _use_fastf1(monkeypatch, _FakeFastF1())
    _set_mode(monkeypatch, "record", tmp_path)
    f1_api.get_pit_stops(year=2024, event="Monaco Grand Prix")
    # Keep the schedule, drop every session frame.
    schedule_key = _replay.frame_key("fastf1", "event_schedule", {"year": 2024})
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.name.startswith(schedule_key):
            path.unlink()

    _refuse_fastf1(monkeypatch)
    _set_mode(monkeypatch, "replay", tmp_path)
    result = f1_api.get_pit_stops(year=2024, event="Monaco Grand Prix")

    assert result["status"] is False and result["replay_miss"] is True
    assert "session_results" in result["message"]


@needs_fastf1
@needs_parquet
def test_fastf1_tampered_parquet_fails_integrity(monkeypatch, tmp_path, no_sockets):
    _use_fastf1(monkeypatch, _FakeFastF1())
    _set_mode(monkeypatch, "record", tmp_path)
    f1_api.get_race_schedule(year=2024)
    (parquet,) = tmp_path.rglob("*.parquet")
    parquet.write_bytes(parquet.read_bytes() + b"x")

    _refuse_fastf1(monkeypatch)
    _set_mode(monkeypatch, "replay", tmp_path)
    result = f1_api.get_race_schedule(year=2024)

    assert result["status"] is False and result["replay_error"] is True
    assert "integrity" in result["message"]


# ============================================================
# Kalshi and Polymarket
# ============================================================


_KALSHI_SERIES = json.dumps({"series": [{"ticker": "KXNFLGAME", "title": "NFL Game"}]}).encode()
_GAMMA_EVENTS = json.dumps([{"id": "1", "title": "Chiefs vs Bills", "slug": "chiefs-bills", "markets": []}]).encode()
_CLOB_LAST = json.dumps({"price": "0.55", "side": "BUY"}).encode()


def _record_and_replay(monkeypatch, tmp_path, routes, call):
    net = _FakeNetwork(routes)
    monkeypatch.setattr(urllib.request, "urlopen", net)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = call()
    assert net.calls

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
    _replay_mode(monkeypatch, tmp_path)
    return recorded, call()


@pytest.mark.parametrize(
    ("routes", "call"),
    [
        ({"/series": _KALSHI_SERIES}, lambda: kalshi.get_series_list(category="Sports")),
        ({"/events": _GAMMA_EVENTS}, lambda: polymarket.get_sports_events(limit=5)),
        ({"/last-trade-price": _CLOB_LAST}, lambda: polymarket.get_last_trade_price(token_id="123")),
    ],
    ids=["kalshi-series", "polymarket-gamma", "polymarket-clob"],
)
def test_markets_replay_public_call_without_network(monkeypatch, tmp_path, no_sockets, routes, call):
    recorded, replayed = _record_and_replay(monkeypatch, tmp_path, routes, call)
    assert recorded["status"] is True, recorded
    assert replayed == recorded


def test_kalshi_deterministic_error_replays(monkeypatch, tmp_path, no_sockets):
    recorded, replayed = _record_and_replay(
        monkeypatch, tmp_path, {"/series/NOPE": 404}, lambda: kalshi.get_series(series_ticker="NOPE")
    )
    assert recorded["status"] is False
    assert replayed == recorded


@pytest.mark.parametrize(
    "call",
    [
        lambda: kalshi.get_series_list(),
        lambda: polymarket.get_sports_events(),
        lambda: polymarket.get_last_trade_price(token_id="123"),
    ],
    ids=["kalshi", "polymarket-gamma", "polymarket-clob"],
)
def test_markets_replay_miss_fails_closed(monkeypatch, tmp_path, no_sockets, call):
    _replay_mode(monkeypatch, tmp_path)

    result = call()

    assert result["status"] is False and result["replay_miss"] is True
    assert "Replay miss" in result["message"]


@pytest.mark.parametrize(
    ("module", "fetch"),
    [
        (kalshi, lambda url: kalshi_conn._http_fetch(url)),
        (polymarket_conn, lambda url: polymarket_conn._http_fetch(url, polymarket_conn._gamma_rate_limiter)),
    ],
    ids=["kalshi", "polymarket"],
)
def test_markets_off_mode_is_live_and_writes_nothing(monkeypatch, tmp_path, module, fetch):
    net = _FakeNetwork({"/x": b'{"ok": true}'})
    monkeypatch.setattr(urllib.request, "urlopen", net)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))

    assert fetch("https://example.test/x") == (b'{"ok": true}', None)
    assert len(net.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_markets_transient_errors_are_not_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/series": 503}))
    _set_mode(monkeypatch, "record", tmp_path)
    result = kalshi.get_series_list()

    assert result["status"] is False
    assert not any(tmp_path.rglob("*.json"))


def test_polymarket_trading_client_is_not_routed_through_replay():
    """Authenticated order paths use py_clob_client_v2 directly, never _replay."""
    from sports_skills.polymarket import _cli

    assert "_replay" not in inspect.getsource(_cli)


@needs_parquet
def test_frame_fill_serves_recorded_frames_and_records_only_missing(monkeypatch, tmp_path):
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = _replay.frame("ns", "loader", {"season": 2024}, _frame)
    parquet_path, _ = _replay.frame_paths(str(tmp_path), _replay.frame_key("ns", "loader", {"season": 2024}))
    before = pathlib.Path(parquet_path).read_bytes()

    _set_mode(monkeypatch, "fill", tmp_path)
    served = _replay.frame("ns", "loader", {"season": 2024}, lambda: pytest.fail("live load for a recorded frame"))
    pd.testing.assert_frame_equal(served, recorded)
    assert pathlib.Path(parquet_path).read_bytes() == before, "an existing frame is never rewritten"

    new = _replay.frame("ns", "loader", {"season": 2025}, _frame)
    pd.testing.assert_frame_equal(new, _frame())
    _set_mode(monkeypatch, "replay", tmp_path)
    pd.testing.assert_frame_equal(
        _replay.frame("ns", "loader", {"season": 2025}, lambda: pytest.fail("live")),
        _replay.frame("ns", "loader", {"season": 2024}, lambda: pytest.fail("live")),
    )


# ============================================================
# Long-tail providers (own urllib / feedparser / zip downloads)
# ============================================================


def _rss(*titles):
    items = "".join(
        f"<item><title>{t}</title><link>https://example.test/{i}</link>"
        f"<description>1. Team {t}, wedstr: 14, punten: 40&lt;br /&gt;2. Other, wedstr: 14, punten: 30</description>"
        f"<pubDate>Mon, 21 Sep 2026 10:00:00 GMT</pubDate></item>"
        for i, t in enumerate(titles)
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>{items}</channel></rss>'.encode()


def _cricsheet_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for match_id, date in (("1001", "2024-04-01"), ("1002", "2024-04-03")):
            info = {
                "dates": [date],
                "teams": ["Mumbai Indians", "Chennai Super Kings"],
                "season": "2024",
                "venue": "Wankhede",
                "outcome": {"winner": "Mumbai Indians"},
            }
            zf.writestr(f"{match_id}.json", json.dumps({"info": info, "innings": []}))
    return buffer.getvalue()


_NEVOBO_ROUTES = {
    "/competitie/poules": json.dumps(
        {
            "hydra:member": [
                {"@id": "/competitie/poules/nationale-competitie/competitie-eredivisie/nationale-competitie-eh-12"}
            ]
        }
    ).encode(),
    "/competitie/competities": json.dumps(
        {"hydra:member": [{"@id": "/competitie/competities/nationale-competitie/competitie-eredivisie"}]}
    ).encode(),
    "stand.rss": _rss("Standen"),
}

_PROPHETX_ROUTES = {
    "/v1/tournaments/1/events": json.dumps({"data": [{"id": 11, "name": "A v B", "scheduled": "2026-09-23T18:00:00Z"}]}).encode(),
    "/v1/tournaments/2/events": json.dumps({"data": [{"id": 22, "name": "C v D", "scheduled": "2026-09-23T19:00:00Z"}]}).encode(),
    "/v1/tournaments": json.dumps(
        {
            "data": {
                "tournaments": [
                    {"id": 1, "name": "NFL", "sport": {"id": 16, "name": "American Football"}},
                    {"id": 2, "name": "NCAAF", "sport": {"id": 16, "name": "American Football"}},
                ]
            }
        }
    ).encode(),
}

_OPENFOOTBALL = json.dumps(
    {
        "matches": [
            {"date": "2019-08-09", "team1": "Liverpool", "team2": "Norwich", "score": {"ft": [4, 1]}},
            {"date": "2019-08-10", "team1": "West Ham", "team2": "Man City", "score": {"ft": [0, 5]}},
        ]
    }
).encode()

_FOOTBALL_ROUTES = {"/standings": b"{}", "raw.githubusercontent.com/openfootball": _OPENFOOTBALL}

_TFRRS_PROFILE = (
    b"<html><h3 class='panel-title'>Jane Hedengren</h3>"
    b"<table><tr><td>1500</td><td>4:05.12</td></tr></table></html>"
)

# (id, routes, public call) — each call exercises one provider end to end.
_LONGTAIL = [
    (
        "opendota",
        {"/proMatches": json.dumps([{"match_id": 1, "radiant_name": "OG", "dire_name": "Liquid"}]).encode()},
        lambda: esports.get_pro_matches(limit=5),
    ),
    (
        "leaguepedia",
        {
            "lol.fandom.com": json.dumps(
                {"cargoquery": [{"title": {"Name": "LCK 2026", "DateStart": "2026-01-14", "DateStart__precision": "0"}}]}
            ).encode()
        },
        lambda: esports.lol_cargo_query(tables="Tournaments", fields="Name,DateStart", limit=5),
    ),
    ("cricsheet", {"ipl_json.zip": _cricsheet_zip()}, lambda: cricket.get_matches(competition="ipl", season=2024)),
    ("nevobo", _NEVOBO_ROUTES, lambda: volleyball.get_standings(competition_id="nevobo-eredivisie-heren")),
    (
        "tfrrs",
        {"/athletes/": _TFRRS_PROFILE},
        lambda: xctf.get_athlete_profile(athlete_id="9230145", school="BYU", name="Jane_Hedengren"),
    ),
    ("stride", {"blog-feed.xml": _rss("Pre-Nats preview", "Week 3 rankings")}, lambda: xctf.get_news(limit=5)),
    (
        "thesportsdb",
        {"searchteams.php": json.dumps({"teams": [{"idTeam": "133604", "strTeam": "Arsenal"}]}).encode()},
        lambda: metadata.search_teams(query="Arsenal"),
    ),
    ("prophetx", _PROPHETX_ROUTES, lambda: prophetx.get_tournaments(limit=10)),
    ("openfootball", _FOOTBALL_ROUTES, lambda: football.get_season_standings(season_id="premier-league-2019")),
    ("google-news", {"news.google.com": _rss("Arsenal win", "Saka injury")}, lambda: news.fetch_feed(query="arsenal")),
]

_LONGTAIL_IDS = [case[0] for case in _LONGTAIL]


def _record_longtail(monkeypatch, tmp_path, routes, call):
    net = _FakeNetwork(routes)
    monkeypatch.setattr(urllib.request, "urlopen", net)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = call()
    assert net.calls
    return recorded, net


def _replay_longtail(monkeypatch, tmp_path, call):
    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
    _refuse_waits(monkeypatch)
    _replay_mode(monkeypatch, tmp_path)
    return call()


@pytest.mark.parametrize(("name", "routes", "call"), _LONGTAIL, ids=_LONGTAIL_IDS)
def test_longtail_replays_public_call_without_network(monkeypatch, tmp_path, no_sockets, name, routes, call):
    recorded, net = _record_longtail(monkeypatch, tmp_path, routes, call)
    assert recorded["status"] is True, recorded
    assert recorded["data"], recorded
    assert len(list(tmp_path.rglob("*.json"))) == len(set(net.calls))

    assert _replay_longtail(monkeypatch, tmp_path, call) == recorded


@pytest.mark.parametrize(("name", "routes", "call"), _LONGTAIL, ids=_LONGTAIL_IDS)
def test_longtail_replay_miss_fails_closed(monkeypatch, tmp_path, no_sockets, name, routes, call):
    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True, result
    assert "Replay miss" in result["message"]


def test_cricsheet_zip_is_recorded_as_base64_and_skips_the_disk_cache(monkeypatch, tmp_path, no_sockets):
    """The zip is binary; replay must serve the recording, not a cached download."""
    call = lambda: cricket.get_matches(competition="ipl")  # noqa: E731
    recorded, _ = _record_longtail(monkeypatch, tmp_path, {"ipl_json.zip": _cricsheet_zip()}, call)
    (entry,) = tmp_path.rglob("*.json")
    assert json.loads(entry.read_text())["body_encoding"] == "base64"
    # A fresh live-cache copy with different content must not leak into replay.
    cache = os.path.join(os.environ["XDG_CACHE_HOME"], "sports-skills", "cricsheet", "ipl_json.zip")
    with zipfile.ZipFile(cache, "w") as zf:
        zf.writestr("9999.json", json.dumps({"info": {"dates": ["2030-01-01"]}}))

    replayed = _replay_longtail(monkeypatch, tmp_path, call)

    assert replayed == recorded and replayed["data"]["count"] == 2


def _drop_entry(directory, url):
    os.unlink(_replay.entry_path(str(directory), _replay.request_key(url)))


def test_prophetx_scan_does_not_skip_a_missing_page(monkeypatch, tmp_path, no_sockets):
    """Composite scans skip a failing tournament; a replay miss must fail the call,
    or the answer would silently come back shorter than the recording."""
    call = lambda: prophetx.get_todays_events()  # noqa: E731
    recorded, net = _record_longtail(monkeypatch, tmp_path, _PROPHETX_ROUTES, call)
    assert recorded["status"] is True
    (missing,) = [url for url in net.calls if "/v1/tournaments/2/events" in url]
    _drop_entry(tmp_path, missing)

    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True


def test_xctf_meet_does_not_skip_a_missing_compiled_page(monkeypatch, tmp_path, no_sockets):
    call = lambda: xctf.get_meet_results(meet_id="95890", slug="BU_Dual")  # noqa: E731
    recorded, net = _record_longtail(monkeypatch, tmp_path, {"/results/": b"<h3 class='panel-title'>BU Dual</h3>"}, call)
    assert recorded["status"] is True
    _drop_entry(tmp_path, f"{xctf_conn._BASE}/results/95890/m/BU_Dual")

    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True


def test_openfootball_miss_is_not_reported_as_no_data(monkeypatch, tmp_path, no_sockets):
    """openfootball is a silent fallback (None = no file); a replay gap must not
    turn into a "No standings found" answer."""
    call = lambda: football.get_season_standings(season_id="premier-league-2019")  # noqa: E731
    _, net = _record_longtail(monkeypatch, tmp_path, _FOOTBALL_ROUTES, call)
    (of_url,) = [url for url in net.calls if "openfootball" in url]
    _drop_entry(tmp_path, of_url)

    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True


def test_openfootball_missing_file_replays_as_no_data(monkeypatch, tmp_path, no_sockets):
    """A 404 is a deterministic answer ("no file for this season") and replays as one."""
    call = lambda: football.get_season_standings(season_id="premier-league-2019")  # noqa: E731
    recorded, _ = _record_longtail(monkeypatch, tmp_path, {"/standings": b"{}"}, call)
    assert recorded["data"]["standings"] == []

    assert _replay_longtail(monkeypatch, tmp_path, call) == recorded


def test_nevobo_poule_resolution_miss_fails_closed(monkeypatch, tmp_path, no_sockets):
    """Poule resolution falls back to a configured path on errors; a replay miss
    there must surface rather than silently use the fallback."""
    call = lambda: volleyball.get_standings(competition_id="nevobo-eredivisie-heren")  # noqa: E731
    _, net = _record_longtail(monkeypatch, tmp_path, _NEVOBO_ROUTES, call)
    (poules_url,) = [url for url in net.calls if "/competitie/poules" in url and "stand.rss" not in url]
    _drop_entry(tmp_path, poules_url)

    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True


def test_nevobo_competitions_miss_is_not_a_partial_success(monkeypatch, tmp_path, no_sockets):
    result = _replay_longtail(monkeypatch, tmp_path, lambda: volleyball.get_competitions())

    assert result["status"] is False and result["replay_miss"] is True


@pytest.mark.parametrize(
    ("routes", "call"),
    [
        ({"searchteams.php": 404}, lambda: metadata.search_teams(query="Nope")),
        ({"/athletes/": 404}, lambda: xctf.get_athlete_profile(athlete_id="1", school="X", name="Y")),
        ({"/v1/tournaments": 404}, lambda: prophetx.get_tournaments()),
        ({"/matches/": 404}, lambda: esports.get_match(match_id="1")),
        ({"ipl_json.zip": 404}, lambda: cricket.get_matches(competition="ipl")),
        ({"stand.rss": 404, **{k: v for k, v in _NEVOBO_ROUTES.items() if k != "stand.rss"}},
         lambda: volleyball.get_standings(competition_id="nevobo-eredivisie-heren")),
        ({"news.google.com": 404}, lambda: news.fetch_feed(query="x")),
    ],
    ids=["thesportsdb", "tfrrs", "prophetx", "opendota", "cricsheet", "nevobo-rss", "google-news"],
)
def test_longtail_deterministic_error_replays(monkeypatch, tmp_path, no_sockets, routes, call):
    recorded, _ = _record_longtail(monkeypatch, tmp_path, routes, call)
    assert recorded["status"] is False
    assert not recorded.get("replay_miss")

    assert _replay_longtail(monkeypatch, tmp_path, call) == recorded


@pytest.mark.parametrize(
    ("name", "routes", "call"),
    [case for case in _LONGTAIL if case[0] not in ("nevobo", "stride", "google-news")],
    ids=[i for i in _LONGTAIL_IDS if i not in ("nevobo", "stride", "google-news")],
)
def test_longtail_off_mode_is_live_and_writes_nothing(monkeypatch, tmp_path, name, routes, call):
    net = _FakeNetwork(routes)
    monkeypatch.setattr(urllib.request, "urlopen", net)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    off = call()
    assert net.calls
    assert list(tmp_path.iterdir()) == []

    _clear_caches()
    _set_mode(monkeypatch, "record", tmp_path)
    assert call() == off


@pytest.mark.parametrize(
    ("routes", "call", "body"),
    [
        (_NEVOBO_ROUTES, lambda: volleyball.get_standings(competition_id="nevobo-eredivisie-heren"), _rss("Standen")),
        ({}, lambda: xctf.get_news(limit=5), _rss("Pre-Nats preview")),
        ({}, lambda: news.fetch_feed(query="arsenal"), _rss("Arsenal win")),
    ],
    ids=["nevobo", "stride", "google-news"],
)
def test_feeds_off_mode_still_lets_feedparser_fetch(monkeypatch, tmp_path, routes, call, body):
    """Off mode hands feedparser the URL, exactly as before; record parses bytes."""
    real_parse = feedparser.parse
    seen = []

    def spy(source, *args, **kwargs):
        seen.append(source)
        return real_parse(body if isinstance(source, str) else source, *args, **kwargs)

    monkeypatch.setattr(feedparser, "parse", spy)
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork(routes))
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    off = call()
    assert off["status"] is True, off
    assert seen and all(isinstance(s, str) and s.startswith("https://") for s in seen)
    assert list(tmp_path.iterdir()) == []

    _clear_caches()
    seen.clear()
    feed_routes = {**routes, "stand.rss": body, "blog-feed.xml": body, "news.google.com": body}
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork(feed_routes))
    _set_mode(monkeypatch, "record", tmp_path)
    assert call() == off
    assert seen and all(isinstance(s, bytes) for s in seen)


def test_news_local_feed_is_not_routed_through_replay(monkeypatch, tmp_path, no_sockets):
    """A local file is not network; replay mode still reads it directly."""
    feed_file = tmp_path / "feed.xml"
    feed_file.write_bytes(_rss("Local item"))
    _replay_mode(monkeypatch, tmp_path / "replay")

    result = news.fetch_items(url=str(feed_file))

    assert result["status"] is True and result["data"]["items"][0]["title"] == "Local item"


def test_metadata_off_mode_error_shape_is_unchanged(monkeypatch, tmp_path):
    """status_code is added only so _replay can record a 4xx; callers never see it."""
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"searchteams.php": 404}))

    assert metadata_conn._http_fetch(f"{metadata_conn.BASE_URL}/searchteams.php?t=x") == {
        "error": True,
        "message": "HTTP 404: err",
    }


def test_leaguepedia_in_body_throttle_is_not_recorded(monkeypatch, tmp_path, no_sockets):
    """Leaguepedia throttles with HTTP 200 + {"error": {"code": "ratelimited"}}.
    That is transient: recording it would freeze an outage into the fixture."""
    throttled = json.dumps({"error": {"code": "ratelimited", "info": "You've exceeded your rate limit."}}).encode()
    call = lambda: esports.get_lol_tournaments(limit=3)  # noqa: E731
    recorded, _ = _record_longtail(monkeypatch, tmp_path, {"lol.fandom.com": throttled}, call)
    assert recorded["status"] is False and "rate limit" in recorded["message"]
    assert not any(tmp_path.rglob("*.json"))

    result = _replay_longtail(monkeypatch, tmp_path, call)

    assert result["status"] is False and result["replay_miss"] is True


def test_leaguepedia_in_body_cargo_error_is_still_recorded(monkeypatch, tmp_path, no_sockets):
    """A bad-field error is deterministic, so it records and replays like data."""
    bad_field = json.dumps({"error": {"code": "internal_api_error_MWException", "info": "No field named X"}}).encode()
    call = lambda: esports.lol_cargo_query(tables="Tournaments", fields="X")  # noqa: E731
    recorded, _ = _record_longtail(monkeypatch, tmp_path, {"lol.fandom.com": bad_field}, call)

    assert _replay_longtail(monkeypatch, tmp_path, call) == recorded


@pytest.mark.parametrize(("name", "routes", "call"), _LONGTAIL, ids=_LONGTAIL_IDS)
def test_longtail_fill_serves_recorded_without_network(monkeypatch, tmp_path, no_sockets, name, routes, call):
    recorded, _ = _record_longtail(monkeypatch, tmp_path, routes, call)
    entries = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)
    _clear_caches()
    _set_mode(monkeypatch, "fill", tmp_path)

    assert call() == recorded
    assert {p: p.read_bytes() for p in tmp_path.rglob("*.json")} == entries


def test_leaguepedia_throttle_is_not_recorded_in_fill_mode(monkeypatch, tmp_path, no_sockets):
    throttled = json.dumps({"error": {"code": "ratelimited", "info": "You've exceeded your rate limit."}}).encode()
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"lol.fandom.com": throttled}))
    _set_mode(monkeypatch, "fill", tmp_path)

    result = esports.get_lol_tournaments(limit=3)

    assert result["status"] is False and "rate limit" in result["message"]
    assert not any(tmp_path.rglob("*.json"))

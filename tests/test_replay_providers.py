"""Record/replay for nflverse, FastF1, Kalshi and Polymarket.

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

import pandas as pd
import pytest

from sports_skills import _replay, kalshi, nfl, polymarket
from sports_skills.kalshi import _connector as kalshi_conn
from sports_skills.nfl import _nflverse
from sports_skills.polymarket import _connector as polymarket_conn


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
def _isolate(monkeypatch):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    monkeypatch.delenv(_replay.DIR_ENV, raising=False)
    monkeypatch.setattr(kalshi_conn._RateLimiter, "acquire", lambda _self: None)
    monkeypatch.setattr(polymarket_conn._RateLimiter, "acquire", lambda _self: None)
    kalshi_conn._cache.clear()
    polymarket_conn._cache.clear()
    yield
    kalshi_conn._cache.clear()
    polymarket_conn._cache.clear()


def _set_mode(monkeypatch, mode, directory=None):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    if directory is not None:
        monkeypatch.setenv(_replay.DIR_ENV, str(directory))


def _replay_mode(monkeypatch, directory):
    """Switch to replay and drop the in-process caches, as a fresh run would."""
    kalshi_conn._cache.clear()
    polymarket_conn._cache.clear()
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

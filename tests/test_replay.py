"""Record/replay: a recorded run must replay identically with zero network."""

import io
import json
import os
import pathlib
import urllib.error
import urllib.request

import pytest

from sports_skills import _espn_base, _replay
from sports_skills.football import _connector as football


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
    """Stand-in for urlopen: serves canned bodies/errors and counts calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None, context=None):
        url = req.full_url
        self.calls.append(url)
        for fragment, outcome in self.routes.items():
            if fragment in url:
                if isinstance(outcome, int):
                    raise urllib.error.HTTPError(url, outcome, "err", {}, io.BytesIO(b""))
                return _FakeResponse(outcome)
        raise urllib.error.HTTPError(url, 404, "not found", {}, io.BytesIO(b""))


def _no_network(req, timeout=None, context=None):
    raise AssertionError(f"network access during replay: {req.full_url}")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    monkeypatch.delenv(_replay.DIR_ENV, raising=False)
    monkeypatch.setattr(_espn_base.time, "sleep", lambda _s: None)
    monkeypatch.setattr(football.time, "sleep", lambda _s: None)
    # With sleep stubbed, an exhausted token bucket would spin; the limiter is
    # not under test here.
    monkeypatch.setattr(_espn_base.RateLimiter, "acquire", lambda _self: None)
    monkeypatch.setattr(football._RateLimiter, "acquire", lambda _self: None)
    _espn_base._cache.clear()
    yield
    _espn_base._cache.clear()


def _set_mode(monkeypatch, mode, directory=None):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    if directory is not None:
        monkeypatch.setenv(_replay.DIR_ENV, str(directory))


def test_off_mode_is_live_and_writes_nothing(monkeypatch, tmp_path):
    net = _FakeNetwork({"/a": b'{"x": 1}'})
    monkeypatch.setattr(urllib.request, "urlopen", net)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))

    raw, err = _espn_base._http_fetch("https://example.test/a")

    assert (raw, err) == (b'{"x": 1}', None)
    assert len(net.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_record_then_replay_is_byte_identical_without_network(monkeypatch, tmp_path):
    body = b'{"events": [1, 2, 3]}'
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/a": body}))
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = _espn_base._http_fetch("https://example.test/a?b=2&a=1")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    # Query order differs from the recording; the key is normalized.
    replayed = _espn_base._http_fetch("https://example.test/a?a=1&b=2")

    assert recorded == replayed == (body, None)


def test_binary_body_round_trips(monkeypatch, tmp_path):
    body = bytes(range(256))
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/bin": body}))
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/bin")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    assert _espn_base._http_fetch("https://example.test/bin") == (body, None)


def test_replay_miss_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)

    raw, err = _espn_base._http_fetch("https://example.test/never-recorded")

    assert raw is None
    assert err["error"] is True and err["replay_miss"] is True
    assert "never-recorded" in err["message"]


def test_deterministic_http_error_is_recorded_and_replayed(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/gone": 404}))
    _set_mode(monkeypatch, "record", tmp_path)
    live = _espn_base._http_fetch("https://example.test/gone")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    raw, err = _espn_base._http_fetch("https://example.test/gone")

    assert raw is None
    assert err["status_code"] == 404 == live[1]["status_code"]
    assert err["message"] == live[1]["message"]


@pytest.mark.parametrize("code", [429, 500, 503])
def test_transient_errors_are_never_recorded(monkeypatch, tmp_path, code):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/flaky": code}))
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/flaky")

    assert not any(tmp_path.rglob("*.json"))


def test_tampered_entry_fails_integrity_check(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/a": b"original"}))
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/a")

    path = _replay.entry_path(str(tmp_path), _replay.request_key("https://example.test/a"))
    with open(path, encoding="utf-8") as handle:
        entry = json.load(handle)
    entry["body"] = "edited"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entry, handle)

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    raw, err = _espn_base._http_fetch("https://example.test/a")

    assert raw is None and err["replay_error"] is True
    assert "integrity" in err["message"]


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_missing_directory_is_a_config_error_without_network(monkeypatch, mode):
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, mode)

    raw, err = _espn_base._http_fetch("https://example.test/a")

    assert raw is None and err["replay_error"] is True
    assert _replay.DIR_ENV in err["message"]


def test_invalid_mode_is_a_config_error_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "sometimes", tmp_path)

    raw, err = _espn_base._http_fetch("https://example.test/a")

    assert raw is None and err["replay_error"] is True
    assert "sometimes" in err["message"]


def test_espn_request_mirror_fallback_replays_exactly(monkeypatch, tmp_path):
    """Primary host refuses (403), mirror serves: replay must follow the same path."""
    payload = {"leagues": [{"abbreviation": "NBA"}]}
    net = _FakeNetwork(
        {
            "site.api.espn.com": 403,
            "site.web.api.espn.com": json.dumps(payload).encode(),
        }
    )
    monkeypatch.setattr(urllib.request, "urlopen", net)
    _set_mode(monkeypatch, "record", tmp_path)
    recorded = _espn_base.espn_request("basketball/nba", "scoreboard", {"dates": "20260101"})
    assert len(net.calls) == 2

    _espn_base._cache.clear()
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    replayed = _espn_base.espn_request("basketball/nba", "scoreboard", {"dates": "20260101"})

    assert recorded == replayed == payload


def test_football_fetch_path_is_covered(monkeypatch, tmp_path):
    body = b'{"table": []}'
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/soccer": body}))
    _set_mode(monkeypatch, "record", tmp_path)
    football._http_fetch("https://example.test/soccer")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    assert football._http_fetch("https://example.test/soccer") == (body, None)


def test_entry_is_human_readable_and_versioned(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/a": b'{"x": 1}'}))
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/a?z=1&y=2")

    (path,) = list(tmp_path.rglob("*.json"))
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["schema_version"] == _replay.ENTRY_SCHEMA_VERSION
    assert entry["url"] == "https://example.test/a?y=2&z=1"
    assert entry["body_encoding"] == "utf-8" and entry["body"] == '{"x": 1}'
    assert entry["outcome"] == "ok" and entry["recorded_at"].endswith("Z")
    assert not any(name.endswith(".tmp") for name in os.listdir(path.parent))


def test_public_skill_call_replays_end_to_end(monkeypatch, tmp_path):
    """A real skill function (NBA scoreboard by date) returns the same normalized
    result from a replay as from the recorded live run."""
    from sports_skills.nba import _connector as nba

    scoreboard = {
        "day": {"date": "2026-01-01"},
        "events": [
            {
                "id": "401",
                "name": "Knicks at Celtics",
                "date": "2026-01-01T00:30Z",
                "status": {"type": {"name": "STATUS_FINAL", "completed": True}},
                "competitions": [{"competitors": []}],
            }
        ],
    }
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _FakeNetwork({"basketball/nba/scoreboard": json.dumps(scoreboard).encode()}),
    )
    _set_mode(monkeypatch, "record", tmp_path)
    request = {"params": {"date": "2026-01-01"}}
    recorded = nba.get_scoreboard(request)
    assert not recorded.get("error")

    _espn_base._cache.clear()
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)

    assert nba.get_scoreboard(request) == recorded


def test_fill_serves_recorded_entries_and_records_only_missing_ones(monkeypatch, tmp_path):
    body = b'{"x": 1}'
    net = _FakeNetwork({"/a": body, "/b": b'{"y": 2}'})
    monkeypatch.setattr(urllib.request, "urlopen", net)
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/a")
    path_a = _replay.entry_path(str(tmp_path), _replay.request_key("https://example.test/a"))
    before = pathlib.Path(path_a).read_text(encoding="utf-8")

    # fill: /a is recorded -> served from disk, no network; /b is new -> fetched and recorded.
    net.calls.clear()
    monkeypatch.setattr(urllib.request, "urlopen", net)
    _set_mode(monkeypatch, "fill", tmp_path)
    assert _espn_base._http_fetch("https://example.test/a") == (body, None)
    assert _espn_base._http_fetch("https://example.test/b") == (b'{"y": 2}', None)
    assert net.calls == ["https://example.test/b"]
    assert pathlib.Path(path_a).read_text(encoding="utf-8") == before, "an existing entry is never rewritten"

    # The newly filled entry now replays offline.
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "replay", tmp_path)
    assert _espn_base._http_fetch("https://example.test/b") == (b'{"y": 2}', None)


def test_fill_does_not_overwrite_drifted_upstream_data(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/a": b'{"score": 118}'}))
    _set_mode(monkeypatch, "record", tmp_path)
    _espn_base._http_fetch("https://example.test/a")
    # Upstream changes; fill keeps serving what was recorded (record would overwrite).
    monkeypatch.setattr(urllib.request, "urlopen", _FakeNetwork({"/a": b'{"score": 121}'}))
    _set_mode(monkeypatch, "fill", tmp_path)
    assert _espn_base._http_fetch("https://example.test/a") == (b'{"score": 118}', None)


def test_fill_requires_a_directory(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    _set_mode(monkeypatch, "fill")
    raw, err = _espn_base._http_fetch("https://example.test/a")
    assert raw is None and err["replay_error"] is True

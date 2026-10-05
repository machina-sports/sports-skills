"""Offline tests for the schema drift check in scripts/nightly_improve.py.

Every source response below is a synthetic fixture. Fetches, baseline/report
paths, command execution and git commits are replaced in-process, so no test
touches the network, git, or the repository's reviewed baseline file. Only
check_schema_drift and print_summary are exercised; main() is never run.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "nightly_improve.py"

# Synthetic sources: one object-rooted with required keys, one array-of-objects.
SYNTHETIC_SOURCES = {
    "synthetic_object": {
        "url": "https://synthetic.invalid/object",
        "required_keys": ["events", "season"],
    },
    "synthetic_array": {
        "url": "https://synthetic.invalid/array",
        "required_keys": None,
        "root": "array",
    },
}
SYNTHETIC_OBJECT_BODY = json.dumps({"day": "synthetic", "events": [], "season": {}}).encode()
SYNTHETIC_ARRAY_BODY = json.dumps([{"id": "1", "question": "synthetic?"}, {"id": "2", "question": "x"}]).encode()
SYNTHETIC_BASELINE = {
    "synthetic_object": {"keys": ["day", "events", "season"], "first_seen": "2026-01-01"},
    "synthetic_array": {"keys": ["id", "question"], "first_seen": "2026-01-01"},
}
HYGIENE = {"ruff_fixed": False, "mypy_clean": True, "mypy_errors": []}
FRESHNESS = {"updated": []}


def _load_script():
    spec = importlib.util.spec_from_file_location("nightly_improve_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Env:
    def __init__(self, module, tmp_path):
        self.module = module
        self.baseline = tmp_path / "schema_baseline.json"
        self.drift_dir = tmp_path / "drift"
        self.responses: dict = {}
        self.fetched: list = []

    def write_baseline(self, data) -> bytes:
        text = data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
        self.baseline.write_text(text, encoding="utf-8")
        return self.baseline.read_bytes()

    def run(self) -> dict:
        return self.module.check_schema_drift()

    def report(self) -> str:
        return (self.drift_dir / f"{self.module.TODAY}.md").read_text(encoding="utf-8")

    def summary_drift_line(self, result, capsys) -> str:
        capsys.readouterr()
        self.module.print_summary(HYGIENE, FRESHNESS, result)
        out = capsys.readouterr().out
        return next(line for line in out.splitlines() if line.strip().startswith("Drift:"))


@pytest.fixture
def env(tmp_path, monkeypatch):
    module = _load_script()
    e = _Env(module, tmp_path)
    url_to_source = {cfg["url"]: name for name, cfg in SYNTHETIC_SOURCES.items()}

    def fake_fetch(url):
        source = url_to_source[url]
        e.fetched.append(source)
        body = e.responses[source]
        if isinstance(body, bytes):
            return body, None
        return None, body  # str = synthetic transport error

    def forbidden(*args, **kwargs):
        raise AssertionError("drift check must not run commands or commit")

    monkeypatch.setattr(module, "BASELINE_SOURCES", SYNTHETIC_SOURCES)
    monkeypatch.setattr(module, "BASELINE_PATH", e.baseline)
    monkeypatch.setattr(module, "DRIFT_DIR", e.drift_dir)
    monkeypatch.setattr(module, "_fetch", fake_fetch)
    monkeypatch.setattr(module, "_run", forbidden)
    monkeypatch.setattr(module, "_git_commit", forbidden)
    return e


def _statuses(result):
    return {o["source"]: o["status"] for o in result["sources"]}


def test_all_fetches_failing_is_inconclusive_and_reported(env, capsys):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    env.responses = {
        "synthetic_object": "HTTP Error 503: synthetic outage",
        "synthetic_array": "synthetic timeout",
    }

    result = env.run()

    assert result["drift_detected"] is False
    assert result["new_sources"] is False
    assert result["status"] == "inconclusive"
    assert result["coverage"] == {"total": 2, "checked": 0, "failed": 2, "inconclusive": 0}
    assert _statuses(result) == {"synthetic_object": "fetch_failed", "synthetic_array": "fetch_failed"}
    report = env.report()
    assert "0/2 checked, 2 fetch failed" in report
    assert "HTTP Error 503: synthetic outage" in report
    assert env.baseline.read_bytes() == before
    assert "none" not in env.summary_drift_line(result, capsys)


def test_partial_coverage_unchanged_plus_failure(env, capsys):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": "synthetic DNS failure"}

    result = env.run()

    assert result["status"] == "partial"
    assert result["drift_detected"] is False
    assert result["coverage"] == {"total": 2, "checked": 1, "failed": 1, "inconclusive": 0}
    assert _statuses(result) == {"synthetic_object": "unchanged", "synthetic_array": "fetch_failed"}
    assert "1/2 checked" in env.report()
    assert env.baseline.read_bytes() == before
    line = env.summary_drift_line(result, capsys)
    assert "none" not in line
    assert "PARTIAL" in line


def test_complete_unchanged_is_verified(env, capsys):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": SYNTHETIC_ARRAY_BODY}

    result = env.run()

    assert result["status"] == "verified_no_change"
    assert result["drift_detected"] is False
    assert result["new_sources"] is False
    assert result["coverage"] == {"total": 2, "checked": 2, "failed": 0, "inconclusive": 0}
    assert "2/2 checked" in env.report()
    assert env.baseline.read_bytes() == before
    assert "none" in env.summary_drift_line(result, capsys)


def test_changed_keys_keep_drifting_and_baseline_is_byte_exact(env):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    changed = json.dumps({"events": [], "season": {}, "provider": "synthetic"}).encode()
    env.responses = {"synthetic_object": changed, "synthetic_array": SYNTHETIC_ARRAY_BODY}

    for _ in range(2):  # a regression must not disappear on the next run
        result = env.run()
        assert result["drift_detected"] is True
        assert result["status"] == "drift"
        drift = next(o for o in result["sources"] if o["source"] == "synthetic_object")
        assert drift["status"] == "drift"
        assert drift["added"] == ["provider"]
        assert drift["removed"] == ["day"]
        assert drift["missing_required"] == []
        assert env.baseline.read_bytes() == before

    report = env.report()
    assert "**Added fields:** `provider`" in report
    assert "**Removed fields:** `day`" in report
    assert "Missing required" not in report


def test_first_observation_is_proposed_not_accepted(env, capsys):
    reviewed = {"synthetic_object": SYNTHETIC_BASELINE["synthetic_object"]}
    before = env.write_baseline(reviewed)
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": SYNTHETIC_ARRAY_BODY}

    for _ in range(2):  # still a proposal on the next run: nothing was accepted
        result = env.run()
        assert result["new_sources"] is True
        assert result["drift_detected"] is False
        assert result["status"] == "proposed"
        assert _statuses(result)["synthetic_array"] == "new"
        assert env.baseline.read_bytes() == before

    report = env.report()
    assert "Proposed baseline entries (unreviewed — not applied)" in report
    assert '"question"' in report
    assert "none" not in env.summary_drift_line(result, capsys)


def test_first_observation_missing_required_is_drift_not_proposal(env):
    reviewed = {"synthetic_array": SYNTHETIC_BASELINE["synthetic_array"]}
    before = env.write_baseline(reviewed)
    env.responses = {
        "synthetic_object": json.dumps({"day": "synthetic"}).encode(),
        "synthetic_array": SYNTHETIC_ARRAY_BODY,
    }

    result = env.run()

    obj = next(o for o in result["sources"] if o["source"] == "synthetic_object")
    assert obj["status"] == "drift"
    assert obj["missing_required"] == ["events", "season"]
    assert result["drift_detected"] is True
    assert result["new_sources"] is False
    report = env.report()
    assert "**⚠️ Missing required:** `events`, `season`" in report
    assert "Proposed baseline entries" not in report
    assert env.baseline.read_bytes() == before


def test_empty_object_shows_missing_required_not_transport_failure(env):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    env.responses = {"synthetic_object": b"{}", "synthetic_array": SYNTHETIC_ARRAY_BODY}

    result = env.run()

    obj = next(o for o in result["sources"] if o["source"] == "synthetic_object")
    assert obj["status"] == "drift"
    assert obj["removed"] == ["day", "events", "season"]
    assert obj["missing_required"] == ["events", "season"]
    assert result["coverage"]["checked"] == 2
    assert env.baseline.read_bytes() == before


@pytest.mark.parametrize(
    ("source", "body", "expected"),
    [
        ("synthetic_array", b"[]", "unexpected_shape"),
        ("synthetic_array", b"{not json", "invalid_json"),
        ("synthetic_array", b"\x80synthetic", "invalid_json"),
        ("synthetic_array", b"42", "unexpected_shape"),
        ("synthetic_array", b'"synthetic"', "unexpected_shape"),
        ("synthetic_array", b"null", "unexpected_shape"),
        ("synthetic_array", b'{"id": "1"}', "unexpected_shape"),
        ("synthetic_array", b'[{"id": "1"}, ["synthetic"]]', "unexpected_shape"),
        ("synthetic_array", b'[["synthetic"]]', "unexpected_shape"),
        ("synthetic_object", b"[]", "unexpected_shape"),
        ("synthetic_object", b'[{"events": []}]', "unexpected_shape"),
        ("synthetic_object", b"7", "unexpected_shape"),
        ("synthetic_object", b"true", "unexpected_shape"),
    ],
)
def test_unobservable_bodies_are_inconclusive(env, capsys, source, body, expected):
    before = env.write_baseline(SYNTHETIC_BASELINE)
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": SYNTHETIC_ARRAY_BODY}
    env.responses[source] = body

    result = env.run()

    assert _statuses(result)[source] == expected
    assert result["coverage"] == {"total": 2, "checked": 1, "failed": 0, "inconclusive": 1}
    assert result["status"] == "partial"
    assert result["drift_detected"] is False
    assert f"## {source}: {expected}" in env.report()
    assert env.baseline.read_bytes() == before
    assert "none" not in env.summary_drift_line(result, capsys)


@pytest.mark.parametrize(
    "corrupt",
    [
        "{not valid json",
        "[]",
        '{"synthetic_object": {"first_seen": "2026-01-01"}}',
        '{"synthetic_object": {"keys": "events"}}',
    ],
)
def test_corrupt_baseline_is_preserved_and_unverified(env, capsys, corrupt):
    before = env.write_baseline(corrupt)
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": SYNTHETIC_ARRAY_BODY}

    result = env.run()

    assert result["status"] == "baseline_error"
    assert result["baseline_status"] == "invalid"
    assert result["new_sources"] is False
    assert result["coverage"] == {"total": 2, "checked": 0, "failed": 0, "inconclusive": 2}
    assert set(_statuses(result).values()) == {"baseline_error"}
    assert env.fetched == []
    assert "**Baseline:** invalid" in env.report()
    assert env.baseline.read_bytes() == before
    assert "none" not in env.summary_drift_line(result, capsys)


def test_missing_baseline_is_not_created_and_unverified(env, capsys):
    env.responses = {"synthetic_object": SYNTHETIC_OBJECT_BODY, "synthetic_array": SYNTHETIC_ARRAY_BODY}

    result = env.run()

    assert result["status"] == "baseline_error"
    assert result["baseline_status"] == "missing"
    assert set(_statuses(result).values()) == {"new"}
    assert not env.baseline.exists()
    assert "Proposed baseline entries (unreviewed — not applied)" in env.report()
    assert "none" not in env.summary_drift_line(result, capsys)

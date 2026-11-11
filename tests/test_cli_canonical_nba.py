"""The canonical CLI mode for ``nba get_event_summary``. No network, no clock.

The NBA command is replaced by one returning the checked-in ESPN summary fixture,
normalized by the package's own normalizers, so nothing here can be a cached live
response. What the mode prints is compared with what the library adapter returns for
the same input: the CLI adds a way to ask, never a second reading of the game.
"""

import json
from pathlib import Path

import pytest

from sports_skills import canonical, cli
from sports_skills.nba._connector import _normalize_event, _normalize_plays
from tests.test_canonical_reference_fixtures import canonical_bytes

FIXTURE = Path(__file__).parent / "fixtures/nba_summary_401859967.json"
OBSERVED_AT = "2026-06-14T03:30:00Z"
ARGV = ["nba", "get_event_summary", "--event_id=401859967", "--canonical", "--observed-at", OBSERVED_AT]


def native(start_time=None, *, plays=True):
    """The command's payload. ESPN states the start to the minute; a test may state it exactly."""
    summary = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event = _normalize_event(summary["header"])
    if start_time is not None:
        event["start_time"] = start_time
    data = {"event": event}
    if plays:
        data["plays"] = _normalize_plays(summary)
    return data


def run(argv, monkeypatch, capsys, *, data=None):
    """Drive ``cli.main``. With no ``data`` the command fails the test if it is reached,
    which is how "refused before the request" is asserted rather than assumed."""
    from sports_skills import football, nba

    def unreachable(**kwargs):
        raise AssertionError("the command was called; the CLI should have refused first")

    def reached(**kwargs):
        return {"status": True, "data": data, "message": ""}

    monkeypatch.setattr(nba, "get_event_summary", unreachable if data is None else reached)
    monkeypatch.setattr(football, "get_event_summary", unreachable)
    monkeypatch.setattr("sys.argv", ["sports-skills"] + argv)
    code = 0
    try:
        cli.main()
    except SystemExit as exit_:
        code = exit_.code
    return code, capsys.readouterr().out


def test_an_exact_start_prints_the_envelope_the_library_adapter_returns(monkeypatch, capsys):
    data = native("2026-06-14T00:30:00Z")
    code, out = run(ARGV + ["--start-time-precision", "second"], monkeypatch, capsys, data=data)
    assert code == 0, out
    expected = canonical.canonicalize_nba_event(
        data["event"], data["plays"], observed_at=OBSERVED_AT, start_time_precision="second")
    assert out == canonical_bytes(expected)
    block = json.loads(out)["machina_sports_schema"]
    assert block["event_view"]["sport"] == "basketball"
    assert len(block["event_view"]["actions"]) == data["plays"]["count"]
    assert block["sport_schema_graph"]["@graph"]


def test_the_start_espn_states_to_the_minute_prints_bounds_and_no_graph(monkeypatch, capsys):
    data = native()
    code, out = run(ARGV + ["--start-time-precision", "minute"], monkeypatch, capsys, data=data)
    assert code == 0, out
    expected = canonical.canonicalize_nba_event(
        data["event"], data["plays"], observed_at=OBSERVED_AT, start_time_precision="minute")
    assert out == canonical_bytes(expected)
    block = json.loads(out)["machina_sports_schema"]
    assert "sport_schema_graph" not in block
    assert block["event_view"]["temporal_evidence"]["precision"] == "minute"
    assert len(block["event_view"]["actions"]) == data["plays"]["count"]


def test_a_game_with_no_plays_is_the_event_without_actions(monkeypatch, capsys):
    code, out = run(ARGV + ["--start-time-precision", "minute"], monkeypatch, capsys, data=native(plays=False))
    assert code == 0, out
    assert "actions" not in json.loads(out)["machina_sports_schema"]["event_view"]


def test_the_precision_is_required_and_refused_before_the_request(monkeypatch, capsys):
    """The adapter will not guess how exactly the source stated the start, so neither does
    the CLI: it is the caller's fact to state, like ``--observed-at``."""
    code, out = run(ARGV, monkeypatch, capsys)
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "CANONICAL_START_TIME_PRECISION_REQUIRED"
    for value in ("minute", "second", "fractional_second"):
        assert value in payload["message"]


def test_an_unknown_precision_is_refused_before_the_request(monkeypatch, capsys):
    code, out = run(ARGV + ["--start-time-precision", "hour"], monkeypatch, capsys)
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "CANONICAL_UNKNOWN_START_TIME_PRECISION"
    assert "hour" in payload["message"]


def test_a_precision_the_source_value_does_not_have_is_refused_with_the_adapters_reason(monkeypatch, capsys):
    code, out = run(ARGV + ["--start-time-precision", "second"], monkeypatch, capsys, data=native())
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "CANONICAL_EVENT_REFUSED"
    assert "start_time" in payload["message"]


def test_a_production_consumer_is_refused_before_the_provider_is_called(monkeypatch, capsys):
    code, out = run(ARGV + ["--start-time-precision", "minute", "--consumer-tier", "production"], monkeypatch, capsys)
    assert code == 1
    assert [f["code"] for f in json.loads(out)["findings"]] == ["rights-prototype-only"]


def test_the_precision_flag_is_refused_where_no_adapter_reads_it(monkeypatch, capsys):
    """Football events state an exact start. Accepting the flag there would imply a
    declaration the football adapter never checks."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical", "--observed-at", OBSERVED_AT,
         "--start-time-precision", "minute"], monkeypatch, capsys)
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "CANONICAL_START_TIME_PRECISION_NOT_READ"
    assert "nba get_event_summary" in payload["message"]


def test_the_precision_flag_without_canonical_mode_is_refused(monkeypatch, capsys):
    code, out = run(["nba", "get_event_summary", "--event_id=401859967", "--start-time-precision", "minute"], monkeypatch, capsys)
    assert code == 1
    assert "--start-time-precision" in json.loads(out)["message"]


def test_the_default_output_is_the_native_payload(monkeypatch, capsys):
    data = native()
    code, out = run(["nba", "get_event_summary", "--event_id=401859967"], monkeypatch, capsys, data=data)
    assert code == 0
    assert json.loads(out)["data"] == data


def test_the_other_nba_commands_stay_refused(monkeypatch, capsys):
    """One command was checked against the adapter. A scoreboard or a box score in a
    canonical envelope would claim a conformance nobody verified."""
    code, out = run(["nba", "get_scoreboard", "--canonical", "--observed-at", OBSERVED_AT], monkeypatch, capsys)
    payload = json.loads(out)
    assert code == 1
    assert payload["error_code"] == "CANONICAL_UNSUPPORTED_COMMAND"
    assert "nba get_event_summary" in payload["message"]


def test_the_precision_flag_is_documented_in_the_help(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["sports-skills", "--help"])
    with pytest.raises(SystemExit):
        cli.main()
    assert "--start-time-precision" in capsys.readouterr().out

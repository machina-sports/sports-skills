"""The explicit canonical CLI mode. No network, no clock, no credential.

Every test here drives ``cli.main`` with the football command functions replaced by
ones that return the checked-in synthetic reference payload. That substitution is the
whole reason these tests are honest about the CLI rather than about ESPN: the transport
layer is never reached, so a passing run cannot be a cached live response.

The mode is opt-in twice over — a format the user names and an ``observed_at`` the user
states — because both are the difference between a reproducible document and one that
silently depends on when it was produced.
"""

import json
from pathlib import Path

import pytest

from sports_skills import cli
from tests.test_canonical_reference_fixtures import (
    ENVELOPE_PATH,
    NATIVE_PATH,
    canonical_bytes,
)

OBSERVED_AT = "2026-03-01T22:05:00+00:00"

CANONICAL_FORMAT = "machina-canonical"

PROVIDER_NAMESPACE = "sports-skills/espn"

CLI_SOURCE = Path(__file__).resolve().parents[1] / "src/sports_skills"


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def second_event():
    """A second synthetic event, distinguishable from the first by identity alone."""
    event = native()
    event["id"] = "9002"
    event["competitors"][0]["team"]["name"] = "Synthetic Third City"
    return event


def wrapped(data):
    """The shape ``sports_skills._response.wrap`` hands the CLI on success."""
    return {"status": True, "data": data, "message": ""}


def run(argv, monkeypatch, capsys, *, summary=None, schedule=None):
    """Drive ``cli.main`` with ``argv`` and return ``(exit_code, stdout)``.

    ``summary`` and ``schedule`` replace the two football commands. A command left as
    ``None`` fails the test if the CLI reaches it, which is how "refused before the
    request" is asserted rather than assumed.
    """
    from sports_skills import football

    def unreachable(name):
        def call(**kwargs):
            raise AssertionError(f"{name} was called; the CLI should have refused first")
        return call

    monkeypatch.setattr(football, "get_event_summary",
                        summary or unreachable("get_event_summary"))
    monkeypatch.setattr(football, "get_daily_schedule",
                        schedule or unreachable("get_daily_schedule"))
    monkeypatch.setattr("sys.argv", ["sports-skills"] + argv)

    code = 0
    try:
        cli.main()
    except SystemExit as exit_:
        code = exit_.code
    return code, capsys.readouterr().out


def event_summary(event=None):
    def call(**kwargs):
        return wrapped({"event": native() if event is None else event, "statistics": {}})
    return call


def daily_schedule(events=None):
    def call(**kwargs):
        return wrapped({
            "date": "2026-03-01",
            "events": [native(), second_event()] if events is None else events,
        })
    return call


# ---------------------------------------------------------------------------
# The single-event envelope
# ---------------------------------------------------------------------------

def test_the_summary_command_prints_the_canonical_envelope_directly(monkeypatch, capsys):
    """Directly: no wrapper, no ``status``/``data`` envelope of our own. One event is
    one canonical document, and burying it in a second envelope would make every
    consumer unwrap two."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001",
         "--format", CANONICAL_FORMAT, "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert sorted(json.loads(out)) == ["machina_sports_schema"]


def test_the_printed_envelope_is_the_cross_repository_reference_bytes(monkeypatch, capsys):
    """The strongest assertion available here: the CLI's stdout, byte for byte, is the
    envelope machina-templates published for this payload."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001",
         "--format", CANONICAL_FORMAT, "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert out == ENVELOPE_PATH.read_text(encoding="utf-8")


def test_the_canonical_alias_selects_the_same_mode(monkeypatch, capsys):
    explicit = run(
        ["football", "get_event_summary", "--event_id=9001",
         "--format", CANONICAL_FORMAT, "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    alias = run(
        ["football", "get_event_summary", "--event_id=9001",
         "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert alias == explicit


def test_the_equals_form_of_the_format_flag_also_selects_the_mode(monkeypatch, capsys):
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001",
         f"--format={CANONICAL_FORMAT}", f"--observed-at={OBSERVED_AT}"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert out == ENVELOPE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The multi-event wrapper
# ---------------------------------------------------------------------------

def test_the_scoreboard_command_wraps_one_envelope_per_event(monkeypatch, capsys):
    code, out = run(
        ["football", "get_daily_schedule", "--date=2026-03-01",
         "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert code == 0, out
    document = json.loads(out)
    assert sorted(document) == ["events", "format", "provider"]
    assert document["provider"] == PROVIDER_NAMESPACE
    assert document["format"] == CANONICAL_FORMAT
    assert len(document["events"]) == 2
    for envelope in document["events"]:
        assert sorted(envelope) == ["machina_sports_schema"]


def test_every_wrapped_event_is_the_full_envelope_that_event_alone_would_produce(
    monkeypatch, capsys,
):
    """A wrapper that trimmed its members would publish a document claiming profile
    conformance it no longer has."""
    from sports_skills import canonical

    code, out = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert code == 0, out
    events = json.loads(out)["events"]
    assert events[0] == canonical.canonicalize_event(native(), observed_at=OBSERVED_AT)
    assert events[1] == canonical.canonicalize_event(
        second_event(), observed_at=OBSERVED_AT
    )


def test_the_scores_alias_reaches_the_same_wrapper(monkeypatch, capsys):
    """``scores`` is the cross-sport alias the CLI already resolves to
    ``get_daily_schedule`` for football, so canonical mode has to see the resolved
    command rather than what the user typed."""
    aliased = run(
        ["football", "scores", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    resolved = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert resolved[0] == 0, resolved[1]
    assert aliased == resolved


def test_the_wrapper_is_deterministic(monkeypatch, capsys):
    first = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    second = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert first[0] == 0, first[1]
    assert first == second


def test_an_empty_scoreboard_is_an_empty_event_list_not_a_refusal(monkeypatch, capsys):
    """A day with no matches is an answer. Refusing it would make the mode unusable
    exactly when a caller most needs to distinguish "nothing on" from "it broke"."""
    code, out = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(events=[]),
    )
    assert code == 0, out
    assert json.loads(out)["events"] == []


# ---------------------------------------------------------------------------
# observed_at is stated, never guessed
# ---------------------------------------------------------------------------

def test_canonical_mode_without_an_observed_at_refuses_before_the_request(
    monkeypatch, capsys,
):
    """Refused before the request, not after: a caller who forgot the flag should not
    pay for an ESPN round trip to find out. The substituted command raises if reached."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical"],
        monkeypatch, capsys,
    )
    assert code == 1
    payload = json.loads(out)
    assert payload["status"] is False
    assert "--observed-at" in payload["message"]


def test_an_observed_at_without_an_offset_is_refused(monkeypatch, capsys):
    """A local-looking timestamp names no instant. Two consumers reading the same
    document would disagree about when it was observed."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", "2026-03-01T22:05:00"],
        monkeypatch, capsys,
    )
    assert code == 1
    payload = json.loads(out)
    assert payload["status"] is False
    assert "offset" in payload["message"]


def test_an_unparseable_observed_at_is_refused_with_the_expected_form(
    monkeypatch, capsys,
):
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", "last tuesday"],
        monkeypatch, capsys,
    )
    assert code == 1
    assert OBSERVED_AT in json.loads(out)["message"]


def test_the_utc_designator_is_accepted_and_carried_through_verbatim(
    monkeypatch, capsys,
):
    """``Z`` is offset-aware, so refusing it would be pedantry. It is not rewritten
    either: the document records what the caller stated."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", "2026-03-01T22:05:00Z"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    provenance = json.loads(out)["machina_sports_schema"]["provenance"]
    assert provenance["observed_at"] == "2026-03-01T22:05:00Z"


def test_the_envelope_records_the_stated_instant_and_reads_no_clock(monkeypatch, capsys):
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", "2020-01-01T00:00:00+00:00"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    document = json.loads(out)["machina_sports_schema"]
    assert document["provenance"]["observed_at"] == "2020-01-01T00:00:00+00:00"


def test_the_canonical_cli_path_never_reads_the_clock():
    """Static, because a default that only appears on an untested branch is exactly
    how "no silent current time" stops being true."""
    import ast

    source = (CLI_SOURCE / "canonical/_cli.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("now", "utcnow", "today", "time"), node.attr


# ---------------------------------------------------------------------------
# The consumer-tier rights gate
# ---------------------------------------------------------------------------

def test_naming_the_prototype_tier_explicitly_changes_nothing(monkeypatch, capsys):
    default = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    explicit = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT, "--consumer-tier", "prototype"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert explicit == default


def test_a_production_consumer_is_refused_with_one_actionable_finding(
    monkeypatch, capsys,
):
    """Every envelope this adapter emits is ``open-public`` and prototype-only, so a
    production consumer is refused every time. One finding, not one per flag and not
    one per event: a cascade buries the line that names the fix."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT, "--consumer-tier", "production"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 1
    payload = json.loads(out)
    assert payload["status"] is False
    assert payload["data"] is None
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["code"] == "rights-prototype-only"
    assert finding["consumer_tier"] == "production"
    assert finding["data_class"] == "open-public"


def test_a_production_consumer_is_refused_once_for_a_whole_scoreboard(
    monkeypatch, capsys,
):
    """Two events carrying one adapter's single rights constant is one licence
    problem, and reporting it twice would scale the noise with the fixture list."""
    code, out = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT,
         "--consumer-tier", "production"],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert code == 1
    assert len(json.loads(out)["findings"]) == 1


def test_the_refusal_prints_no_canonical_document(monkeypatch, capsys):
    """A refusal that also emitted the envelope would refuse nothing."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT, "--consumer-tier", "production"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 1
    assert json.loads(out)["findings"][0]["code"] == "rights-prototype-only"
    assert "machina_sports_schema" not in out


def test_an_unknown_consumer_tier_is_refused_with_the_tiers_that_exist(
    monkeypatch, capsys,
):
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT, "--consumer-tier", "enterprise"],
        monkeypatch, capsys,
    )
    assert code == 1
    message = json.loads(out)["message"]
    assert "prototype" in message
    assert "production" in message


@pytest.mark.parametrize("flag,value", [("--consumer-tier", "production"),
                                        ("--observed-at", OBSERVED_AT)])
def test_a_canonical_only_flag_without_canonical_mode_is_refused(
    flag, value, monkeypatch, capsys,
):
    """``--consumer-tier`` gates a canonical rights block and a native payload has
    none; ``--observed-at`` records an observation the native path does not make.
    Accepting either silently would imply a check, or a record, that never happened."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", flag, value],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 1
    message = json.loads(out)["message"]
    assert flag in message
    assert "machina-canonical" in message


# ---------------------------------------------------------------------------
# Refusals that are not rights refusals
# ---------------------------------------------------------------------------

def test_canonical_mode_on_a_command_that_is_not_event_shaped_is_refused(
    monkeypatch, capsys,
):
    """The alternative is wrapping arbitrary data in a document that claims to be one
    observation of one event, which is a false conformance claim."""
    from sports_skills import football

    monkeypatch.setattr(football, "get_competitions",
                        lambda **kwargs: wrapped({"competitions": []}))
    code, out = run(
        ["football", "get_competitions", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys,
    )
    assert code == 1
    message = json.loads(out)["message"]
    assert "get_competitions" in message
    assert "get_event_summary" in message
    assert "get_daily_schedule" in message


def test_canonical_mode_on_another_module_is_refused(monkeypatch, capsys):
    """The adapter this package owns reads football events. There is no ESPN-NFL
    canonical reading, and a mode that pretended otherwise would emit a soccer
    observation of a gridiron game."""
    code, out = run(
        ["nfl", "get_scoreboard", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys,
    )
    assert code == 1
    assert "nfl" in json.loads(out)["message"]


def test_an_event_with_no_competition_identifier_is_refused_with_the_native_field(
    monkeypatch, capsys,
):
    """The documented trap. ``_normalize_espn_event`` takes ``competition.id`` from its
    ``league_slug`` argument, so an event normalized without one carries no competition
    identifier, and inventing one is the fabrication this contract exists to refuse."""
    slugless = native()
    slugless["competition"] = {"id": "", "name": ""}
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(slugless),
    )
    assert code == 1
    payload = json.loads(out)
    assert "competition.id" in payload["message"]
    assert "league_slug" in payload["hint"]


def test_a_refusal_names_the_event_it_could_not_read_in_a_scoreboard(
    monkeypatch, capsys,
):
    """One bad event among many is a needle. A message that did not say which event
    would send the reader to check all of them."""
    broken = second_event()
    broken["status"] = "penalty_shootout"
    code, out = run(
        ["football", "get_daily_schedule", "--canonical", "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, schedule=daily_schedule(events=[native(), broken]),
    )
    assert code == 1
    assert "9002" in json.loads(out)["message"]


def test_a_failed_native_call_reports_its_own_message_rather_than_a_canonical_one(
    monkeypatch, capsys,
):
    """When the request itself failed there is nothing to canonicalize, and reporting
    that as a canonical refusal would point the reader at the wrong layer."""
    def failed(**kwargs):
        return {"status": False, "data": None, "message": "Could not resolve event"}

    code, out = run(
        ["football", "get_event_summary", "--event_id=nope", "--canonical",
         "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=failed,
    )
    assert code == 1
    assert "Could not resolve event" in json.loads(out)["message"]


def test_no_refusal_prints_a_traceback(monkeypatch, capsys):
    """Every path above is agent-facing. A traceback is not an error message."""
    for argv, kwargs in (
        (["football", "get_event_summary", "--event_id=9001", "--canonical"], {}),
        (["football", "get_competitions", "--canonical", "--observed-at", OBSERVED_AT], {}),
        (["nfl", "get_scoreboard", "--canonical", "--observed-at", OBSERVED_AT], {}),
        (["football", "get_event_summary", "--event_id=9001", "--canonical",
          "--observed-at", OBSERVED_AT, "--consumer-tier", "production"],
         {"summary": event_summary()}),
    ):
        code, out = run(argv, monkeypatch, capsys, **kwargs)
        assert code == 1, argv
        assert "Traceback" not in out, argv
        assert json.loads(out)["status"] is False, argv


# ---------------------------------------------------------------------------
# The native path is untouched
# ---------------------------------------------------------------------------

def test_the_default_output_is_the_native_payload_unchanged(monkeypatch, capsys):
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert json.loads(out) == wrapped({"event": native(), "statistics": {}})


def test_the_native_snapshot_is_byte_for_byte_what_it_always_was(monkeypatch, capsys):
    """The formatting too, not only the values: downstream tooling diffs this output."""
    code, out = run(
        ["football", "get_daily_schedule", "--date=2026-03-01"],
        monkeypatch, capsys, schedule=daily_schedule(),
    )
    assert code == 0, out
    expected = wrapped({"date": "2026-03-01", "events": [native(), second_event()]})
    assert out == json.dumps(expected, indent=2, default=str, ensure_ascii=False) + "\n"


def test_a_format_flag_the_canonical_mode_does_not_claim_still_reaches_the_command(
    monkeypatch, capsys,
):
    """``--format`` is an existing parameter of ``betting devig``. Only the one
    canonical value is intercepted; every other value belongs to the command."""
    from sports_skills import betting

    seen = {}

    def devig(**kwargs):
        seen.update(kwargs)
        return wrapped({"probabilities": []})

    monkeypatch.setattr(betting, "devig", devig)
    code, out = run(
        ["betting", "devig", "--odds=-110,-110", "--format=probability"],
        monkeypatch, capsys,
    )
    assert code == 0, out
    assert seen == {"odds": "-110,-110", "format": "probability"}


def test_the_canonical_flags_are_not_passed_to_the_command(monkeypatch, capsys):
    """They are the CLI's own, and a connector that received them would raise a
    ``TypeError`` reported as a parameter-name mistake."""
    seen = {}

    def summary(**kwargs):
        seen.update(kwargs)
        return wrapped({"event": native(), "statistics": {}})

    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT, "--consumer-tier", "prototype"],
        monkeypatch, capsys, summary=summary,
    )
    assert code == 0, out
    assert seen == {"event_id": "9001"}


def test_importing_the_cli_does_not_import_the_canonical_package():
    """The canonical import lives inside the branch that needs it, so a user of the
    native CLI still does not pay for the schema runtime."""
    import subprocess
    import sys

    script = (
        "import sys; import sports_skills.cli; "
        "print(any(name.startswith('sports_skills.canonical') for name in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(CLI_SOURCE.parent), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", result.stdout


def test_a_native_run_leaves_the_canonical_package_unimported(monkeypatch, capsys):
    """The runtime half of the claim above: reaching the native output path does not
    reach the canonical one, whatever the import graph allows."""
    import sys

    for name in [n for n in sys.modules if n.startswith("sports_skills.canonical")]:
        monkeypatch.delitem(sys.modules, name)

    code, out = run(
        ["football", "get_event_summary", "--event_id=9001"],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert not [n for n in sys.modules if n.startswith("sports_skills.canonical")]


def test_the_canonical_bytes_format_is_the_one_both_repositories_agreed(
    monkeypatch, capsys,
):
    """Stated as its own test because the byte comparison above would keep passing if
    the CLI and the fixture drifted to a new shared format."""
    code, out = run(
        ["football", "get_event_summary", "--event_id=9001", "--canonical",
         "--observed-at", OBSERVED_AT],
        monkeypatch, capsys, summary=event_summary(),
    )
    assert code == 0, out
    assert out == canonical_bytes(json.loads(out))


@pytest.mark.parametrize("flag", ["--canonical", "--observed-at", "--consumer-tier"])
def test_every_canonical_flag_is_documented_in_the_help(flag, monkeypatch, capsys):
    """A flag with no help text is a flag nobody finds."""
    monkeypatch.setattr("sys.argv", ["sports-skills", "--help"])
    with pytest.raises(SystemExit):
        cli.main()
    assert flag in capsys.readouterr().out

"""What ``--format machina-canonical`` accepts, and what it refuses.

This module is the whole canonical CLI mode except for the printing and the exit
status, which stay in :mod:`sports_skills.cli` where the rest of the CLI's error
reporting lives. Nothing here touches the network, the clock or the process: it takes a
command's already-returned payload and either produces a document or explains why it
produced none.

Four things it refuses, each because emitting something would be worse than emitting
nothing:

**A command whose payload is not one or more normalized football events.** The envelope
declares itself one provider's observation of one event, conforming to a named profile
at a pinned commit. Wrapping a standings table in it would be a false conformance claim,
so the supported commands are enumerated rather than guessed from the shape of whatever
arrived.

**A missing or offset-naive ``observed_at``.** It is the one input that makes the
document reproducible, and it is the caller's fact to state. Defaulting it to the
current time would make two runs over the same fixture disagree, which is exactly what
the checked-in reference bytes exist to catch. A timestamp with no UTC offset names no
instant, so it is refused rather than assumed to be local or assumed to be UTC.

**An event the adapter cannot read.** The adapter already refuses to invent a fact it
was not given and names the native field that was empty; this module adds *which* event,
so one bad fixture in a day's scoreboard is findable.

**A consumer tier the rights block does not permit.** The gate is the vendored one, so
this package and ``machina-templates`` answer the question with the same code. Every
envelope this adapter emits is ``open-public`` and ``prototype_only``, so a
``production`` consumer is refused every time — that is the answer, not a defect. The
refusal is one finding even for a scoreboard: two events carrying one adapter's single
rights constant is one licence problem, and repeating it per event would scale the noise
with the fixture list while burying the line that names the fix.

That refusal is decided *before* the provider is called, against the adapter's own
rights constant rather than against whatever came back, because the answer does not
depend on the result set. Asking only the emitted envelopes would serve an empty
scoreboard at every tier — there is nothing to object to — and a production integration
would read that as permission to configure a prototype-only adapter, on the accident of
a day with no matches. The envelopes are still gated after they are built, so a document
whose licence claim ever disagreed with the constant is refused on its own terms.
"""

from datetime import datetime

from . import canonicalize_event, rights_findings
from ._vendored.rights import CONSUMER_TIERS, ENVELOPE_KEY
from .adapters import football

#: The one ``--format`` value this mode answers to. Any other value is left alone for
#: the command to interpret — ``format`` is an existing parameter of ``betting devig``.
CANONICAL_FORMAT = "machina-canonical"

#: The tier assumed when the caller names none. ``prototype``, because that is what this
#: package is for and because a default of ``production`` would refuse every command.
#: The strict direction stays reachable, and refuses.
DEFAULT_CONSUMER_TIER = "prototype"

#: ``(module, command) -> (payload field, one envelope per item)``. An allowlist, not a
#: shape sniff: a command that happens to return something event-like is not thereby a
#: command whose output this adapter has been checked against.
EVENT_COMMANDS = {
    ("football", "get_event_summary"): ("event", False),
    ("football", "get_daily_schedule"): ("events", True),
}

#: Shown in every ``observed_at`` refusal, because "ISO-8601" is not an example.
OBSERVED_AT_EXAMPLE = "2026-03-01T22:05:00+00:00"

#: The trap worth naming by its CLI-visible cause. ``_normalize_espn_event`` takes
#: ``competition.id`` from its ``league_slug`` argument, so an event normalized without
#: one carries no competition identifier — and a reader told only "competition.id is
#: empty" has no way to know that.
LEAGUE_SLUG_HINT = (
    "The football normalizer takes competition.id from its league_slug argument, so an "
    "event normalized without a league slug carries no competition identifier. "
    "Inventing one would be a fabricated fact, so the event is refused instead."
)


class CanonicalCliError(ValueError):
    """Why no canonical document was produced, in terms the caller can act on.

    ``findings`` carries the rights gate's own output when that is what refused, so the
    machine-readable reason a consumer was turned away is the gate's, not a paraphrase.
    """

    def __init__(self, message, *, error_code, hint=None, findings=None):
        super().__init__(message)
        self.error_code = error_code
        self.hint = hint
        self.findings = findings


def supported_commands():
    return sorted(f"{module} {command}" for module, command in EVENT_COMMANDS)


def validate_request(module, command, *, observed_at, consumer_tier):
    """Everything refusable before the provider is called.

    Called first on purpose: a caller who forgot ``--observed-at``, or who named a tier
    this adapter's licence cannot serve, should not pay for an ESPN round trip to be
    told so.
    """
    if (module, command) not in EVENT_COMMANDS:
        raise CanonicalCliError(
            f"--format {CANONICAL_FORMAT} reads normalized football events, and "
            f"'{module} {command}' does not return any. Supported: "
            f"{', '.join(supported_commands())}. Wrapping other data in a canonical "
            "envelope would claim a conformance the document does not have.",
            error_code="CANONICAL_UNSUPPORTED_COMMAND",
        )
    if not observed_at:
        raise CanonicalCliError(
            f"--format {CANONICAL_FORMAT} requires --observed-at: the instant of the "
            "observation is the one input that makes the document reproducible, and "
            "reading it off the clock would make every run of the same query differ. "
            f"Example: --observed-at={OBSERVED_AT_EXAMPLE}",
            error_code="CANONICAL_OBSERVED_AT_REQUIRED",
        )
    _check_offset_aware(observed_at)
    if consumer_tier not in CONSUMER_TIERS:
        raise CanonicalCliError(
            f"--consumer-tier '{consumer_tier}' is not a tier the rights gate knows; "
            f"expected one of {', '.join(CONSUMER_TIERS)}. Refused rather than read as "
            "the permissive tier.",
            error_code="CANONICAL_UNKNOWN_CONSUMER_TIER",
        )
    _check_rights([_adapter_envelope()], consumer_tier)


def render(module, command, result, *, observed_at, consumer_tier):
    """One command's payload as the canonical document it maps to.

    One event is the envelope itself, with no wrapper: a second envelope around a
    document that is already one would make every consumer unwrap twice. Many events are
    a three-key wrapper, and every member of it is the full envelope that event alone
    would produce — a trimmed member would publish a conformance claim it no longer has.
    """
    field, many = EVENT_COMMANDS[(module, command)]
    payload = _payload(result)
    if not many:
        document = _envelope(payload.get(field) or {}, observed_at=observed_at)
        envelopes = [document]
    else:
        envelopes = [
            _envelope(event, observed_at=observed_at, label=_label(event, index))
            for index, event in enumerate(payload.get(field) or [])
        ]
        document = {
            "provider": football.PROVIDER["namespace"],
            "format": CANONICAL_FORMAT,
            "events": envelopes,
        }
    _check_rights(envelopes, consumer_tier)
    return document


def _check_offset_aware(observed_at):
    """``observed_at`` names an instant, or refuse.

    ``Z`` is accepted — it is offset-aware, and refusing the commonest spelling of UTC
    would be pedantry — but it is not rewritten: the document records what the caller
    stated, and silently normalizing it would make the output disagree with the input.
    """
    text = observed_at
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise CanonicalCliError(
            f"--observed-at '{observed_at}' is not an ISO-8601 timestamp. Expected an "
            f"offset-aware instant, e.g. {OBSERVED_AT_EXAMPLE}",
            error_code="CANONICAL_OBSERVED_AT_INVALID",
        ) from None
    if moment.utcoffset() is None:
        raise CanonicalCliError(
            f"--observed-at '{observed_at}' states no UTC offset, so it names no instant "
            "and two readers of the document would disagree about when the observation "
            f"was made. Expected an offset-aware timestamp, e.g. {OBSERVED_AT_EXAMPLE}",
            error_code="CANONICAL_OBSERVED_AT_NOT_OFFSET_AWARE",
        )


def _payload(result):
    """The command's data, or refuse with the command's own explanation.

    A request that failed leaves nothing to canonicalize, and reporting that as a
    canonical refusal would point the reader at the wrong layer.
    """
    if isinstance(result, dict) and result.get("status") is not False:
        data = result.get("data")
        if isinstance(data, dict):
            return data
        return _no_data("the command returned no data block")
    message = result.get("message") if isinstance(result, dict) else ""
    return _no_data(message or "the command returned no data")


def _no_data(message):
    raise CanonicalCliError(
        f"{message}, so there was nothing to canonicalize.",
        error_code="CANONICAL_REQUEST_FAILED",
    )


def _label(event, index):
    """Which event, for a refusal inside a list of them."""
    identifier = event.get("id") if isinstance(event, dict) else None
    return f"'{identifier}'" if identifier else f"at index {index}"


def _envelope(event, *, observed_at, label=None):
    try:
        return canonicalize_event(event, observed_at=observed_at)
    except ValueError as exc:
        where = "" if label is None else f"{label} "
        raise CanonicalCliError(
            f"event {where}could not be canonicalized: {exc}",
            error_code="CANONICAL_EVENT_REFUSED",
            hint=LEAGUE_SLUG_HINT if "competition.id" in str(exc) else None,
        ) from None


def _adapter_envelope():
    """The licence claim every envelope this mode can emit will carry, gate-shaped.

    Built from the adapter's own constant, so the tier is answered by the same fact the
    documents would have stated rather than by a second reading of the policy. It is a
    rights block and nothing else because that is all the gate reads, and a fuller
    stand-in would be a document claiming an observation nobody made.
    """
    return {ENVELOPE_KEY: {"rights": dict(football.RIGHTS)}}


def _check_rights(envelopes, consumer_tier):
    """The vendored gate, run over every envelope, reported once per distinct reason.

    "this adapter's output" rather than "this document", because the preflight runs the
    same gate over the same rights before any document exists — and one refusal that
    reads correctly in both places beats two that each read correctly in one.
    """
    findings = []
    seen = set()
    for envelope in envelopes:
        for finding in rights_findings(envelope, consumer_tier=consumer_tier):
            if finding["code"] in seen:
                continue
            seen.add(finding["code"])
            findings.append(finding)
    if findings:
        raise CanonicalCliError(
            f"the '{consumer_tier}' consumer tier may not consume this adapter's "
            f"output: {findings[0]['detail']}",
            error_code="RIGHTS_REFUSED",
            findings=findings,
        )

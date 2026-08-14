"""Validate a canonical observation before anything tries to serialize it.

This is the only place fabrication can be caught while the evidence is still
present. By the time a serializer runs, ``"Unknown Venue"`` looks exactly like a
venue name, and a reviewer reading the output has no way to tell which provider
field produced it. Here, the error names the path, so the fix lands in the
adapter where it belongs.

Three deliberate design choices:

- **Hand-rolled, no ``jsonschema``.** Neither repository carries it, and this is
  a key walk. Adding a dependency to a published zero-dependency package to
  avoid writing a key walk is not a trade worth making.
- **Every error is reported, not just the first.** A validator that stops early
  turns fixing an adapter into whack-a-mole, and then people stop running it.
- **Nothing is repaired.** No default is filled in, no value is coerced, and the
  document is never mutated. A validator that quietly fixes its input hides the
  bug it was written to expose.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible, standard
library only, and no import of ``tools.*``.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from . import (
    ACCEPTED_SCHEMA_VERSIONS,
    PREDECESSOR_SCHEMA_VERSION,
    SCHEMA_VERSION,
)

#: Values that are a fabricated stand-in for a fact the provider never supplied.
#:
#: This duplicates ``tools.iptc.profile.PLACEHOLDER_VALUES``, and the duplication
#: is forced: this module is copied byte-exact into a package that cannot import
#: ``tools.iptc``. ``tests/test_iptc_canonical_serializer.py`` asserts the two
#: sets are equal, which is what stops them drifting.
PLACEHOLDERS = frozenset({
    "", "unknown", "Unknown", "UNKNOWN", "UNK", "unk", "TBD", "tbd", "N/A", "n/a",
    "Unknown Player", "Unknown Team", "Unknown Venue", "Unknown City",
    "Unknown Country", "Unknown Competition", "Unknown Season", "Unknown Round",
    "Unknown Phase", "Unknown Category", "Unknown Group", "Unknown Channel",
    "Unknown Title", "unknown Phase",
})

#: Keys ``observation.event`` must carry unconditionally. An event without a
#: status is not an event we can place on a timeline.
#:
#: The start instant is **not** here, and its absence from this tuple is the
#: whole of RFC 002 §12.2 in the required-field machinery: an event states
#: its start
#: either exactly, in ``start_time``, or as reduced-precision evidence, and which
#: one is required depends on the document. :func:`_check_temporal_state` owns
#: that question so it is answered in one place and reported once.
REQUIRED_EVENT_KEYS = ("provider_id", "status")

#: ``(path-within-observation, key)`` pairs that must be present.
#:
#: ``rights`` and ``adapter`` are here rather than optional-if-present because
#: neither is derivable from a payload. An observation with no rights block leaves
#: every consumer to pick its own licence default, and one with no adapter block is
#: an anonymous claim: when a fact turns out to be wrong there is nothing naming
#: the code that produced it. Defaulting either would be the silent repair this
#: module exists to refuse.
_REQUIRED_FIELDS = (
    (("provider",), "namespace"),
    ((), "observed_at"),
    ((), "adapter"),
    ((), "rights"),
    (("sport",), "medtop"),
    (("competition",), "provider_id"),
) + tuple((("event",), key) for key in REQUIRED_EVENT_KEYS)

#: Participation kinds the graph has a class for. Anything else is a parse
#: artefact, not a participant.
PARTICIPANT_KINDS = ("team", "individual")

#: How a provider identifier came to be attached to a Machina identity, in the
#: order RFC 002 §5 lists them: the provider stated it, no stable provider
#: identifier exists and the value is positional, or the caller supplied it.
#: There is no fourth value and no fuzzy matching in this phase, which is why
#: this is a closed set rather than a free string.
RESOLUTION_METHODS = ("provider-native", "ordinal-derived", "declared")

#: What an identity-bearing section that says nothing means.
#:
#: Defaulting at all is a real choice, and it is defensible only in this
#: direction: an adapter that read a provider field and did not annotate it did
#: read a provider field. The two cases that are *not* provider-native — a
#: hardcoded mapping constant and a positional key — are exactly the cases an
#: adapter author has to think about, so those are the ones that must be written
#: down. Requiring the key everywhere would have every adapter spell out
#: ``provider-native`` on six sections, which buries the two lines that matter.
RESOLUTION_DEFAULT = "provider-native"

#: Sections whose ``provider_id`` becomes a crosswalk entry, and which may
#: therefore state how that identifier was resolved. Participants are the sixth
#: and are handled with the rest of their per-item checks, because their path
#: carries an index.
#:
#: A resolution method anywhere else would be a fact about an identifier the
#: crosswalk never records, so it is not accepted there rather than being
#: accepted and ignored.
IDENTITY_BEARING_SECTIONS = (
    ("competition",),
    ("competition", "season"),
    ("phase",),
    ("site",),
    ("event",),
)

#: The provider payload. Held verbatim, surfaced only in ``event_view``, and
#: deliberately exempt from the placeholder scan: a real payload is full of
#: nulls and provider-side "TBD" strings, and scanning it would make every
#: genuine observation invalid. The pressure release for that would be adapters
#: dropping ``raw``, which costs the provenance trail — a much worse outcome
#: than tolerating provider noise in a field that never reaches the graph.
RAW_KEY = "raw"

_ALLOWLIST_PATH = Path(__file__).resolve().parent / "official-property-names.json"

#: RFC 3339 instant with a mandatory explicit offset. A naive timestamp is
#: ambiguous by an unknown number of hours, so it is not a fact either.
_DATETIME_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?"
    r"(?:[Zz]|[+-](\d{2}):(\d{2}))$"
)

#: A minute-precision value with a mandatory explicit offset: the shape a
#: source-normalizer produces when the provider published no second-of-minute.
#: No seconds group at all, which is what makes an exact value smuggled into the
#: evidence member a parse failure rather than a value to be inspected.
_MINUTE_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2})(?:[Zz]|([+-])(\d{2}):(\d{2}))$"
)

#: How wide the interval each declared precision denotes is, in seconds. A table
#: rather than a constant, because the number is a property of the precision and
#: the validator has to be able to say which one it checked.
PRECISION_WIDTH_SECONDS = {"minute": 60}

#: Where reduced-precision temporal evidence lives, within ``observation.event``.
TEMPORAL_EVIDENCE_KEY = "temporal_evidence"

#: Which event instant the evidence describes. Closed to the one instant
#: ``event.start_time`` covers: an unrecognised ``kind`` would otherwise let an
#: end-of-event bound satisfy a consumer asking for a bounded *start*.
TEMPORAL_KINDS = ("start",)

#: How the bounds were produced. One value, because there is one derivation and
#: no best-effort branch (RFC 002 §12.2).
TEMPORAL_DERIVATIONS = ("declared_precision_interval",)

#: The complete key set of the evidence member, and the reason it is closed
#: rather than merely documented: RFC 002 §12.2 refuses "any additional offset-bearing
#: field alongside ``source_value``", and no list of the field names somebody
#: might invent for a second offset can be complete. Refusing every unknown key
#: is the same rule stated in a way a machine can check.
TEMPORAL_EVIDENCE_KEYS = ("kind", "source_value", "precision",
                          "lower_inclusive", "upper_exclusive", "provenance")

#: A derived bound as the contract requires it: second-precision, UTC, spelled
#: ``Z``. ``+00:00`` is the same instant and a different spelling, and two
#: spellings of one bound is drift waiting to happen.
_BOUND_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_allowlist_cache = None


def derive_bounds(source_value, precision):
    """``(lower_inclusive, upper_exclusive)`` for one reduced-precision value.

    A pure function of ``(source_value, precision)`` and nothing else (RFC 002 §12.1,
    G2). Both bounds come back as second-precision RFC 3339 instants normalized
    to UTC, so every consumer compares like with like, and the interval is
    half-open and strictly non-empty.

    **No timezone database participates, ever** (G7). The offset is explicit, it
    is read out of ``source_value`` itself, and the arithmetic is fixed-offset
    subtraction. There is no zone name to resolve, so there is no DST rule to
    apply and no ``zoneinfo`` to consult — a value at a DST transition instant
    derives exactly the bounds the same wall value derives anywhere else.

    Raises ``ValueError`` for anything this version cannot derive: an unknown
    precision, a naive value, a zone name, an out-of-range offset, or an already
    exact value. Deriving from a value the contract refuses would put a bound
    under a document the validator is about to reject.
    """
    if precision not in PRECISION_WIDTH_SECONDS:
        raise ValueError(
            "precision '{0}' is not one of {1}".format(
                precision, ", ".join(sorted(PRECISION_WIDTH_SECONDS))
            )
        )
    if not isinstance(source_value, str):
        raise ValueError("source_value must be a string")
    match = _MINUTE_RE.match(source_value)
    if match is None:
        raise ValueError(
            "source_value is not a minute-precision RFC 3339 value with an "
            "explicit offset"
        )
    year, month, day, hour, minute = (int(group) for group in match.groups()[:5])
    sign, offset_hour, offset_minute = match.group(6), match.group(7), match.group(8)
    if offset_hour is None:
        offset = datetime.timedelta(0)
    else:
        if int(offset_hour) > 23 or int(offset_minute) > 59:
            raise ValueError("source_value carries an out-of-range UTC offset")
        offset = datetime.timedelta(hours=int(offset_hour), minutes=int(offset_minute))
        if sign == "-":
            offset = -offset
    # datetime() is what refuses 2030-02-30 and hour 25: the regex counts digits,
    # and a calendar is the only thing that knows February.
    stated = datetime.datetime(year, month, day, hour, minute)
    lower = stated - offset
    upper = lower + datetime.timedelta(seconds=PRECISION_WIDTH_SECONDS[precision])
    return _utc_instant(lower), _utc_instant(upper)


def _utc_instant(moment):
    """``moment`` as a second-precision, ``Z``-normalized RFC 3339 instant.

    Formatted field by field rather than with ``strftime``: ``%Y`` is not
    zero-padded consistently across platforms, and a bound whose spelling depends
    on the C library is not a bound two repositories can compare.
    """
    return "{0:04d}-{1:02d}-{2:02d}T{3:02d}:{4:02d}:{5:02d}Z".format(
        moment.year, moment.month, moment.day,
        moment.hour, moment.minute, moment.second,
    )


def official_property_curies():
    """Full CURIEs of every official Sport Schema property, from the pin.

    Full CURIEs rather than local names, because a local name is not a term:
    ``startDateTime`` is declared by ``.../ontologies/main/`` alone, so matching
    on the local name accepts ``spsocstat:startDateTime``, and matching on it
    accepts ``notpinned:shotsTotal`` too — a CURIE under a prefix nothing binds,
    which expands to nothing at all.

    Generated by ``export_official_terms``. If the file is missing this raises
    rather than falling back to an empty set: an empty allowlist would silently
    reject every statistic, and an "accept everything" fallback would silently
    accept invented ones. Both failures are worse than not starting.
    """
    global _allowlist_cache
    if _allowlist_cache is None:
        if not _ALLOWLIST_PATH.is_file():
            raise RuntimeError(
                "missing {0}. Regenerate it with: "
                "python -m tools.iptc.canonical.export_official_terms".format(
                    _ALLOWLIST_PATH.name
                )
            )
        with _ALLOWLIST_PATH.open(encoding="utf-8") as handle:
            _allowlist_cache = frozenset(json.load(handle)["curies"])
    return _allowlist_cache


def _is_datetime(value):
    """True when ``value`` is a real instant with an explicit offset."""
    match = _DATETIME_RE.match(value)
    if match is None:
        return False
    year, month, day, hour, minute, second = (int(g) for g in match.groups()[:6])
    offset_hour, offset_minute = match.group(7), match.group(8)
    if offset_hour is not None and (int(offset_hour) > 23 or int(offset_minute) > 59):
        return False
    try:
        datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        # Catches 2026-02-30, hour 25, and every other impossible reading.
        return False
    return True


def _scan_fabrication(node, path, errors):
    """Report every null, empty string and placeholder reachable from ``node``.

    Recursive rather than key-driven on purpose: the rule is about the shape of a
    *value*, so a field nobody thought to enumerate is covered too.
    """
    if isinstance(node, dict):
        for key in sorted(node):
            if key == RAW_KEY:
                continue
            _scan_fabrication(node[key], "{0}.{1}".format(path, key), errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _scan_fabrication(item, "{0}[{1}]".format(path, index), errors)
    elif node is None:
        errors.append(
            "{0}: null is not a fact; omit the key instead".format(path)
        )
    elif node == "":
        errors.append(
            "{0}: empty string is not a fact; omit the key instead".format(path)
        )
    elif isinstance(node, str) and node in PLACEHOLDERS:
        errors.append(
            "{0}: placeholder '{1}'; omit the key instead".format(path, node)
        )


def _check_required(observation, errors):
    for parents, key in _REQUIRED_FIELDS:
        node = observation
        path = "observation"
        missing_parent = False
        for parent in parents:
            path = "{0}.{1}".format(path, parent)
            node = node.get(parent) if isinstance(node, dict) else None
            if not isinstance(node, dict):
                if not missing_parent:
                    errors.append("{0}: required field is missing".format(path))
                missing_parent = True
                break
        if missing_parent:
            continue
        if key not in node:
            errors.append("{0}.{1}: required field is missing".format(path, key))


def _check_datetimes(observation, errors):
    candidates = [("observation.observed_at", observation.get("observed_at"))]
    event = observation.get("event")
    if isinstance(event, dict):
        candidates.append(("observation.event.start_time", event.get("start_time")))
    actions = observation.get("actions")
    if isinstance(actions, list):
        for index, action in enumerate(actions):
            if isinstance(action, dict) and "action_time" in action:
                candidates.append((
                    "observation.actions[{0}].action_time".format(index),
                    action.get("action_time"),
                ))
    for path, value in candidates:
        if value is None or value == "":
            # Already reported as missing or as fabrication; do not say it twice.
            continue
        if not isinstance(value, str) or not _is_datetime(value):
            errors.append(
                "{0}: '{1}' is not an RFC 3339 datetime with an explicit "
                "offset".format(path, value)
            )


def _parse_bound(value):
    """A ``Z``-normalized second-precision bound as a datetime, or ``None``."""
    if not isinstance(value, str) or not _BOUND_RE.match(value):
        return None
    try:
        return datetime.datetime(
            int(value[0:4]), int(value[5:7]), int(value[8:10]),
            int(value[11:13]), int(value[14:16]), int(value[17:19]),
        )
    except ValueError:
        return None


def _check_temporal_provenance(evidence, path, errors):
    """Provenance for the derivation: identifiers and versions only.

    Required, because the bounds are derived data sitting next to observed data
    and nothing else in the member says which of the two a reader is looking at.
    Scanned for request- and credential-shaped material with the same rule
    ``source_refs`` uses, rather than a second copy of it — and the finding names
    the field and the marker, never the value, for the reason
    :func:`_check_source_refs` gives.
    """
    provenance = evidence.get("provenance")
    if not isinstance(provenance, dict):
        errors.append(
            "{0}.provenance: required object is missing; a derived bound with no "
            "stated derivation is not auditable".format(path)
        )
        return
    derivation = provenance.get("derivation")
    if derivation not in TEMPORAL_DERIVATIONS:
        errors.append(
            "{0}.provenance.derivation: '{1}' is not one of {2}".format(
                path, derivation, ", ".join(TEMPORAL_DERIVATIONS)
            )
        )
    for key in sorted(provenance):
        marker = credential_marker(provenance.get(key))
        if marker is not None:
            errors.append(
                "{0}.provenance.{1}: request- or credential-shaped material was "
                "redacted (contains '{2}'). Provenance records identifiers and "
                "versions only.".format(path, key, marker)
            )


def _check_temporal_bounds(evidence, path, errors):
    """The derived half-open interval: well-formed, non-empty, and recomputable."""
    parsed = {}
    for key in ("lower_inclusive", "upper_exclusive"):
        if key not in evidence:
            errors.append("{0}.{1}: required field is missing".format(path, key))
            continue
        moment = _parse_bound(evidence[key])
        if moment is None:
            errors.append(
                "{0}.{1}: bounds are second-precision RFC 3339 instants "
                "normalized to UTC and spelled 'Z'".format(path, key)
            )
            continue
        parsed[key] = moment

    lower, upper = parsed.get("lower_inclusive"), parsed.get("upper_exclusive")
    if lower is None or upper is None:
        return
    if lower >= upper:
        # One finding for inverted and zero-width alike: both are the same
        # defect, an interval that admits no instant.
        errors.append(
            "{0}: lower_inclusive must be strictly before upper_exclusive; "
            "a zero-width or inverted interval is not an interval".format(path)
        )
        return
    expected = PRECISION_WIDTH_SECONDS.get(evidence.get("precision"))
    if expected is not None and (upper - lower).total_seconds() != expected:
        errors.append(
            "{0}: precision '{1}' denotes an interval of exactly {2} s, not "
            "{3:.0f} s".format(path, evidence.get("precision"), expected,
                               (upper - lower).total_seconds())
        )


def _check_temporal_recomputation(evidence, path, errors):
    """The bounds are the ones ``(source_value, precision)`` actually denotes.

    This is what makes the derivation auditable rather than merely documented: a
    reviewer, and this validator, recompute it from the two observed facts. A
    bound that cannot be recomputed is a number with a plausible source
    reference, which is the failure the whole log exists to prevent.
    """
    try:
        lower, upper = derive_bounds(evidence.get("source_value"),
                                     evidence.get("precision"))
    except ValueError as error:
        errors.append("{0}.source_value: {1}".format(path, error))
        return
    for key, derived in (("lower_inclusive", lower), ("upper_exclusive", upper)):
        if key in evidence and evidence[key] != derived:
            errors.append(
                "{0}.{1}: '{2}' is not recomputable from source_value and "
                "precision, which denote '{3}'".format(
                    path, key, evidence[key], derived)
            )


def _check_temporal_evidence(event, path, errors):
    """Every reason ``event.temporal_evidence`` is not valid reduced evidence."""
    evidence = event.get(TEMPORAL_EVIDENCE_KEY)
    if not isinstance(evidence, dict):
        errors.append("{0}: expected an object".format(path))
        return

    unknown = sorted(set(evidence) - set(TEMPORAL_EVIDENCE_KEYS))
    if unknown:
        # The offset lives in source_value and nowhere else, so a second
        # offset-bearing field is refused by refusing every key the member does
        # not define. The names are echoed because they are contract keys the
        # adapter author chose, not values.
        errors.append(
            "{0}: unexpected field(s) {1}; the member is closed to {2}, and the "
            "UTC offset lives in source_value alone".format(
                path, ", ".join(unknown), ", ".join(TEMPORAL_EVIDENCE_KEYS))
        )

    kind = evidence.get("kind")
    if kind not in TEMPORAL_KINDS:
        errors.append("{0}.kind: '{1}' is not one of {2}".format(
            path, kind, ", ".join(TEMPORAL_KINDS)))

    precision = evidence.get("precision")
    if precision not in PRECISION_WIDTH_SECONDS:
        errors.append(
            "{0}.precision: '{1}' is not one of {2}; precision is declared, "
            "never inferred from how the value is spelled".format(
                path, precision, ", ".join(sorted(PRECISION_WIDTH_SECONDS)))
        )

    if "source_value" not in evidence:
        errors.append(
            "{0}.source_value: required field is missing; the lexical value the "
            "source stated is the observed fact the bounds are derived "
            "from".format(path)
        )

    _check_temporal_provenance(evidence, path, errors)
    _check_temporal_bounds(evidence, path, errors)
    if precision in PRECISION_WIDTH_SECONDS and "source_value" in evidence:
        _check_temporal_recomputation(evidence, path, errors)


def has_reduced_temporal_evidence(event):
    """Whether ``event`` carries **valid** reduced temporal evidence.

    Validity is the whole point: the capability report and the graph refusal both
    key on this, and a report that answered "the key is there" would advertise a
    bounded start for a member the validator is about to reject.
    """
    if not isinstance(event, dict) or TEMPORAL_EVIDENCE_KEY not in event:
        return False
    errors = []
    _check_temporal_evidence(event, "event.{0}".format(TEMPORAL_EVIDENCE_KEY), errors)
    return not errors


def _check_temporal_state(observation, errors):
    """D5 — exactly one of the two admissible temporal states, or refuse."""
    event = observation.get("event")
    if not isinstance(event, dict):
        # Already reported by _check_required; saying it again buries the finding
        # that names the fix.
        return
    path = "observation.event.{0}".format(TEMPORAL_EVIDENCE_KEY)
    exact = "start_time" in event
    reduced = TEMPORAL_EVIDENCE_KEY in event
    if exact and reduced:
        errors.append(
            "{0}: an event states its start exactly, in observation.event."
            "start_time, or as reduced-precision evidence here — never both. "
            "Two claims about one instant is an inconsistent dual "
            "assertion.".format(path)
        )
    elif not exact and not reduced:
        errors.append(
            "observation.event: required field is missing; state the start "
            "instant exactly in start_time, or as reduced-precision evidence in "
            "{0}".format(TEMPORAL_EVIDENCE_KEY)
        )
    if reduced:
        _check_temporal_evidence(event, path, errors)


def _check_statistics(statistics, path, errors):
    if not isinstance(statistics, dict):
        errors.append("{0}: expected an object of CURIE -> string".format(path))
        return
    allowed = official_property_curies()
    for curie in sorted(statistics):
        if curie.count(":") != 1 or not curie.split(":")[0]:
            errors.append(
                "{0}: '{1}' is not a CURIE; a statistic must be written "
                "'prefix:localName'".format(path, curie)
            )
            continue
        # Membership is the whole CURIE. Both halves have to be right together:
        # the prefix must be one the shared context binds, and the local name must
        # be one that prefix's namespace actually declares.
        if curie not in allowed:
            errors.append(
                "{0}: '{1}' is not an official Sport Schema property at the "
                "pinned commit".format(path, curie)
            )
        if not isinstance(statistics[curie], str):
            errors.append(
                "{0}.{1}: must be a string; the pinned shapes declare "
                "sh:datatype xsd:string for statistics".format(path, curie)
            )


def _check_participants(observation, errors):
    participants = observation.get("participants")
    if not isinstance(participants, list):
        errors.append("observation.participants: required field is missing")
        return
    if len(participants) < 2:
        errors.append("observation.participants: need at least 2")
    for index, participant in enumerate(participants):
        path = "observation.participants[{0}]".format(index)
        if not isinstance(participant, dict):
            errors.append("{0}: expected an object".format(path))
            continue
        required = ["kind", "provider_id", "name"]
        if participant.get("kind") == "team":
            # A TeamParticipation carries sport:alignment as a mandatory
            # property, and home/away is not derivable from list order.
            required.append("alignment")
        for key in required:
            if key not in participant:
                errors.append("{0}.{1}: required field is missing".format(path, key))
        kind = participant.get("kind")
        if kind is not None and kind not in PARTICIPANT_KINDS:
            errors.append(
                "{0}.kind: '{1}' is not one of {2}".format(
                    path, kind, ", ".join(PARTICIPANT_KINDS)
                )
            )
        if "statistics" in participant:
            _check_statistics(
                participant["statistics"], "{0}.statistics".format(path), errors
            )


def _check_resolution_method(node, path, errors):
    """``resolution_method`` is optional; when present it is one of three values.

    Checked rather than defaulted, because the field's whole job is to be the
    place a weak crosswalk says so. A value outside the set is not a weaker claim
    than ``provider-native`` — it is an unreadable one, and a consumer deciding
    whether to trust an identifier cannot act on it.
    """
    if not isinstance(node, dict) or "resolution_method" not in node:
        return
    method = node["resolution_method"]
    if method not in RESOLUTION_METHODS:
        errors.append(
            "{0}.resolution_method: '{1}' is not one of {2}".format(
                path, method, ", ".join(RESOLUTION_METHODS)
            )
        )


def _check_resolution_methods(observation, errors):
    for section in IDENTITY_BEARING_SECTIONS:
        node = observation
        path = "observation"
        for key in section:
            path = "{0}.{1}".format(path, key)
            node = node.get(key) if isinstance(node, dict) else None
        _check_resolution_method(node, path, errors)
    participants = observation.get("participants")
    if isinstance(participants, list):
        for index, participant in enumerate(participants):
            _check_resolution_method(
                participant, "observation.participants[{0}]".format(index), errors
            )


def _check_rights(observation, errors):
    rights = observation.get("rights")
    if rights is None:
        # Absence is already reported by _check_required, and an explicit null by
        # the fabrication scan. Saying it a third time here buries the one error
        # that names the fix.
        return
    if not isinstance(rights, dict):
        errors.append("observation.rights: expected an object")
        return
    if "data_class" not in rights:
        errors.append("observation.rights.data_class: required field is missing")
    for flag in ("prototype_only", "commercial_use"):
        if flag not in rights:
            errors.append("observation.rights.{0}: required field is missing".format(flag))
        elif not isinstance(rights[flag], bool):
            errors.append(
                "observation.rights.{0}: must be a boolean; a rights flag read "
                "as a truthy string is a licence decision made by accident".format(flag)
            )


def _check_adapter(observation, errors):
    adapter = observation.get("adapter")
    if adapter is None:
        # As in _check_rights: absence is reported once, by _check_required.
        return
    if not isinstance(adapter, dict):
        errors.append("observation.adapter: expected an object")
        return
    for key in ("name", "version"):
        if key not in adapter:
            errors.append("observation.adapter.{0}: required field is missing".format(key))
    _check_source_refs(adapter, errors)


#: Substrings that make a ``source_refs`` entry a request or a credential rather
#: than an endpoint class. A URL is how an API key, a licensed path or a customer
#: identifier ends up committed to a fixture file, and a fixture is the artefact
#: that gets published. Rejected here rather than stripped by the serializer:
#: stripping would let such a fixture validate clean, which is the wrong place to
#: be lenient.
#:
#: Written casefolded and matched casefolded. The first version of this tuple
#: matched raw substrings, so ``Authorization`` was refused while
#: ``authorization`` was accepted, ``token=`` while ``TOKEN=`` was accepted, and
#: ``key=`` while ``API_KEY=`` was accepted. Casing is not something the producer
#: of a leaked header controls on our behalf, so a case-sensitive credential
#: filter is a filter with a documented way round it.
#:
#: Order is the reported order: the URL and query markers come first because a
#: request-shaped value is the more useful thing to be told about, and the
#: ``api_key``/``api-key``/``apikey`` spellings precede ``key=`` so the error names
#: the whole word rather than its tail.
CREDENTIAL_MARKERS = (
    "://", "?", "&",
    "api_key", "api-key", "apikey", "key=",
    "token", "authorization", "bearer",
    "secret", "password", "cookie",
)

#: The fields of a ``source_refs`` entry that are published verbatim, and are
#: therefore all scanned. Scanning ``value`` alone would leave two published
#: fields as places to put the string ``value`` may not hold.
SOURCE_REF_TEXT_FIELDS = ("kind", "value", "note")


def credential_marker(text):
    """The first :data:`CREDENTIAL_MARKERS` entry ``text`` contains, or ``None``.

    Case-insensitive via ``str.casefold``, which folds more than ``lower`` does
    and is the right primitive for "are these the same characters" on text that
    did not have to be ASCII.

    Non-strings are not scanned. They are reported as a type error by the caller,
    and guessing at ``str()`` of a dict would invent text nobody wrote.
    """
    if not isinstance(text, str):
        return None
    folded = text.casefold()
    for marker in CREDENTIAL_MARKERS:
        if marker in folded:
            return marker
    return None


def source_ref_credential_findings(ref):
    """``[(field, marker)]`` for every published field of ``ref`` that is unsafe.

    The one rule both the validator and the serializer read. They used to be two
    rules — a substring tuple here and "the validator has already run" there —
    and the second one is not a rule at all: ``provenance_block`` is a public
    function, so a caller that skipped :func:`validate_observation` published
    whatever it was handed.
    """
    if not isinstance(ref, dict):
        return []
    findings = []
    for field in SOURCE_REF_TEXT_FIELDS:
        marker = credential_marker(ref.get(field))
        if marker is not None:
            findings.append((field, marker))
    return findings


def _check_source_refs(adapter, errors):
    """``adapter.source_refs`` is optional; when present it names endpoint classes.

    Optional because most adapters have nothing to add beyond their own name and
    version, and a required field with nothing to say gets filled with a
    placeholder.
    """
    refs = adapter.get("source_refs")
    if refs is None:
        return
    if not isinstance(refs, list):
        errors.append("observation.adapter.source_refs: expected an array")
        return
    for index, ref in enumerate(refs):
        pointer = "observation.adapter.source_refs[{0}]".format(index)
        if not isinstance(ref, dict):
            errors.append("{0}: expected an object".format(pointer))
            continue
        if set(ref) - {"kind", "value", "note"}:
            # The key names are not echoed, for the reason the values are not:
            # a key is producer-controlled text, so an entry keyed
            # "Authorization: Bearer …" published its own credential through
            # this finding and through the ValueError the envelope raises. Not
            # even the benign names are listed — an error whose text depends on
            # the keys says which of them was filtered, and is one edit away
            # from naming all of them again. The pointer is what the adapter
            # author fixes the entry with; the key names are what they already
            # have.
            errors.append("{0}: unexpected field name(s) redacted; only kind, "
                          "value and note are recorded".format(pointer))
        for key in ("kind", "value"):
            if not isinstance(ref.get(key), str) or not ref.get(key):
                errors.append("{0}.{1}: required non-empty string is missing".format(
                    pointer, key))
        for field, marker in source_ref_credential_findings(ref):
            # The value is the material being refused, so it is named by its
            # path and by the marker that matched, never by its text. Quoting it
            # moved the credential from the envelope — where it was caught — into
            # this error, and from there into every log, ticket and terminal that
            # read a validation finding or the ValueError the envelope raises.
            # The pointer is what the adapter author fixes the bug with; the
            # value is what they already have.
            errors.append(
                "{0}.{1}: request- or credential-shaped material was redacted "
                "(contains '{2}'). Record the endpoint class only; no URL, "
                "query or credential.".format(pointer, field, marker)
            )


def validate_observation(document):
    """Every reason ``document`` is not a valid canonical observation.

    An empty list means valid. The document is never modified.
    """
    if not isinstance(document, dict):
        return ["document: expected a JSON object"]

    errors = []
    declared = document.get("schema_version")
    if declared not in ACCEPTED_SCHEMA_VERSIONS:
        errors.append(
            "schema_version: '{0}' is not one of {1}".format(
                declared, ", ".join(ACCEPTED_SCHEMA_VERSIONS)
            )
        )

    observation = document.get("observation")
    if not isinstance(observation, dict):
        errors.append("observation: required field is missing")
        return errors

    _check_predecessor_carries_no_temporal_evidence(declared, observation, errors)
    _check_required(observation, errors)
    _check_temporal_state(observation, errors)
    _check_participants(observation, errors)
    _check_resolution_methods(observation, errors)
    _check_datetimes(observation, errors)
    _check_rights(observation, errors)
    _check_adapter(observation, errors)
    _scan_fabrication(observation, "observation", errors)
    return errors


def _check_predecessor_carries_no_temporal_evidence(declared, observation, errors):
    """A document may not carry a member the contract it declares never defined.

    The predecessor identifier stays accepted so existing exact documents keep
    reading, and that is all it stays accepted for. Reading temporal evidence
    under it would validate a document against a contract that does not describe
    it — the "member added without a bump" failure the version bump exists to
    make impossible.
    """
    if declared != PREDECESSOR_SCHEMA_VERSION:
        return
    event = observation.get("event")
    if isinstance(event, dict) and TEMPORAL_EVIDENCE_KEY in event:
        errors.append(
            "schema_version: '{0}' defines no observation.event.{1}; a document "
            "carrying reduced-precision temporal evidence declares '{2}'".format(
                PREDECESSOR_SCHEMA_VERSION, TEMPORAL_EVIDENCE_KEY, SCHEMA_VERSION
            )
        )

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

from . import SCHEMA_VERSION

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

#: Keys ``observation.event`` must carry. An event without a status is not an
#: event we can place on a timeline, and one without a start time is not an event
#: we can place at all.
REQUIRED_EVENT_KEYS = ("provider_id", "start_time", "status")

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

_allowlist_cache = None


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
        extra = sorted(set(ref) - {"kind", "value", "note"})
        if extra:
            errors.append("{0}: unexpected key(s) {1}; only kind, value and note "
                          "are recorded".format(pointer, ", ".join(extra)))
        for key in ("kind", "value"):
            if not isinstance(ref.get(key), str) or not ref.get(key):
                errors.append("{0}.{1}: required non-empty string is missing".format(
                    pointer, key))
        for field, marker in source_ref_credential_findings(ref):
            errors.append(
                "{0}.{1}: '{2}' looks like a request or a credential rather "
                "than an endpoint class (contains '{3}'). Record the endpoint "
                "class only; no URL, query or credential.".format(
                    pointer, field, ref[field], marker)
            )


def validate_observation(document):
    """Every reason ``document`` is not a valid canonical observation.

    An empty list means valid. The document is never modified.
    """
    if not isinstance(document, dict):
        return ["document: expected a JSON object"]

    errors = []
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            "schema_version: expected '{0}', found '{1}'".format(
                SCHEMA_VERSION, document.get("schema_version")
            )
        )

    observation = document.get("observation")
    if not isinstance(observation, dict):
        errors.append("observation: required field is missing")
        return errors

    _check_required(observation, errors)
    _check_participants(observation, errors)
    _check_resolution_methods(observation, errors)
    _check_datetimes(observation, errors)
    _check_rights(observation, errors)
    _check_adapter(observation, errors)
    _scan_fabrication(observation, "observation", errors)
    return errors

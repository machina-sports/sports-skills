"""A credential-shaped ``source_ref`` is refused here, and never reaches an envelope.

``adapter.source_refs`` is the one free-text field this package publishes verbatim:
its entries land in ``provenance.source_refs``, stamped with the note "endpoint class
only; no URL, query or credential is recorded". So a leaked ``Authorization`` header
that survives the check is not merely accepted — it is published under a note stating
that it is not there.

The reviewer's evidence is reproduced below as data rather than prose, because the
whole finding was about casing and about which field the string was put in:

- ``Authorization`` was refused and ``authorization`` accepted;
- ``token=`` refused and ``TOKEN=``/``ToKeN=`` accepted;
- ``key=`` refused and ``API_KEY=``/``api-key``/``apikey`` accepted;
- ``password``, ``cookie`` and ``set-cookie`` were not markers at all;
- and every one of those was scanned in ``value`` only, so ``kind`` and ``note`` —
  both published verbatim — were unguarded even for the markers that did work.

Both ends are checked, because they fail closed for different reasons.
``canonical_envelope`` raises, which is what a caller going through
:mod:`sports_skills.canonical` hits. ``provenance_block`` is public and can be called
on its own; it used to project whatever it was handed on the grounds that the
validator had run, and nothing made that true. These tests are this repository's own
evidence — the rule itself lives upstream in the vendored runtime and is re-vendored,
never edited here.
"""

import json

import pytest

from sports_skills import canonical
from sports_skills.canonical._vendored.ids import surrogate_resolver
from sports_skills.canonical._vendored.observation import validate_observation
from sports_skills.canonical._vendored.serialize import SOURCE_REF_NOTE, provenance_block
from tests.test_canonical_reference_fixtures import NATIVE_PATH

OBSERVED_AT = "2026-03-01T22:05:00+00:00"

#: The reviewer's evidence, one string per reported bypass. Each is applied to every
#: published field in turn, so the parametrization is the finding: a marker that only
#: works in ``value``, or only in one casing, fails a row here rather than passing the
#: suite.
CREDENTIAL_EVIDENCE = (
    "Authorization: Bearer abc123",
    "authorization: Bearer abc123",
    "AuThOrIzAtIoN: Bearer abc123",
    "token=abc123",
    "TOKEN=abc123",
    "ToKeN=abc123",
    "API_KEY=abc123",
    "api-key: abc123",
    "apikey abc123",
    "password=hunter2",
    "secret=abc123",
    "SECRET=abc123",
    "cookie: session=abc123",
    "set-cookie: session=abc123",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/summary",
    "espn/summary?event=9001",
    "espn/summary&lang=en",
)

#: What an honest entry looks like: an endpoint class, opaque, naming no host, no
#: query and no credential. These must keep validating and keep being published —
#: a filter that also drops these has replaced one bug with a quieter one.
SAFE_REFS = (
    {"kind": "endpoint-class", "value": "espn/summary"},
    {"kind": "endpoint-class", "value": "espn/scoreboard", "note": "one event per row"},
    {"kind": "fixture", "value": "sports-skills-espn-soccer-native"},
)

#: The fields of a ``source_refs`` entry that reach the envelope verbatim.
PUBLISHED_FIELDS = ("kind", "value", "note")


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def observation_with(refs):
    """The reference observation, with its ``source_refs`` replaced.

    Built through the real adapter rather than hand-written, so everything except the
    entry under test is a document that is known to validate and known to serialize.
    """
    document = canonical.to_observation(native(), observed_at=OBSERVED_AT)
    document["observation"]["adapter"]["source_refs"] = [dict(ref) for ref in refs]
    return document


def ref_carrying(field, text):
    """One entry that is safe except for ``text`` in ``field``."""
    ref = {"kind": "endpoint-class", "value": "espn/summary"}
    ref[field] = text
    return ref


@pytest.mark.parametrize("text", CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_a_credential_shaped_source_ref_is_refused_in_every_published_field(field, text):
    errors = validate_observation(observation_with([ref_carrying(field, text)]))
    assert errors, f"{field} carrying {text!r} validated clean"
    assert any(
        f"observation.adapter.source_refs[0].{field}" in error for error in errors
    ), errors


@pytest.mark.parametrize("text", CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_an_envelope_is_refused_rather_than_built_from_one(field, text):
    with pytest.raises(ValueError) as raised:
        canonical.to_envelope(observation_with([ref_carrying(field, text)]))
    assert f"source_refs[0].{field}" in str(raised.value)


@pytest.mark.parametrize("text", CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_the_provenance_block_drops_one_rather_than_publishing_it(field, text):
    """``provenance_block`` is public, so "the validator already ran" is not a rule.

    A caller reaching it directly is the path the raise above does not cover, and it
    is the path that would publish the string under the note that says it did not.
    """
    document = observation_with([ref_carrying(field, text), SAFE_REFS[0]])
    block = provenance_block(document, id_resolver=surrogate_resolver("sports-skills/espn"))

    assert block["provenance"]["source_refs"] == [
        {"kind": "endpoint-class", "value": "espn/summary", "note": SOURCE_REF_NOTE}
    ]
    assert text not in json.dumps(block, ensure_ascii=False)


@pytest.mark.parametrize("text", CREDENTIAL_EVIDENCE)
def test_the_only_entry_being_unsafe_leaves_no_source_refs_at_all(text):
    """The block omits the key rather than publishing an empty promise."""
    document = observation_with([ref_carrying("value", text)])
    block = provenance_block(document, id_resolver=surrogate_resolver("sports-skills/espn"))

    assert "source_refs" not in block["provenance"]
    assert text not in json.dumps(block, ensure_ascii=False)


def test_an_opaque_endpoint_class_still_validates_and_is_still_published():
    document = observation_with(SAFE_REFS)
    assert validate_observation(document) == []

    block = provenance_block(document, id_resolver=surrogate_resolver("sports-skills/espn"))
    assert block["provenance"]["source_refs"] == [
        {"kind": "endpoint-class", "value": "espn/summary", "note": SOURCE_REF_NOTE},
        {"kind": "endpoint-class", "value": "espn/scoreboard", "note": "one event per row"},
        {"kind": "fixture", "value": "sports-skills-espn-soccer-native", "note": SOURCE_REF_NOTE},
    ]


def test_the_note_that_states_the_constraint_does_not_trip_the_constraint():
    """``SOURCE_REF_NOTE`` says "no URL, query or credential is recorded". A filter
    matching the word "credential" would drop every unannotated entry it stamps."""
    document = observation_with([{"kind": "endpoint-class", "value": "espn/summary",
                                  "note": SOURCE_REF_NOTE}])
    assert validate_observation(document) == []

    block = provenance_block(document, id_resolver=surrogate_resolver("sports-skills/espn"))
    assert block["provenance"]["source_refs"][0]["note"] == SOURCE_REF_NOTE


def test_the_envelope_this_package_actually_ships_names_no_credential_anywhere():
    """The end-to-end statement, over the whole document rather than one block.

    Credential words only. ``://`` is deliberately not checked here: the envelope is
    JSON-LD, so its ``@context`` and its upstream pin are URLs by construction, and a
    document-wide ban on them would be a test that can only be made to pass by
    breaking the format. Where ``://`` genuinely must not appear is a published
    ``source_ref``, which the test below states over the fields that carry one.
    """
    document = canonical.canonicalize_event(native(), observed_at=OBSERVED_AT)
    blob = json.dumps(document, ensure_ascii=False).casefold()

    for marker in ("authorization", "bearer", "api_key", "api-key", "apikey",
                   "token", "password", "cookie", "secret"):
        assert marker not in blob, marker


def test_no_published_source_ref_field_carries_a_url_or_a_query():
    document = canonical.canonicalize_event(native(), observed_at=OBSERVED_AT)
    refs = document["machina_sports_schema"]["provenance"]["source_refs"]

    assert refs, "the shipped envelope publishes no source_refs at all"
    for ref in refs:
        for field in PUBLISHED_FIELDS:
            for marker in ("://", "?", "&"):
                assert marker not in ref.get(field, ""), (field, marker, ref)

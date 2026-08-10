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

**Refusing is half of it: the refusal must not repeat what it refused.** A rejected
entry is named by its pointer, never by its text, because the alternative moves the
credential from one published surface to another — out through
``validate_observation``'s findings and through the ``ValueError``
:func:`canonical.to_envelope` raises, and from there into whatever log, ticket or
terminal read them. Two classes of producer-controlled text are proven absent from
every surface this package exposes, each with a sentinel that exists nowhere else in
the repository so absence is provable rather than merely plausible:

1. **The published fields.** ``kind``, ``value`` and ``note`` reach
   ``provenance.source_refs`` verbatim, so credential- and request-shaped text in any
   of them must appear in no finding, no exception, and no serialized surface.
2. **The key names.** A key is the fourth place in the same entry a producer can put
   ``Authorization: Bearer …``, and the error that echoed the sorted unexpected keys
   published it through exactly the surfaces the value redaction exists to keep
   clean. Benign names are not listed either: an error whose text depends on the keys
   says which of them was the interesting one, and is one edit away from naming all of
   them again.

Both classes are driven through the validator, the raise, and the three public
builders with validation bypassed — and the safe opaque refs are asserted to keep
validating and to keep being emitted unchanged, because a filter that also drops
those has replaced one bug with a quieter one.
"""

import json

import pytest

from sports_skills import canonical
from sports_skills.canonical._vendored.ids import surrogate_resolver
from sports_skills.canonical._vendored.observation import validate_observation
from sports_skills.canonical._vendored.serialize import (
    SOURCE_REF_NOTE,
    event_view,
    provenance_block,
    sport_schema_graph,
)
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

#: One string that appears nowhere else in this repository, embedded in every shape
#: below. Absence of the raw text is the property under test, and searching for the
#: raw text alone is not enough to establish it: a redacted finding legitimately
#: names the *marker* that matched, so ``"token"`` appears in the message that refused
#: ``token=…``. The sentinel has exactly one possible origin, so finding it on any
#: surface means that surface echoed producer-controlled text.
SENTINEL = "SPORTS_SKILLS_SOURCE_REF_SENTINEL_4a91c7"

#: The credential and request shapes again, each carrying the sentinel. Separate from
#: :data:`CREDENTIAL_EVIDENCE` rather than folded into it, because that tuple is the
#: reviewer's report quoted literally and is worth keeping readable as such; this one
#: is the same shapes instrumented so that "it was not echoed" is checkable.
SENTINEL_CREDENTIAL_EVIDENCE = tuple(template.format(SENTINEL) for template in (
    "Authorization: Bearer {0}",
    "authorization: Bearer {0}",
    "AuThOrIzAtIoN: Bearer {0}",
    "token={0}",
    "TOKEN={0}",
    "access_token={0}",
    "API_KEY={0}",
    "api-key: {0}",
    "apikey {0}",
    "password={0}",
    "secret={0}",
    "SECRET={0}",
    "cookie: session={0}",
    "set-cookie: session={0}",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/summary?event={0}",
    "espn/summary?event={0}",
    "espn/summary&lang={0}",
))

#: Unexpected key names shaped like the material a leaked header, a query string or a
#: pasted URL produces — plus the bare sentinel, because a key does not have to look
#: dangerous to be somebody's identifier.
DANGEROUS_UNEXPECTED_KEYS = tuple(template.format(SENTINEL) for template in (
    "Authorization: Bearer {0}",
    "authorization: Bearer {0}",
    "token={0}",
    "TOKEN={0}",
    "access_token={0}",
    "API_KEY={0}",
    "api-key: {0}",
    "password={0}",
    "client_secret={0}",
    "cookie: session={0}",
    "Set-Cookie: session={0}",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/summary?event={0}",
    "espn/summary?event={0}",
    "{0}",
))

#: Unexpected keys with nothing dangerous in them, one of them carrying the sentinel.
#: These must not be listed either, for the reason given in the module docstring: an
#: error that names the benign keys and hides the rest reports which key was worth
#: looking at. Chosen so that none of them is a fragment of text the refusal or the
#: envelope contains by construction — ``kind``, ``value`` and ``endpoint`` all appear
#: in a clean output, so a key spelled that way could not distinguish an echo from the
#: surface's own words. The sentinel-bearing one carries no such ambiguity and is what
#: makes the benign half of this class provable at all.
BENIGN_UNEXPECTED_KEYS = (
    "notes",
    "Value",
    "extra_field",
    "url_class",
    f"note_{SENTINEL}",
)

#: Both classes of unexpected key. Every assertion below runs over all of them: the
#: rule is that the refusal does not depend on the key, so a test that only covered
#: the frightening ones would pass on a filter that listed the rest.
UNEXPECTED_KEYS = DANGEROUS_UNEXPECTED_KEYS + BENIGN_UNEXPECTED_KEYS


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


def ref_with_key(key):
    """One entry that is safe except for carrying an unexpected ``key``."""
    ref = {"kind": "endpoint-class", "value": "espn/summary"}
    ref[key] = "x"
    return ref


def resolver():
    return surrogate_resolver("sports-skills/espn")


def serialized_surfaces(document):
    """Every public builder that can publish a ``source_refs`` entry, called directly.

    Validation is bypassed on purpose. Each of these is exported, so "the validator
    already ran" is not a rule they are entitled to rely on; the whole point of the
    filter living in the projection as well as in the validator is that these three
    hold on their own. ``canonical_envelope`` composes all three and is covered by the
    raise instead, since it refuses to build at all.

    ``provenance`` is serialized whole rather than reduced to its ``source_refs``: the
    block also copies the observation's ``adapter`` section, which is where the
    unfiltered list would travel if the copy stopped dropping it.
    """
    return {
        "provenance": provenance_block(document, id_resolver=resolver()),
        "event_view": event_view(document, id_resolver=resolver()),
        "sport_schema_graph": sport_schema_graph(document, id_resolver=resolver()),
    }


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


# --------------------------------------------------------------------------------
# Class 1: the refusal never repeats the credential- or request-shaped text.
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("text", SENTINEL_CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_no_credential_shaped_text_reaches_the_validation_findings(field, text):
    """The finding says where and why, and quotes nothing.

    Asserted as "the pointer and the marker survived, the text did not" rather than
    against the message verbatim: the message is the vendored runtime's, so restating
    it here would give one sentence two owners across the vendoring boundary and make
    an upstream copy edit look like a security regression.
    """
    errors = validate_observation(observation_with([ref_carrying(field, text)]))
    joined = "\n".join(errors)

    assert f"observation.adapter.source_refs[0].{field}" in joined, errors
    assert "endpoint class" in joined, errors
    assert text not in joined
    assert SENTINEL not in joined


@pytest.mark.parametrize("text", SENTINEL_CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_no_credential_shaped_text_reaches_the_raised_exception(field, text):
    """The path a caller of :mod:`sports_skills.canonical` actually takes.

    The ValueError carries every finding, so it is the surface that ends up in a log
    line, a CI transcript or a pasted traceback.
    """
    with pytest.raises(ValueError) as raised:
        canonical.to_envelope(observation_with([ref_carrying(field, text)]))
    message = str(raised.value)

    assert f"source_refs[0].{field}" in message
    assert text not in message
    assert SENTINEL not in message


@pytest.mark.parametrize("text", SENTINEL_CREDENTIAL_EVIDENCE)
@pytest.mark.parametrize("field", PUBLISHED_FIELDS)
def test_no_credential_shaped_text_reaches_any_serialized_surface(field, text):
    document = observation_with([ref_carrying(field, text), SAFE_REFS[0]])
    for name, built in sorted(serialized_surfaces(document).items()):
        blob = json.dumps(built, ensure_ascii=False)
        assert text not in blob, name
        assert SENTINEL not in blob, name


@pytest.mark.parametrize("text", SENTINEL_CREDENTIAL_EVIDENCE)
def test_the_safe_entry_beside_a_rejected_one_is_still_published_unchanged(text):
    """Dropping the unsafe entry is not permission to drop the record it sat in."""
    document = observation_with([ref_carrying("value", text), SAFE_REFS[0]])
    block = provenance_block(document, id_resolver=resolver())["provenance"]

    assert block["source_refs"] == [
        {"kind": "endpoint-class", "value": "espn/summary", "note": SOURCE_REF_NOTE}
    ]


# --------------------------------------------------------------------------------
# Class 2: nor does it repeat the unexpected key names.
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("key", UNEXPECTED_KEYS)
def test_an_unexpected_source_ref_key_is_refused_without_being_named(key):
    errors = validate_observation(observation_with([ref_with_key(key)]))

    assert len(errors) == 1, errors
    assert errors[0].startswith("observation.adapter.source_refs[0]:"), errors[0]
    assert key not in errors[0]
    assert SENTINEL not in errors[0]


def test_the_unexpected_key_finding_does_not_depend_on_the_keys_at_all():
    """The invariant the per-key assertions above are instances of.

    Stated as one set because it is the rule that cannot be satisfied by a longer
    denylist: if the message varies with the key, some key is being described, and the
    next shape nobody thought of is the one it describes in full.
    """
    findings = {
        "\n".join(validate_observation(observation_with([ref_with_key(key)])))
        for key in UNEXPECTED_KEYS
    }
    assert len(findings) == 1, findings


def test_several_unexpected_keys_at_once_are_one_finding_naming_none_of_them():
    ref = {"kind": "endpoint-class", "value": "espn/summary"}
    for key in DANGEROUS_UNEXPECTED_KEYS[:3] + BENIGN_UNEXPECTED_KEYS[:2]:
        ref[key] = "x"
    errors = validate_observation(observation_with([ref]))

    assert len(errors) == 1, errors
    assert SENTINEL not in errors[0]


def test_each_entry_with_an_unexpected_key_is_reported_against_its_own_index():
    errors = validate_observation(observation_with([
        SAFE_REFS[0],
        ref_with_key(DANGEROUS_UNEXPECTED_KEYS[0]),
        ref_with_key("notes"),
    ]))

    assert [error.split(":")[0] for error in errors] == [
        "observation.adapter.source_refs[1]",
        "observation.adapter.source_refs[2]",
    ], errors
    assert SENTINEL not in "\n".join(errors)


def test_redacting_the_key_names_does_not_swallow_the_entry_s_other_faults():
    """The entry has two problems and the author is told about both.

    A redaction that reported the key and stopped would hide the one finding naming a
    field they can actually act on.
    """
    ref = {"kind": "endpoint-class", "value": "token=" + SENTINEL}
    ref[DANGEROUS_UNEXPECTED_KEYS[0]] = "x"
    errors = validate_observation(observation_with([ref]))

    assert len(errors) == 2, errors
    assert any(error.startswith("observation.adapter.source_refs[0]:") for error in errors)
    assert any("source_refs[0].value" in error for error in errors)
    assert SENTINEL not in "\n".join(errors)


@pytest.mark.parametrize("key", UNEXPECTED_KEYS)
def test_no_unexpected_key_name_reaches_the_raised_exception(key):
    with pytest.raises(ValueError) as raised:
        canonical.to_envelope(observation_with([ref_with_key(key)]))
    message = str(raised.value)

    assert "observation.adapter.source_refs[0]" in message
    assert key not in message
    assert SENTINEL not in message


@pytest.mark.parametrize("key", UNEXPECTED_KEYS)
def test_no_unexpected_key_name_reaches_any_serialized_surface(key):
    document = observation_with([ref_with_key(key)])
    for name, built in sorted(serialized_surfaces(document).items()):
        blob = json.dumps(built, ensure_ascii=False)
        assert key not in blob, name
        assert SENTINEL not in blob, name


@pytest.mark.parametrize("key", UNEXPECTED_KEYS)
def test_an_entry_whose_only_fault_is_the_key_still_publishes_its_endpoint_class(key):
    """The projection copies the three recorded fields rather than filtering the key
    out of the entry, which is why the name cannot reach the output at all."""
    document = observation_with([ref_with_key(key)])
    block = provenance_block(document, id_resolver=resolver())["provenance"]

    assert block["source_refs"] == [
        {"kind": "endpoint-class", "value": "espn/summary", "note": SOURCE_REF_NOTE}
    ]

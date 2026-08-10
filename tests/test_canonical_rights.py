"""Two rights questions, two answers, and one gate that reads neither of them loosely.

**What is this data?** is answered at runtime, by the class the adapter stamps onto
every envelope it emits. This package reads ESPN's public endpoints, so the answer is
``open-public`` — for the synthetic reference fixture and for every real match the
published adapter will ever read, because it is one constant in one module. A class
naming the fixture instead would travel out attached to live ESPN events and call them
synthetic, which is a false statement about real data.

**What is the checked-in evidence behind the reference fixture?** is a different
question with a different answer, ``mapping-contract-synthetic``, and it stays recorded
in machina-templates' ``provenance.json`` rather than in the envelope. This repository
holds the other half: the source payload must stay obviously invented.

**May this consumer consume it?** is the gate, and it is vendored rather than written
here. Reimplementing a licence rule on the near side of a repository boundary gives two
definitions of one contract, and the copy that drifts is the one deciding whether
prototype-only data reaches a commercial surface.
"""

import ast
import json
from pathlib import Path

from sports_skills import canonical
from sports_skills.canonical.adapters import football
from tests.test_canonical_reference_fixtures import (
    ENVELOPE_PATH,
    NATIVE_PATH,
    OBSERVATION_PATH,
)

OBSERVED_AT = "2026-03-01T22:05:00+00:00"

#: The **runtime** classification: what the data this adapter emits actually is.
RUNTIME_RIGHTS_CLASS = "open-public"

#: The **fixture evidence** classification, which lives in machina-templates'
#: provenance and must never be written into a runtime rights block.
FIXTURE_EVIDENCE_CLASS = "mapping-contract-synthetic"

CANONICAL_PACKAGE = Path(__file__).resolve().parents[1] / "src/sports_skills/canonical"

VENDORED = CANONICAL_PACKAGE / "_vendored"

#: Every finding code the gate can return. Named here so the static test below can
#: assert this repository defines none of them outside the vendored copy.
FINDING_CODES = (
    "rights-prototype-only",
    "rights-non-commercial",
    "rights-unreadable",
    "rights-unknown-consumer-tier",
)


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def envelope():
    return canonical.canonicalize_event(native(), observed_at=OBSERVED_AT)


# ---------------------------------------------------------------------------
# The runtime class is not the fixture evidence class
# ---------------------------------------------------------------------------

def test_the_adapter_stamps_the_runtime_open_data_class():
    """The load-bearing constant. It is emitted onto live ESPN reads, so it has to
    describe the reading rather than the fixture the reading was demonstrated on."""
    assert football.RIGHTS["data_class"] == RUNTIME_RIGHTS_CLASS


def test_reclassifying_the_data_did_not_relax_the_two_flags_the_gate_reads():
    """``open-public`` describes the source, not an entitlement. The package is public
    and personal/non-commercial and can never emit anything else."""
    assert football.RIGHTS["prototype_only"] is True
    assert football.RIGHTS["commercial_use"] is False


def test_no_runtime_rights_class_calls_a_real_event_synthetic():
    """Every place the class travels in a freshly built envelope. The word
    ``synthetic`` or ``prototype`` in any of them is a lie about every live match."""
    document = envelope()["machina_sports_schema"]
    graph_node = next(node for node in document["sport_schema_graph"]["@graph"]
                      if "machina:rightsClass" in node)
    for label, value in (
        ("adapter constant", football.RIGHTS["data_class"]),
        ("envelope rights", document["rights"]["data_class"]),
        ("envelope provenance", document["provenance"]["rights"]["data_class"]),
        ("graph machina:rightsClass", graph_node["machina:rightsClass"]),
    ):
        assert value == RUNTIME_RIGHTS_CLASS, label
        assert "synthetic" not in value, label
        assert "prototype" not in value, label


def test_the_checked_in_reference_fixtures_carry_the_runtime_class():
    """The contract bytes, not the live output. These are the files machina-templates
    published, so a class change that did not reach them is drift, not a decision."""
    observation = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))["observation"]
    assert observation["rights"]["data_class"] == RUNTIME_RIGHTS_CLASS

    document = json.loads(ENVELOPE_PATH.read_text(encoding="utf-8"))["machina_sports_schema"]
    assert document["rights"]["data_class"] == RUNTIME_RIGHTS_CLASS
    assert document["provenance"]["rights"]["data_class"] == RUNTIME_RIGHTS_CLASS


def test_the_two_classes_are_not_the_same_string():
    """The guard against 'simplifying' them back into one field. If they ever
    collapse, one of the two facts has been lost."""
    assert RUNTIME_RIGHTS_CLASS != FIXTURE_EVIDENCE_CLASS
    assert FIXTURE_EVIDENCE_CLASS not in RUNTIME_RIGHTS_CLASS


def test_the_fixture_evidence_stays_synthetic_outside_the_rights_block():
    """The fact that moved out of the envelope did not evaporate: the payload behind
    the reference row is still, visibly, invented. This is the half of the two-class
    split that this repository owns — no real ESPN event may ever be labelled
    synthetic, and no synthetic one may pass as real."""
    blob = NATIVE_PATH.read_text(encoding="utf-8")
    assert "Synthetic" in blob
    for token in ("Arsenal", "Real Madrid", "Premier League", "espn.com"):
        assert token not in blob, token

    observation = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))["observation"]
    assert observation["raw"] == native()


# ---------------------------------------------------------------------------
# The gate, vendored rather than reimplemented
# ---------------------------------------------------------------------------

def test_the_public_surface_exposes_the_vendored_gate_itself():
    """Not a copy of it, and not a wrapper that could disagree with it. The identity
    check is the whole point: this package and machina-templates have to answer the
    same question about the same document with the same code."""
    from sports_skills.canonical._vendored import rights as vendored_rights

    assert canonical.rights_findings is vendored_rights.rights_findings
    assert canonical.CONSUMER_TIERS is vendored_rights.CONSUMER_TIERS


def test_a_production_consumer_is_refused_once_with_an_actionable_finding():
    findings = canonical.rights_findings(envelope(), consumer_tier="production")
    assert len(findings) == 1
    assert findings[0]["code"] == "rights-prototype-only"
    assert findings[0]["consumer_tier"] == "production"
    assert findings[0]["data_class"] == RUNTIME_RIGHTS_CLASS
    assert "prototype_only" in findings[0]["detail"]


def test_a_prototype_consumer_may_consume_the_envelope():
    assert canonical.rights_findings(envelope(), consumer_tier="prototype") == []


def test_the_gate_fails_closed_on_a_document_it_cannot_read_a_licence_from():
    """An absent rights block is the absence of a claim, not a permissive claim."""
    document = envelope()
    document["machina_sports_schema"].pop("rights")
    findings = canonical.rights_findings(document, consumer_tier="production")
    assert [finding["code"] for finding in findings] == ["rights-unreadable"]
    assert canonical.rights_findings({}, consumer_tier="prototype")[0]["code"] == (
        "rights-unreadable"
    )


def test_an_unknown_consumer_tier_is_refused_rather_than_read_as_the_lenient_one():
    findings = canonical.rights_findings(envelope(), consumer_tier="enterprise")
    assert [finding["code"] for finding in findings] == ["rights-unknown-consumer-tier"]


def test_the_tiers_are_exactly_prototype_and_production():
    assert canonical.CONSUMER_TIERS == ("prototype", "production")


def test_this_repository_defines_no_second_rights_rule():
    """Static, so it holds for every code path. A module of this package that spelled
    one of the finding codes itself would be a second definition of the licence rule,
    which is the drift the vendoring exists to prevent."""
    scanned = 0
    for path in sorted(CANONICAL_PACKAGE.rglob("*.py")):
        if VENDORED in path.parents:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8")
        for code in FINDING_CODES:
            assert code not in text, (path.name, code)
    assert scanned > 0


def test_the_gate_is_reachable_without_importing_anything_from_machina_templates():
    """The reason it is vendored at all: a consumer of this package has no checkout of
    the other repository, and the rule still has to run."""
    source = (VENDORED / "rights.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        module = None
        if isinstance(node, ast.Import):
            module = node.names[0].name
        elif isinstance(node, ast.ImportFrom):
            module = node.module
        if module:
            assert not module.startswith("tools"), module

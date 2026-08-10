"""The cross-repository reference contract, as bytes this repository ships.

``machina-templates`` deliberately ships no sports-skills/ESPN adapter. What it
ships is the contract: a synthetic native payload, the observation that payload must
produce, and the envelope its serializer emits from that observation. This repository
owns the adapter, and these three files are what its output is compared to.

They are checked in here rather than read from the other repository, because CI has
no checkout of it. So the pin is a recorded sha256, and the cross-repository
comparison is an extra test that runs only when a checkout happens to be at hand.
That split is the point: normal CI is self-contained, and a developer with both
worktrees open gets the stronger check for free.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures/canonical"

MANIFEST_PATH = FIXTURES / "REFERENCE-CONTRACT.json"

NATIVE_PATH = FIXTURES / "sports-skills-espn-soccer-native.json"
OBSERVATION_PATH = FIXTURES / "sports-skills-espn-soccer-observation.json"
ENVELOPE_PATH = FIXTURES / "sports-skills-espn-soccer-envelope.json"

#: The keys ``_normalize_espn_event`` returns, in the order it builds them. The
#: source fixture must have exactly these: a fixture in a shape the adapter's real
#: input never has would test nothing about the adapter that reads it.
NATIVE_KEYS = (
    "id", "status", "start_time", "matchday", "round", "round_name",
    "competition", "season", "venue", "competitors", "scores", "odds",
    "referees",
)

#: The four native fields that carry a stand-in rather than a fact, and what they
#: carry. Present in the source payload on purpose; the adapter contract is that
#: every one of them is dropped.
NATIVE_PLACEHOLDERS = {
    "matchday": None,
    "round": "",
    "round_name": "",
    "odds": None,
}


def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def canonical_bytes(document):
    """The exact bytes every fixture in this contract is checked in as.

    Duplicated from machina-templates' contract test on purpose: it is the format
    the two repositories agree on, so it has to be stated on both sides of the
    boundary rather than imported across it.
    """
    return json.dumps(document, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def templates_checkout():
    """A machina-templates checkout that *contains* the pinned commit, or ``None``.

    Containment rather than ``HEAD ==``: the pin is a commit, and git can produce that
    commit's bytes from any checkout that has it, whatever the working tree is currently
    on. Requiring ``HEAD`` to match made this gate skip itself the moment the sibling
    repository landed its next commit — which is always, since it is under active
    development — so the strong half of the contract stopped running for a reason that
    had nothing to do with drift. ``pinned_bytes`` below reads the blob, never the file
    on disk, so a dirty or advanced worktree cannot make this test pass *or* fail.
    """
    candidates = []
    configured = os.environ.get("MACHINA_TEMPLATES_ROOT")
    if configured:
        candidates.append(Path(configured))
    repo_root = Path(__file__).resolve().parents[1]
    candidates.extend(sorted(repo_root.parent.glob("machina-templates*")))

    pinned = manifest()["source_commit"]
    for candidate in candidates:
        if not (candidate / ".git").exists():
            continue
        try:
            subprocess.run(
                ["git", "-C", str(candidate), "cat-file", "-e", pinned + "^{commit}"],
                capture_output=True, check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        return candidate
    return None


def pinned_bytes(checkout, source_path, commit=None):
    """One file's bytes exactly as the pinned commit recorded them."""
    return subprocess.run(
        ["git", "-C", str(checkout), "show",
         f"{commit or manifest()['source_commit']}:{source_path}"],
        capture_output=True, check=True,
    ).stdout


def test_the_manifest_names_its_upstream_source_and_pins_every_fixture():
    document = manifest()
    assert document["source_repository"] == "machina-sports/machina-templates"
    assert len(document["source_commit"]) == 40
    assert sorted(document["files"]) == [
        "sports-skills-espn-soccer-envelope.json",
        "sports-skills-espn-soccer-native.json",
        "sports-skills-espn-soccer-observation.json",
    ]
    for name, entry in sorted(document["files"].items()):
        assert entry["source_path"].startswith("tools/iptc/fixtures/"), name
        assert entry["source_path"].endswith(name), name
        assert len(entry["sha256"]) == 64, name


def test_every_fixture_matches_the_recorded_hash():
    """The self-contained half of the gate: this is what CI runs, with no checkout
    of the other repository anywhere."""
    for name, entry in sorted(manifest()["files"].items()):
        local = FIXTURES / name
        assert local.is_file(), name
        assert hashlib.sha256(local.read_bytes()).hexdigest() == entry["sha256"], (
            f"{name} is no longer the contract machina-templates published; re-copy it "
            "and regenerate REFERENCE-CONTRACT.json in the same change"
        )


def test_the_fixture_directory_ships_nothing_the_manifest_does_not_pin():
    shipped = sorted(
        path.name for path in FIXTURES.iterdir()
        if path.is_file() and path.name != MANIFEST_PATH.name
    )
    assert shipped == sorted(manifest()["files"])


def test_every_fixture_is_checked_in_as_canonical_bytes():
    """Byte-for-byte comparison is only meaningful if the serialization is agreed.
    A fixture reformatted by an editor would fail the adapter tests for a reason
    that has nothing to do with the adapter."""
    for path in (NATIVE_PATH, OBSERVATION_PATH, ENVELOPE_PATH):
        text = path.read_text(encoding="utf-8")
        assert text == canonical_bytes(json.loads(text)), path.name


def test_the_source_fixture_is_the_shape_this_repository_actually_returns():
    """Checked against the live normalizer rather than a copied key list, because a
    copied list agrees with itself forever. ``_normalize_espn_event`` is pure and
    reads nothing off the network, so an empty payload is enough to read its shape.
    """
    from sports_skills.football._connector import _normalize_espn_event

    native = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
    assert tuple(native) == NATIVE_KEYS
    assert tuple(_normalize_espn_event({})) == NATIVE_KEYS
    assert sorted(native["venue"]) == ["city", "country", "id", "name"]
    assert sorted(native["competitors"][0]["team"]) == ["abbreviation", "id", "name", "short_name"]
    assert [c["qualifier"] for c in native["competitors"]] == ["home", "away"]


def test_the_source_fixture_is_obviously_synthetic():
    """This payload is published in two repositories. If a reader has to check
    whether a name is a real club, the fixture has already failed at its job."""
    blob = NATIVE_PATH.read_text(encoding="utf-8")
    assert "Synthetic" in blob
    for token in ("Arsenal", "Real Madrid", "Manchester", "Liverpool",
                  "Premier League", "espn.com", "http"):
        assert token not in blob, token


def test_the_source_fixture_carries_the_native_placeholders_on_purpose():
    native = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
    for key, value in sorted(NATIVE_PLACEHOLDERS.items()):
        assert key in native
        assert native[key] == value


def test_the_source_scoreline_is_the_native_integer_form():
    """Native scores are integers; the canonical contract is strings, because the
    pinned shapes declare ``sh:datatype xsd:string``. The conversion is the
    adapter's job, and it can only be tested if the input really is an integer."""
    native = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
    assert [c["score"] for c in native["competitors"]] == [2, 1]
    assert native["scores"] == {"home": 2, "away": 1}


def test_the_expected_observation_pins_the_adapter_this_repository_owns():
    observation = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))["observation"]
    assert observation["adapter"]["name"] == "sports_skills.canonical.adapters.football"
    assert observation["adapter"]["version"] == "1"
    assert observation["provider"] == {"namespace": "sports-skills/espn", "family": "open-data"}


def test_the_expected_envelope_is_the_full_machina_sports_schema_block():
    block = json.loads(ENVELOPE_PATH.read_text(encoding="utf-8"))["machina_sports_schema"]
    assert sorted(block) == [
        "capabilities", "event_view", "profile", "provenance", "provider_ids",
        "rights", "schema_version", "sport_schema_graph",
    ]
    assert block["schema_version"] == "machina-sports-schema/1"
    assert block["profile"] == "machina-iptc-profile/1.1"


def test_the_fixtures_are_byte_identical_to_the_machina_templates_originals():
    """The strong cross-repository check, run whenever a checkout carrying the pinned
    commit is present. Skipped in CI by design; a recorded sha256 is what holds the line
    there."""
    checkout = templates_checkout()
    if checkout is None:
        pytest.skip(
            "no machina-templates checkout carrying the pinned commit; "
            "set MACHINA_TEMPLATES_ROOT to run this comparison"
        )
    for name, entry in sorted(manifest()["files"].items()):
        assert (FIXTURES / name).read_bytes() == pinned_bytes(
            checkout, entry["source_path"]
        ), name

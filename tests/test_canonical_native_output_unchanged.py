"""The canonical surface is additive: the default native output is untouched.

The claim is not "we did not mean to change it". Three independent things have to
hold, and each is checked separately because each fails differently:

1. **No native module can reach the canonical package.** A static rule, so it holds
   for every code path rather than for the ones a test happens to exercise.
2. **Importing ``sports_skills`` does not import the canonical package.** Nothing is
   wired in, and a consumer's import cost does not grow.
3. **Normalizing an event produces the same bytes before and after canonicalizing
   one.** The runtime half: no shared cache, no monkeypatch, no mutated module state.

No network anywhere. ``_normalize_espn_event`` is pure, so a synthetic transport
payload is enough to read its output.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src/sports_skills"

#: Modules on the default output path. If one of these imported the canonical
#: package, "canonical is additive" would stop being checkable by inspection.
NATIVE_SURFACE = (
    SRC / "cli.py",
    SRC / "__init__.py",
    SRC / "__main__.py",
    SRC / "football",
)

#: A synthetic ESPN scoreboard event, in the transport shape
#: ``_normalize_espn_event`` reads. Invented ids and ``Synthetic *`` names, for the
#: same reason the cross-repository fixture uses them.
ESPN_TRANSPORT_EVENT = {
    "id": "9001",
    "date": "2026-03-01T20:00Z",
    "season": {"year": 2026},
    "week": {"text": "Matchweek 27"},
    "competitions": [{
        "date": "2026-03-01T20:00:00+00:00",
        "status": {"type": {"name": "STATUS_FINAL"}},
        "venue": {
            "id": "9101",
            "fullName": "Synthetic Home Ground",
            "address": {"city": "Synthetic City", "country": "SYN"},
        },
        "competitors": [
            {"homeAway": "home", "score": "2",
             "team": {"id": "9011", "displayName": "Synthetic Home United",
                      "shortDisplayName": "Home United", "abbreviation": "SHU"}},
            {"homeAway": "away", "score": "1",
             "team": {"id": "9012", "displayName": "Synthetic Away Town",
                      "shortDisplayName": "Away Town", "abbreviation": "SAT"}},
        ],
        "odds": [],
    }],
}

#: The normalizer takes the competition identifier from its ``league_slug``
#: argument, so a payload normalized without one carries ``competition.id: ""``. A
#: synthetic slug is used rather than a real one so no real competition name is
#: pulled out of ``LEAGUES``.
LEAGUE_SLUG = "syn.1"


def normalized():
    from sports_skills.football._connector import _normalize_espn_event

    return _normalize_espn_event(ESPN_TRANSPORT_EVENT, LEAGUE_SLUG)


def python_files(target):
    return [target] if target.is_file() else sorted(target.rglob("*.py"))


def test_no_module_on_the_default_output_path_imports_the_canonical_package():
    """Static, so it covers every code path rather than the exercised ones. An
    import here is how canonical output would start leaking into native output."""
    scanned = 0
    for target in NATIVE_SURFACE:
        for path in python_files(target):
            scanned += 1
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                module = None
                if isinstance(node, ast.Import):
                    module = node.names[0].name
                elif isinstance(node, ast.ImportFrom):
                    module = node.module
                if module:
                    assert "canonical" not in module, (path.name, module)
    assert scanned > 0


def test_importing_the_package_does_not_import_the_canonical_surface():
    """A subprocess, because this test session has already imported it. If the
    canonical package were reachable from ``sports_skills.__init__``, a consumer who
    never asked for it would pay for it on every import."""
    script = (
        "import sys; import sports_skills; import sports_skills.football; "
        "print(any(name.startswith('sports_skills.canonical') for name in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(SRC.parent), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", result.stdout


def test_the_normalizer_returns_identical_bytes_before_and_after_canonicalizing():
    """The runtime half of the claim. If the canonical path shared a cache with the
    native one, or mutated a module-level table, this is where it would show."""
    before = json.dumps(normalized(), sort_keys=True)

    from sports_skills import canonical

    canonical.canonicalize_event(normalized(), observed_at="2026-03-01T22:05:00+00:00")

    assert json.dumps(normalized(), sort_keys=True) == before


def test_canonicalizing_does_not_mutate_the_normalized_event_it_was_handed():
    """The native payload a caller passes in is the value it is about to return to
    its own caller. An in-place edit here would corrupt the default output."""
    from sports_skills import canonical

    event = normalized()
    before = json.dumps(event, sort_keys=True)
    canonical.canonicalize_event(event, observed_at="2026-03-01T22:05:00+00:00")
    assert json.dumps(event, sort_keys=True) == before


def test_an_event_normalized_without_a_league_slug_cannot_be_canonicalized():
    """Found by this file's first RED run, and worth pinning rather than working
    around. The normalizer takes ``competition.id`` from its ``league_slug``
    argument, so a caller that omits it produces a native payload with no competition
    identifier — a fact the canonical observation contract requires. The adapter
    refuses and names the native field, which is the right outcome: inventing a
    competition identifier is exactly the fabrication this contract exists to stop.
    """
    from sports_skills import canonical
    from sports_skills.football._connector import _normalize_espn_event

    slugless = _normalize_espn_event(ESPN_TRANSPORT_EVENT)
    assert slugless["competition"]["id"] == ""
    with pytest.raises(ValueError) as excinfo:
        canonical.canonicalize_event(slugless, observed_at="2026-03-01T22:05:00+00:00")
    assert "competition.id" in str(excinfo.value)


def test_the_transport_payload_normalizes_to_the_reference_native_shape():
    """Ties the two halves of this PR together: the shape this synthetic transport
    payload normalizes to is the shape the cross-repository fixture is written in, so
    the adapter's tested input really is what the normalizer produces.

    ``round_name`` differs deliberately — the reference fixture pins the empty case
    and this payload carries ESPN's week text — and so do the competition and season
    identifiers, which come from the league slug. The comparison is therefore on the
    key set plus every field whose value the adapter reads unchanged.
    """
    reference = json.loads(
        (Path(__file__).resolve().parent
         / "fixtures/canonical/sports-skills-espn-soccer-native.json").read_text(encoding="utf-8")
    )
    event = normalized()

    assert tuple(event) == tuple(reference)
    for key in ("id", "status", "start_time", "matchday", "round", "venue",
                "competitors", "scores", "odds", "referees"):
        assert event[key] == reference[key], key

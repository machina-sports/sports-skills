"""The vendored canonical runtime is machina-templates' code, byte-exact.

Editing a copy under ``_vendored/`` is a drift bug, not a fix: change it upstream,
re-vendor, and regenerate ``VENDORED.json`` in the same commit. These tests are the
only thing that makes that instruction enforceable, because neither repository's CI
can reach the other.

Three separate failures are kept separate on purpose:

- a hash that no longer matches means someone edited a vendored file here;
- a non-stdlib or ``tools.*`` import means the vendored boundary was broken upstream
  and the copy is unpublishable;
- a 3.10+ syntax construct means the copy cannot be imported by the oldest Python
  this package supports, which no hash check would notice.
"""

import ast
import hashlib
import json
from pathlib import Path

VENDORED = Path(__file__).resolve().parents[1] / "src/sports_skills/canonical/_vendored"

MANIFEST_PATH = VENDORED / "VENDORED.json"

#: Every file that must be vendored, and nothing that must not be. Written out
#: rather than globbed: a glob would happily pass on a directory that lost a file.
EXPECTED_FILES = (
    "__init__.py",
    "capabilities.py",
    "ids.py",
    "observation.py",
    "official-property-names.json",
    "serialize.py",
    "shared-context.json",
    "vocab.py",
)

#: Standard-library modules the vendored runtime is allowed to reach for. A
#: published zero-dependency package cannot import anything else, and the copy is
#: the whole reason this package stays zero-dependency.
ALLOWED_IMPORTS = frozenset({
    "__future__", "collections", "datetime", "hashlib", "json", "pathlib", "re",
    "typing",
})


def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def vendored_modules():
    """Every vendored module, asserted non-empty.

    Without the assertion each import-boundary test below is a loop over nothing,
    which passes on a directory that does not exist. A vacuous guard is worse than
    no guard: it reports the boundary as held.
    """
    modules = sorted(VENDORED.glob("*.py"))
    assert [path.name for path in modules] == sorted(
        name for name in EXPECTED_FILES if name.endswith(".py")
    )
    return modules


def test_the_manifest_names_its_upstream_source_and_the_contract_versions():
    """A hash pin with no provenance tells a reader nothing about what to re-vendor
    from. The commit is the part that makes drift diagnosable rather than merely
    detectable."""
    document = manifest()
    assert document["consumer"] == "machina-sports/sports-skills"
    assert document["source_repository"] == "machina-sports/machina-templates"
    assert len(document["source_commit"]) == 40
    assert document["profile"] == "machina-iptc-profile/1.1"
    assert document["schema_version"] == "canonical-observation/1"
    assert document["machina_schema_version"] == "machina-sports-schema/1"


def test_every_vendored_file_matches_the_recorded_hash():
    recorded = manifest()["files"]
    assert sorted(recorded) == sorted(EXPECTED_FILES)
    for name, digest in sorted(recorded.items()):
        local = VENDORED / name
        assert local.is_file(), name
        assert hashlib.sha256(local.read_bytes()).hexdigest() == digest, (
            f"{name} drifted from machina-templates; re-vendor rather than editing here"
        )


def test_the_manifest_pins_every_file_the_directory_actually_ships():
    """The mirror of the test above. A vendored file absent from the manifest is a
    file nobody checks, which is the same failure with the arrow reversed."""
    shipped = sorted(
        path.name for path in VENDORED.iterdir()
        if path.is_file() and path.name != MANIFEST_PATH.name
    )
    assert shipped == sorted(EXPECTED_FILES)


def test_the_vendored_runtime_imports_only_the_standard_library():
    for path in vendored_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative import of a vendored sibling, which is
                # the one non-stdlib import the boundary allows.
                modules = [] if node.level else [node.module]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] in ALLOWED_IMPORTS, (path.name, module)


def test_no_vendored_module_imports_machina_templates():
    """Stated separately from the allowlist because it is the actual architectural
    rule, and a reader scanning failures should see it named."""
    for path in vendored_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            module = None
            if isinstance(node, ast.Import):
                module = node.names[0].name
            elif isinstance(node, ast.ImportFrom):
                module = node.module
            if module:
                assert not module.startswith("tools"), (path.name, module)


def test_the_vendored_runtime_parses_as_python_39():
    """``ast.parse`` with a feature version rejects 3.10+ syntax. This package
    supports 3.9, and an unimportable vendored copy is not caught by any hash."""
    for path in vendored_modules():
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_the_runtime_is_importable_and_exposes_the_pinned_versions():
    from sports_skills.canonical import _vendored

    assert _vendored.PROFILE_VERSION == "machina-iptc-profile/1.1"
    assert _vendored.SCHEMA_VERSION == "canonical-observation/1"
    assert _vendored.MACHINA_SCHEMA_VERSION == "machina-sports-schema/1"
    assert _vendored.UPSTREAM_TARGET_VERSION == "1.1"


def test_the_manifest_versions_agree_with_the_code_they_pin():
    """Two copies of a version string, one in JSON and one in Python, are one
    rename away from disagreeing."""
    from sports_skills.canonical import _vendored

    document = manifest()
    assert document["profile"] == _vendored.PROFILE_VERSION
    assert document["schema_version"] == _vendored.SCHEMA_VERSION
    assert document["machina_schema_version"] == _vendored.MACHINA_SCHEMA_VERSION


def test_the_packaged_data_files_are_readable_through_the_package():
    """Both JSON files are read via ``Path(__file__).parent`` at runtime, so they
    have to travel inside the installed package rather than beside the repository."""
    from importlib.resources import files

    package = files("sports_skills.canonical._vendored")
    allowlist = json.loads(package.joinpath("official-property-names.json").read_text(encoding="utf-8"))
    assert allowlist["target_version"] == "1.1"
    context = json.loads(package.joinpath("shared-context.json").read_text(encoding="utf-8"))
    assert "@context" in context


def test_the_serializer_can_load_its_context_and_its_allowlist():
    """The functional half of the test above: the modules resolve their own data
    files, which is what a missing wheel entry would break."""
    from sports_skills.canonical._vendored.observation import official_property_curies
    from sports_skills.canonical._vendored.serialize import shared_context

    assert "sport:startDateTime" in official_property_curies()
    assert shared_context()["sport"] == "https://sportschema.org/ontologies/main/"

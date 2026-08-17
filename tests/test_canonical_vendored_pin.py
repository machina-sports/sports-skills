"""The complete canonical 0.4.1 runtime is vendored byte-exact."""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_canonical_reference_fixtures import pinned_bytes, templates_checkout

VENDORED = Path(__file__).resolve().parents[1] / "src/sports_skills/canonical/_vendored"
MANIFEST_PATH = VENDORED / "VENDORED.json"
TRUSTED_MANIFEST_PATH = VENDORED / "data/trusted_loader_manifest_v1.json"
TRUSTED_MANIFEST_SHA256 = "0fdf5e8a6661e1d2bb7f5190f6c4fe08637f3eab5149254c26885aead557eace"
ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "collections",
        "copy",
        "datetime",
        "decimal",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "types",
        "typing",
    }
)


def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def runtime_manifest():
    return json.loads(TRUSTED_MANIFEST_PATH.read_text(encoding="utf-8"))


def recorded_files():
    document = runtime_manifest()
    return {item["relative_path"]: item for item in document["runtime_files"] + document["required_data_files"]}


def vendored_modules():
    modules = sorted(VENDORED.rglob("*.py"))
    expected = sorted(VENDORED / path for path in recorded_files() if path.endswith(".py"))
    assert modules == expected
    return modules


def test_manifest_names_the_reviewed_release_and_contract_versions():
    document = manifest()
    assert document["consumer"] == "machina-sports/sports-skills"
    assert document["source_repository"] == "machina-sports/machina-templates"
    assert document["source_commit"] == "bf96c8d84b308e2e23d7dd7ec8942e2da82f6c14"
    assert document["profile"] == "machina-iptc-profile/1.3"
    assert document["schema_version_input"] == "canonical-observation/1.2"
    assert document["machina_schema_version"] == "machina-sports-schema/1.1"
    assert document["owner_distribution"]["version"] == "0.4.1"
    assert document["owner_distribution"]["wheel_sha256"] == (
        "cd454eb8411b5639af7313c713276bfa4a0dc72aab037b66ba451bc3e0f090bd"
    )


def test_every_runtime_and_required_data_file_matches_the_owner_receipt():
    assert hashlib.sha256(TRUSTED_MANIFEST_PATH.read_bytes()).hexdigest() == TRUSTED_MANIFEST_SHA256
    for name, item in sorted(recorded_files().items()):
        payload = (VENDORED / name).read_bytes()
        assert len(payload) == item["byte_length"], name
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == item["sha256"], name


def test_manifest_and_vendored_directory_have_the_exact_complete_inventory():
    document = manifest()
    runtime = runtime_manifest()
    assert document["runtime_files"] == runtime["runtime_files"]
    assert document["required_data_files"] == runtime["required_data_files"]
    assert document["private_symbols"] == runtime["private_symbols"]
    assert document["aggregate_runtime_digest"] == runtime["aggregate_runtime_digest"]
    shipped = {
        path.relative_to(VENDORED).as_posix()
        for path in VENDORED.rglob("*")
        if path.is_file() and path.name != MANIFEST_PATH.name and "__pycache__" not in path.parts
    }
    assert shipped == set(recorded_files()) | {"data/trusted_loader_manifest_v1.json"}


def test_vendored_runtime_imports_only_the_standard_library():
    for path in vendored_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [] if node.level else [node.module]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] in ALLOWED_IMPORTS, (path.name, module)


def test_no_vendored_module_imports_an_external_canonical_runtime():
    for path in vendored_modules():
        source = path.read_text(encoding="utf-8")
        assert "machina_sports_canonical" not in source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                modules = []
            assert all(not module.startswith("tools") for module in modules), path


def test_vendored_runtime_parses_as_python_39():
    for path in vendored_modules():
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_runtime_exposes_immutable_legacy_and_additive_versions():
    from sports_skills.canonical import _vendored

    assert _vendored.PROFILE_VERSION == "machina-iptc-profile/1.2"
    assert _vendored.SCHEMA_VERSION == "canonical-observation/1.1"
    assert _vendored.MACHINA_SCHEMA_VERSION == "machina-sports-schema/1"
    assert _vendored.SUCCESSOR_PROFILE_VERSION == "machina-iptc-profile/1.3"
    assert _vendored.SUCCESSOR_SCHEMA_VERSION == "canonical-observation/1.2"
    assert _vendored.SUCCESSOR_MACHINA_SCHEMA_VERSION == "machina-sports-schema/1.1"
    assert _vendored.LONGITUDINAL_SCHEMA_VERSION == "canonical-longitudinal-statistics/1"
    assert _vendored.UPSTREAM_TARGET_VERSION == "1.1"


def test_all_packaged_data_files_are_readable_through_the_package():
    from importlib.resources import files

    package = files("sports_skills.canonical._vendored")
    for name in recorded_files():
        if not name.endswith(".py"):
            assert package.joinpath(name).read_bytes()


def test_legacy_reference_contract_retains_its_historical_owner_commit():
    from tests.test_canonical_reference_fixtures import manifest as contract

    assert manifest()["source_commit"] == "bf96c8d84b308e2e23d7dd7ec8942e2da82f6c14"
    assert contract()["source_commit"] == "ddf12f04803eeb03016c10759aaf2a2be8e85f84"


def test_runtime_is_byte_identical_to_the_reviewed_owner_source():
    checkout = templates_checkout()
    if checkout is None:
        pytest.skip(
            "no machina-templates checkout carrying the pinned commit; "
            "set MACHINA_TEMPLATES_ROOT to run this comparison"
        )
    document = manifest()
    # The protected release manifest is fixed-point release metadata and is
    # verified by its released digest above rather than by the source-commit blob.
    names = set(recorded_files())
    for name in sorted(names):
        upstream = pinned_bytes(
            checkout,
            f"{document['source_path']}/{name}",
            commit=document["source_commit"],
        )
        assert (VENDORED / name).read_bytes() == upstream, name


def test_serializer_can_load_context_allowlist_and_phase1_data():
    from sports_skills.canonical._vendored.observation import official_property_curies
    from sports_skills.canonical._vendored.serialize import shared_context

    assert "sport:startDateTime" in official_property_curies()
    assert shared_context()["sport"] == "https://sportschema.org/ontologies/main/"
    assert runtime_manifest()["schema_version"] == "machina-canonical-runtime-vendored-manifest/1"

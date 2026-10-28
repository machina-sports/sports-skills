"""Release gates for the sports-skills 0.39.0 distribution candidate."""

import email
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import textwrap
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.39.0"
TAG = f"v{VERSION}"
REVIEWED_SOURCE_COMMIT = "7511c724559045e39aa9d0c5ce84c447532ed4e1"
REVIEWED_SOURCE_TREE = "382e033ea55ac7392a86f5bbfde49be20bf290fb"
# The published v0.39.0 tag. REVIEWED_SOURCE_COMMIT is the reviewed code *before* the
# release-metadata overlay (provenance URL, checksum authority, receipt) was committed on
# top; the immutable checksums were produced from this tag's tree. They are reproduced
# from it here, not from the current tree, which later features legitimately change.
PUBLISHED_SOURCE_COMMIT = "0784ab06b04f1198a0aaf2ca4c5f73de6e39de95"
# Every input the wheel and sdist are built from (see [tool.hatch.build.targets.*]).
BUILD_INPUTS = (".gitignore", "LICENSE", "README_PYPI.md", "pyproject.toml", "src/sports_skills", "packaging/release.py")
SOURCE_DATE_EPOCH = 1792797037
AUTHORITY = ROOT / "release" / VERSION / "SHA256SUMS"
REVIEW_RECEIPT = ROOT / "release" / VERSION / "review-receipt.json"
WHEEL_NAME = f"sports_skills-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"sports_skills-{VERSION}.tar.gz"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_rows():
    rows = AUTHORITY.read_text(encoding="ascii").splitlines()
    assert len(rows) == 2
    parsed = []
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", row)
        assert match is not None, row
        parsed.append(match.groups())
    assert [name for _, name in parsed] == [WHEEL_NAME, SDIST_NAME]
    return dict(parsed)


def _build(output, source_root=ROOT):
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = str(SOURCE_DATE_EPOCH)
    subprocess.run(
        [sys.executable, str(source_root / "packaging/release.py"), str(source_root), str(output)],
        check=True,
        cwd=source_root,
        env=env,
    )
    assert sorted(path.name for path in output.iterdir()) == sorted([SDIST_NAME, WHEEL_NAME])
    return output / WHEEL_NAME, output / SDIST_NAME


def _safe_extract(payload, destination):
    """Extract a tar we produced, refusing anything but plain files/dirs inside ``destination``.

    Explicit per-member checks rather than ``tarfile``'s ``filter=``, which Python 3.9 lacks.
    """
    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts
            target = (root / member.name).resolve()
            if Path(member.name).is_absolute() or ".." in parts or (target != root and root not in target.parents):
                raise AssertionError(f"unsafe archive member path: {member.name!r}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            else:
                raise AssertionError(f"unexpected archive member type: {member.name!r}")


def _assert_checksum_file_is_not_an_artifact_input(wheel, sdist):
    with zipfile.ZipFile(wheel) as archive:
        assert not any(name.endswith("SHA256SUMS") for name in archive.namelist())
    with tarfile.open(sdist, "r:gz") as archive:
        assert not any(name.endswith("SHA256SUMS") for name in archive.getnames())


@pytest.fixture(scope="session")
def release_builds(tmp_path_factory):
    first = tmp_path_factory.mktemp("release-build-a")
    second = tmp_path_factory.mktemp("release-build-b")
    return _build(first), _build(second)


@pytest.fixture(scope="session")
def published_build(tmp_path_factory):
    """Build the exact published tag from a local `git archive` (no network, no checkout)."""
    source = tmp_path_factory.mktemp("published-source")
    payload = subprocess.run(
        ["git", "-C", str(ROOT), "archive", "--format=tar", PUBLISHED_SOURCE_COMMIT, "--", *BUILD_INPUTS],
        check=True,
        capture_output=True,
    ).stdout
    _safe_extract(payload, source)
    wheel, sdist = _build(tmp_path_factory.mktemp("published-build"), source)
    return source, wheel, sdist


def test_every_active_version_surface_is_0390():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "src/sports_skills/__init__.py").read_text(encoding="utf-8")
    phase1 = (ROOT / "src/sports_skills/canonical/_phase1.py").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert re.search(r'^version = "0\.39\.0"$', pyproject, re.MULTILINE)
    assert re.search(r'^__version__ = "0\.39\.0"$', package, re.MULTILINE)
    assert '"package_version": "0.39.0"' in phase1
    assert re.search(r'(?ms)^name = "sports-skills"\nversion = "0\.39\.0"$', lock)
    assert changelog.startswith("## [0.39.0]\n")


def test_release_source_and_epoch_match_review_receipt():
    receipt = json.loads(REVIEW_RECEIPT.read_text(encoding="ascii"))
    assert type(receipt) is dict
    assert receipt == {
        "schema": "sports-skills-release-review-receipt-v1",
        "reviewed_source_commit": REVIEWED_SOURCE_COMMIT,
        "reviewed_source_tree": REVIEWED_SOURCE_TREE,
        "source_date_epoch": SOURCE_DATE_EPOCH,
    }
    assert {key: type(value) for key, value in receipt.items()} == {
        "schema": str,
        "reviewed_source_commit": str,
        "reviewed_source_tree": str,
        "source_date_epoch": int,
    }

    release_source = (ROOT / "packaging/release.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert f'REVIEWED_SOURCE_COMMIT = "{receipt["reviewed_source_commit"]}"' in release_source
    assert f"SOURCE_DATE_EPOCH = {receipt['source_date_epoch']}" in release_source
    assert (
        '"Reviewed source" = '
        f'"https://github.com/machina-sports/sports-skills/tree/{receipt["reviewed_source_commit"]}"'
    ) in pyproject
    assert f'REVIEWED_SOURCE_COMMIT: "{receipt["reviewed_source_commit"]}"' in workflow
    assert f'SOURCE_DATE_EPOCH: "{receipt["source_date_epoch"]}"' in workflow


def test_checksum_authority_is_two_basename_rows_and_not_an_artifact_input(release_builds):
    _authority_rows()
    wheel, sdist = release_builds[0]
    _assert_checksum_file_is_not_an_artifact_input(wheel, sdist)


def test_published_tag_reproduces_the_immutable_checksum_authority(published_build):
    source, wheel, sdist = published_build
    assert _authority_rows() == {_sha256(wheel): WHEEL_NAME, _sha256(sdist): SDIST_NAME}
    _assert_checksum_file_is_not_an_artifact_input(wheel, sdist)

    # The frozen source carries the release version and reviewed-source provenance.
    pyproject = (source / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "0\.39\.0"$', pyproject, re.MULTILINE)
    assert (
        f'"Reviewed source" = "https://github.com/machina-sports/sports-skills/tree/{REVIEWED_SOURCE_COMMIT}"'
    ) in pyproject
    release_source = (source / "packaging/release.py").read_text(encoding="utf-8")
    assert f'REVIEWED_SOURCE_COMMIT = "{REVIEWED_SOURCE_COMMIT}"' in release_source
    assert f"SOURCE_DATE_EPOCH = {SOURCE_DATE_EPOCH}" in release_source
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))
    assert metadata["Version"] == VERSION
    assert metadata.get_all("Project-URL") == [
        f"Reviewed source, https://github.com/machina-sports/sports-skills/tree/{REVIEWED_SOURCE_COMMIT}"
    ]


def test_two_clean_builds_are_byte_identical(release_builds):
    (wheel_a, sdist_a), (wheel_b, sdist_b) = release_builds
    assert wheel_a.read_bytes() == wheel_b.read_bytes()
    assert sdist_a.read_bytes() == sdist_b.read_bytes()


def test_artifact_metadata_provenance_license_and_dependencies_are_exact(release_builds):
    wheel, _ = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))

    assert metadata["Name"] == "sports-skills"
    assert metadata["Version"] == VERSION
    assert metadata["Requires-Python"] == ">=3.9.10"
    assert metadata.get_all("License-Expression") == ["MIT"]
    assert metadata.get_all("License-File") == ["LICENSE"]
    assert metadata.get_all("Project-URL") == [
        f"Reviewed source, https://github.com/machina-sports/sports-skills/tree/{REVIEWED_SOURCE_COMMIT}"
    ]
    assert not any(
        requirement.casefold().startswith(("machina-sports-canonical", "machina_sports_canonical"))
        for requirement in metadata.get_all("Requires-Dist", [])
    )


def test_artifact_member_metadata_and_package_inventory_are_exact(release_builds):
    wheel, sdist = release_builds[0]
    source_files = {
        path.relative_to(ROOT / "src").as_posix()
        for path in (ROOT / "src/sports_skills").rglob("*")
        if path.is_file() and path.suffix not in {".pyc", ".pyo"} and "__pycache__" not in path.parts
    }

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        packaged = {name for name in names if name.startswith("sports_skills/")}
        assert packaged == source_files
        assert not any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names)
        assert not any(name.startswith(("tests/", ".hermes/", "release/")) for name in names)
        expected_time = time.gmtime(SOURCE_DATE_EPOCH)[:5] + (SOURCE_DATE_EPOCH % 60 // 2 * 2,)
        assert {item.date_time for item in archive.infolist()} == {expected_time}

    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        prefix = f"sports_skills-{VERSION}/"
        packaged = {
            member.name.removeprefix(prefix + "src/")
            for member in members
            if member.isfile() and member.name.startswith(prefix + "src/sports_skills/")
        }
        assert packaged == source_files
        assert {member.mtime for member in members} == {SOURCE_DATE_EPOCH}
        assert {member.uid for member in members} == {0}
        assert {member.gid for member in members} == {0}
        assert {member.uname for member in members} == {""}
        assert {member.gname for member in members} == {""}
        assert not any(
            part in member.name
            for member in members
            for part in ("/.git/", "/.hermes/", "/release/", "/tests/", "/__pycache__/")
        )


def test_artifacts_ship_gemini_module_and_cli_registry_entries(release_builds):
    wheel, sdist = release_builds[0]
    required = {"sports_skills/gemini/__init__.py", "sports_skills/gemini/_connector.py"}
    with zipfile.ZipFile(wheel) as archive:
        assert required <= set(archive.namelist())
        cli = archive.read("sports_skills/cli.py").decode("utf-8")

    with tarfile.open(sdist, "r:gz") as archive:
        assert {f"sports_skills-{VERSION}/src/{name}" for name in required} <= set(archive.getnames())

    assert cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    gemini = cli.split('    "gemini": {\n', 1)[1].split("\n    },\n", 1)[0]
    for command in ("get_events", "get_event", "search_markets", "get_todays_events"):
        assert f'"{command}": ' in gemini


def test_wheel_ships_novig_module_and_cli_registry_entries(release_builds):
    wheel, _ = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert {"sports_skills/novig/__init__.py", "sports_skills/novig/_connector.py"} <= names
        cli = archive.read("sports_skills/cli.py").decode("utf-8")

    assert cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    novig = cli.split('    "novig": {\n', 1)[1].split("\n    },\n", 1)[0]
    for command in (
        "get_sports_config",
        "get_events",
        "get_event",
        "get_markets",
        "get_market",
        "get_order_book",
        "search_markets",
        "get_todays_events",
    ):
        assert f'"{command}": ' in novig
    markets = cli.split('    "markets": {\n', 1)[1].split("\n    },\n", 1)[0]
    assert '"compare_market_url": {"required": ["url"]}' in markets


def test_installed_wheel_imports_resources_wrappers_and_owner_inventory(release_builds, tmp_path):
    wheel, _ = release_builds[0]
    environment = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "--no-index", str(wheel)],
        check=True,
        cwd=tmp_path,
    )
    probe = textwrap.dedent(
        f"""
        import hashlib
        import importlib
        import importlib.metadata
        import importlib.resources
        import inspect
        import json
        import pathlib
        import sys
        import types

        distribution = importlib.metadata.distribution("sports-skills")
        assert distribution.version == "{VERSION}"
        root = pathlib.Path(distribution.locate_file(""))
        package = types.ModuleType("sports_skills")
        package.__path__ = [str(root / "sports_skills")]
        package.__package__ = "sports_skills"
        sys.modules["sports_skills"] = package

        canonical = importlib.import_module("sports_skills.canonical")
        football = importlib.import_module("sports_skills.canonical.adapters.football")
        nba = importlib.import_module("sports_skills.canonical.adapters.nba")
        assert pathlib.Path(canonical.__file__).is_relative_to(root)
        assert pathlib.Path(football.__file__).is_relative_to(root)
        assert pathlib.Path(nba.__file__).is_relative_to(root)
        assert str(inspect.signature(canonical.to_successor_envelope)) == "(*, operation, request_bytes, operation_arguments_bytes, output_mode, consumer_tier) -> bytes"
        assert str(inspect.signature(canonical.to_longitudinal_envelope)) == "(*, operation, request_bytes, operation_arguments_bytes, consumer_tier) -> bytes"

        vendored = importlib.resources.files("sports_skills.canonical._vendored")
        receipt = json.loads(vendored.joinpath("VENDORED.json").read_text(encoding="utf-8"))
        runtime = json.loads(vendored.joinpath("data/trusted_loader_manifest_v1.json").read_text(encoding="utf-8"))
        assert receipt["runtime_files"] == runtime["runtime_files"]
        assert receipt["required_data_files"] == runtime["required_data_files"]
        assert receipt["private_symbols"] == runtime["private_symbols"]
        for item in runtime["runtime_files"] + runtime["required_data_files"]:
            payload = vendored.joinpath(item["relative_path"]).read_bytes()
            assert len(payload) == item["byte_length"]
            assert "sha256:" + hashlib.sha256(payload).hexdigest() == item["sha256"]
        successor = importlib.import_module("sports_skills.canonical._vendored.successor")
        assert all(hasattr(successor, item["symbol"]) for item in runtime["private_symbols"])
        assert importlib.util.find_spec("machina_sports_canonical") is None
        """
    )
    subprocess.run([str(python), "-I", "-c", probe], check=True, cwd=tmp_path)


def test_publish_workflow_is_tag_triggered_build_once_and_least_privilege():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "types: [published]" not in workflow
    assert not re.search(r"(?m)^  release:\s*$", workflow.split("jobs:", 1)[0])
    assert re.search(r'(?ms)^on:\n  push:\n    tags:\n      - "v\*"$', workflow)
    assert re.search(r"(?ms)^permissions:\n  contents: read$", workflow)
    assert f'RELEASE_VERSION: "{VERSION}"' in workflow
    assert f'REVIEWED_SOURCE_COMMIT: "{REVIEWED_SOURCE_COMMIT}"' in workflow
    assert f'SOURCE_DATE_EPOCH: "{SOURCE_DATE_EPOCH}"' in workflow

    action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s#]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)

    build = workflow.split("  build:", 1)[1].split("  verify-installed:", 1)[0]
    verify = workflow.split("  verify-installed:", 1)[1].split("  publish:", 1)[0]
    publish = workflow.split("  publish:", 1)[1].split("  release:", 1)[0]
    release = workflow.split("  release:", 1)[1]
    assert 'test "$GITHUB_REF_NAME" = "v${RELEASE_VERSION}"' in build
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in build
    assert 'assert package["project"]["version"] == os.environ["RELEASE_VERSION"]' in build
    assert "merge-base" not in workflow
    assert "--is-ancestor" not in workflow
    assert "git diff" not in workflow
    assert "id-token: write" not in build
    assert build.count("packaging/release.py") == 1
    assert 'python-version: ["3.9", "3.14"]' in verify
    assert "needs: [build, verify-installed]" in publish
    assert "environment: pypi" in publish
    assert "id-token: write" in publish
    assert "actions/checkout" not in publish
    assert "packaging/release.py" not in publish
    assert "python -m build" not in publish
    assert "sha256sum --check --strict" in publish
    assert "License-Expression" in publish and "License-File" in publish
    assert "needs: publish" in release
    assert "contents: write" in release
    assert "sha256sum --check --strict" in release
    assert "dist/*.whl" in release and "dist/*.tar.gz" in release and "SHA256SUMS" in release


def test_ci_reaches_release_gates_on_python_39_and_current_python():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "paths-ignore" not in workflow and "paths:" not in workflow
    assert "pull_request:" in workflow and "push:" in workflow
    assert '"3.9"' in workflow and '"3.14"' in workflow
    test_job = workflow.split("  test:", 1)[1]
    assert re.search(
        r"(?m)^      - uses: actions/checkout@[^\n]+\n        with:\n          fetch-depth: 0$",
        test_job,
    )
    assert "pytest -v" in workflow

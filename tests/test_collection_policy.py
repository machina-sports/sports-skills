"""Tests for repository-wide pytest collection policy."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("collection_policy", Path(__file__).with_name("conftest.py"))
assert SPEC and SPEC.loader
collection_policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collection_policy)


def test_non_release_paths_defer_to_other_ignore_hooks():
    assert collection_policy.pytest_ignore_collect(Path("tests/test_markets.py"), None) is None


@pytest.mark.parametrize(
    "name,variable",
    [
        ("test_release_036.py", "SPORTS_SKILLS_VERIFY_RELEASE_036"),
        ("test_release_037.py", "SPORTS_SKILLS_VERIFY_RELEASE_037"),
    ],
)
def test_release_proof_is_opt_in(monkeypatch, name, variable):
    path = Path("tests") / name
    monkeypatch.delenv(variable, raising=False)
    assert collection_policy.pytest_ignore_collect(path, None) is True

    monkeypatch.setenv(variable, "1")
    assert collection_policy.pytest_ignore_collect(path, None) is False


def test_one_release_variable_does_not_enable_another(monkeypatch):
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_037", raising=False)
    monkeypatch.setenv("SPORTS_SKILLS_VERIFY_RELEASE_036", "1")
    assert collection_policy.pytest_ignore_collect(Path("tests/test_release_037.py"), None) is True

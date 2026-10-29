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


def test_active_release_proof_defers_to_other_ignore_hooks(monkeypatch):
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_036", raising=False)
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_037", raising=False)
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_038", raising=False)
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_039", raising=False)
    assert collection_policy.pytest_ignore_collect(Path("tests/test_release_040.py"), None) is None


@pytest.mark.parametrize(
    ("name", "variable", "other"),
    [
        ("test_release_036.py", "SPORTS_SKILLS_VERIFY_RELEASE_036", "SPORTS_SKILLS_VERIFY_RELEASE_037"),
        ("test_release_037.py", "SPORTS_SKILLS_VERIFY_RELEASE_037", "SPORTS_SKILLS_VERIFY_RELEASE_036"),
        ("test_release_038.py", "SPORTS_SKILLS_VERIFY_RELEASE_038", "SPORTS_SKILLS_VERIFY_RELEASE_037"),
        ("test_release_039.py", "SPORTS_SKILLS_VERIFY_RELEASE_039", "SPORTS_SKILLS_VERIFY_RELEASE_038"),
    ],
)
def test_historical_release_proof_is_opt_in(monkeypatch, name, variable, other):
    path = Path("tests") / name
    monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(other, "1")
    assert collection_policy.pytest_ignore_collect(path, None) is True

    monkeypatch.setenv(variable, "1")
    assert collection_policy.pytest_ignore_collect(path, None) is False

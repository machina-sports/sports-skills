"""Smoke tests — verify every module imports and the CLI registry is consistent."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HAS_FASTF1 = importlib.util.find_spec("fastf1") is not None

# Every public module that should be importable
MODULES = [
    "sports_skills",
    "sports_skills.nfl",
    "sports_skills.nba",
    "sports_skills.wnba",
    "sports_skills.nhl",
    "sports_skills.mlb",
    "sports_skills.cfb",
    "sports_skills.cbb",
    "sports_skills.golf",
    "sports_skills.tennis",
    "sports_skills.cricket",
    "sports_skills.volleyball",
    "sports_skills.xctf",
    "sports_skills.esports",
    "sports_skills.football",
    "sports_skills.metadata",
    "sports_skills.polymarket",
    "sports_skills.kalshi",
    "sports_skills.news",
    "sports_skills._espn_base",
    "sports_skills._response",
    "sports_skills.cli",
]

if _HAS_FASTF1:
    MODULES.insert(1, "sports_skills.f1")


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    """Every module should import without errors."""
    mod = importlib.import_module(module)
    assert mod is not None


def test_package_root_directly_exports_news_and_volleyball():
    import sports_skills

    assert sports_skills.news is importlib.import_module("sports_skills.news")
    assert sports_skills.volleyball is importlib.import_module("sports_skills.volleyball")


@pytest.mark.parametrize("module", ["sports_skills.news", "sports_skills.volleyball"])
def test_package_root_propagates_public_module_import_errors(module):
    """Root imports are eager: failures in public modules must not be masked."""
    script = f"""
import importlib.abc
import importlib.util
import sys

target = {module!r}

class FailingLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raise ImportError("root-import-sentinel:" + target)

class FailingFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == {module!r}:
            return importlib.util.spec_from_loader(fullname, FailingLoader())
        return None

sys.meta_path.insert(0, FailingFinder())
import sports_skills
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode != 0
    assert f"ImportError: root-import-sentinel:{module}" in result.stderr


def test_cli_entrypoint():
    """The sports-skills CLI should be callable and print help."""
    result = subprocess.run(
        [sys.executable, "-m", "sports_skills.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "sports-skills" in result.stdout


def test_cli_registry_modules_loadable():
    """Every module in the CLI registry should be loadable."""
    from sports_skills.cli import _REGISTRY, _load_module

    for module_name in _REGISTRY:
        if module_name == "f1" and not _HAS_FASTF1:
            continue
        mod = _load_module(module_name)
        assert mod is not None, f"Failed to load module: {module_name}"


def test_cli_registry_commands_callable():
    """Every command in registry modules should resolve to a callable."""
    from sports_skills.cli import _REGISTRY, _load_module

    for module_name, commands in _REGISTRY.items():
        if module_name == "f1" and not _HAS_FASTF1:
            continue
        mod = _load_module(module_name)
        for command_name in commands:
            fn = getattr(mod, command_name, None)
            assert fn is not None, f"{module_name}.{command_name} not found"
            assert callable(fn), f"{module_name}.{command_name} is not callable"


def test_nflverse_provider_module_imports():
    """The nflverse provider module should import without optional deps installed."""
    mod = importlib.import_module("sports_skills.nfl._nflverse")
    assert mod is not None


def test_response_envelope():
    """The response wrapper should produce the standard envelope."""
    from sports_skills._response import wrap

    result = wrap({"key": "value"})
    assert result["status"] is True
    assert result["data"] == {"key": "value"}
    assert "message" in result


def test_response_error_envelope():
    """Error responses should have status=False."""
    from sports_skills._response import wrap

    result = wrap({"error": True, "message": "something broke"})
    assert result["status"] is False
    assert "something broke" in result["message"]


def test_version_consistency():
    """Package __version__ should match pyproject.toml."""
    import re
    from pathlib import Path

    import sports_skills

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    text = pyproject.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "Could not find version in pyproject.toml"
    assert sports_skills.__version__ == match.group(1)

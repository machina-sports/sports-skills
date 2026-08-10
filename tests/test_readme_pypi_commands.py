"""README_PYPI.md is the PyPI long description — its examples are checked here.

Offline and against the real registry: no example is executed against a provider. A
wrong command on the package page is the first thing a new user runs, and the drift is
invisible from inside the code, so the doc is asserted against `cli._REGISTRY`, the
module attributes the SDK examples name, and the canonical mode's own constants.
"""

import re
import sys
from pathlib import Path

import pytest

from sports_skills.canonical import _cli as canonical
from sports_skills.cli import _REGISTRY, _load_module, main

README_PYPI = Path(__file__).resolve().parent.parent / "README_PYPI.md"
TEXT = README_PYPI.read_text(encoding="utf-8")

#: Handled by `main()` before the registry lookup, so they are not registry entries.
RESERVED_MODULES = {"catalog", "deploy", "premium"}
RESERVED_COMMANDS = {"schema"}

#: `sports-skills <module> <command>` at the start of a documented shell line. Lines
#: whose first token is a flag (`sports-skills --help`) name no module and are skipped.
CLI_INVOCATION = re.compile(r"^sports-skills +(?!-)([a-z0-9-]+)(?: +(?!-)([a-z0-9_]+))?", re.M)

#: `module.command(` inside a documented Python block.
SDK_CALL = re.compile(r"\b([a-z0-9]+)\.([a-z0-9_]+)\(")


def _cli_examples():
    return CLI_INVOCATION.findall(TEXT)


def _section(heading_contains):
    """One `##` section's body, so a claim is asserted where it is documented."""
    match = re.search(
        rf"^##[^\n]*{re.escape(heading_contains)}[^\n]*\n(.*?)(?=^## |\Z)",
        TEXT,
        re.M | re.S,
    )
    assert match, f"README_PYPI.md has no '## ...{heading_contains}...' section"
    return match.group(1)


class TestDocumentedCliExamples:
    def test_examples_exist(self):
        assert _cli_examples(), "README_PYPI.md documents no sports-skills invocations"

    def test_every_example_names_a_registered_module(self):
        unknown = sorted({m for m, _ in _cli_examples() if m not in _REGISTRY and m not in RESERVED_MODULES})
        assert not unknown, f"README_PYPI.md documents unregistered modules: {unknown}"

    def test_every_example_names_a_registered_command(self):
        unknown = sorted(
            {
                f"{module} {command}"
                for module, command in _cli_examples()
                if command
                and module in _REGISTRY
                and command not in _REGISTRY[module]
                and command not in RESERVED_COMMANDS
            }
        )
        assert not unknown, f"README_PYPI.md documents unregistered commands: {unknown}"

    def test_documented_module_listing_actually_lists_commands(self, capsys, monkeypatch):
        """The example under "list commands for a sport" must do that, not print global help."""
        match = re.search(r"List commands for a specific sport:\s*```bash\n([^\n]+)\n", TEXT)
        assert match, "README_PYPI.md no longer documents how to list a module's commands"
        argv = match.group(1).split()
        monkeypatch.setattr(sys, "argv", argv)
        try:
            main()
        except SystemExit:
            # argparse consumes --help at the top level and prints the global help.
            pytest.fail(f"'{match.group(1)}' does not list a module's commands")
        module = argv[1]
        assert capsys.readouterr().out.startswith(f"Commands for '{module}':")


class TestDocumentedSdkExamples:
    def test_every_sdk_call_exists_on_its_module(self):
        missing = sorted(
            {
                f"{module}.{attr}"
                for module, attr in SDK_CALL.findall(TEXT)
                if module in _REGISTRY and not hasattr(_load_module(module), attr)
            }
        )
        assert not missing, f"README_PYPI.md documents missing SDK functions: {missing}"


class TestDocumentedCanonicalMode:
    def test_names_every_supported_command(self):
        section = _section("Machina Sports Schema")
        for command in canonical.supported_commands():
            assert command in section, f"canonical section omits '{command}'"

    def test_names_the_format_and_its_alias(self):
        section = _section("Machina Sports Schema")
        assert f"--format={canonical.CANONICAL_FORMAT}" in section
        assert "--canonical" in section

    def test_states_that_observed_at_is_required_and_offset_aware(self):
        section = _section("Machina Sports Schema")
        assert "--observed-at" in section
        assert canonical.OBSERVED_AT_EXAMPLE in section
        assert "UTC offset" in section

    def test_states_the_default_tier_and_the_production_refusal(self):
        section = _section("Machina Sports Schema")
        assert f"`{canonical.DEFAULT_CONSUMER_TIER}`" in section
        assert "--consumer-tier=production" in section
        assert "refuse" in section

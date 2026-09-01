"""Every registered command is documented in its own skill folder.

`test_readme_pypi_commands.py` asserts the other direction: that a documented
command exists. Nothing asserted that a command that exists is documented, and
the skill files make that omission load-bearing rather than cosmetic. Twenty of
them close their command section with, verbatim from
`skills/cbb-data/SKILL.md`:

    "If a command is not listed in the Commands table above, it does not exist."

So an undocumented command is not merely undiscoverable. The skill tells the
agent it does not exist, which takes a working command off the table in the
product's primary use case.
"""

from pathlib import Path

import pytest

from sports_skills.cli import _REGISTRY

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

#: Modules whose skill directory is not `<module>` or `<module>-data`.
SKILL_DIR_OVERRIDES = {"news": "sports-news", "f1": "fastf1"}


def _skill_dir(module: str) -> Path:
    if module in SKILL_DIR_OVERRIDES:
        return SKILLS / SKILL_DIR_OVERRIDES[module]
    for candidate in (module, f"{module}-data"):
        path = SKILLS / candidate
        if path.is_dir():
            return path
    pytest.fail(f"no skill directory for registered module '{module}'")


def _documented_text(module: str) -> str:
    """Every file in the module's skill folder, concatenated.

    Deliberately the whole folder rather than SKILL.md alone: several skills
    keep their command table in `references/api-reference.md` and point at it
    from SKILL.md, so either location counts as documented.
    """
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(_skill_dir(module).rglob("*"))
        if path.is_file()
    )


@pytest.mark.parametrize("module", sorted(_REGISTRY))
def test_every_registered_command_is_documented(module):
    documented = _documented_text(module)
    missing = sorted(command for command in _REGISTRY[module] if command not in documented)
    assert not missing, (
        f"skills/{_skill_dir(module).name}/ documents none of {missing}, "
        f"while `sports-skills {module}` registers them. The skill's closed-world "
        f"statement makes an agent treat them as nonexistent."
    )


def test_every_registered_module_has_a_skill_directory():
    for module in _REGISTRY:
        assert _skill_dir(module).is_dir()

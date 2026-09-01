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

import re
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


def _declared_commands(text: str) -> set[str]:
    """Command names declared in Markdown table rows or command headings."""
    commands = set()
    in_fence = False
    excluded_section = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        section = re.match(r"^##\s+(.+)$", line)
        if section:
            excluded_section = "do not exist" in section.group(1).lower()
        if excluded_section:
            continue
        table_command = re.match(r"^\|\s*`([a-z0-9_]+)`\s*\|", line)
        heading_command = re.match(r"^#{3,4}\s+`?([a-z0-9_]+)`?\s*$", line)
        match = table_command or heading_command
        if match:
            commands.add(match.group(1))
    return commands


def _documented_commands(module: str) -> set[str]:
    commands = set()
    for path in sorted(_skill_dir(module).rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        commands.update(_declared_commands(text))
    return commands


@pytest.mark.parametrize("module", sorted(_REGISTRY))
def test_every_registered_command_is_documented(module):
    documented = _documented_commands(module)
    missing = sorted(command for command in _REGISTRY[module] if command not in documented)
    assert not missing, (
        f"skills/{_skill_dir(module).name}/ documents none of {missing}, "
        f"while `sports-skills {module}` registers them. The skill's closed-world "
        f"statement makes an agent treat them as nonexistent."
    )


def test_every_registered_module_has_a_skill_directory():
    for module in _REGISTRY:
        assert _skill_dir(module).is_dir()


def test_command_mentions_do_not_count_as_declarations():
    text = """Use `get_market` in an example.

```markdown
| `get_market` | Example only |
```

- ~~`get_odds`~~ — does not exist.
| `get_markets` | List markets |

## Commands that DO NOT exist

### get_odds
"""
    assert _declared_commands(text) == {"get_markets"}

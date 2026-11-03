"""SKILL.md frontmatter descriptions: parseable, bounded, and keep routing caveats."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SKILLS = Path(__file__).resolve().parent.parent / "skills"
SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))

# Agent Skills spec limit for the description field.
MAX_DESCRIPTION = 1024


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    return yaml.safe_load(text.split("---\n", 2)[1])


def _description(slug):
    return _frontmatter(SKILLS / slug / "SKILL.md")["description"]


def test_skill_files_found():
    assert SKILL_FILES


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_description_is_bounded_nonempty_string(path):
    description = _frontmatter(path).get("description")
    assert isinstance(description, str) and description.strip(), f"{path.parent.name}: empty description"
    assert len(description) <= MAX_DESCRIPTION, f"{path.parent.name}: {len(description)} chars"


def test_football_description_keeps_scope_caveats():
    description = _description("football-data").lower()
    # American football routes elsewhere.
    assert "nfl" in description and "nfl-data" in description
    # Not a live-score source.
    assert "real-time" in description or "post-match" in description
    # Premier League-only and top-5-only operations.
    assert "get_season_leaders" in description and "get_missing_players" in description
    assert "premier league" in description
    assert "get_event_xg" in description


def test_espn_description_forbids_automatic_fallback():
    description = _description("espn-api").lower()
    assert "dedicated" in description
    assert "automatic" in description

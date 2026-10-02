"""Coverage copy regressions for the README, homepage, and espn-api detail page.

Dedicated skills (package + CLI) and the prompt-only espn-api reference must stay
distinct; the espn-api slug inventory is reported as a reference list computed from
league-slugs.md, never as integrated or canonical coverage. Needs the `site` extra.
"""

import importlib.util
import re
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")
pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
BUILD_PY = ROOT / "site" / "build.py"
README = ROOT / "README.md"
LEAGUE_SLUGS = ROOT / "skills" / "espn-api" / "references" / "league-slugs.md"
INSTALL = "npx skills add machina-sports/sports-skills@espn-api"
UNCOVERED = [
    "MMA",
    "lacrosse",
    "rugby",
    "Australian football",
    "NCAA volleyball",
    "field hockey",
    "water polo",
    "NASCAR",
    "IndyCar",
]


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("site_build_under_test", BUILD_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def inventory(build):
    return build.espn_reference_inventory()


def _env(build):
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(build.TEMPLATES)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_index(build, inventory):
    return _env(build).get_template("index.html").render(
        skills=[],
        categories=[],
        skills_json="[]",
        total_skills=0,
        total_commands=0,
        espn_inventory=inventory,
        base_url=build.BASE_URL,
    )


def _render_skill(build, slug, inventory):
    skill = build.load_skill(slug, ROOT / "skills" / slug, "open")
    return _env(build).get_template("skill.html").render(
        skill=skill, related=[], espn_inventory=inventory, base_url=build.BASE_URL
    )


def _assert_no_espn_runtime(text):
    assert "get_data" not in text
    assert "from sports_skills import espn_api" not in text
    assert "sports_skills.espn_api" not in text
    assert "sports-skills espn-api" not in text
    assert "sports-skills espn " not in text


def test_inventory_matches_league_slugs_scope_note(inventory):
    scope = re.search(
        r"lists (\d+) league rows across (\d+) sport sections",
        LEAGUE_SLUGS.read_text(encoding="utf-8"),
    )
    assert scope, "league-slugs.md scope note changed; update the coverage copy"
    assert inventory == {"leagues": int(scope.group(1)), "sports": int(scope.group(2))}


def test_inventory_counts_only_sport_sections(build, tmp_path):
    doc = tmp_path / "league-slugs.md"
    doc.write_text(
        "## Lacrosse (sport: `lacrosse`)\n\n| League | Slug | Abbreviation |\n"
        "|---|---|---|\n| PLL | `pll` | PLL |\n| NLL | `nll` | NLL |\n\n"
        "## Cricket (sport: `cricket`)\n\nUse discovery.\n\n"
        "## CDN Sport Slugs\n\n| CDN Slug | Maps To |\n|---|---|\n| `nba` | `x` |\n",
        encoding="utf-8",
    )
    assert build.espn_reference_inventory(doc) == {"sports": 2, "leagues": 2}
    assert build.espn_reference_inventory(tmp_path / "missing.md") is None


def test_readme_distinguishes_dedicated_and_reference_coverage(inventory):
    readme = README.read_text(encoding="utf-8")
    heading = "### Dedicated Skills vs Reference-Only Coverage"
    assert heading in readme
    assert "(#dedicated-skills-vs-reference-only-coverage)" in readme
    section = readme.split(heading, 1)[1].split("\n## ", 1)[0]
    flat = " ".join(section.split())

    assert INSTALL in flat
    assert "is prompt-only" in flat
    assert "no CLI command and no Python module" in flat
    for sport in UNCOVERED:
        assert sport in flat
    assert f"{inventory['leagues']} documented league slugs across {inventory['sports']} sport sections" in flat
    assert "reference inventory, not a count of integrated, normalized, canonical, or live-tested" in flat
    assert "SPORTS_SKILLS_REPLAY" in flat
    assert "no commercial or redistribution rights" in flat
    for link in re.findall(r"\]\((skills/espn-api/[^)]+)\)", section):
        assert (ROOT / link).exists(), link
    _assert_no_espn_runtime(readme)


def test_readme_keeps_canonical_and_rights_boundaries():
    readme = README.read_text(encoding="utf-8")
    assert '"prototype_only": true, "commercial_use": false' in readme
    assert "## Machina Sports Schema (canonical output)" in readme
    assert "(#machina-sports-schema-canonical-output)" in readme
    assert "## Record & Replay" in readme and "(#record--replay)" in readme


def test_homepage_coverage_section(build, inventory):
    html = _render_index(build, inventory)
    section = html.split('id="coverage"', 1)[1]

    assert 'href="/espn-api/"' in section
    assert INSTALL in section
    assert "Dedicated runtime skills" in section
    assert "not every catalog entry is a runtime module or replay-backed" in section
    assert "no CLI command or Python module" in section
    for sport in UNCOVERED:
        assert sport in section
    assert f"{inventory['leagues']} league slugs across {inventory['sports']} sport sections" in section
    assert "reference inventory, not a count of integrated, normalized, canonical or live-tested" in section
    assert "SPORTS_SKILLS_REPLAY" in section
    assert "no commercial rights" in section
    _assert_no_espn_runtime(html)


def test_homepage_omits_counts_without_inventory(build):
    html = _render_index(build, None)
    assert 'id="coverage"' in html
    assert "league slugs across" not in html


def test_espn_api_page_explains_reference_coverage(build, inventory):
    html = _render_skill(build, "espn-api", inventory)
    section = html.split('id="coverage"', 1)[1]

    assert f"{inventory['leagues']} documented league slugs across {inventory['sports']} sport sections" in section
    assert "references/league-slugs.md" in section
    assert "reference inventory" in section
    assert "provider-native" in section
    assert "not record/replay-backed" in section
    assert "non-commercial" in section
    assert INSTALL in html
    _assert_no_espn_runtime(html)


def test_other_skill_pages_have_no_espn_coverage_block(build, inventory):
    for slug in ("nba-data", "machina"):
        assert "Reference coverage:" not in _render_skill(build, slug, inventory)


def test_build_wires_inventory_into_pages(build, monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    monkeypatch.setattr(build, "DIST", dist)
    build.build()

    assert "league slugs across" in (dist / "index.html").read_text(encoding="utf-8")
    assert "Reference coverage:" in (dist / "espn-api" / "index.html").read_text(encoding="utf-8")

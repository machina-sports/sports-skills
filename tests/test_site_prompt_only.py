"""Site rendering regressions for prompt-only, CLI-backed, and premium skill pages.

A prompt-only open skill must show how to install it and how to ask for it, never
an invented `get_data` command or a `sports_skills.<slug>` module. CLI-backed and
premium pages keep their existing rendering. Needs the `site` extra.
"""

import importlib.util
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")
pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
BUILD_PY = ROOT / "site" / "build.py"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("site_build_under_test", BUILD_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(build, skill):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(build.TEMPLATES)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("skill.html").render(skill=skill, related=[], base_url=build.BASE_URL)


def _write_skill(tmp_path, slug, body="# Demo\n\nDoes a thing.\n"):
    skill_dir = tmp_path / slug
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: |\n  Demo skill for tests.\nlicense: MIT\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def _assert_no_invented_runtime(html, slug):
    assert "get_data" not in html
    assert f"from sports_skills import {slug.replace('-', '_')}" not in html
    assert f"sports-skills {slug} " not in html


def test_espn_api_page_is_install_plus_reference(build):
    skill = build.load_skill("espn-api", ROOT / "skills" / "espn-api", "open")
    assert skill["commands"] == []
    assert skill["examples"]

    html = _render(build, skill)
    _assert_no_invented_runtime(html, "espn-api")
    assert "npx skills add machina-sports/sports-skills@espn-api" in html
    assert "prompt-only: no CLI command or Python module" in html
    assert "Premier Lacrosse League scores" in html
    assert f'href="{skill["source_url"]}/SKILL.md"' in html


def test_generic_prompt_only_page_without_examples(build, tmp_path):
    skill = build.load_skill("demo-skill", _write_skill(tmp_path, "demo-skill"), "open")
    assert skill["commands"] == [] and skill["examples"] == []

    html = _render(build, skill)
    _assert_no_invented_runtime(html, "demo-skill")
    assert "npx skills add machina-sports/sports-skills@demo-skill" in html
    assert "Use the demo-skill skill to ..." in html


def test_open_premium_gateway_page_is_not_given_a_runtime(build):
    skill = build.load_skill("machina", ROOT / "skills" / "machina", "open")
    assert skill["commands"] == []
    _assert_no_invented_runtime(_render(build, skill), "machina")


def test_cli_backed_page_keeps_cli_and_python_quickstart(build):
    skill = build.load_skill("nba-data", ROOT / "skills" / "nba-data", "open")
    assert skill["commands"]
    first = skill["commands"][0]["name"]

    html = _render(build, skill)
    assert f"sports-skills nba-data {first}" in html
    assert "from sports_skills import nba_data" in html
    assert f"nba_data.{first}()" in html
    assert "get_data" not in html
    assert "prompt-only: no CLI command or Python module" not in html


def test_pro_page_keeps_machina_cta_and_no_quickstart(build, tmp_path):
    skill = build.load_skill("pro-demo", _write_skill(tmp_path, "pro-demo"), "pro")

    html = _render(build, skill)
    assert 'href="https://machina.gg"' in html
    assert "Run on Machina" in html
    assert "Quick Start" not in html
    assert "npx skills add" not in html
    assert "get_data" not in html


def test_espn_api_has_no_cli_mapping(build):
    assert "espn-api" not in build.SLUG_TO_CLI_MODULE
    if build.CLI_REGISTRY is not None:
        assert not any("espn" in module for module in build.CLI_REGISTRY)

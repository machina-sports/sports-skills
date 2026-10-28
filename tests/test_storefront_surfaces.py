"""Every human/agent surface points at the live Machina Agent Storefront, safely.

Offline, static checks: skill docs, skills/catalog.json, README.md, README_PYPI.md
and the rendered site template. The set of skills that must carry a discovery block
is derived from catalog.json risk metadata, not a hand-kept list.
"""

import importlib.util
import json
import re
import shutil
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CATALOG = json.loads((SKILLS / "catalog.json").read_text(encoding="utf-8"))
TITLE = "Discover the Machina Agent Storefront"
STOREFRONT = "https://agents.machina.gg"
MANIFEST = "https://agents.machina.gg/manifest.json"

# Discovery must not loosen any risk classification.
CURRENT_RISK = {
    name: (
        meta["mode"],
        meta["risk"],
        meta["money_movement"],
        meta["secrets_required"],
        meta["requires_explicit_confirmation"],
    )
    for name, meta in CATALOG["skills"].items()
}
EXPECTED_RISK = {
    "betting": ("compute", "low", False, False, False),
    "machina": ("premium_mcp", "high", False, True, True),
    "polymarket-trading": ("financial_execution", "critical", True, True, True),
    "world-cup": ("read_only", "high", False, False, True),
}

# Live prices from the sampled manifest, formatted the way a doc would quote them.
SAMPLED_PRICES = ("$0.01", "$0.05", "$0.12", "$0.40")


def _relevant_skills():
    """Independently installable non-trading data/analysis/orchestration skills."""
    return sorted(
        name
        for name, meta in CATALOG["skills"].items()
        if meta["mode"] in {"read_only", "compute"} and not meta["money_movement"]
    )


def _section(text, needle):
    """The Markdown section whose heading contains ``needle``, through its subsections."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match and needle in match.group(2):
            level = len(match.group(1))
            body = [line]
            for nxt in lines[i + 1 :]:
                head = re.match(r"^(#{1,6})\s", nxt)
                if head and len(head.group(1)) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return None


def _assert_safe_discovery_copy(block, where):
    lower = block.lower()
    assert MANIFEST in block, where
    assert "x402" in lower and "mpp" in lower, where
    assert "untrusted" in lower, where
    assert "free" in lower, where  # free tools first when adequate
    assert "authoriz" in lower or "approv" in lower, where
    assert "/zcj/" not in block, where  # request-specific attribution IDs never ship
    assert not re.search(r"\$\d+\.\d", block), where  # no hardcoded rates
    for forbidden in ("video", "factory", "private_key", "private key", "seed phrase"):
        assert forbidden not in lower, (where, forbidden)
    for claim in ("automatically purchase", "auto-purchase", "auto purchase", "guaranteed", "zero-latency"):
        assert claim not in lower, (where, claim)


# ── Skills ──────────────────────────────────────────────────────────────


def test_relevant_set_is_derived_and_excludes_trading_and_gateway():
    names = _relevant_skills()
    assert "polymarket-trading" not in names
    assert "machina" not in names
    assert {"football-data", "world-cup", "betting", "markets", "sports-reporter", "espn-api"} <= set(names)


@pytest.mark.parametrize("name", _relevant_skills())
def test_every_relevant_skill_carries_a_self_contained_discovery_block(name, tmp_path):
    # Installed alone (`npx skills add ...@<name>`): the block must stand without siblings.
    installed = tmp_path / name / "SKILL.md"
    installed.parent.mkdir()
    shutil.copy(SKILLS / name / "SKILL.md", installed)
    text = installed.read_text(encoding="utf-8")
    block = _section(text, "Machina Agent Storefront")
    assert block, f"{name}: no '... Machina Agent Storefront' section"
    _assert_safe_discovery_copy(block, name)
    assert "../" not in block
    # Discovery never installs anything as a side effect.
    assert "pip install" not in block and "npm install" not in block


@pytest.mark.parametrize("name", ["polymarket-trading"])
def test_trading_skill_gets_no_storefront_block(name):
    assert _section((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"), "Machina Agent Storefront") is None


def test_risk_classifications_unchanged():
    for name, expected in EXPECTED_RISK.items():
        assert CURRENT_RISK[name] == expected, name
    for name in _relevant_skills():
        if name in EXPECTED_RISK:
            continue
        mode, _, money, secrets, _ = CURRENT_RISK[name]
        assert mode == "read_only" and money is False and secrets is False, name


def test_skill_frontmatter_risk_still_matches_catalog():
    for name in _relevant_skills():
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), name
        front = text.split("---", 2)[1]
        if "money_movement:" in front:
            assert "money_movement: false" in front, name


# ── catalog.json ────────────────────────────────────────────────────────


def test_catalog_json_advertises_storefront_discovery():
    entry = CATALOG["storefront"]
    assert entry["title"] == TITLE
    assert entry["url"].rstrip("/") == STOREFRONT
    assert entry["manifest"] == MANIFEST
    assert entry["command"] == "sports-skills storefront"
    dumped = json.dumps(entry)
    assert "/zcj/" not in dumped and not re.search(r"\$\d+\.\d", dumped)


def test_catalog_json_keeps_metered_billing_gate():
    assert "metered_billing" in CATALOG["default_policy"]["require_confirmation_for"]
    assert "financial_execution" in CATALOG["default_policy"]["require_confirmation_for"]


# ── READMEs ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("doc", ["README.md", "README_PYPI.md"])
def test_readme_has_discovery_section(doc):
    section = _section((ROOT / doc).read_text(encoding="utf-8"), TITLE)
    assert section, f"{doc}: no '{TITLE}' section"
    _assert_safe_discovery_copy(section, doc)
    assert f"{STOREFRONT}" in section
    assert "sports-skills storefront" in section
    lower = section.lower()
    # Package update (new CLI command) is separate from prompt-skill update/reload.
    assert "upgrade" in lower
    assert "npx skills add" in section
    assert "reload" in lower or "restart" in lower


@pytest.mark.parametrize("doc", ["README.md", "README_PYPI.md"])
def test_readmes_do_not_hardcode_sampled_prices(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for price in SAMPLED_PRICES:
        assert price not in text, (doc, price)


def test_world_cup_does_not_hardcode_sampled_prices():
    text = (SKILLS / "world-cup" / "SKILL.md").read_text(encoding="utf-8")
    for price in SAMPLED_PRICES:
        assert price not in text, price


# ── Site template ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def build():
    jinja2 = pytest.importorskip("jinja2")
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location("site_build_storefront", ROOT / "site" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._jinja2 = jinja2
    return module


def _render(build, skill):
    env = build._jinja2.Environment(
        loader=build._jinja2.FileSystemLoader(str(build.TEMPLATES)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("skill.html").render(skill=skill, related=[], base_url=build.BASE_URL)


@pytest.fixture
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("site render must not depend on the live manifest")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


SECTION = 'id="storefront"'  # the discovery section itself, not any global nav link


@pytest.mark.parametrize("slug", ["football-data", "world-cup", "espn-api", "betting"])
def test_open_landing_page_links_storefront_and_manifest_directly(build, offline, slug):
    skill = build.load_skill(slug, SKILLS / slug, "open")
    html = _render(build, skill)
    assert SECTION in html
    assert TITLE in html
    assert re.search(r'href="https://agents\.machina\.gg/?"', html)
    assert f'href="{MANIFEST}"' in html
    assert "sports-skills storefront" in html
    assert "/zcj/" not in html
    assert not re.search(r"\$\d+\.\d", html)
    section = html[html.index(TITLE) :]
    section = section[: section.find("</section>") if "</section>" in section else len(section)]
    assert "video" not in section.lower() and "factory" not in section.lower()


@pytest.mark.parametrize("catalogued", [True, False], ids=["catalogued", "uncatalogued"])
def test_landing_page_escapes_skill_text(build, offline, tmp_path, monkeypatch, catalogued):
    if catalogued:
        monkeypatch.setitem(build.CATALOG_SKILLS, "demo-skill", {"mode": "read_only", "money_movement": False})
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: |\n  Demo <script>alert(1)</script>\nlicense: MIT\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    html = _render(build, build.load_skill("demo-skill", skill_dir, "open"))
    assert "<script>alert(1)</script>" not in html
    # catalogued read_only/no-money gets the section; uncatalogued (safety=None) fails closed
    assert (SECTION in html) == catalogued


@pytest.mark.parametrize("slug", sorted(n for n in CATALOG["skills"] if (SKILLS / n / "SKILL.md").exists()))
def test_site_discovery_matches_prompt_skill_policy(build, offline, slug):
    """Open tier, known read_only/compute mode, no money movement: same set as the SKILL.md blocks."""
    html = _render(build, build.load_skill(slug, SKILLS / slug, "open"))
    assert (SECTION in html) == (slug in _relevant_skills()), slug


@pytest.mark.parametrize("slug", ["machina", "polymarket-trading"])
def test_ineligible_open_pages_have_no_discovery_section(build, offline, slug):
    html = _render(build, build.load_skill(slug, SKILLS / slug, "open"))
    assert SECTION not in html
    assert f"<h2>{TITLE}</h2>" not in html


def test_premium_tier_page_has_no_discovery_section(build, offline):
    html = _render(build, build.load_skill("football-data", SKILLS / "football-data", "pro"))
    assert SECTION not in html


def test_unknown_safety_mode_has_no_discovery_section(build, offline, monkeypatch):
    monkeypatch.setitem(build.CATALOG_SKILLS, "football-data", {"mode": "future_mode", "money_movement": False})
    html = _render(build, build.load_skill("football-data", SKILLS / "football-data", "open"))
    assert SECTION not in html

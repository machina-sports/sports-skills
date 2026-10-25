"""World Cup skill's free-to-paid routing contract (no network or purchase)."""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/world-cup/SKILL.md"
GITHUB = "https://github.com/machina-sports/sports-skills/blob/main/skills/{}/SKILL.md"
SIBLINGS = ("football-data", "kalshi", "polymarket", "markets", "machina")


def _links(text):
    return re.findall(r"\]\(([^)\s]+)\)", text)


def test_links_resolve_from_single_skill_install(tmp_path):
    # `npx skills add machina-sports/sports-skills@world-cup` installs only this folder.
    installed = tmp_path / "skills/world-cup/SKILL.md"
    installed.parent.mkdir(parents=True)
    shutil.copy(SKILL, installed)
    text = installed.read_text()
    links = _links(text)
    assert links
    for target in links:
        if target.startswith("https://"):
            continue
        assert (installed.parent / target.split("#")[0]).exists(), target
    assert "../" not in text
    for skill in SIBLINGS:
        assert GITHUB.format(skill) in links


def test_sibling_skills_are_optional_explicit_installs():
    text = SKILL.read_text()
    for skill in SIBLINGS:
        assert f"npx skills add machina-sports/sports-skills@{skill}" in text
    assert "only the skill the task needs" in text
    assert "not prerequisites" in text
    assert "pipx install machina-cli" not in text  # CLI setup lives in the machina skill.


def test_semantic_unknown_only_permits_read_only_schema_fallback():
    text = SKILL.read_text()
    assert "service.openapi" in text
    assert "task_support_not_established" in text
    assert "not the HTTP status" in text
    assert "read-only" in text and "never call a paid operation" in text
    assert "at most once" in text
    assert "same origin" in text
    assert "illustrative, not executed" in text
    assert '{"event":"Brazil vs Morocco"}' in text
    assert "real auth, payment or policy denial" in text


def test_metadata_version_bumped():
    assert 'version: "0.2.1"' in SKILL.read_text()


def test_funnel_recipe_separates_proof_statuses():
    text = (ROOT / "docs/zeroclick-funnel.md").read_text()
    for status in ("install", "discovery", "paid", "not-run"):
        assert f"`{status}`" in text
    assert "separate budget and authorization" in text
    assert "not cleared" in text


def test_storefront_is_before_optional_project_setup():
    text = SKILL.read_text()
    storefront = re.search(r"^## .*Machina Agent Storefront", text, re.M)
    assert storefront, "no '## ... Machina Agent Storefront' section"
    assert storefront.start() < text.index("## Optional: existing Machina project")
    for path in ("", "/llms.txt", "/manifest.json", "/zeroclick/agent/guide"):
        assert f"https://agents.machina.gg{path}" in text
    assert "/zcj/" not in text  # No request-specific referral IDs in shipped skills.


def test_free_data_and_payment_consent_remain_explicit():
    text = SKILL.read_text()
    assert "Free first" in text
    assert "explicit user approval" in text
    assert "Do not retry-loop" in text
    assert "no login, wallet, payment or Machina CLI" in text


def test_catalog_scope_and_freshness_not_overpromised():
    text = SKILL.read_text()
    # Discovery-first: the live manifest is the inventory, not a dated table in the skill.
    assert "Catalog checked" not in text
    assert "| Agent needs | Catalog service |" not in text
    assert "https://agents.machina.gg/manifest.json" in text
    assert "archival" in text and "timestamps" in text
    assert "Do not hardcode prices" in text


def test_catalog_description_tracks_skill_and_keeps_risk_gates():
    item = json.loads((ROOT / "skills/catalog.json").read_text())["skills"]["world-cup"]
    assert "Machina Agent Storefront" in item["description"]
    assert item["requires_explicit_confirmation"] is True
    assert item["money_movement"] is False


def test_discovery_metadata_does_not_require_credentials_or_mcp():
    item = json.loads((ROOT / "skills/catalog.json").read_text())["skills"]["world-cup"]
    assert item["mode"] == "read_only"
    assert item["secrets_required"] is False
    text = SKILL.read_text()
    assert "premium: false" in text
    assert "billing: optional_metered" in text
    assert "external_mcp: false" in text
    assert "requires_explicit_confirmation: true" in text


def test_handoff_supports_convenience_without_unsupported_claims():
    text = SKILL.read_text()
    assert "when the user wants a hosted contract, forecast or finished artifact" in text
    assert "Never ask for secrets in chat" in text
    # Availability comes only from the live manifest plus the operation schema.
    assert "Do not sell an" in text
    assert "available unless the live manifest and its operation schema establish it" in text
    assert "A wallet existing is not authorization" in text
    assert "request-specific referral" not in text  # No referral implementation jargon in buyer copy.

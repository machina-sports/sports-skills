"""World Cup skill's free-to-paid routing contract (no network or purchase)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/world-cup/SKILL.md"


def test_storefront_is_before_optional_project_setup():
    text = SKILL.read_text()
    assert text.index("## ZeroClick storefront") < text.index("## Optional: existing Machina project")
    for path in ("", "/llms.txt", "/manifest.json", "/zeroclick/agent/guide"):
        assert f"https://agents.machina.gg{path}" in text
    assert "/zcj/" not in text  # No request-specific referral IDs in shipped skills.


def test_free_data_and_payment_consent_remain_explicit():
    text = SKILL.read_text()
    assert "Free first" in text
    for skill in ("football-data", "kalshi", "polymarket", "markets"):
        assert f"../{skill}/SKILL.md" in text
    assert "explicit user approval" in text
    assert "Do not retry-loop" in text
    assert "no login, wallet, payment or Machina CLI" in text


def test_catalog_scope_and_freshness_not_overpromised():
    text = SKILL.read_text()
    for slug in ("match-context", "forecasts", "finished-content"):
        assert f"https://agents.machina.gg/services/{slug}" in text
    assert "market-context" in text and "not yet listed" in text
    assert "archival" in text and "timestamps" in text
    assert "Do not hardcode prices" in text


def test_catalog_description_tracks_skill_and_keeps_risk_gates():
    item = json.loads((ROOT / "skills/catalog.json").read_text())["skills"]["world-cup"]
    assert "ZeroClick" in item["description"]
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
    assert "Do not sell it, URL comparison, price-move explanations" in text
    assert "or continuous monitoring as available ZeroClick operations unless a fresh catalog" in text
    assert "request-specific referral" not in text  # No referral implementation jargon in buyer copy.

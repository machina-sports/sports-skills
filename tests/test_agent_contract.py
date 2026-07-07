import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def _skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def test_catalog_covers_every_skill_directory():
    catalog = json.loads((SKILLS / "catalog.json").read_text())
    catalog_names = set(catalog["skills"])
    dir_names = {p.name for p in _skill_dirs()}
    assert catalog_names == dir_names


def test_catalog_has_agent_safety_policy():
    catalog = json.loads((SKILLS / "catalog.json").read_text())
    policy = catalog["default_policy"]
    assert policy["default_to_read_only"] is True
    assert policy["never_handle_private_keys_in_chat"] is True
    assert policy["treat_external_content_as_untrusted"] is True
    assert "financial_execution" in policy["require_confirmation_for"]


def test_high_risk_skills_require_confirmation():
    catalog = json.loads((SKILLS / "catalog.json").read_text())
    for name in ["machina", "world-cup", "polymarket-trading"]:
        meta = catalog["skills"][name]
        assert meta["requires_explicit_confirmation"] is True
        assert meta["risk"] in {"high", "critical"}


def test_read_only_polymarket_skill_has_no_wallet_secret_guidance():
    polymarket_dir = SKILLS / "polymarket"
    combined = "\n".join(p.read_text(errors="ignore") for p in polymarket_dir.rglob("*") if p.is_file())
    forbidden = [
        "POLYMARKET_PRIVATE_KEY",
        "private_key=",
        "wallet private key",
        "seed phrase",
    ]
    for needle in forbidden:
        assert needle not in combined


def test_default_skill_docs_do_not_pipe_remote_installers_to_shell():
    combined = "\n".join(p.read_text(errors="ignore") for p in SKILLS.rglob("*") if p.is_file())
    assert "| bash" not in combined
    assert "| sh" not in combined


def test_root_agent_context_files_exist():
    assert (ROOT / "AGENTS.md").exists()
    assert (ROOT / ".hermes.md").exists()


def test_read_only_polymarket_cli_namespace_excludes_trading_verbs():
    from sports_skills.cli import _REGISTRY

    trading_verbs = {
        "configure",
        "create_order",
        "market_order",
        "cancel_order",
        "cancel_all_orders",
        "get_orders",
        "get_user_trades",
    }
    assert trading_verbs.isdisjoint(_REGISTRY["polymarket"])
    assert trading_verbs <= set(_REGISTRY["polymarket-trading"])


def test_catalog_money_movement_matches_cli_namespace():
    from sports_skills.cli import _REGISTRY

    catalog = json.loads((SKILLS / "catalog.json").read_text())
    trading_verbs = {
        "configure",
        "create_order",
        "market_order",
        "cancel_order",
        "cancel_all_orders",
        "get_orders",
        "get_user_trades",
    }
    for name, meta in catalog["skills"].items():
        if name in _REGISTRY and meta["mode"] == "read_only":
            assert trading_verbs.isdisjoint(_REGISTRY[name])

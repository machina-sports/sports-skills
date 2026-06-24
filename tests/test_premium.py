"""Tests for premium data CLI helpers."""

import json

from sports_skills import _premium
from sports_skills._response import error, success, wrap


class TestBuildHint:
    def test_rate_limited_shape(self):
        hint = _premium.build_hint("rate_limited")
        assert hint["trigger"] == "rate_limited"
        assert hint["reason"]
        assert hint["capability"]
        assert hint["via"]["data"]["command"] == "sports-skills premium"
        assert hint["via"]["data"]["docs"] == "http://docs.machina.gg/"
        assert hint["via"]["deploy"]["command"] == "sports-skills deploy"
        assert hint["x402"] is None

    def test_licensed_data_shape(self):
        hint = _premium.build_hint("licensed_data")
        assert hint["trigger"] == "licensed_data"
        assert hint["reason"]
        assert hint["capability"]
        assert hint["via"]["data"]["command"] == "sports-skills premium"
        assert hint["x402"] is None

    def test_unknown_trigger_returns_none(self):
        assert _premium.build_hint("nope") is None


class TestAttach:
    def test_fires_on_429(self):
        result = {"status": False, "data": None, "message": "rate limited", "status_code": 429}
        out = _premium.attach(result)
        assert "upgrade" in out
        assert out["upgrade"]["trigger"] == "rate_limited"

    def test_noop_on_success(self):
        result = {"status": True, "data": {"x": 1}, "message": "", "status_code": 429}
        assert "upgrade" not in _premium.attach(result)

    def test_noop_on_non_429_error(self):
        result = {"status": False, "data": None, "message": "boom", "status_code": 500}
        assert "upgrade" not in _premium.attach(result)

    def test_noop_when_no_status_code(self):
        result = {"status": False, "data": None, "message": "boom"}
        assert "upgrade" not in _premium.attach(result)

    def test_noop_on_non_dict(self):
        assert _premium.attach("not a dict") == "not a dict"
        assert _premium.attach(None) is None

    def test_idempotent(self):
        result = {"status": False, "status_code": 429, "upgrade": {"trigger": "preexisting"}}
        out = _premium.attach(result)
        assert out["upgrade"]["trigger"] == "preexisting"

    def test_suppressed_by_env(self, monkeypatch):
        monkeypatch.setenv(_premium._SUPPRESS_ENV, "1")
        result = {"status": False, "data": None, "message": "rate limited", "status_code": 429}
        assert "upgrade" not in _premium.attach(result)

    def test_not_suppressed_when_env_falsey(self, monkeypatch):
        monkeypatch.setenv(_premium._SUPPRESS_ENV, "")
        result = {"status": False, "data": None, "message": "rate limited", "status_code": 429}
        assert "upgrade" in _premium.attach(result)


class TestWrapStatusCode:
    def test_preserves_status_code_on_error(self):
        wrapped = wrap({"error": True, "status_code": 429, "message": "rate limited"})
        assert wrapped["status"] is False
        assert wrapped["status_code"] == 429

    def test_no_status_code_when_absent(self):
        wrapped = wrap({"error": True, "message": "something broke"})
        assert wrapped["status"] is False
        assert "status_code" not in wrapped

    def test_success_unaffected(self):
        wrapped = wrap({"leaders": []})
        assert wrapped["status"] is True
        assert "status_code" not in wrapped

    def test_end_to_end_429_to_hint(self):
        out = _premium.attach(wrap({"error": True, "status_code": 429, "message": "rate limited"}))
        assert out["upgrade"]["trigger"] == "rate_limited"


class TestPremiumHandoff:
    def test_json_payload(self, capsys):
        _premium.premium_handoff(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is True
        assert payload["data"]["docs"] == "http://docs.machina.gg/"
        assert payload["data"]["install"] == "pip install machina-cli"
        assert "machina_cli_installed" in payload["data"]
        assert any("machina login" in step for step in payload["data"]["next"])

    def test_human_output_mentions_docs(self, capsys):
        _premium.premium_handoff([])
        out = capsys.readouterr().out
        assert "http://docs.machina.gg/" in out
        assert "machina" in out.lower()


class TestRegression:
    def test_normal_success_has_no_upgrade(self):
        assert "upgrade" not in _premium.attach(success({"games": []}))

    def test_plain_error_has_no_upgrade(self):
        assert "upgrade" not in _premium.attach(error("not found"))


class TestPremiumTier:
    def test_shape(self):
        t = _premium.premium_tier()
        assert t["available"] is True
        assert "machina" in t["skills"]
        assert t["activate"] == "sports-skills premium"
        assert t["docs"] == "http://docs.machina.gg/"
        assert isinstance(t["machina_cli_installed"], bool)


class TestCatalog:
    """`catalog` is a public contract consumed by downstream tooling (sportsclaw)."""

    def test_modules_key_preserved(self):
        from sports_skills.cli import _REGISTRY, build_catalog

        cat = build_catalog()
        assert isinstance(cat["modules"], list) and cat["modules"]
        assert "version" in cat
        # back-compat: top-level modules must equal the registry (what sportsclaw reads)
        assert cat["modules"] == list(_REGISTRY.keys())

    def test_premium_tier_advertised_additively(self):
        from sports_skills.cli import build_catalog

        cat = build_catalog()
        assert "machina" in cat["tiers"]["premium"]["skills"]
        # back-compat guard: top-level modules must equal the open tier's modules
        assert cat["modules"] == cat["tiers"]["open"]["modules"]

    def test_output_is_json_serializable(self):
        from sports_skills.cli import build_catalog

        json.dumps(build_catalog())  # must not raise

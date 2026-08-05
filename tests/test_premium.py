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
        assert hint["via"]["data"]["docs"].startswith("https://docs.machina.gg/")
        assert "ref=sports-skills-hint" in hint["via"]["data"]["docs"]
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


class TestMarkerTrigger:
    """Connectors flag structural coverage refusals; `attach` turns the flag
    into an `upgrade` block and never lets the raw marker reach callers."""

    def test_marker_on_error_becomes_hint(self):
        result = {
            "status": False,
            "data": None,
            "message": "No ESPN coverage for x",
            _premium.UPGRADE_MARKER: "licensed_data",
        }
        out = _premium.attach(result)
        assert out["upgrade"]["trigger"] == "licensed_data"
        assert _premium.UPGRADE_MARKER not in out

    def test_marker_on_empty_success_becomes_hint(self):
        """Coverage gaps often surface as empty results, not errors."""
        result = {
            "status": True,
            "data": {"teams": []},
            "message": "xG not available here",
            _premium.UPGRADE_MARKER: "licensed_data",
        }
        out = _premium.attach(result)
        assert out["upgrade"]["trigger"] == "licensed_data"
        assert _premium.UPGRADE_MARKER not in out

    def test_unknown_marker_is_dropped_without_hint(self):
        result = {"status": False, "data": None, _premium.UPGRADE_MARKER: "bogus"}
        out = _premium.attach(result)
        assert "upgrade" not in out
        assert _premium.UPGRADE_MARKER not in out

    def test_marker_stripped_even_when_suppressed(self, monkeypatch):
        """The internal flag must never leak, hints on or off."""
        monkeypatch.setenv(_premium._SUPPRESS_ENV, "1")
        result = {"status": False, "data": None, _premium.UPGRADE_MARKER: "licensed_data"}
        out = _premium.attach(result)
        assert "upgrade" not in out
        assert _premium.UPGRADE_MARKER not in out


class TestWrapAttaches:
    """`wrap` is the SDK envelope; it must carry the same guidance the CLI does."""

    def test_sdk_429_gains_hint(self):
        out = wrap({"error": True, "status_code": 429, "message": "rate limited"})
        assert out["status"] is False
        assert out["upgrade"]["trigger"] == "rate_limited"

    def test_marked_error_gains_hint(self):
        out = wrap(
            {
                "error": True,
                "message": "No ESPN coverage for x",
                _premium.UPGRADE_MARKER: "licensed_data",
            }
        )
        assert out["status"] is False
        assert out["upgrade"]["trigger"] == "licensed_data"
        assert _premium.UPGRADE_MARKER not in out

    def test_marked_plain_dict_gains_hint_outside_data(self):
        """The marker rides the envelope, not the payload."""
        out = wrap({"teams": [], "message": "gap", _premium.UPGRADE_MARKER: "licensed_data"})
        assert out["status"] is True
        assert out["upgrade"]["trigger"] == "licensed_data"
        assert _premium.UPGRADE_MARKER not in out
        assert _premium.UPGRADE_MARKER not in out["data"]
        assert "upgrade" not in out["data"]

    def test_marked_standard_envelope_gains_hint(self):
        out = wrap(
            {
                "status": False,
                "data": None,
                "message": "gap",
                _premium.UPGRADE_MARKER: "licensed_data",
            }
        )
        assert out["upgrade"]["trigger"] == "licensed_data"

    def test_plain_success_untouched(self):
        out = wrap({"teams": [{"id": "1"}]})
        assert out["status"] is True
        assert "upgrade" not in out

    def test_suppression_covers_the_sdk_path(self, monkeypatch):
        monkeypatch.setenv(_premium._SUPPRESS_ENV, "1")
        out = wrap({"error": True, "status_code": 429, "message": "rate limited"})
        assert "upgrade" not in out

    def test_cli_double_attach_is_safe(self):
        """cli.py calls attach() on wrap()'s output; the hint must not double."""
        once = wrap({"error": True, "status_code": 429, "message": "rate limited"})
        twice = _premium.attach(once)
        assert twice["upgrade"]["trigger"] == "rate_limited"
        assert list(twice.keys()).count("upgrade") == 1


class TestFootballCoverageRefusals:
    """The football connector flags requests its free sources cannot serve.

    Uses `get_missing_players` on a non-Premier-League season: the league
    resolves from the local config and the refusal branch returns before any
    network call, so this exercises the full connector → wrap path offline.
    """

    def test_missing_players_gap_carries_hint(self):
        from sports_skills import football

        result = football.get_missing_players(season_id="bundesliga-2024")
        assert result["status"] is True
        assert (result.get("data") or {}).get("teams") == []
        assert result["upgrade"]["trigger"] == "licensed_data"
        assert _premium.UPGRADE_MARKER not in result
        assert _premium.UPGRADE_MARKER not in result["data"]

    def test_missing_players_gap_respects_suppression(self, monkeypatch):
        from sports_skills import football

        monkeypatch.setenv(_premium._SUPPRESS_ENV, "1")
        result = football.get_missing_players(season_id="bundesliga-2024")
        assert "upgrade" not in result
        assert _premium.UPGRADE_MARKER not in result

    def test_every_marker_in_football_names_a_known_trigger(self):
        """A typo'd trigger would silently produce no hint — pin them all."""
        import inspect

        from sports_skills.football import _connector as fb

        src = inspect.getsource(fb)
        assert src.count("UPGRADE_MARKER:") == 7
        for line in src.splitlines():
            if "UPGRADE_MARKER:" in line:
                trigger = line.split(":", 1)[1].strip().strip('",')
                assert trigger.strip('"') in _premium.TRIGGERS


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
        assert payload["data"]["docs"].startswith("https://docs.machina.gg/")
        assert "ref=sports-skills-premium-cmd" in payload["data"]["docs"]
        assert payload["data"]["install"].startswith("pipx install machina-cli")
        assert "uv tool install machina-cli" in payload["data"]["install"]
        assert "| bash" not in payload["data"]["install_sh"]
        assert "machina_cli_installed" in payload["data"]
        assert any("machina login" in step for step in payload["data"]["next"])

    def test_human_output_mentions_docs(self, capsys):
        _premium.premium_handoff([])
        out = capsys.readouterr().out
        assert "https://docs.machina.gg/" in out
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
        assert t["docs"].startswith("https://docs.machina.gg/")
        assert "ref=sports-skills-catalog" in t["docs"]
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

"""Tests for the American odds domain check and the CLI registry contract."""

import inspect

import pytest

from sports_skills.betting import _calcs
from sports_skills.cli import _REGISTRY, _load_module

# ── American odds domain ─────────────────────────────────────────────


class TestAmericanOddsDomain:
    """American prices are undefined strictly between -100 and +100."""

    @pytest.mark.parametrize("odds", [0, 1, -1, 50, -50, 99, -99, 99.9])
    def test_band_is_rejected(self, odds):
        assert _calcs._invalid_american(odds) is not None

    @pytest.mark.parametrize("odds", [100, -100, 110, -110, 150, -2000, 900])
    def test_valid_prices_accepted(self, odds):
        assert _calcs._invalid_american(odds) is None

    def test_message_names_every_offender(self):
        msg = _calcs._invalid_american(-110, 50, 0)
        assert "50" in msg and "0" in msg

    def test_message_suggests_the_other_formats(self):
        msg = _calcs._invalid_american(1.91)
        assert "decimal" in msg and "probability" in msg

    def test_convert_odds_rejects_band(self):
        r = _calcs.convert_odds({"params": {"odds": 50}})
        assert r["status"] is False and "Invalid American odds" in r["message"]

    @pytest.mark.parametrize("odds", [100, -100])
    def test_convert_odds_accepts_even_money(self, odds):
        r = _calcs.convert_odds({"params": {"odds": odds}})
        assert r["status"] is True
        assert r["data"]["implied_probability"] == 0.5

    def test_decimal_odds_passed_as_american_is_caught(self):
        """The common mistake: 1.91 is decimal, not American."""
        assert _calcs.convert_odds({"params": {"odds": 1.91}})["status"] is False

    def test_decimal_format_still_works(self):
        r = _calcs.convert_odds({"params": {"odds": 1.91, "from_format": "decimal"}})
        assert r["status"] is True
        assert r["data"]["implied_probability"] == pytest.approx(0.52356, abs=1e-4)

    def test_probability_format_still_works(self):
        r = _calcs.convert_odds({"params": {"odds": 0.55, "from_format": "probability"}})
        assert r["status"] is True and r["data"]["implied_probability"] == 0.55

    def test_devig_rejects_band(self):
        r = _calcs.devig({"params": {"odds": "-110,50"}})
        assert r["status"] is False and "Invalid American odds" in r["message"]

    def test_devig_valid_unaffected(self):
        r = _calcs.devig({"params": {"odds": "-110,-110"}})
        assert r["status"] is True
        assert r["data"]["outcomes"][0]["fair_prob"] == pytest.approx(0.5)

    def test_parlay_rejects_band(self):
        r = _calcs.parlay_analysis({"params": {"legs": "0.5,0.5", "parlay_odds": 50}})
        assert r["status"] is False and "Invalid American odds" in r["message"]

    def test_parlay_valid_unaffected(self):
        r = _calcs.parlay_analysis({"params": {"legs": "0.5,0.5", "parlay_odds": 264}})
        assert r["status"] is True

    def test_line_movement_rejects_band(self):
        r = _calcs.line_movement({"params": {"open_odds": 0, "close_odds": 50}})
        assert r["status"] is False and "Invalid American odds" in r["message"]

    def test_line_movement_valid_unaffected(self):
        r = _calcs.line_movement({"params": {"open_odds": -110, "close_odds": -130}})
        assert r["status"] is True

    def test_negative_odds_still_mean_favorite(self):
        """The band check exists because the formula inverts inside it."""
        favorite = _calcs.convert_odds({"params": {"odds": -200}})["data"]
        underdog = _calcs.convert_odds({"params": {"odds": 200}})["data"]
        assert favorite["implied_probability"] > 0.5 > underdog["implied_probability"]


# ── CLI registry contract ─────────────────────────────────────────────


class TestRegistryMatchesSignatures:
    """The registry is the agent-facing contract; drift breaks real calls."""

    @staticmethod
    def _pairs():
        for mod_name, cmds in sorted(_REGISTRY.items()):
            try:
                mod = _load_module(mod_name)
            except Exception:  # pragma: no cover - optional dependency absent
                continue
            if mod is None:
                continue
            for cmd, info in cmds.items():
                fn = getattr(mod, cmd, None)
                if callable(fn):
                    yield mod_name, cmd, info, fn

    def test_every_command_exists(self):
        missing = []
        for mod_name, cmds in sorted(_REGISTRY.items()):
            try:
                mod = _load_module(mod_name)
            except Exception:  # pragma: no cover
                continue
            if mod is None:
                continue
            missing += [
                f"{mod_name}.{c}" for c in cmds if not callable(getattr(mod, c, None))
            ]
        assert not missing, f"registry names with no function: {missing}"

    def test_required_params_match(self):
        """A param the function defaults must not be advertised as required."""
        bad = []
        for mod_name, cmd, info, fn in self._pairs():
            real = {
                p
                for p, v in inspect.signature(fn).parameters.items()
                if v.default is inspect.Parameter.empty
            }
            declared = set(info.get("required", []))
            if real != declared:
                bad.append(
                    f"{mod_name}.{cmd}: registry={sorted(declared)} actual={sorted(real)}"
                )
        assert not bad, "registry/signature drift: " + "; ".join(bad)

    def test_no_phantom_params(self):
        """Every advertised param must be accepted by the function."""
        bad = []
        for mod_name, cmd, info, fn in self._pairs():
            accepted = set(inspect.signature(fn).parameters)
            declared = set(info.get("required", [])) | set(info.get("optional", []))
            extra = declared - accepted
            if extra:
                bad.append(f"{mod_name}.{cmd}: {sorted(extra)}")
        assert not bad, "params the function does not accept: " + "; ".join(bad)

    def test_convert_odds_from_format_is_optional(self):
        """It defaults to "american"; requiring it blocked the documented call."""
        assert "from_format" not in _REGISTRY["betting"]["convert_odds"].get("required", [])

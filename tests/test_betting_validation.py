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


class TestDevigDecimalAndProbabilityDomain:
    """devig checks decimal and probability input the way convert_odds does."""

    def test_probabilities_passed_as_decimal_are_rejected(self):
        """0.6 and 0.45 read as decimal odds flip the favourite to 43%."""
        r = _calcs.devig({"params": {"odds": "0.6,0.45", "format": "decimal"}})
        assert r["status"] is False and "greater than 1.0" in r["message"]

    def test_decimal_even_one_is_rejected(self):
        r = _calcs.devig({"params": {"odds": "1.0,1.0", "format": "decimal"}})
        assert r["status"] is False

    @pytest.mark.parametrize("odds", ["0.7,1.2", "55,50", "0.5,0"])
    def test_probability_outside_zero_one_is_rejected(self, odds):
        r = _calcs.devig({"params": {"odds": odds, "format": "probability"}})
        assert r["status"] is False and "between 0 and 1" in r["message"]

    def test_evaluate_bet_rejects_probabilities_passed_as_decimal(self):
        r = _calcs.evaluate_bet({"params": {"book_odds": "0.6,0.45", "book_format": "decimal", "market_prob": 0.5}})
        assert r["status"] is False

    def test_valid_decimal_and_probability_unaffected(self):
        assert _calcs.devig({"params": {"odds": "1.91,1.91", "format": "decimal"}})["status"] is True
        assert _calcs.devig({"params": {"odds": "0.55,0.50", "format": "probability"}})["status"] is True


_NON_FINITE = ["nan", "inf", "-inf"]
_FORMATS = ["american", "decimal", "probability"]
_VALID = {"american": "-110,-110", "decimal": "1.91,1.91", "probability": "0.55,0.50"}


class TestNonFiniteOdds:
    """NaN and infinities are never prices; float() accepts them, so check explicitly."""

    @pytest.mark.parametrize("fmt", _FORMATS)
    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_devig_rejects_non_finite_string(self, fmt, bad):
        good = _VALID[fmt].split(",")[0]
        r = _calcs.devig({"params": {"odds": f"{good},{bad}", "format": fmt}})
        assert r["status"] is False

    @pytest.mark.parametrize("fmt", _FORMATS)
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_devig_rejects_non_finite_list(self, fmt, bad):
        good = float(_VALID[fmt].split(",")[0])
        r = _calcs.devig({"params": {"odds": [good, bad], "format": fmt}})
        assert r["status"] is False

    @pytest.mark.parametrize("fmt", _FORMATS)
    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_evaluate_bet_propagates_non_finite_rejection(self, fmt, bad):
        good = _VALID[fmt].split(",")[0]
        r = _calcs.evaluate_bet(
            {"params": {"book_odds": f"{good},{bad}", "book_format": fmt, "market_prob": 0.5}}
        )
        assert r["status"] is False

    @pytest.mark.parametrize("fmt", _FORMATS)
    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_convert_odds_rejects_non_finite(self, fmt, bad):
        r = _calcs.convert_odds({"params": {"odds": bad, "from_format": fmt}})
        assert r["status"] is False

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_parlay_rejects_non_finite_american(self, bad):
        r = _calcs.parlay_analysis({"params": {"legs": "0.5,0.5", "parlay_odds": bad}})
        assert r["status"] is False

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_line_movement_rejects_non_finite_american(self, bad):
        r = _calcs.line_movement({"params": {"open_odds": -110, "close_odds": bad}})
        assert r["status"] is False


class TestDevigDomainBoundaries:
    """Boundaries for decimal and probability input, string and list alike."""

    @pytest.mark.parametrize("odds", ["0.5,0", "0.5,1", "0.5,-0.1", "0.5,1.2"])
    def test_probability_boundaries_rejected_string(self, odds):
        r = _calcs.devig({"params": {"odds": odds, "format": "probability"}})
        assert r["status"] is False

    @pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.2])
    def test_probability_boundaries_rejected_list(self, bad):
        r = _calcs.devig({"params": {"odds": [0.5, bad], "format": "probability"}})
        assert r["status"] is False

    @pytest.mark.parametrize("odds", ["1.91,1.0", "1.91,0.5", "1.91,0", "1.91,-2"])
    def test_decimal_at_or_below_one_rejected_string(self, odds):
        r = _calcs.devig({"params": {"odds": odds, "format": "decimal"}})
        assert r["status"] is False

    @pytest.mark.parametrize("bad", [1.0, 0.5, 0.0, -2.0])
    def test_decimal_at_or_below_one_rejected_list(self, bad):
        r = _calcs.devig({"params": {"odds": [1.91, bad], "format": "decimal"}})
        assert r["status"] is False

    @pytest.mark.parametrize("fmt", _FORMATS)
    def test_valid_inputs_preserved(self, fmt):
        as_str = _calcs.devig({"params": {"odds": _VALID[fmt], "format": fmt}})
        as_list = _calcs.devig(
            {"params": {"odds": [float(o) for o in _VALID[fmt].split(",")], "format": fmt}}
        )
        assert as_str["status"] is True and as_list["status"] is True
        assert as_str["data"]["outcomes"] == as_list["data"]["outcomes"]

    @pytest.mark.parametrize("fmt", _FORMATS)
    def test_evaluate_bet_valid_inputs_preserved(self, fmt):
        r = _calcs.evaluate_bet(
            {"params": {"book_odds": _VALID[fmt], "book_format": fmt, "market_prob": 0.45}}
        )
        assert r["status"] is True, r


_NON_FINITE_FLOATS = [float("nan"), float("inf"), float("-inf")]


class TestNonFiniteArbitrageParlayLines:
    """Range checks written as `not lo < x < hi` so NaN cannot slip through."""

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_arbitrage_rejects_non_finite_string(self, bad):
        r = _calcs.find_arbitrage({"params": {"market_probs": f"0.5,{bad}"}})
        assert r["status"] is False and "between 0 and 1" in r["message"]

    @pytest.mark.parametrize("bad", _NON_FINITE_FLOATS)
    def test_arbitrage_rejects_non_finite_list(self, bad):
        r = _calcs.find_arbitrage({"params": {"market_probs": [0.5, bad]}})
        assert r["status"] is False and "between 0 and 1" in r["message"]

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_parlay_rejects_non_finite_leg_string(self, bad):
        r = _calcs.parlay_analysis({"params": {"legs": f"0.5,{bad}", "parlay_odds": 600}})
        assert r["status"] is False and "leg probabilities" in r["message"]

    @pytest.mark.parametrize("bad", _NON_FINITE_FLOATS)
    def test_parlay_rejects_non_finite_leg_list(self, bad):
        r = _calcs.parlay_analysis({"params": {"legs": [0.5, bad], "parlay_odds": 600}})
        assert r["status"] is False and "leg probabilities" in r["message"]

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_parlay_rejects_non_finite_decimal_odds(self, bad):
        r = _calcs.parlay_analysis(
            {"params": {"legs": "0.5,0.5", "parlay_odds": bad, "odds_format": "decimal"}}
        )
        assert r["status"] is False and "greater than 1.0" in r["message"]

    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_parlay_rejects_non_finite_correlation(self, bad):
        r = _calcs.parlay_analysis(
            {"params": {"legs": "0.5,0.5", "parlay_odds": 600, "correlation": bad}}
        )
        assert r["status"] is False and "correlation" in r["message"]

    @pytest.mark.parametrize("corr", [0, 0.5])
    def test_parlay_correlation_boundaries_accepted(self, corr):
        r = _calcs.parlay_analysis(
            {"params": {"legs": "0.5,0.5", "parlay_odds": 600, "correlation": corr}}
        )
        assert r["status"] is True and r["data"]["correlation_applied"] == corr

    @pytest.mark.parametrize("market_type", ["spread", "total"])
    @pytest.mark.parametrize("position", ["open_line", "close_line"])
    @pytest.mark.parametrize("bad", _NON_FINITE)
    def test_line_movement_rejects_non_finite_line(self, market_type, position, bad):
        params = {"open_line": -3.0, "close_line": -3.5, "market_type": market_type}
        params[position] = bad
        r = _calcs.line_movement({"params": params})
        assert r["status"] is False and "finite" in r["message"]


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

"""Tests for CLI argument parsing (no network)."""

import json

import pytest

from sports_skills.cli import _parse_cli_kwargs


class TestParseCliKwargs:
    def test_equals_form(self):
        assert _parse_cli_kwargs(["--query=FIFA"]) == {"query": "FIFA"}

    def test_space_form(self):
        # Conventional CLI form — previously the value was silently
        # dropped and the flag coerced to a boolean.
        assert _parse_cli_kwargs(["--query", "FIFA"]) == {"query": "FIFA"}

    def test_mixed_forms(self):
        assert _parse_cli_kwargs(["--sport=mlb", "--query", "Mets", "--limit", "5"]) == {
            "sport": "mlb",
            "query": "Mets",
            "limit": 5,
        }

    def test_space_form_negative_number(self):
        # A negative value must not be mistaken for a flag.
        assert _parse_cli_kwargs(["--price", "-1.5"]) == {"price": -1.5}

    def test_bool_flag_bare(self):
        assert _parse_cli_kwargs(["--google_news"]) == {"google_news": True}

    def test_bool_flag_with_value(self):
        assert _parse_cli_kwargs(["--google_news", "false"]) == {"google_news": False}

    def test_typed_values(self):
        assert _parse_cli_kwargs(["--limit=20", "--price=0.5"]) == {
            "limit": 20,
            "price": 0.5,
        }

    def test_float_param_single_value_coerced(self):
        assert _parse_cli_kwargs(["--odds=-150"]) == {"odds": -150.0}

    def test_float_param_comma_separated_passes_through(self):
        # `odds` is a float for convert_odds but a comma-separated string
        # for devig — previously float() rejected the multi-outcome form
        # and devig was unusable through the CLI.
        assert _parse_cli_kwargs(["--odds=-230,+330,+750"]) == {
            "odds": "-230,+330,+750"
        }

    def test_float_param_comma_separated_space_form(self):
        assert _parse_cli_kwargs(["--odds", "-110,-110"]) == {"odds": "-110,-110"}

    def test_valueless_flag_fails_loudly(self, capsys):
        with pytest.raises(SystemExit):
            _parse_cli_kwargs(["--query"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is False
        assert "--query" in payload["message"]

    def test_bad_int_returns_structured_error(self, capsys):
        # Previously: raw ValueError traceback.
        with pytest.raises(SystemExit):
            _parse_cli_kwargs(["--season_year=premier-league-2026"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is False
        assert "season_year" in payload["message"]
        assert "integer" in payload["message"]

    def test_bad_float_returns_structured_error(self, capsys):
        with pytest.raises(SystemExit):
            _parse_cli_kwargs(["--price", "expensive"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is False
        assert "number" in payload["message"]

    def test_unexpected_positional_fails_loudly(self, capsys):
        with pytest.raises(SystemExit):
            _parse_cli_kwargs(["FIFA"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] is False

    def test_empty(self):
        assert _parse_cli_kwargs([]) == {}

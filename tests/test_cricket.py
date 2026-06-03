"""Tests for the cricket module — ESPN live backend and Cricsheet historical backend."""

import io
import json
import zipfile

import pytest

from sports_skills.cricket import _cricsheet

# ── get_competitions ────────────────────────────────────────


class TestGetCompetitions:
    def test_returns_known_codes_with_attribution(self):
        result = _cricsheet.get_competitions({})
        codes = {c["code"] for c in result["competitions"]}
        assert "ipl" in codes
        assert "tests" in codes
        assert "wbb" in codes
        assert result["count"] == len(result["competitions"])
        assert "cricsheet.org" in result["attribution"]

    def test_every_competition_has_name(self):
        result = _cricsheet.get_competitions({})
        for c in result["competitions"]:
            assert c["code"]
            assert c["name"]

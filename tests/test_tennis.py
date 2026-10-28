"""Tennis connector (#163): the full-year calendar body is fetched once, then cached."""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import pytest

from sports_skills import tennis
from sports_skills.cli import _REGISTRY
from sports_skills.tennis import _connector as t

_SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "tennis-data"
_SKILL = (_SKILL_DIR / "SKILL.md").read_text()
_API_REF = (_SKILL_DIR / "references" / "api-reference.md").read_text()

_TOUR_REQUIRED = ("get_rankings", "get_calendar", "get_news")
_NO_TOUR = ("get_player_info", "get_wta_entry_list", "get_wta_player_results")


def _section(text, heading):
    """Body of the markdown section starting at `heading` up to the next heading of any level."""
    m = re.search(rf"^{re.escape(heading)}\s*$(.*?)(?=^#)", text + "\n#", re.M | re.S)
    assert m, f"missing section {heading!r}"
    return m.group(1)


def test_calendar_is_cached_after_the_first_fetch(monkeypatch):
    calls = []

    def fake(sport_path, resource="scoreboard", params=None, **kw):
        calls.append(params)
        return {"events": [{"id": "188-2026", "name": "Wimbledon", "groupings": [{}]}]}

    monkeypatch.setattr(t, "espn_request", fake)
    first = t.get_calendar({"params": {"tour": "atp", "year": 1999}})
    second = t.get_calendar({"params": {"tour": "atp", "year": 1999}})
    assert first == second and first["tournaments"][0]["name"] == "Wimbledon"
    assert "draws" not in first["tournaments"][0]
    assert calls == [{"dates": "1999"}]


# --- tour contract: registry, public signatures, wrapper behavior ---


def test_registry_tour_contract():
    reg = _REGISTRY["tennis"]
    assert "tour" in reg["get_scoreboard"].get("optional", [])
    assert "tour" not in reg["get_scoreboard"].get("required", [])
    for cmd in _TOUR_REQUIRED:
        assert "tour" in reg[cmd].get("required", []), cmd
    for cmd in _NO_TOUR:
        assert "tour" not in reg[cmd].get("required", []) + reg[cmd].get("optional", []), cmd


def test_public_signatures_tour_contract():
    sb = inspect.signature(tennis.get_scoreboard).parameters
    assert sb["tour"].default is None and sb["date"].default is None
    for cmd in _TOUR_REQUIRED:
        assert inspect.signature(getattr(tennis, cmd)).parameters["tour"].default is inspect.Parameter.empty, cmd
    for cmd in _NO_TOUR:
        assert "tour" not in inspect.signature(getattr(tennis, cmd)).parameters, cmd


@pytest.fixture
def espn_calls(monkeypatch):
    calls = []

    def fake(sport_path, resource="scoreboard", params=None, **kw):
        calls.append((sport_path, resource, params))
        return {"events": []}

    monkeypatch.setattr(t, "espn_request", fake)
    return calls


def test_scoreboard_without_tour_fetches_atp_and_wta_in_one_call(espn_calls):
    result = tennis.get_scoreboard(date="2026-10-28")
    assert result["status"] is True and result["data"]["tour"] == "all"
    assert sorted(espn_calls) == [
        ("tennis/atp", "scoreboard", {"dates": "20261028"}),
        ("tennis/wta", "scoreboard", {"dates": "20261028"}),
    ]


def test_scoreboard_with_tour_fetches_only_that_tour(espn_calls):
    result = tennis.get_scoreboard(tour="wta")
    assert result["status"] is True and result["data"]["tour"] == "WTA"
    assert [c[0] for c in espn_calls] == ["tennis/wta"]


def test_scoreboard_without_tour_keeps_the_tour_that_answered_when_the_other_fails(monkeypatch):
    def fake(sport_path, resource="scoreboard", params=None, **kw):
        if sport_path == "tennis/wta":
            return {"error": True, "message": "upstream 503"}
        return {"events": [{"id": "1", "name": "Paris Masters", "groupings": []}]}

    monkeypatch.setattr(t, "espn_request", fake)
    result = tennis.get_scoreboard()
    assert result["status"] is True
    data = result["data"]
    assert data["partial"] is True and data["warnings"] == ["WTA: upstream 503"]
    assert [(x["name"], x["tour"]) for x in data["tournaments"]] == [("Paris Masters", "ATP")]
    assert data["count"] == 1


def test_cli_scoreboard_without_tour_dispatches_both_tours_with_the_date(espn_calls, monkeypatch, capsys):
    from sports_skills import cli

    monkeypatch.setattr(sys, "argv", ["sports-skills", "tennis", "get_scoreboard", "--date=2026-10-28"])
    cli.main()
    out = json.loads(capsys.readouterr().out)
    assert out["status"] is True and out["data"]["tour"] == "all"
    assert sorted(espn_calls) == [
        ("tennis/atp", "scoreboard", {"dates": "20261028"}),
        ("tennis/wta", "scoreboard", {"dates": "20261028"}),
    ]


@pytest.mark.parametrize("cmd", _TOUR_REQUIRED)
def test_tour_required_commands_fail_gracefully_without_tour(espn_calls, cmd):
    result = getattr(tennis, cmd)(tour=None)
    assert result["status"] is False and "tour" in result["message"]
    assert espn_calls == []


# --- documentation matches the contract ---


@pytest.mark.parametrize("doc", [_SKILL, _API_REF], ids=["SKILL", "api-reference"])
def test_docs_drop_blanket_tour_claims(doc):
    low = doc.lower()
    assert "there is no default" not in low
    assert "calling the command twice" not in low
    assert "most espn-backed commands require" not in low


def test_skill_command_table_says_scoreboard_covers_one_or_both_tours():
    row = next(line for line in _SKILL.splitlines() if line.startswith("| `get_scoreboard`"))
    assert "both" in row.lower()


@pytest.mark.parametrize("doc", [_SKILL, _API_REF], ids=["SKILL", "api-reference"])
def test_tour_section_names_each_command(doc):
    body = _section(doc, "## The `tour` Parameter")
    for cmd in _REGISTRY["tennis"]:
        assert cmd in body, cmd


def test_api_reference_tour_param_per_command():
    sb = _section(_API_REF, "### get_scoreboard")
    assert "`tour` (str, optional)" in sb and "`date` (str, optional)" in sb
    for cmd in _TOUR_REQUIRED:
        assert "`tour` (str, required)" in _section(_API_REF, f"### {cmd}"), cmd
    for cmd in _NO_TOUR:
        assert "`tour`" not in _section(_API_REF, f"### {cmd}"), cmd

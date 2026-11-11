"""``nba get_event_summary``: one game as its normalized event plus its play-by-play.

No network: the ESPN summary read is replaced by the checked-in summary fixture. The
command exists because the canonical NBA adapter reads an event and its plays together,
and no other command returns both from one read in one shape.
"""

import json
from pathlib import Path

import pytest

from sports_skills import cli, nba
from sports_skills.nba import _connector

FIXTURE = Path(__file__).parent / "fixtures/nba_summary_401859967.json"
EVENT_ID = "401859967"


def summary():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def reads(monkeypatch):
    """Serve the fixture for the one ESPN summary read, and fail on any live-CDN lookup."""
    calls = []

    def espn_summary(sport_path, event_id):
        calls.append((sport_path, event_id))
        return summary()

    def no_cdn(*args, **kwargs):
        raise AssertionError("get_event_summary must read ESPN only, so its shape never changes mid-game")

    monkeypatch.setattr(_connector, "espn_summary", espn_summary)
    monkeypatch.setattr(_connector, "_find_live_cdn_game", no_cdn)
    return calls


def test_it_returns_the_event_as_the_scoreboard_states_it_and_the_plays(reads):
    result = nba.get_event_summary(event_id=EVENT_ID)
    assert result["status"] is True
    data = result["data"]
    assert set(data) == {"event", "plays"}
    assert data["event"] == _connector._normalize_event(summary()["header"])
    assert data["plays"] == _connector._normalize_plays(summary())
    assert data["event"]["id"] == EVENT_ID
    assert data["plays"]["count"] == len(data["plays"]["plays"]) > 0


def test_it_makes_one_summary_read(reads):
    nba.get_event_summary(event_id=EVENT_ID)
    assert reads == [(_connector.SPORT_PATH, EVENT_ID)]


def test_a_game_with_no_plays_yet_is_the_event_alone(monkeypatch, reads):
    without_plays = summary()
    without_plays.pop("plays")
    monkeypatch.setattr(_connector, "espn_summary", lambda sport_path, event_id: without_plays)
    data = nba.get_event_summary(event_id=EVENT_ID)["data"]
    assert set(data) == {"event"}


@pytest.mark.parametrize("payload", [None, {}, {"plays": []}])
def test_a_summary_with_no_game_in_it_is_a_readable_failure(monkeypatch, reads, payload):
    monkeypatch.setattr(_connector, "espn_summary", lambda sport_path, event_id: payload)
    result = nba.get_event_summary(event_id="1")
    assert result["status"] is False
    assert "1" in result["message"]


def test_the_command_is_registered_with_its_required_parameter():
    assert cli._REGISTRY["nba"]["get_event_summary"] == {"required": ["event_id"]}

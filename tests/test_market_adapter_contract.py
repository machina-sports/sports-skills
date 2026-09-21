"""Every scoreboard sport's summary normalizer must satisfy the markets contract.

`compare_odds` dates a game by `game_info.start_time` and prices it from the
summary's `odds` block. Only NFL produced either, so the same comparison that
worked for NFL refused for the other six. Each sport's real normalizer runs
here against a synthetic-but-ESPN-shaped summary; only the sport-module
boundary is mocked, and no normalized payload is hand-enriched.
"""

from unittest.mock import MagicMock, patch

import pytest

from sports_skills.cbb._connector import _normalize_game_summary as _cbb_normalize
from sports_skills.cfb._connector import _normalize_game_summary as _cfb_normalize
from sports_skills.markets._connector import compare_odds
from sports_skills.mlb._connector import _normalize_game_summary as _mlb_normalize
from sports_skills.nba._connector import _normalize_game_summary as _nba_normalize
from sports_skills.nfl._connector import _normalize_game_summary as _nfl_normalize
from sports_skills.nhl._connector import _normalize_game_summary as _nhl_normalize
from sports_skills.wnba._connector import _normalize_game_summary as _wnba_normalize

# ESPN stamps a summary competition with a minute-precision UTC timestamp.
START_TIME = "2026-09-22T00:15Z"


def _team(team_id, location, name, abbreviation):
    return {
        "id": team_id,
        "location": location,
        "name": name,
        "abbreviation": abbreviation,
        "displayName": f"{location} {name}",
    }


# sport -> (its own normalizer, home team, away team). NFL is the control: it
# already shipped both fields, and must keep shipping them.
SPORTS = {
    "nfl": (_nfl_normalize, _team("14", "Los Angeles", "Rams", "LAR"), _team("19", "New York", "Giants", "NYG")),
    "nba": (_nba_normalize, _team("2", "Boston", "Celtics", "BOS"), _team("18", "New York", "Knicks", "NYK")),
    "wnba": (_wnba_normalize, _team("17", "Las Vegas", "Aces", "LV"), _team("9", "New York", "Liberty", "NY")),
    "mlb": (_mlb_normalize, _team("19", "Los Angeles", "Dodgers", "LAD"), _team("26", "San Francisco", "Giants", "SF")),
    "nhl": (_nhl_normalize, _team("7", "Colorado", "Avalanche", "COL"), _team("9", "Dallas", "Stars", "DAL")),
    "cfb": (_cfb_normalize, _team("194", "Ohio State", "Buckeyes", "OSU"), _team("130", "Michigan", "Wolverines", "MICH")),
    "cbb": (_cbb_normalize, _team("150", "Duke", "Blue Devils", "DUKE"), _team("153", "North Carolina", "Tar Heels", "UNC")),
}

EVERY_SPORT = pytest.mark.parametrize("sport", sorted(SPORTS))


def _raw_summary(home, away, date=START_TIME, pickcenter=True):
    """Header identity + one complete DraftKings pickcenter pair, ESPN-shaped."""
    competition = {
        "id": "401872947",
        "competitors": [
            {"id": home["id"], "homeAway": "home", "score": "0", "team": dict(home)},
            {"id": away["id"], "homeAway": "away", "score": "0", "team": dict(away)},
        ],
        "status": {"type": {"name": "STATUS_SCHEDULED", "shortDetail": "9/21 - 8:15 PM EDT"}},
    }
    if date is not None:
        competition["date"] = date

    summary = {"header": {"id": "401872947", "competitions": [competition]}}
    if pickcenter:
        summary["pickcenter"] = [
            {
                "provider": {"id": "100", "name": "Draft Kings", "priority": 1},
                "details": f"{home['abbreviation']} -6.5",
                "overUnder": 47.5,
                "spread": -6.5,
                "awayTeamOdds": {"favorite": False, "underdog": True, "moneyLine": 240, "teamId": away["id"]},
                "homeTeamOdds": {"favorite": True, "underdog": False, "moneyLine": -298, "teamId": home["id"]},
                "moneyline": {
                    "displayName": "Moneyline",
                    "home": {"close": {"odds": "-298"}, "open": {"odds": "-375"}},
                    "away": {"close": {"odds": "+240"}, "open": {"odds": "+295"}},
                },
            }
        ]
    return summary


def _normalized(sport, date=START_TIME, pickcenter=True):
    """Run the sport's own normalizer — never hand-build the normalized shape."""
    normalize, home, away = SPORTS[sport]
    return normalize(_raw_summary(home, away, date=date, pickcenter=pickcenter))


def _prophetx_event(sport):
    """One date-compatible ProphetX event exposing the full-game Moneyline."""
    _normalize, home, away = SPORTS[sport]
    return {
        "source": "prophetx",
        "event_id": 1700008786,
        "title": f"{away['displayName']} at {home['displayName']}",
        "scheduled": "2026-09-22T00:15:00Z",
        "markets": [
            {
                "market_key": "1700008786:219",
                "title": "Moneyline",
                "type": "moneyline",
                "selections_available": True,
                "outcomes": [
                    {"outcome": home["displayName"], "odds_american": -275, "implied_probability": 0.72},
                    {"outcome": away["displayName"], "odds_american": 270, "implied_probability": 0.28},
                ],
            }
        ],
    }


def _sport_module(summary):
    mod = MagicMock()
    mod.get_game_summary.return_value = {"status": True, "data": summary}
    return mod


def _compare(sport, summary, prophetx=None):
    with (
        patch("sports_skills.markets._connector._load_sport_module") as load,
        patch("sports_skills.markets._connector._search_kalshi") as kalshi,
        patch("sports_skills.markets._connector._search_polymarket") as poly,
        patch("sports_skills.markets._connector._search_prophetx") as px,
    ):
        load.return_value = _sport_module(summary)
        kalshi.return_value = []
        poly.return_value = []
        px.return_value = prophetx or []
        return compare_odds({"params": {"sport": sport, "event_id": "401872947"}})


class TestSummaryContract:
    @EVERY_SPORT
    def test_start_time_survives_the_sport_normalizer(self, sport):
        assert _normalized(sport)["game_info"]["start_time"] == START_TIME

    @EVERY_SPORT
    def test_the_complete_pickcenter_pair_survives_the_sport_normalizer(self, sport):
        odds = _normalized(sport)["odds"]
        assert (odds["home_odds"], odds["away_odds"]) == (-298, 240)
        assert odds["provider"] == "Draft Kings"
        assert odds["line"] == "close"
        # ESPN publishes no capture timestamp for pickcenter; never invent one.
        assert odds["captured_at"] is None

    @EVERY_SPORT
    def test_no_pickcenter_yields_no_odds_rather_than_a_crash(self, sport):
        assert _normalized(sport, pickcenter=False)["odds"] is None


class TestComparisonAcrossSports:
    @EVERY_SPORT
    def test_espn_and_a_dated_reference_both_price_the_game(self, sport):
        _normalize, home, away = SPORTS[sport]
        result = _compare(sport, _normalized(sport), prophetx=[_prophetx_event(sport)])
        assert result["status"] is True, result["message"]
        data = result["data"]
        assert data["start_time"] == START_TIME
        assert data["home_team"] == home["displayName"]
        assert data["away_team"] == away["displayName"]
        assert data["espn_odds"]["provider"] == "Draft Kings"
        assert data["sources"]["espn"]["outcome"] == "ok"
        assert data["sources"]["prophetx"]["outcome"] == "ok"
        assert "espn" in data["completeness"]["usable_sources"]

    @EVERY_SPORT
    @pytest.mark.parametrize("date", [None, "not-a-timestamp"])
    def test_an_undated_summary_still_admits_no_dated_market(self, sport, date):
        # Fail closed: with no usable ESPN date, a repeat meeting of this
        # matchup would validate exactly as well as this one.
        result = _compare(
            sport, _normalized(sport, date=date), prophetx=[_prophetx_event(sport)]
        )
        prophetx = result["data"]["sources"]["prophetx"]
        assert prophetx["outcome"] == "unmatched"
        assert "unstated time" in prophetx["detail"]
        assert "prophetx" not in result["data"]["completeness"]["usable_sources"]

    @EVERY_SPORT
    def test_a_summary_without_pickcenter_invents_no_espn_price(self, sport):
        result = _compare(sport, _normalized(sport, pickcenter=False))
        assert result["status"] is False
        data = result["data"]
        assert data["espn_odds"] == {}
        assert data["sources"]["espn"]["outcome"] == "empty"
        assert data["completeness"]["usable_sources"] == []

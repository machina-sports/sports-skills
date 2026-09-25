"""ESPN college standings report season totals, not the last split ESPN lists."""

from sports_skills.cbb import _connector as cbb
from sports_skills.cfb import _connector as cfb


def _stat(name, display, type_=None):
    return {"name": name, "type": type_ or name.lower(), "displayValue": display}


def test_cfb_standings_use_season_totals():
    """North Texas 2025 (12-2, 631 PF), trimmed from ESPN's standings payload.

    ESPN repeats wins/pointsFor for home, away, vs. conference and vs. ranked
    splits; the last one listed (vs. USA ranked: 1 win, 52 PF) used to win.
    """
    entry = {
        "team": {"id": "249", "displayName": "North Texas Mean Green", "abbreviation": "UNT"},
        "stats": [
            _stat("pointsAgainst", "371"),
            _stat("pointsFor", "631"),
            _stat("streak", "W1"),
            _stat("wins", "12"),
            _stat("overall", "12-2", "total"),
            _stat("pointsFor", "320", "homerecord_pointsfor"),
            _stat("wins", "6", "homerecord_wins"),
            _stat("pointsFor", "382", "vsconf_pointsfor"),
            _stat("wins", "7", "vsconf_wins"),
            _stat("vs. Conf.", "7-1", "vsconf"),
            _stat("pointsAgainst", "51", "vsusarankedteams_pointsagainst"),
            _stat("pointsFor", "52", "vsusarankedteams_pointsfor"),
            _stat("wins", "1", "vsusarankedteams_wins"),
        ],
    }
    (row,) = cfb._normalize_standings_entries({"entries": [entry]})
    assert row["wins"] == "12"
    assert row["losses"] == "2"
    assert row["win_pct"] == "0.857"
    assert row["points_for"] == "631"
    assert row["points_against"] == "371"
    assert row["conference_record"] == "7-1"


def test_cbb_standings_use_season_totals():
    """NJIT 2024-25 went 6-25 overall, 3-13 in conference; the conference split came last."""
    entry = {
        "team": {"id": "2885", "displayName": "NJIT Highlanders", "abbreviation": "NJIT"},
        "stats": [
            _stat("losses", "25"),
            _stat("winPercent", ".194"),
            _stat("wins", "6"),
            _stat("losses", "13", "vsconf_losses"),
            _stat("winPercent", ".188", "vsconf_winpercent"),
            _stat("wins", "3", "vsconf_wins"),
        ],
    }
    (row,) = cbb._normalize_standings_entries({"entries": [entry]})
    assert (row["wins"], row["losses"], row["win_pct"]) == ("6", "25", ".194")

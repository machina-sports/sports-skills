"""MLB roster rows read bats/throws from ESPN's separate ``bats`` and ``throws``.

ESPN's MLB roster has no ``hand`` field (that is NHL's). Fixtures are
synthetic and minimal; no network.
"""

from sports_skills.mlb import _connector as mlb


def _athlete(**extra):
    return {"id": "39832", "displayName": "Player A", "position": {"abbreviation": "DH"}, **extra}


def test_bats_throws_from_bats_and_throws():
    row = mlb._parse_athlete(
        _athlete(
            bats={"type": "LEFT", "abbreviation": "L", "displayValue": "Left"},
            throws={"type": "RIGHT", "abbreviation": "R", "displayValue": "Right"},
        )
    )
    assert row["bats_throws"] == "L/R"


def test_switch_hitter():
    row = mlb._parse_athlete(
        _athlete(
            bats={"type": "BOTH", "abbreviation": "B", "displayValue": "Both"},
            throws={"type": "RIGHT", "abbreviation": "R", "displayValue": "Right"},
        )
    )
    assert row["bats_throws"] == "B/R"


def test_empty_when_espn_sends_neither():
    assert mlb._parse_athlete(_athlete())["bats_throws"] == ""

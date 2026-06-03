"""Cricket historical data connector — Cricsheet.org open data.

Ball-by-ball (delivery-level) data for completed matches, distributed as
zipped JSON files per competition. License: ODC-BY 1.0 — attribution
required, so every response includes an `attribution` field.

Data lags live play: matches appear roughly a day after completion.
"""

import csv
import io
import json
import logging
import os
import time
import urllib.request
import zipfile

from sports_skills._espn_base import _USER_AGENT

logger = logging.getLogger("sports_skills.cricket")

_ATTRIBUTION = "Data from Cricsheet (cricsheet.org), ODC-BY 1.0"

# Cricsheet competition codes — every code verified live 2026-06-03
# against https://cricsheet.org/downloads/{code}_json.zip
_COMPETITIONS = {
    "tests": "Test matches (men)",
    "odis": "One-day internationals (men)",
    "t20s": "T20 internationals (men)",
    "ipl": "Indian Premier League",
    "bbl": "Big Bash League",
    "psl": "Pakistan Super League",
    "cpl": "Caribbean Premier League",
    "hnd": "The Hundred (men)",
    "ntb": "T20 Blast",
    "cch": "County Championship",
    "sat": "SA20",
    "msl": "Mzansi Super League",
    "lpl": "Lanka Premier League",
    "ilt": "International League T20",
    "wbb": "Women's Big Bash League",
    "wpl": "Women's Premier League",
}


def get_competitions(request_data):
    """List supported Cricsheet competition codes."""
    competitions = [
        {"code": code, "name": name} for code, name in sorted(_COMPETITIONS.items())
    ]
    return {
        "competitions": competitions,
        "count": len(competitions),
        "attribution": _ATTRIBUTION,
    }

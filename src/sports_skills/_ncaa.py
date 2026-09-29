"""Shared NCAA connector (sdataprod.ncaa.com + ncaa.com) — stdlib only.

The NCAA serves official college data through a GraphQL API at
``sdataprod.ncaa.com`` using *persisted queries*: each route is addressed by a
sha256 hash pinned to ncaa.com's frontend build, keyed by ``(sport,
division)``. Scoreboards, schedules, game detail (info, box score,
play-by-play, scoring summary) and tournament brackets all come from here.

The older ``data.ncaa.com/casablanca`` JSON feed is not used: it stopped
updating (football on 2025-08-29, so every later game stays ``pre``; nothing
newer than early 2025 for basketball), returns ``NoSuchKey`` for 2026, and
carries game ids that have since been reissued (#165).

The hashes rotate when ncaa.com redeploys, so they live in one table below and
every consumer fails with the same explanatory message when that happens.

This module is the shared core in the same sense as ``_espn_base``: the sport
is a parameter here, and the public sport modules (cfb, cbb) expose wrappers
pinned to their own sport, mirroring how the nba module combines ESPN, the
live CDN, and stats.nba.com behind one skill.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import ssl
import unicodedata
import urllib.parse
from datetime import datetime
from typing import Any

from sports_skills._espn_base import (
    RateLimiter,
    _cache_get,
    _cache_set,
    _http_fetch,
)

logger = logging.getLogger("sports_skills._ncaa")

_GRAPHQL_BASE = "https://sdataprod.ncaa.com/"
_SCHOOLS_URL = "https://www.ncaa.com/json/schools"

# No User-Agent policy observed on any NCAA host (bare clients pass), but
# identify honestly anyway, consistent with the NHL connector.
_NCAA_HEADERS = {"User-Agent": "sports-skills (+https://github.com/machina-sports/sports-skills)"}


# Every NCAA host serves a leaf-only TLS chain — the intermediate below is
# missing from their handshake. Platforms that fetch missing intermediates
# themselves (macOS system Python) verify anyway; plain OpenSSL builds fail
# with CERTIFICATE_VERIFY_FAILED. Shipping the intermediate keeps verification
# fully on (hostname + signature against the GlobalSign Root R46 in every
# standard root store) instead of the tempting-but-wrong unverified context.
#
# Certificate: GlobalSign GCC R46 OV TLS CA 2025 (issued by GlobalSign Root R46)
# Source: AIA of the ncaa.com leaf — http://secure.globalsign.com/cacert/gsgccr46ovtlsca2025.crt
# Valid: 2025-09-17 to 2029-06-23
# SHA256: D1:60:E2:DE:4E:56:CB:10:B6:6C:1C:B0:AD:CB:79:CF:93:C7:8D:CD:9D:B3:0C:20:18:22:02:62:C0:40:63:F9
_GLOBALSIGN_INTERMEDIATE = """\
-----BEGIN CERTIFICATE-----
MIIFfDCCA2SgAwIBAgIRAIRDWJCDb2c5QYLLnJpdyZ8wDQYJKoZIhvcNAQELBQAw
RjELMAkGA1UEBhMCQkUxGTAXBgNVBAoTEEdsb2JhbFNpZ24gbnYtc2ExHDAaBgNV
BAMTE0dsb2JhbFNpZ24gUm9vdCBSNDYwHhcNMjUwOTE3MDI1NTU2WhcNMjkwNjIz
MDAwMDAwWjBUMQswCQYDVQQGEwJCRTEZMBcGA1UEChMQR2xvYmFsU2lnbiBudi1z
YTEqMCgGA1UEAxMhR2xvYmFsU2lnbiBHQ0MgUjQ2IE9WIFRMUyBDQSAyMDI1MIIB
IjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1JyrGiv+210Lw4LTp9qxx9WC
o6w8HnxcTKr5XwR6WwtKidGXriLqGXtBINGTi4HUZ1Vl3FUIvscLwNcq2DRLwjWs
cYFNClVnuSw4CtwAcfa7Iltz+0FmFeh/KOWv5BfgCxAo9FaeXRG725b2eedo/7fb
0zBc6M/XcfQREVteZ6GovnLE96+T8RzRImvX38Y8vZoulp/XWv3p09C1pgp/53+1
itDl7xbrM4sglGNkeJ5LBN2dOR1sqWCMZ/V4a4cPQwopBtZis1vVh7/k4S6Ysgk0
CTi5vei0RSEIhxoFk48BHSXzTA4FJxqjfauYCZ4M5tmZ/R5VgXOZ4Ck/PifnXQID
AQABo4IBVTCCAVEwDgYDVR0PAQH/BAQDAgGGMBMGA1UdJQQMMAoGCCsGAQUFBwMB
MBIGA1UdEwEB/wQIMAYBAf8CAQAwHQYDVR0OBBYEFGl0Pq/DWwGVSe4UQVqT+rEw
mNqiMB8GA1UdIwQYMBaAFANcq3OBh6jMsKbVlOI2lkn/BZksMHsGCCsGAQUFBwEB
BG8wbTAuBggrBgEFBQcwAYYiaHR0cDovL29jc3AuZ2xvYmFsc2lnbi5jb20vcm9v
dHI0NjA7BggrBgEFBQcwAoYvaHR0cDovL3NlY3VyZS5nbG9iYWxzaWduLmNvbS9j
YWNlcnQvcm9vdHI0Ni5jcnQwNgYDVR0fBC8wLTAroCmgJ4YlaHR0cDovL2NybC5n
bG9iYWxzaWduLmNvbS9yb290cjQ2LmNybDAhBgNVHSAEGjAYMAgGBmeBDAECAjAM
BgorBgEEAaAyCgECMA0GCSqGSIb3DQEBCwUAA4ICAQBEUTiKxe5jEintARUvLBm9
qWZtGiOSV9E+3bntbFFBDBAroqwB6Cj53Zp/W08HwgxaPXdkVaRNYHB/eAatEtSm
1ldtoorfPc+mVlzbwCwfbpIs2uqW5rF78ne37qy2o+iVnJptq9AzPnlC03+zhhB9
JwmjUXVtPuqQZ96tFl0fAT77xGSLzCO8yfEDrxCqdWz2wneShSbCCsC15JB07OgO
StE+MsVBkwe5+PNzAlAr8NZ6f8mzeY/FzaBzlhYw5+c1yyzXJqp+gjRXWrLpD3Ho
hGOvIXIvCBnyVrYI/HPe6DR5w7oteui9Rt0xfUUudaTkt0iz7fc23eGboZ+bpvgT
gbd/kYK6JOrxawMyfBYxrR5zDHIJX0Mws99DNgACKBUfFadKAfwFw0+0airY5WAI
Xs8yhCb5XGwyzVpcB30BrQbWtqdI0PoE9usNvNbH3YFGfuS8oRmAJEgUUQnwOoGK
jMWtHacw0n8QESdRM274LJvLd9nwawYU4svJpf06FtKPqGH3nXefL741NO9KzDAG
PM11YScyJVfYdBDXFM86HU1fBGTKlkLcG/qMJxOqppY4wydRI3koSH6A78nO2QaJ
yqjTOQyCNHaSlmGjdiOvhJ8y1PiazHnuvWBx6z+7JJF2ukqqfjlSARwyfkfnRUIY
la7ZYEqcc56eoPAiElhvrg==
-----END CERTIFICATE-----
"""


# The root that anchors the chain above. It is a standard Mozilla-trusted root
# (byte-identical to the copy in certifi), but ships here too because platform
# bundles that predate it (e.g. macOS's /etc/ssl/cert.pem, which some Python
# builds read) do not contain it. Loaded only into this module's context, in
# addition to the system defaults — chains from other CAs still verify normally.
#
# Certificate: GlobalSign Root R46 (self-signed, valid 2019-03-20 to 2046-03-20)
# Source: http://secure.globalsign.com/cacert/rootr46.crt
# SHA256: 4F:A3:12:6D:8D:3A:11:D1:C4:85:5A:4F:80:7C:BA:D6:CF:91:9D:3A:5A:88:B0:3B:EA:2C:63:72:D9:3C:40:C9
_GLOBALSIGN_ROOT_R46 = """\
-----BEGIN CERTIFICATE-----
MIIFWjCCA0KgAwIBAgISEdK7udcjGJ5AXwqdLdDfJWfRMA0GCSqGSIb3DQEBDAUA
MEYxCzAJBgNVBAYTAkJFMRkwFwYDVQQKExBHbG9iYWxTaWduIG52LXNhMRwwGgYD
VQQDExNHbG9iYWxTaWduIFJvb3QgUjQ2MB4XDTE5MDMyMDAwMDAwMFoXDTQ2MDMy
MDAwMDAwMFowRjELMAkGA1UEBhMCQkUxGTAXBgNVBAoTEEdsb2JhbFNpZ24gbnYt
c2ExHDAaBgNVBAMTE0dsb2JhbFNpZ24gUm9vdCBSNDYwggIiMA0GCSqGSIb3DQEB
AQUAA4ICDwAwggIKAoICAQCsrHQy6LNl5brtQyYdpokNRbopiLKkHWPd08EsCVeJ
OaFV6Wc0dwxu5FUdUiXSE2te4R2pt32JMl8Nnp8semNgQB+msLZ4j5lUlghYruQG
vGIFAha/r6gjA7aUD7xubMLL1aa7DOn2wQL7Id5m3RerdELv8HQvJfTqa1VbkNud
316HCkD7rRlr+/fKYIje2sGP1q7Vf9Q8g+7XFkyDRTNrJ9CG0Bwta/OrffGFqfUo
0q3v84RLHIf8E6M6cqJaESvWJ3En7YEtbWaBkoe0G1h6zD8K+kZPTXhc+CtI4wSE
y132tGqzZfxCnlEmIyDLPRT5ge1lFgBPGmSXZgjPjHvjK8Cd+RTyG/FWaha/LIWF
zXg4mutCagI0GIMXTpRW+LaCtfOW3T3zvn8gdz57GSNrLNRyc0NXfeD412lPFzYE
+cCQYDdF3uYM2HSNrpyibXRdQr4G9dlkbgIQrImwTDsHTUB+JMWKmIJ5jqSngiCN
I/onccnfxkF0oE32kRbcRoxfKWMxWXEM2G/CtjJ9++ZdU6Z+Ffy7dXxd7Pj2Fxzs
x2sZy/N78CsHpdlseVR2bJ0cpm4O6XkMqCNqo98bMDGfsVR7/mrLZqrcZdCinkqa
ByFrgY/bxFn63iLABJzjqls2k+g9vXqhnQt2sQvHnf3PmKgGwvgqo6GDoLclcqUC
4wIDAQABo0IwQDAOBgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNV
HQ4EFgQUA1yrc4GHqMywptWU4jaWSf8FmSwwDQYJKoZIhvcNAQEMBQADggIBAHx4
7PYCLLtbfpIrXTncvtgdokIzTfnvpCo7RGkerNlFo048p9gkUbJUHJNOxO97k4Vg
JuoJSOD1u8fpaNK7ajFxzHmuEajwmf3lH7wvqMxX63bEIaZHU1VNaL8FpO7XJqti
2kM3S+LGteWygxk6x9PbTZ4IevPuzz5i+6zoYMzRx6Fcg0XERczzF2sUyQQCPtIk
pnnpHs6i58FZFZ8d4kuaPp92CC1r2LpXFNqD6v6MVenQTqnMdzGxRBF6XLE+0xRF
FRhiJBPSy03OXIPBNvIQtQ6IbbjhVp+J3pZmOUdkLG5NrmJ7v2B0GbhWrJKsFjLt
rWhV/pi60zTe9Mlhww6G9kuEYO4Ne7UyWHmRVSyBQ7N0H3qqJZ4d16GLuc1CLgSk
ZoNNiTW2bKg2SnkheCLQQrzRQDGQob4Ez8pn7fXwgNNgyYMqIgXQBztSvwyeqiv5
u+YfjyW6hY0XHgL+XVAEV8/+LbzvXMAaq7afJMbfc2hIkCwU9D9SGuTSyxTDYWnP
4vkYxboznxSjBF25cfe1lNj2M8FawTSLfJvdkzrnE6JwYZ+vj+vYxXX4M2bUdGc6
N3ec592kD3ZDZopD8p/7DEJ4Y9HiD2971KE9dJeFt0g5QdYg/NA6s/rob8SKunE3
vouXsXgxT7PntgMTzlSdriVZzH81Xwj3QEUxeCp6
-----END CERTIFICATE-----
"""


def _ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=_GLOBALSIGN_INTERMEDIATE + "\n" + _GLOBALSIGN_ROOT_R46)
    return context


_NCAA_SSL_CONTEXT = _ssl_context()


_ncaa_rate_limiter = RateLimiter(max_tokens=2, refill_rate=2.0)

_TIMEOUT = 15

# Sport configuration: GraphQL sport codes, valid divisions with their GraphQL
# division codes, and whether scoreboards are addressed by week or by date.
SPORTS = {
    "football": {
        "code": "MFB",
        "sport_url": "football",
        "divisions": {"fbs": 11, "fcs": 12},
        "default_division": "fbs",
        "date_style": "week",
    },
    "basketball-men": {
        "code": "MBB",
        "sport_url": "basketball-men",
        "divisions": {"d1": 1, "d2": 2, "d3": 3},
        "default_division": "d1",
        "date_style": "date",
    },
    "basketball-women": {
        "code": "WBB",
        "sport_url": "basketball-women",
        "divisions": {"d1": 1, "d2": 2, "d3": 3},
        "default_division": "d1",
        "date_style": "date",
    },
}

# ── persisted-query hashes (sdataprod) ─────────────────────────────
# Taken from ncaa.com's frontend build. When the site redeploys with changed
# queries these stop matching and _graphql() raises the rotation message.
# Reference for current values: https://github.com/henrygd/ncaa-api (src/codes.ts).
GAME_HASHES = {
    "scoreboard": "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c",
    "schedule": "a25ad021179ce1d97fb951a49954dc98da150089f9766e7e85890e439516ffbf",
    "game_info": "93a02c7193c89d85bcdda8c1784925d9b64657f73ef584382e2297af555acd4b",
    "scoring_summary": "7f86673d4875cd18102b7fa598e2bc5da3f49d05a1c15b1add0e2367ee890198",
    "bracket": "e651c2602fb9e82cdad6e947389600c6b69e0e463e437b78bf7ec614d6d15f80",
}

PBP_HASHES = {
    "football": "47928f2cabc7a164f0de0ed535a623bdf5a852cce7c30d6a6972a38609ba46a2",
    "basketball": "6b1232714a3598954c5bacabc0f81570e16d6ee017c9a6b93b601a3d40dafb98",
    "generic": "57f922d56d60d88326b62202b3d88e8cd3cfb6687931bc0b5b3dfab089b84faa",
}

BOXSCORE_HASHES = {
    "football": "babb939def47c602a6e81af7aa3f6b35197fb1f1b1a2f2b081f3a3e4924be82e",
    "basketball": "4a7fa26398db33de3ff51402a90eb5f25acef001cca28d239fe5361315d1419a",
}

_ROTATION_MESSAGE = (
    "The NCAA GraphQL endpoint rejected this query — ncaa.com has likely "
    "redeployed and rotated its persisted-query hashes, which this backend "
    "pins. get_ncaa_schools (ncaa.com/json) is unaffected, and the ESPN-backed "
    "get_scoreboard/get_schedule commands cover the same games. Current "
    "hashes can be found in henrygd/ncaa-api's src/codes.ts."
)


class _NcaaError(Exception):
    """A request cannot be built or served as asked."""


def guard(fn):
    """Return connector errors as data instead of raising.

    These functions are called by autonomous agents, so a bad parameter or an
    upstream failure has to arrive as a readable message rather than an
    unhandled traceback.
    """

    @functools.wraps(fn)
    def wrapper(request_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(request_data)
        except _NcaaError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("ncaa call failed", exc_info=True)
            return {
                "error": True,
                "message": f"NCAA backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _fetch_json(url: str, ttl: int = 300) -> Any:
    cached = _cache_get(f"ncaa:{url}")
    if cached is not None:
        return cached
    raw, err = _http_fetch(
        url,
        headers=_NCAA_HEADERS,
        rate_limiter=_ncaa_rate_limiter,
        timeout=_TIMEOUT,
        ssl_context=_NCAA_SSL_CONTEXT,
    )
    if err:
        raise _NcaaError(err.get("message", "request failed"))
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError) as exc:
        raise _NcaaError("the NCAA API returned invalid JSON") from exc
    _cache_set(f"ncaa:{url}", data, ttl=ttl)
    return data


def _graphql(sha: str, variables: dict[str, Any], operation: str | None = None, ttl: int = 300) -> dict[str, Any]:
    """Run one persisted query, translating rejections into the rotation message."""
    ext = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": sha}})
    url = _GRAPHQL_BASE + "?"
    if operation:
        url += f"operationName={operation}&"
    url += f"variables={urllib.parse.quote(json.dumps(variables))}&extensions={urllib.parse.quote(ext)}"
    try:
        data = _fetch_json(url, ttl=ttl)
    except _NcaaError as exc:
        if "400" in str(exc):
            raise _NcaaError(_ROTATION_MESSAGE) from exc
        raise
    if isinstance(data, dict) and data.get("errors") and not (data.get("data") or {}):
        first = (data["errors"] or [{}])[0]
        if "PersistedQuery" in str(first.get("message", "")):
            raise _NcaaError(_ROTATION_MESSAGE)
        raise _NcaaError(f"NCAA GraphQL error: {first.get('message', 'unknown')}")
    return data.get("data") or {}


def sport_config(sport: str) -> dict[str, Any]:
    config = SPORTS.get(str(sport))
    if config is None:
        raise _NcaaError(f"Unknown sport {sport!r}. Supported: {', '.join(sorted(SPORTS))}")
    return config


def resolve_division(sport: str, division: Any) -> tuple[str, int]:
    """Return ``(division_slug, graphql_code)`` for a sport, validating both."""
    config = sport_config(sport)
    divisions = config["divisions"]
    slug = str(division or config["default_division"]).strip().lower()
    if slug not in divisions:
        raise _NcaaError(
            f"Invalid division {division!r} for {sport}. Valid values: {', '.join(divisions)}"
        )
    return slug, divisions[slug]


def require_game_id(game_id: Any) -> str:
    """Validate the NCAA game id, catching ESPN event ids early.

    NCAA game ids are the short numeric ids from the scoreboard/schedule
    (e.g. 6306261). ESPN event ids are nine digits starting with 4 — the
    natural mix-up when both id systems serve the same games.
    """
    if not game_id:
        raise _NcaaError(
            "game_id is required — the NCAA game id from get_ncaa_scoreboard "
            "(e.g. '6306261'), not an ESPN event id."
        )
    text = str(game_id).strip()
    if re.fullmatch(r"4\d{8}", text):
        raise _NcaaError(
            f"{game_id!r} looks like an ESPN event id. Pass the NCAA game id from "
            "get_ncaa_scoreboard instead — join via game date plus team names; "
            "the two id systems share nothing."
        )
    if not re.fullmatch(r"\d{1,8}", text):
        raise _NcaaError(
            f"Invalid NCAA game id {game_id!r}. Expected the numeric id from "
            "get_ncaa_scoreboard (e.g. '6306261')."
        )
    return text


def current_season_year(sport: str) -> int:
    """The season identified by its starting calendar year."""
    now = datetime.now()
    if sport == "football":
        return now.year if now.month >= 8 else now.year - 1
    # Basketball seasons start in November; the season label follows the start.
    return now.year if now.month >= 11 else now.year - 1


def fold(text: Any) -> str:
    """Lowercase and strip diacritics for name matching."""
    normalized = unicodedata.normalize("NFKD", str(text))
    return normalized.encode("ascii", "ignore").decode().lower()


# ── scoreboard / schedule ─────────────────────────────


def _normalize_contest(contest: dict[str, Any]) -> dict[str, Any]:
    teams = contest.get("teams") or []
    home = next((t for t in teams if t.get("isHome")), {})
    away = next((t for t in teams if not t.get("isHome")), {})
    return {
        "game_id": str(contest.get("contestId", "")),
        "start_date": contest.get("startDate"),
        "start_time": contest.get("startTime"),
        "status": contest.get("statusCodeDisplay") or contest.get("gameState"),
        "period": contest.get("currentPeriod") or None,
        "home_team": home.get("nameShort"),
        "away_team": away.get("nameShort"),
        "home_seo": home.get("seoname"),
        "away_seo": away.get("seoname"),
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "home_conference": home.get("conferenceSeo"),
        "away_conference": away.get("conferenceSeo"),
    }


def _season_of(day: datetime) -> int:
    """Basketball season (by starting year) that a calendar day falls in."""
    return day.year if day.month >= 7 else day.year - 1


def _iso(us_date: str) -> str:
    return datetime.strptime(us_date, "%m/%d/%Y").strftime("%Y-%m-%d")


def fetch_scoreboard(sport: str, division: Any, *, year: Any = None, week: Any = None, date: Any = None) -> dict[str, Any]:
    """Scoreboard for one sport/division and one week (football) or day."""
    config = sport_config(sport)
    slug, code = resolve_division(sport, division)
    variables: dict[str, Any] = {"sportCode": config["code"], "division": code}

    if config["date_style"] == "week":
        season = int(year) if year is not None else current_season_year(sport)
        if week is None:
            raise _NcaaError("week is required for football scoreboards (1-20).")
        variables.update(seasonYear=season, week=int(week))
        scope = {"season": str(season), "week": int(week)}
    else:
        if date is None:
            raise _NcaaError("date is required — YYYY-MM-DD.")
        try:
            day = datetime.strptime(str(date), "%Y-%m-%d")
        except ValueError:
            raise _NcaaError(f"Invalid date {date!r}. Use YYYY-MM-DD.") from None
        variables.update(seasonYear=_season_of(day), contestDate=day.strftime("%m/%d/%Y"))
        scope = {"date": str(date)}

    data = _graphql(GAME_HASHES["scoreboard"], variables, ttl=60)
    games = [_normalize_contest(c) for c in data.get("contests") or []]
    result = {
        "provider": "ncaa",
        "sport": sport,
        "division": slug,
        "games": games,
        "count": len(games),
    }
    result.update(scope)
    return result


def fetch_schedule(sport: str, division: Any, *, year: Any = None, month: Any = None) -> dict[str, Any]:
    """Schedule index: which weeks (football) or dates have games."""
    config = sport_config(sport)
    slug, code = resolve_division(sport, division)
    season = int(year) if year is not None else current_season_year(sport)
    if config["date_style"] == "date" and month is None:
        raise _NcaaError("month is required for this sport's schedule (1-12).")

    data = _graphql(
        GAME_HASHES["schedule"],
        {"sportCode": config["code"], "division": code, "seasonYear": season},
        operation="NCAA_schedules_today_web",
        ttl=3600,
    )
    entries = (data.get("schedules") or {}).get("games") or []
    schedule: list[dict[str, Any]] = []
    if config["date_style"] == "week":
        # One entry per week in order ("MM/DD/YYYY-MM/DD/YYYY"), so position is
        # the week number the scoreboard takes. The feed then appends one entry
        # spanning the whole postseason, a rollup of those weeks: it starts
        # before the previous entry ends, so it is not a week of its own.
        for entry in entries:
            first, _, last = str(entry.get("contestDate", "")).partition("-")
            start, end = _iso(first), _iso(last or first)
            if schedule and start < schedule[-1]["end_date"]:
                continue
            schedule.append({"week": len(schedule) + 1, "start_date": start, "end_date": end, "games": entry.get("count")})
    else:
        for entry in entries:
            day = _iso(str(entry.get("contestDate", "")))
            if int(day[5:7]) == int(month):
                schedule.append({"date": day, "games": entry.get("count")})
    return {
        "provider": "ncaa",
        "sport": sport,
        "division": slug,
        "season": str(season),
        "schedule": schedule,
        "count": len(schedule),
    }


# ── sdataprod layer (persisted queries) ─────────────────────────────


def fetch_game_info(game_id: Any) -> dict[str, Any]:
    gid = require_game_id(game_id)
    data = _graphql(GAME_HASHES["game_info"], {"id": gid, "week": None, "staticTestEnv": None})
    contests = data.get("contests") or []
    if not contests:
        raise _NcaaError(
            f"No game found for game_id {gid!r}. NCAA reissues game ids; take a "
            "current one from get_ncaa_scoreboard."
        )
    return {"provider": "ncaa", "game_id": gid, "game": contests[0]}


def _pbp_hash(sport: str) -> str:
    if sport == "football":
        return PBP_HASHES["football"]
    if sport.startswith("basketball"):
        return PBP_HASHES["basketball"]
    return PBP_HASHES["generic"]


def _team_names_by_id(payload: dict[str, Any]) -> dict[str, str]:
    names = {}
    for team in payload.get("teams") or []:
        tid = team.get("teamId")
        if tid is not None:
            names[str(tid)] = team.get("nameShort") or team.get("nameFull") or team.get("seoname")
    return names


def fetch_play_by_play(sport: str, game_id: Any, limit: Any = None) -> dict[str, Any]:
    gid = require_game_id(game_id)
    data = _graphql(_pbp_hash(sport), {"contestId": gid, "staticTestEnv": None})
    pbp = data.get("playbyplay") or {}
    names = _team_names_by_id(pbp)
    plays = []
    for period in pbp.get("periods") or []:
        stanza = period.get("periodNumber")
        for block in period.get("playbyplayStats") or []:
            team = names.get(str(block.get("teamId")))
            if block.get("plays"):
                # Football shape: plays nest inside per-drive blocks.
                for p in block["plays"]:
                    plays.append(
                        {
                            "period": stanza,
                            "clock": p.get("clock") or block.get("clock") or None,
                            "team": team,
                            "is_home": block.get("isHome"),
                            "description": p.get("playText"),
                            "drive": p.get("driveText") or None,
                            "home_score": p.get("homeScore"),
                            "away_score": p.get("visitorScore"),
                        }
                    )
            else:
                # Basketball shape: each block is itself one play.
                plays.append(
                    {
                        "period": stanza,
                        "clock": block.get("clock") or None,
                        "team": team,
                        "is_home": block.get("isHome"),
                        "description": block.get("eventDescription") or block.get("homeText") or block.get("visitorText"),
                        "drive": None,
                        "home_score": block.get("homeScore"),
                        "away_score": block.get("visitorScore"),
                    }
                )
    total = len(plays)
    if limit is not None:
        plays = plays[: int(limit)]
    result = {
        "provider": "ncaa",
        "game_id": gid,
        "status": pbp.get("status"),
        "plays": plays,
        "count": len(plays),
    }
    if limit is not None and total > len(plays):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} plays"]
    return result


def fetch_boxscore(sport: str, game_id: Any) -> dict[str, Any]:
    gid = require_game_id(game_id)
    key = "football" if sport == "football" else "basketball"
    data = _graphql(BOXSCORE_HASHES[key], {"contestId": gid, "staticTestEnv": None})
    box = data.get("boxscore") or {}
    if not box:
        raise _NcaaError(f"No box score for game_id {gid!r}")
    teams = [
        {
            "team_id": str(t.get("teamId", "")),
            "name": t.get("nameShort") or t.get("nameFull"),
            "seo": t.get("seoname"),
            "is_home": t.get("isHome"),
            "color": t.get("color") or None,
        }
        for t in box.get("teams") or []
    ]
    return {
        "provider": "ncaa",
        "game_id": gid,
        "description": box.get("description"),
        "status": box.get("status"),
        "period": box.get("period"),
        "teams": teams,
        # Stat tables are sport-specific; passed through as the source shapes them.
        "team_stats": box.get("teamBoxscore") or [],
    }


_FG_SUMMARY = re.compile(r"^(?P<kicker>.+?) field goal is good", re.IGNORECASE)
_FG_PLAY = re.compile(r"^(?:\(\d+:\d+\)\s*)?(?P<kicker>.+?) field goal attempt from (?P<yards>\d+) yards? GOOD", re.IGNORECASE)


def _add_field_goal_distances(gid: str, summary: dict[str, Any]) -> list[str]:
    """Set ``distance_yards`` on made field goals, from the play-by-play.

    The summary text carries no distance ("Smith,Garrison Field Goal is
    good."); the play-by-play attempt does ("... field goal attempt from 43
    yards GOOD"). Made kicks pair up per kicker in game order. Returns warnings.
    """
    fgs = []
    for period in summary.get("periods") or []:
        for entry in period.get("summary") or []:
            m = _FG_SUMMARY.match(str(entry.get("scoreText", "")))
            if entry.get("scoreType") == "FG" and m:
                fgs.append((entry, m.group("kicker").strip().lower()))
    if not fgs:
        return []
    try:
        data = _graphql(PBP_HASHES["football"], {"contestId": gid, "staticTestEnv": None})
    except _NcaaError as exc:
        return [f"field-goal distances unavailable: {exc}"]
    made: dict[str, list[int]] = {}
    for period in (data.get("playbyplay") or {}).get("periods") or []:
        for block in period.get("playbyplayStats") or []:
            for play in block.get("plays") or []:
                m = _FG_PLAY.match(str(play.get("playText", "")))
                if m:
                    made.setdefault(m.group("kicker").strip().lower(), []).append(int(m.group("yards")))
    for entry, kicker in fgs:
        kicks = made.get(kicker)
        entry["distance_yards"] = kicks.pop(0) if kicks else None
    return []


def fetch_scoring_summary(game_id: Any) -> dict[str, Any]:
    gid = require_game_id(game_id)
    data = _graphql(GAME_HASHES["scoring_summary"], {"contestId": gid, "staticTestEnv": None})
    summary = data.get("scoringSummary") or {}
    if not summary:
        raise _NcaaError(f"No scoring summary for game_id {gid!r}")
    result = {"provider": "ncaa", "game_id": gid, "scoring_summary": summary}
    warnings = _add_field_goal_distances(gid, summary)
    if warnings:
        result["warnings"] = warnings
    return result


def fetch_bracket(sport: str, division: Any, year: Any = None) -> dict[str, Any]:
    config = sport_config(sport)
    slug, code = resolve_division(sport, division)
    season = int(year) if year is not None else current_season_year(sport) + 1
    data = _graphql(
        GAME_HASHES["bracket"],
        {"sportUrl": config["sport_url"], "division": code, "year": season},
        operation="get_championship_ncaa",
        ttl=120,
    )
    championships = data.get("championships") or []
    if not championships:
        raise _NcaaError(
            f"No bracket for {sport}/{slug} in {season}. Brackets exist once the "
            "tournament field is announced."
        )
    champ = championships[0]
    games = champ.get("games") or []
    if not any(g.get("teams") for g in games):
        # The source still serves the bracket skeleton (2020: 67 TBA games
        # with success status), which is a placeholder, not a bracket.
        note = (
            " The 2020 NCAA tournaments were cancelled (COVID-19) and never played."
            if season == 2020
            else " The field has not been announced yet."
        )
        raise _NcaaError(f"The {season} {sport}/{slug} bracket has no teams in any game.{note}")
    return {
        "provider": "ncaa",
        "sport": sport,
        "division": slug,
        "year": season,
        "championship_id": champ.get("championshipId"),
        "rounds": champ.get("rounds") or [],
        "regions": champ.get("regions") or [],
        "games": games,
    }


# ── schools index ─────────────────────────────


def fetch_schools(query: Any = None) -> dict[str, Any]:
    data = _fetch_json(_SCHOOLS_URL, ttl=21600)
    schools = data if isinstance(data, list) else []
    if query:
        needle = fold(str(query).strip())
        schools = [
            s
            for s in schools
            if needle in fold(s.get("name", "")) or needle in fold(s.get("slug", ""))
        ]
    rows = [
        {"slug": s.get("slug"), "name": s.get("name"), "long_name": s.get("long_name") or s.get("longName")}
        for s in schools
    ]
    return {
        "provider": "ncaa",
        "query": query,
        "schools": rows,
        "count": len(rows),
    }

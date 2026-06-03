# cricket-data Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `cricket` module + `cricket-data` skill: live-ish cricket data via ESPN's public site API and historical ball-by-ball via Cricsheet.org, zero config, no API keys.

**Architecture:** One `cricket` package with two backend files — `_espn.py` (series discovery, scoreboard, standings, game summary, news; built on the existing `_espn_base.py` shared infra) and `_cricsheet.py` (zip download/cache to `~/.cache/sports-skills/cricsheet/`, ball-by-ball, in-connector aggregation, player registry). `__init__.py` exposes one flat command set wrapped in the standard response envelope. One new entry in the CLI `_REGISTRY`.

**Tech Stack:** Python stdlib only (`urllib`, `zipfile`, `csv`, `json`), pytest, existing `sports_skills._espn_base` / `sports_skills._response` helpers.

**Spec:** `docs/superpowers/specs/2026-06-03-cricket-data-design.md`

**Verified facts the code below relies on (probed 2026-06-03):**
- `https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket` → `{"sports": [{"leagues": [{"id", "name", "abbreviation", "events": [...]}]}]}`
- `https://site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/scoreboard` → keys `leagues, teams, standings, events, provider`; competitor has `team`, `score` (string like `"161/5 (18/20 ov, target 156)"`), `linescores` (per-innings `runs/wickets/overs`), `winner`; `standings` is a list of `{"team": {...}, "stats": [{"name": "rank"|"matchPoints", "value", "displayValue"}]}`
- `.../summary?event={id}` → keys `notes, gameInfo, debuts, rosters, matchcards, leaders, article, videos, news, header, standings`
- `.../cricket/{seriesId}/news` → `{"header", "articles": [...]}`
- Cricsheet zips: `https://cricsheet.org/downloads/{code}_json.zip` — all 16 codes below returned HTTP 200
- Cricsheet registry: `https://cricsheet.org/register/people.csv` — header starts `identifier,name,unique_name,...,key_cricinfo,...`
- Cricsheet match JSON: `{"meta": {...}, "info": {teams, players, dates, season, venue, city, gender, match_type, event, outcome, registry}, "innings": [{"team", "overs": [{"over": N, "deliveries": [{batter, bowler, non_striker, runs: {batter, extras, total, non_boundary?}, extras?: {wides?, noballs?, byes?, legbyes?, penalty?}, wickets?: [{kind, player_out, fielders?}]}]}]}]}`

**Cricket aggregation rules (used in Task 5 — these are the standard conventions):**
- Batting balls faced: every delivery EXCEPT wides (no-balls ARE faced). Runs = `runs.batter`. Fours/sixes: `runs.batter == 4|6` and `runs.non_boundary` is falsy. Strike rate = runs/balls×100.
- Bowling balls: every delivery EXCEPT wides and no-balls. Runs conceded = `runs.batter` + wides + no-balls (byes/leg-byes/penalty NOT charged to bowler). Wickets credited only for kinds: bowled, caught, lbw, stumped, hit wicket, caught and bowled. Economy = runs/(balls/6).

---

### Task 0: Feature branch

**Files:** none

- [ ] **Step 1: Create branch**

```bash
git checkout -b feat/cricket-data
```

---

### Task 1: Cricsheet competitions map + `get_competitions`

**Files:**
- Create: `src/sports_skills/cricket/__init__.py` (placeholder, finalized in Task 10)
- Create: `src/sports_skills/cricket/_cricsheet.py`
- Create: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cricket.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sports_skills.cricket'`

- [ ] **Step 3: Write minimal implementation**

Create `src/sports_skills/cricket/__init__.py` (placeholder for now):

```python
"""Cricket data — live-ish via ESPN public API, historical ball-by-ball via Cricsheet.org."""
```

Create `src/sports_skills/cricket/_cricsheet.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/ tests/test_cricket.py
git commit -m "feat(cricket): add cricsheet competitions map and get_competitions"
```

---

### Task 2: Cricsheet download/cache layer

**Files:**
- Modify: `src/sports_skills/cricket/_cricsheet.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
# ── cache layer ─────────────────────────────────────────────


class TestFetchFile:
    def test_downloads_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        calls = []

        def fake_download(url, dest):
            calls.append(url)
            with open(dest, "wb") as f:
                f.write(b"payload")

        monkeypatch.setattr(_cricsheet, "_download", fake_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"payload"
        assert calls == ["http://x/file.zip"]

    def test_serves_cached_within_ttl(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        (tmp_path / "file.zip").write_bytes(b"cached")

        def fail_download(url, dest):
            raise AssertionError("should not download")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=3600)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"cached"

    def test_serves_stale_on_download_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        stale_file = tmp_path / "file.zip"
        stale_file.write_bytes(b"old")
        old = time.time() - 100_000
        os.utime(stale_file, (old, old))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is True
        assert open(path, "rb").read() == b"old"

    def test_error_when_no_cache_and_download_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert path is None
        assert err["error"] is True
        assert "network down" in err["message"]
```

Add to the imports at the top of `tests/test_cricket.py`:

```python
import os
import time
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestFetchFile -v`
Expected: FAIL with `AttributeError: module ... has no attribute '_cache_dir'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_cricsheet.py`:

```python
_ZIP_TTL = 24 * 3600          # competition zips: 24h
_REGISTRY_TTL = 7 * 24 * 3600  # player registry: 7 days


def _cache_dir():
    """Return (and create) the on-disk cache directory."""
    base = os.environ.get(
        "XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")
    )
    path = os.path.join(base, "sports-skills", "cricsheet")
    os.makedirs(path, exist_ok=True)
    return path


def _download(url, dest):
    """Download url to dest atomically (write to .tmp, then rename)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    tmp = dest + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


def _fetch_file(url, filename, ttl):
    """Return a local path to a cached copy of url, downloading if missing/expired.

    Returns (path, stale, error): on download failure with a stale copy
    present, serves the stale copy with stale=True instead of erroring.
    """
    path = os.path.join(_cache_dir(), filename)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl:
        return path, False, None
    try:
        _download(url, path)
        return path, False, None
    except Exception as e:  # noqa: BLE001 — any failure falls back to stale/error
        if os.path.exists(path):
            logger.warning("cricsheet download failed, serving stale %s: %s", filename, e)
            return path, True, None
        return None, False, {"error": True, "message": f"Cricsheet download failed: {e}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_cricsheet.py tests/test_cricket.py
git commit -m "feat(cricket): add cricsheet download/cache layer with stale fallback"
```

---

### Task 3: `get_matches` (+ shared test fixture zip)

**Files:**
- Modify: `src/sports_skills/cricket/_cricsheet.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the fixture builder and failing tests**

Append to `tests/test_cricket.py`. The fixture builds a competition zip **in memory** — no binary files in the repo. It is reused by Tasks 4 and 5, so field values matter: keep them exactly as written.

```python
# ── cricsheet fixture ───────────────────────────────────────

MATCH_1 = {
    "meta": {"data_version": "1.0.0", "created": "2024-05-01", "revision": 1},
    "info": {
        "city": "Mumbai",
        "dates": ["2024-04-01"],
        "event": {"name": "Indian Premier League", "match_number": 1},
        "gender": "male",
        "match_type": "T20",
        "outcome": {"winner": "Team A", "by": {"runs": 10}},
        "players": {"Team A": ["A One", "A Two"], "Team B": ["B One", "B Two"]},
        "registry": {"people": {"A One": "aaa111"}},
        "season": "2024",
        "teams": ["Team A", "Team B"],
        "toss": {"decision": "bat", "winner": "Team A"},
        "venue": "Wankhede Stadium",
    },
    "innings": [
        {
            "team": "Team A",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        # legal ball, boundary four
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 4, "extras": 0, "total": 4}},
                        # wide — not faced by batter, charged to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 1, "total": 1},
                         "extras": {"wides": 1}},
                        # six
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 6, "extras": 0, "total": 6}},
                        # leg byes — faced, NOT charged to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 1, "total": 1},
                         "extras": {"legbyes": 1}},
                        # bowled — credited to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 0, "total": 0},
                         "wickets": [{"kind": "bowled", "player_out": "A One"}]},
                    ],
                }
            ],
        },
        {
            "team": "Team B",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        # run out — NOT credited to bowler
                        {"batter": "B One", "bowler": "A Two", "non_striker": "B Two",
                         "runs": {"batter": 1, "extras": 0, "total": 1},
                         "wickets": [{"kind": "run out", "player_out": "B One"}]},
                    ],
                }
            ],
        },
    ],
}

MATCH_2 = {
    "meta": {"data_version": "1.0.0", "created": "2023-05-01", "revision": 1},
    "info": {
        "city": "Chennai",
        "dates": ["2023-04-05"],
        "event": {"name": "Indian Premier League", "match_number": 7},
        "gender": "male",
        "match_type": "T20",
        "outcome": {"winner": "Team B", "by": {"wickets": 5}},
        "players": {"Team A": ["A One", "A Two"], "Team B": ["B One", "B Two"]},
        "registry": {"people": {}},
        "season": "2023",
        "teams": ["Team A", "Team B"],
        "toss": {"decision": "field", "winner": "Team B"},
        "venue": "Chepauk",
    },
    "innings": [
        {
            "team": "Team A",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        {"batter": "A One", "bowler": "B Two", "non_striker": "A Two",
                         "runs": {"batter": 1, "extras": 0, "total": 1}},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def fixture_zip(tmp_path, monkeypatch):
    """Build an in-memory ipl_json.zip in a temp cache dir; block real downloads."""
    monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1001.json", json.dumps(MATCH_1))
        zf.writestr("1002.json", json.dumps(MATCH_2))
        zf.writestr("README.txt", "not a match")
    (tmp_path / "ipl_json.zip").write_bytes(buf.getvalue())

    def fail_download(url, dest):
        raise AssertionError("tests must not hit the network")

    monkeypatch.setattr(_cricsheet, "_download", fail_download)
    return tmp_path


# ── get_matches ─────────────────────────────────────────────


class TestGetMatches:
    def test_lists_matches_newest_first(self, fixture_zip):
        result = _cricsheet.get_matches({"params": {"competition": "ipl"}})
        assert result["count"] == 2
        assert [m["match_id"] for m in result["matches"]] == ["1001", "1002"]
        m = result["matches"][0]
        assert m["teams"] == ["Team A", "Team B"]
        assert m["winner"] == "Team A"
        assert m["venue"] == "Wankhede Stadium"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_season_filter(self, fixture_zip):
        result = _cricsheet.get_matches({"params": {"competition": "ipl", "season": 2023}})
        assert result["count"] == 1
        assert result["matches"][0]["match_id"] == "1002"

    def test_unknown_competition_errors(self):
        result = _cricsheet.get_matches({"params": {"competition": "nope"}})
        assert result["error"] is True
        assert "nope" in result["message"]

    def test_missing_competition_errors(self):
        result = _cricsheet.get_matches({"params": {}})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetMatches -v`
Expected: FAIL with `AttributeError: ... no attribute 'get_matches'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_cricsheet.py`:

```python
def _validate_competition(code):
    """Return normalized competition code or error dict."""
    if not code:
        return None, {
            "error": True,
            "message": "competition is required — see get_competitions for codes",
        }
    c = str(code).lower().strip()
    if c not in _COMPETITIONS:
        return None, {
            "error": True,
            "message": f"Unknown competition '{code}'. Valid: {', '.join(sorted(_COMPETITIONS))}",
        }
    return c, None


def _open_competition(code):
    """Return (ZipFile, stale, error) for a competition's cached zip."""
    url = f"https://cricsheet.org/downloads/{code}_json.zip"
    path, stale, err = _fetch_file(url, f"{code}_json.zip", _ZIP_TTL)
    if err:
        return None, False, err
    return zipfile.ZipFile(path), stale, None


def _season_matches(season_value, season_filter):
    """Prefix match so --season=2020 matches Cricsheet's '2020/21'."""
    if season_filter is None:
        return True
    return str(season_value).startswith(str(season_filter))


def _match_summary(name, info):
    """Build a one-line match summary from a Cricsheet info block."""
    outcome = info.get("outcome", {})
    return {
        "match_id": name[:-5],
        "date": (info.get("dates") or [""])[0],
        "teams": info.get("teams", []),
        "venue": info.get("venue", ""),
        "city": info.get("city", ""),
        "season": str(info.get("season", "")),
        "match_type": info.get("match_type", ""),
        "gender": info.get("gender", ""),
        "event": info.get("event", {}).get("name", ""),
        "winner": outcome.get("winner", outcome.get("result", "")),
        "outcome": outcome,
    }


def get_matches(request_data):
    """List completed matches for a Cricsheet competition, newest first."""
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    season = params.get("season")
    zf, stale, err = _open_competition(code)
    if err:
        return err
    matches = []
    with zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as f:
                data = json.load(f)
            info = data.get("info", {})
            if not _season_matches(info.get("season", ""), season):
                continue
            matches.append(_match_summary(name, info))
    matches.sort(key=lambda m: m["date"], reverse=True)
    result = {
        "competition": code,
        "matches": matches,
        "count": len(matches),
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_cricsheet.py tests/test_cricket.py
git commit -m "feat(cricket): add get_matches with season filtering"
```

---

### Task 4: `get_match_deliveries`

**Files:**
- Modify: `src/sports_skills/cricket/_cricsheet.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
# ── get_match_deliveries ────────────────────────────────────


class TestGetMatchDeliveries:
    def test_returns_all_innings(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "1001"}}
        )
        assert result["match"]["match_id"] == "1001"
        assert len(result["innings"]) == 2
        first = result["innings"][0]
        assert first["innings"] == 1
        assert first["team"] == "Team A"
        assert first["count"] == 5
        d0 = first["deliveries"][0]
        assert d0 == {
            "over": 0, "ball": 1, "batter": "A One", "bowler": "B One",
            "non_striker": "A Two", "runs": {"batter": 4, "extras": 0, "total": 4},
        }
        # wide carries its extras dict; wicket ball carries its wickets list
        assert first["deliveries"][1]["extras"] == {"wides": 1}
        assert first["deliveries"][4]["wickets"][0]["kind"] == "bowled"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_innings_filter(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "1001", "innings": 2}}
        )
        assert len(result["innings"]) == 1
        assert result["innings"][0]["team"] == "Team B"

    def test_match_not_found(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "9999"}}
        )
        assert result["error"] is True
        assert "9999" in result["message"]

    def test_missing_match_id(self, fixture_zip):
        result = _cricsheet.get_match_deliveries({"params": {"competition": "ipl"}})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetMatchDeliveries -v`
Expected: FAIL with `AttributeError: ... no attribute 'get_match_deliveries'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_cricsheet.py`:

```python
def get_match_deliveries(request_data):
    """Ball-by-ball deliveries for one match, optionally one innings."""
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    match_id = params.get("match_id")
    if not match_id:
        return {"error": True, "message": "match_id is required — see get_matches"}
    innings_filter = params.get("innings")
    zf, stale, err = _open_competition(code)
    if err:
        return err
    filename = f"{match_id}.json"
    with zf:
        if filename not in zf.namelist():
            return {
                "error": True,
                "message": f"Match '{match_id}' not found in competition '{code}'",
            }
        with zf.open(filename) as f:
            data = json.load(f)
    info = data.get("info", {})
    innings_out = []
    for idx, inn in enumerate(data.get("innings", []), start=1):
        if innings_filter is not None and idx != int(innings_filter):
            continue
        deliveries = []
        for over in inn.get("overs", []):
            over_num = over.get("over", 0)
            for ball_idx, d in enumerate(over.get("deliveries", []), start=1):
                entry = {
                    "over": over_num,
                    "ball": ball_idx,
                    "batter": d.get("batter", ""),
                    "bowler": d.get("bowler", ""),
                    "non_striker": d.get("non_striker", ""),
                    "runs": d.get("runs", {}),
                }
                if d.get("extras"):
                    entry["extras"] = d["extras"]
                if d.get("wickets"):
                    entry["wickets"] = d["wickets"]
                deliveries.append(entry)
        innings_out.append({
            "innings": idx,
            "team": inn.get("team", ""),
            "deliveries": deliveries,
            "count": len(deliveries),
        })
    result = {
        "match": _match_summary(filename, info),
        "innings": innings_out,
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_cricsheet.py tests/test_cricket.py
git commit -m "feat(cricket): add get_match_deliveries with innings filter"
```

---

### Task 5: `get_player_stats` aggregation

**Files:**
- Modify: `src/sports_skills/cricket/_cricsheet.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

These assertions encode the cricket conventions from the plan header. Trace them against `MATCH_1`/`MATCH_2`: "A One" faces 4 legal balls + 1 wide in match 1 (balls faced = 4: the four, the six, the leg-bye ball, the bowled ball — wide excluded) and 1 ball in match 2; runs 4+6+0+0 = 10 in match 1, 1 in match 2. "B One" bowls 5 deliveries in match 1, of which 4 are legal (wide excluded); concedes 4+6+0(legbye not charged)+0 + 1 wide = 11; takes 1 wicket (bowled). "A Two" bowls 1 ball with a run out — 0 wickets credited.

Append to `tests/test_cricket.py`:

```python
# ── get_player_stats ────────────────────────────────────────


class TestGetPlayerStats:
    def test_batting_aggregation(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A One"}}
        )
        bat = result["batting"]
        assert result["player"] == "A One"
        assert result["matches"] == 2
        assert bat["runs"] == 11        # 4+6 in match 1, 1 in match 2
        assert bat["balls"] == 5        # wide not faced
        assert bat["fours"] == 1
        assert bat["sixes"] == 1
        assert bat["dismissals"] == 1   # bowled in match 1
        assert bat["strike_rate"] == round(11 / 5 * 100, 2)
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_bowling_aggregation(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "B One"}}
        )
        bowl = result["bowling"]
        assert bowl["balls"] == 4           # wide doesn't count as a ball bowled
        assert bowl["runs_conceded"] == 11  # 4+6+wide(1); leg-bye not charged
        assert bowl["wickets"] == 1         # bowled credited
        assert bowl["economy"] == round(11 / (4 / 6), 2)

    def test_run_out_not_credited_to_bowler(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A Two"}}
        )
        assert result["bowling"]["wickets"] == 0

    def test_season_filter(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A One", "season": 2023}}
        )
        assert result["matches"] == 1
        assert result["batting"]["runs"] == 1

    def test_unknown_player_errors(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "Nobody"}}
        )
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetPlayerStats -v`
Expected: FAIL with `AttributeError: ... no attribute 'get_player_stats'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_cricsheet.py`:

```python
# Dismissal kinds credited to the bowler (standard convention)
_BOWLER_CREDITED = {"bowled", "caught", "lbw", "stumped", "hit wicket", "caught and bowled"}


def get_player_stats(request_data):
    """Aggregate batting and bowling stats for a player across a competition.

    Conventions: batting balls faced exclude wides (no-balls faced);
    bowling balls exclude wides and no-balls; bowler concedes batter runs
    + wides + no-balls (not byes/leg-byes/penalty); run outs etc. are not
    credited to the bowler.
    """
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    player = params.get("player")
    if not player:
        return {"error": True, "message": "player is required — exact name as in Cricsheet (see find_player)"}
    season = params.get("season")
    zf, stale, err = _open_competition(code)
    if err:
        return err

    matches_played = 0
    bat = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissals": 0}
    bowl = {"balls": 0, "runs_conceded": 0, "wickets": 0}

    with zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as f:
                data = json.load(f)
            info = data.get("info", {})
            if not _season_matches(info.get("season", ""), season):
                continue
            all_players = [p for team in info.get("players", {}).values() for p in team]
            if player not in all_players:
                continue
            matches_played += 1
            for inn in data.get("innings", []):
                for over in inn.get("overs", []):
                    for d in over.get("deliveries", []):
                        runs = d.get("runs", {})
                        extras = d.get("extras", {})
                        wides = extras.get("wides", 0)
                        noballs = extras.get("noballs", 0)
                        if d.get("batter") == player:
                            if not wides:
                                bat["balls"] += 1
                            batter_runs = runs.get("batter", 0)
                            bat["runs"] += batter_runs
                            if not runs.get("non_boundary"):
                                if batter_runs == 4:
                                    bat["fours"] += 1
                                elif batter_runs == 6:
                                    bat["sixes"] += 1
                        if d.get("bowler") == player:
                            if not wides and not noballs:
                                bowl["balls"] += 1
                            bowl["runs_conceded"] += runs.get("batter", 0) + wides + noballs
                            for w in d.get("wickets", []):
                                if w.get("kind") in _BOWLER_CREDITED:
                                    bowl["wickets"] += 1
                        for w in d.get("wickets", []):
                            if w.get("player_out") == player:
                                bat["dismissals"] += 1

    if matches_played == 0:
        return {
            "error": True,
            "message": f"No matches found for player '{player}' in '{code}'"
            + (f" season {season}" if season else "")
            + " — names must match Cricsheet exactly (see find_player)",
        }

    bat["strike_rate"] = round(bat["runs"] / bat["balls"] * 100, 2) if bat["balls"] else 0.0
    bat["average"] = round(bat["runs"] / bat["dismissals"], 2) if bat["dismissals"] else None
    bowl["economy"] = round(bowl["runs_conceded"] / (bowl["balls"] / 6), 2) if bowl["balls"] else None
    bowl["overs"] = f"{bowl['balls'] // 6}.{bowl['balls'] % 6}"

    result = {
        "player": player,
        "competition": code,
        "season": season,
        "matches": matches_played,
        "batting": bat,
        "bowling": bowl,
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_cricsheet.py tests/test_cricket.py
git commit -m "feat(cricket): add get_player_stats with cricket-correct aggregation"
```

---

### Task 6: `find_player` (registry lookup)

**Files:**
- Modify: `src/sports_skills/cricket/_cricsheet.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
# ── find_player ─────────────────────────────────────────────

PEOPLE_CSV = (
    "identifier,name,unique_name,key_bcci,key_bcci_2,key_bigbash,key_cricbuzz,"
    "key_cricheroes,key_crichq,key_cricinfo,key_cricinfo_2,key_cricinfo_3,"
    "key_cricingif,key_cricketarchive,key_cricketarchive_2,key_cricketworld,"
    "key_nvplay,key_nvplay_2,key_opta,key_opta_2,key_pulse,key_pulse_2\n"
    "ba607b88,V Kohli,V Kohli,,,,,,,253802,,,,,,,,,,,,\n"
    "abc123,RG Sharma,RG Sharma,,,,,,,34102,,,,,,,,,,,,\n"
)


class TestFindPlayer:
    def test_finds_by_substring_case_insensitive(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        (tmp_path / "people.csv").write_text(PEOPLE_CSV)
        monkeypatch.setattr(
            _cricsheet, "_download",
            lambda url, dest: (_ for _ in ()).throw(AssertionError("no network")),
        )
        result = _cricsheet.find_player({"params": {"name": "kohli"}})
        assert result["count"] == 1
        p = result["players"][0]
        assert p["cricsheet_id"] == "ba607b88"
        assert p["name"] == "V Kohli"
        assert p["cricinfo_id"] == "253802"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_missing_name_errors(self):
        result = _cricsheet.find_player({"params": {}})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestFindPlayer -v`
Expected: FAIL with `AttributeError: ... no attribute 'find_player'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_cricsheet.py`:

```python
_REGISTRY_URL = "https://cricsheet.org/register/people.csv"
_MAX_PLAYER_RESULTS = 25


def find_player(request_data):
    """Search the Cricsheet player registry by name substring.

    Returns Cricsheet IDs plus the ESPNcricinfo ID mapping (key_cricinfo),
    which bridges Cricsheet data to ESPN match data.
    """
    params = request_data.get("params", {})
    name = params.get("name")
    if not name:
        return {"error": True, "message": "name is required"}
    path, stale, err = _fetch_file(_REGISTRY_URL, "people.csv", _REGISTRY_TTL)
    if err:
        return err
    needle = str(name).lower().strip()
    players = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            haystack = f"{row.get('name', '')} {row.get('unique_name', '')}".lower()
            if needle in haystack:
                players.append({
                    "cricsheet_id": row.get("identifier", ""),
                    "name": row.get("name", ""),
                    "unique_name": row.get("unique_name", ""),
                    "cricinfo_id": row.get("key_cricinfo", ""),
                })
                if len(players) >= _MAX_PLAYER_RESULTS:
                    break
    result = {"players": players, "count": len(players), "attribution": _ATTRIBUTION}
    if stale:
        result["stale"] = True
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_cricsheet.py tests/test_cricket.py
git commit -m "feat(cricket): add find_player registry lookup with cricinfo ID mapping"
```

---

### Task 7: ESPN backend — `get_series`

**Files:**
- Create: `src/sports_skills/cricket/_espn.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
from sports_skills.cricket import _espn

# ── ESPN backend fixtures (shapes captured live 2026-06-03) ─

HEADER_PAYLOAD = {
    "sports": [{
        "id": "200", "name": "Cricket", "slug": "cricket",
        "leagues": [
            {"id": "8048", "name": "Indian Premier League", "abbreviation": "IPL",
             "isTournament": False,
             "events": [{"id": "1535465", "date": "2026-05-31T14:00Z",
                         "name": "Royal Challengers Bengaluru v Gujarat Titans",
                         "status": "post", "summary": "RCB won"}]},
            {"id": "24423", "name": "Sri Lanka tour of West Indies 2026",
             "abbreviation": "SL@WI", "isTournament": False, "events": []},
        ],
    }]
}


class TestGetSeries:
    def test_lists_active_series(self, monkeypatch):
        monkeypatch.setattr(_espn, "_header_request", lambda: HEADER_PAYLOAD)
        result = _espn.get_series({})
        assert result["count"] == 2
        s = result["series"][0]
        assert s["series_id"] == "8048"
        assert s["name"] == "Indian Premier League"
        assert s["abbreviation"] == "IPL"
        assert s["event_count"] == 1
        assert s["events"][0]["event_id"] == "1535465"

    def test_propagates_fetch_error(self, monkeypatch):
        monkeypatch.setattr(
            _espn, "_header_request",
            lambda: {"error": True, "message": "HTTP 503"},
        )
        result = _espn.get_series({})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetSeries -v`
Expected: FAIL with `ImportError: cannot import name '_espn'`

- [ ] **Step 3: Write the implementation**

Create `src/sports_skills/cricket/_espn.py`:

```python
"""Cricket live-ish data connector — ESPN public site API.

Cricket on ESPN has no single league: each series/competition has a
numeric ID used in the league slot of the URL (e.g. 8048 = IPL).
Discover active series IDs with get_series().
"""

import json
import logging
import urllib.parse

from sports_skills._espn_base import (
    _USER_AGENT,
    _cache_get,
    _cache_set,
    _espn_rate_limiter,
    _http_fetch,
    espn_request,
    espn_summary,
)

logger = logging.getLogger("sports_skills.cricket")

_HEADER_URL = "https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header"


def _validate_series_id(series_id):
    """Return normalized series_id string or error dict."""
    if not series_id:
        return None, {
            "error": True,
            "message": "series_id is required — discover active series IDs with get_series",
        }
    return str(series_id).strip(), None


def _header_request():
    """Fetch the cricket scoreboard header (active series). Cached 120s."""
    cache_key = "espn:cricket:header"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = _HEADER_URL + "?" + urllib.parse.urlencode({"sport": "cricket"})
    raw, err = _http_fetch(
        url, headers={"User-Agent": _USER_AGENT}, rate_limiter=_espn_rate_limiter
    )
    if err:
        return err
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN returned invalid JSON"}
    _cache_set(cache_key, data, ttl=120)
    return data


def get_series(request_data):
    """List currently-active cricket series with their ESPN series IDs."""
    data = _header_request()
    if data.get("error"):
        return data
    sports = data.get("sports", [])
    leagues = sports[0].get("leagues", []) if sports else []
    series = []
    for lg in leagues:
        events = lg.get("events", [])
        series.append({
            "series_id": str(lg.get("id", "")),
            "name": lg.get("name", ""),
            "abbreviation": lg.get("abbreviation", ""),
            "is_tournament": lg.get("isTournament", False),
            "event_count": len(events),
            "events": [
                {
                    "event_id": str(e.get("id", "")),
                    "name": e.get("name", ""),
                    "date": e.get("date", ""),
                    "status": e.get("status", ""),
                    "summary": e.get("summary", ""),
                }
                for e in events
            ],
        })
    return {"series": series, "count": len(series)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_espn.py tests/test_cricket.py
git commit -m "feat(cricket): add ESPN get_series active-series discovery"
```

---

### Task 8: ESPN backend — `get_scoreboard` + `get_standings`

**Files:**
- Modify: `src/sports_skills/cricket/_espn.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
SCOREBOARD_PAYLOAD = {
    "leagues": [{"id": "8048", "name": "Indian Premier League", "abbreviation": "IPL"}],
    "standings": [
        {"team": {"id": "335970", "displayName": "Royal Challengers Bengaluru",
                  "abbreviation": "RCB"},
         "stats": [
             {"name": "rank", "value": 1, "displayValue": "1"},
             {"name": "matchPoints", "value": 18, "displayValue": "18"},
         ]},
    ],
    "events": [{
        "id": "1535465",
        "date": "2026-05-31T14:00Z",
        "name": "Royal Challengers Bengaluru v Gujarat Titans",
        "shortName": "RCB v GT",
        "competitions": [{
            "id": "1535465",
            "description": "Final",
            "venue": {"fullName": "Narendra Modi Stadium"},
            "status": {"type": {"name": "STATUS_FINAL", "shortDetail": "RCB won"},
                       "period": 2},
            "notes": [],
            "competitors": [
                {"homeAway": "home", "winner": True,
                 "team": {"id": "335970", "displayName": "Royal Challengers Bengaluru",
                          "abbreviation": "RCB"},
                 "score": "161/5 (18/20 ov, target 156)",
                 "linescores": [{"period": 2, "runs": 161, "wickets": 5, "overs": 18.0,
                                 "isBatting": True, "description": "target reached"}]},
                {"homeAway": "away", "winner": False,
                 "team": {"id": "335974", "displayName": "Gujarat Titans",
                          "abbreviation": "GT"},
                 "score": "155/9 (20 ov)",
                 "linescores": [{"period": 1, "runs": 155, "wickets": 9, "overs": 20.0,
                                 "isBatting": False, "description": "complete"}]},
            ],
        }],
    }],
}


class TestGetScoreboard:
    def test_normalizes_events(self, monkeypatch):
        captured = {}

        def fake_espn_request(sport_path, resource="scoreboard", params=None, **kw):
            captured["sport_path"] = sport_path
            captured["params"] = params
            return SCOREBOARD_PAYLOAD

        monkeypatch.setattr(_espn, "espn_request", fake_espn_request)
        result = _espn.get_scoreboard({"params": {"series_id": "8048", "date": "2026-05-31"}})
        assert captured["sport_path"] == "cricket/8048"
        assert captured["params"] == {"dates": "20260531"}
        assert result["series"]["name"] == "Indian Premier League"
        ev = result["events"][0]
        assert ev["event_id"] == "1535465"
        assert ev["status"] == "closed"
        assert ev["venue"] == "Narendra Modi Stadium"
        home = ev["competitors"][0]
        assert home["team"] == "Royal Challengers Bengaluru"
        assert home["score"] == "161/5 (18/20 ov, target 156)"
        assert home["winner"] is True
        assert home["innings"][0]["runs"] == 161

    def test_requires_series_id(self):
        result = _espn.get_scoreboard({"params": {}})
        assert result["error"] is True


class TestGetStandings:
    def test_extracts_standings_from_scoreboard(self, monkeypatch):
        monkeypatch.setattr(
            _espn, "espn_request",
            lambda sport_path, resource="scoreboard", params=None, **kw: SCOREBOARD_PAYLOAD,
        )
        result = _espn.get_standings({"params": {"series_id": "8048"}})
        row = result["standings"][0]
        assert row["team"] == "Royal Challengers Bengaluru"
        assert row["abbreviation"] == "RCB"
        assert row["stats"]["rank"] == 1
        assert row["stats"]["matchPoints"] == 18

    def test_requires_series_id(self):
        result = _espn.get_standings({"params": {}})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetScoreboard tests/test_cricket.py::TestGetStandings -v`
Expected: FAIL with `AttributeError: ... no attribute 'get_scoreboard'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_espn.py`. Note: cricket statuses use the shared `ESPN_STATUS_MAP`; add the import `ESPN_STATUS_MAP` to the existing `from sports_skills._espn_base import (...)` block.

```python
def _normalize_competitor(comp):
    """Normalize a cricket competitor (a team with innings linescores)."""
    team = comp.get("team", {})
    return {
        "team_id": str(team.get("id", "")),
        "team": team.get("displayName", ""),
        "abbreviation": team.get("abbreviation", ""),
        "home_away": comp.get("homeAway", ""),
        "winner": comp.get("winner", False),
        "score": comp.get("score", ""),
        "innings": [
            {
                "innings": ls.get("period", 0),
                "runs": ls.get("runs", 0),
                "wickets": ls.get("wickets", 0),
                "overs": ls.get("overs", 0),
                "is_batting": ls.get("isBatting", False),
                "description": ls.get("description", ""),
            }
            for ls in comp.get("linescores", [])
        ],
    }


def _normalize_event(event):
    """Normalize one scoreboard event (a cricket match)."""
    competitions = event.get("competitions", [])
    comp = competitions[0] if competitions else {}
    status_type = comp.get("status", {}).get("type", {})
    venue = comp.get("venue", {})
    notes = comp.get("notes", [])
    return {
        "event_id": str(event.get("id", "")),
        "name": event.get("name", ""),
        "short_name": event.get("shortName", ""),
        "date": event.get("date", ""),
        "description": comp.get("description", ""),
        "status": ESPN_STATUS_MAP.get(status_type.get("name", ""), status_type.get("name", "")),
        "status_detail": status_type.get("shortDetail", status_type.get("detail", "")),
        "venue": venue.get("fullName", venue.get("displayName", "")),
        "note": notes[0].get("text", "") if notes else "",
        "competitors": [_normalize_competitor(c) for c in comp.get("competitors", [])],
    }


def _fetch_scoreboard(series_id, date=None):
    """Fetch the raw scoreboard payload for a series."""
    espn_params = {}
    if date:
        espn_params["dates"] = str(date).replace("-", "")
    return espn_request(f"cricket/{series_id}", "scoreboard", espn_params or None)


def get_scoreboard(request_data):
    """Scoreboard (events + scores) for one series. Use get_series for IDs."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = _fetch_scoreboard(series_id, params.get("date"))
    if data.get("error"):
        return data
    leagues = data.get("leagues", [])
    league = leagues[0] if leagues else {}
    events = [_normalize_event(e) for e in data.get("events", [])]
    return {
        "series": {
            "series_id": series_id,
            "name": league.get("name", ""),
            "abbreviation": league.get("abbreviation", ""),
        },
        "events": events,
        "count": len(events),
    }


def get_standings(request_data):
    """Points table for a series, extracted from the scoreboard payload."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = _fetch_scoreboard(series_id)
    if data.get("error"):
        return data
    standings = []
    for row in data.get("standings", []):
        team = row.get("team", {})
        standings.append({
            "team_id": str(team.get("id", "")),
            "team": team.get("displayName", ""),
            "abbreviation": team.get("abbreviation", ""),
            "stats": {s.get("name", ""): s.get("value") for s in row.get("stats", [])},
        })
    if not standings:
        return {
            "series_id": series_id,
            "standings": [],
            "count": 0,
            "message": "No standings published for this series (common for bilateral tours)",
        }
    return {"series_id": series_id, "standings": standings, "count": len(standings)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_espn.py tests/test_cricket.py
git commit -m "feat(cricket): add ESPN get_scoreboard and get_standings"
```

---

### Task 9: ESPN backend — `get_game_summary` + `get_news`

**Files:**
- Modify: `src/sports_skills/cricket/_espn.py`
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
SUMMARY_PAYLOAD = {
    "notes": [{"text": "Final"}],
    "gameInfo": {"venue": {"fullName": "Narendra Modi Stadium"}},
    "rosters": [{"team": {"displayName": "RCB"}}],
    "leaders": [{"team": {"displayName": "RCB"}, "leaders": []}],
    "matchcards": {"cards": []},
    "header": {"id": "1535465"},
    "article": {"headline": "RCB win"},
    "videos": [],
    "news": {},
    "standings": [],
    "debuts": [],
    "wallclockAvailable": False,
    "meta": {},
}

NEWS_PAYLOAD = {
    "header": "IPL News",
    "articles": [
        {"headline": "Stokes wants deeds, not words",
         "description": "Captain prepares to move to No.7",
         "published": "2026-06-02T10:00Z",
         "type": "Story",
         "links": {"web": {"href": "https://www.espncricinfo.com/story/x"}}},
    ],
}


class TestGetGameSummary:
    def test_returns_trimmed_summary(self, monkeypatch):
        captured = {}

        def fake_summary(sport_path, event_id, **kw):
            captured["sport_path"] = sport_path
            captured["event_id"] = event_id
            return SUMMARY_PAYLOAD

        monkeypatch.setattr(_espn, "espn_summary", fake_summary)
        result = _espn.get_game_summary(
            {"params": {"series_id": "8048", "event_id": "1535465"}}
        )
        assert captured["sport_path"] == "cricket/8048"
        assert captured["event_id"] == "1535465"
        assert result["game_info"]["venue"]["fullName"] == "Narendra Modi Stadium"
        assert result["rosters"] == SUMMARY_PAYLOAD["rosters"]
        assert result["leaders"] == SUMMARY_PAYLOAD["leaders"]
        assert result["notes"] == [{"text": "Final"}]
        # noisy keys are dropped
        assert "videos" not in result
        assert "meta" not in result

    def test_requires_event_id(self):
        result = _espn.get_game_summary({"params": {"series_id": "8048"}})
        assert result["error"] is True


class TestGetNews:
    def test_normalizes_articles(self, monkeypatch):
        monkeypatch.setattr(
            _espn, "espn_request",
            lambda sport_path, resource="scoreboard", params=None, **kw: NEWS_PAYLOAD,
        )
        result = _espn.get_news({"params": {"series_id": "8048"}})
        assert result["count"] == 1
        a = result["articles"][0]
        assert a["headline"] == "Stokes wants deeds, not words"
        assert a["link"] == "https://www.espncricinfo.com/story/x"

    def test_requires_series_id(self):
        result = _espn.get_news({"params": {}})
        assert result["error"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestGetGameSummary tests/test_cricket.py::TestGetNews -v`
Expected: FAIL with `AttributeError: ... no attribute 'get_game_summary'`

- [ ] **Step 3: Write the implementation**

Append to `src/sports_skills/cricket/_espn.py`:

```python
def get_game_summary(request_data):
    """Match detail: rosters, leaders, matchcards, game info, header."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required — see get_scoreboard"}
    data = espn_summary(f"cricket/{series_id}", str(event_id))
    if data is None:
        return {"error": True, "message": "ESPN summary request failed"}
    if isinstance(data, dict) and data.get("error"):
        return data
    return {
        "event_id": str(event_id),
        "series_id": series_id,
        "header": data.get("header", {}),
        "game_info": data.get("gameInfo", {}),
        "notes": data.get("notes", []),
        "rosters": data.get("rosters", []),
        "leaders": data.get("leaders", []),
        "matchcards": data.get("matchcards", {}),
        "article": data.get("article", {}),
    }


def get_news(request_data):
    """News articles for a series."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = espn_request(f"cricket/{series_id}", "news")
    if data.get("error"):
        return data
    articles = []
    for a in data.get("articles", []):
        articles.append({
            "headline": a.get("headline", ""),
            "description": a.get("description", ""),
            "published": a.get("published", ""),
            "type": a.get("type", ""),
            "link": a.get("links", {}).get("web", {}).get("href", ""),
        })
    return {"header": data.get("header", ""), "articles": articles, "count": len(articles)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/_espn.py tests/test_cricket.py
git commit -m "feat(cricket): add ESPN get_game_summary and get_news"
```

---

### Task 10: Public API (`cricket/__init__.py`)

**Files:**
- Modify: `src/sports_skills/cricket/__init__.py` (replace placeholder)
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
# ── public API envelope ─────────────────────────────────────


class TestPublicApi:
    def test_success_envelope(self):
        import sports_skills.cricket as cricket

        result = cricket.get_competitions()
        assert result["status"] is True
        assert "competitions" in result["data"]

    def test_error_envelope(self, fixture_zip):
        import sports_skills.cricket as cricket

        result = cricket.get_matches(competition="nope")
        assert result["status"] is False
        assert "nope" in result["message"]

    def test_all_ten_commands_exported(self):
        import sports_skills.cricket as cricket

        for fn in (
            "get_series", "get_scoreboard", "get_standings", "get_game_summary",
            "get_news", "get_competitions", "get_matches", "get_match_deliveries",
            "get_player_stats", "find_player",
        ):
            assert callable(getattr(cricket, fn))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestPublicApi -v`
Expected: FAIL with `AttributeError: module 'sports_skills.cricket' has no attribute 'get_competitions'`

- [ ] **Step 3: Write the implementation**

Replace the entire content of `src/sports_skills/cricket/__init__.py`. Docstrings matter: the CLI parses the Google-style `Args:` sections for `--help` output.

```python
"""Cricket data — live-ish scores via ESPN public API, historical ball-by-ball via Cricsheet.org.

ESPN backend (no API keys): active series, scoreboards, standings, match
summaries, news. Cricket has no single league on ESPN — discover numeric
series IDs with get_series().

Cricsheet backend (ODC-BY 1.0, attribution included in responses):
completed-match ball-by-ball data, player stats aggregation, and the
player registry with ESPNcricinfo ID mappings.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.cricket import _cricsheet, _espn


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


# ── ESPN backend (live-ish) ─────────────────────────────────


def get_series() -> dict:
    """List currently-active cricket series with ESPN series IDs and live events."""
    return wrap(_espn.get_series({}))


def get_scoreboard(*, series_id: str, date: str | None = None) -> dict:
    """Get scoreboard (matches + scores + status) for a series.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
        date: Date in YYYYMMDD or YYYY-MM-DD format. Defaults to current window.
    """
    return wrap(_espn.get_scoreboard(_params(series_id=series_id, date=date)))


def get_standings(*, series_id: str) -> dict:
    """Get the points table for a series. Empty for most bilateral tours.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
    """
    return wrap(_espn.get_standings(_params(series_id=series_id)))


def get_game_summary(*, series_id: str, event_id: str) -> dict:
    """Get match detail: rosters, leaders, matchcards, venue info.

    Args:
        series_id: ESPN series ID. Discover via get_series.
        event_id: ESPN event ID from get_scoreboard or get_series.
    """
    return wrap(_espn.get_game_summary(_params(series_id=series_id, event_id=event_id)))


def get_news(*, series_id: str) -> dict:
    """Get news articles for a series.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
    """
    return wrap(_espn.get_news(_params(series_id=series_id)))


# ── Cricsheet backend (historical, ODC-BY 1.0) ──────────────


def get_competitions() -> dict:
    """List Cricsheet competition codes usable with the historical commands."""
    return wrap(_cricsheet.get_competitions({}))


def get_matches(*, competition: str, season: int | None = None) -> dict:
    """List completed matches for a competition, newest first.

    Args:
        competition: Cricsheet code (e.g. "ipl", "tests"). See get_competitions.
        season: Season start year (e.g. 2024; 2020 matches "2020/21").
    """
    return wrap(_cricsheet.get_matches(_params(competition=competition, season=season)))


def get_match_deliveries(*, competition: str, match_id: str, innings: int | None = None) -> dict:
    """Get ball-by-ball deliveries for a completed match.

    Args:
        competition: Cricsheet code (e.g. "ipl"). See get_competitions.
        match_id: Cricsheet match ID from get_matches (equals the ESPNcricinfo match ID).
        innings: Restrict to one innings (1-4).
    """
    return wrap(_cricsheet.get_match_deliveries(
        _params(competition=competition, match_id=match_id, innings=innings)
    ))


def get_player_stats(*, competition: str, player: str, season: int | None = None) -> dict:
    """Aggregate batting and bowling stats for a player across a competition.

    Args:
        competition: Cricsheet code (e.g. "ipl"). See get_competitions.
        player: Exact player name as it appears in Cricsheet (see find_player).
        season: Season start year to filter by.
    """
    return wrap(_cricsheet.get_player_stats(
        _params(competition=competition, player=player, season=season)
    ))


def find_player(*, name: str) -> dict:
    """Search the Cricsheet player registry; returns ESPNcricinfo ID mappings.

    Args:
        name: Player name substring, case-insensitive (e.g. "kohli").
    """
    return wrap(_cricsheet.find_player(_params(name=name)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/sports_skills/cricket/__init__.py tests/test_cricket.py
git commit -m "feat(cricket): add public API with standard response envelope"
```

---

### Task 11: CLI registration

**Files:**
- Modify: `src/sports_skills/cli.py` — three places: `_REGISTRY` dict (after the `"tennis"` entry, ~line 364), `_INT_PARAMS` set (~line 440), module loader `elif` chain (after `elif name == "tennis"`, ~line 591), plus the two help strings (~lines 836-839)
- Test: `tests/test_cricket.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cricket.py`:

```python
# ── CLI registration ────────────────────────────────────────


class TestCliRegistration:
    def test_cricket_in_registry(self):
        from sports_skills.cli import _REGISTRY

        assert "cricket" in _REGISTRY
        cmds = _REGISTRY["cricket"]
        assert cmds["get_scoreboard"] == {"required": ["series_id"], "optional": ["date"]}
        assert cmds["get_match_deliveries"] == {
            "required": ["competition", "match_id"], "optional": ["innings"],
        }
        assert set(cmds) == {
            "get_series", "get_scoreboard", "get_standings", "get_game_summary",
            "get_news", "get_competitions", "get_matches", "get_match_deliveries",
            "get_player_stats", "find_player",
        }

    def test_innings_parses_as_int(self):
        from sports_skills.cli import _parse_value

        assert _parse_value("innings", "2") == 2

    def test_module_loader_resolves_cricket(self):
        from sports_skills.cli import _load_module

        mod = _load_module("cricket")
        assert callable(mod.get_series)
```

Note: if the loader function is not named `_load_module`, check `src/sports_skills/cli.py` around line 540 for the actual name (the function containing `elif name == "tennis":`) and use that name in the test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cricket.py::TestCliRegistration -v`
Expected: FAIL with `KeyError: 'cricket'` (or AssertionError on `"cricket" in _REGISTRY`)

- [ ] **Step 3: Write the implementation**

In `src/sports_skills/cli.py`:

(a) Add to `_REGISTRY` immediately after the `"tennis"` entry:

```python
    "cricket": {
        "get_series": {},
        "get_scoreboard": {"required": ["series_id"], "optional": ["date"]},
        "get_standings": {"required": ["series_id"]},
        "get_game_summary": {"required": ["series_id", "event_id"]},
        "get_news": {"required": ["series_id"]},
        "get_competitions": {},
        "get_matches": {"required": ["competition"], "optional": ["season"]},
        "get_match_deliveries": {"required": ["competition", "match_id"], "optional": ["innings"]},
        "get_player_stats": {"required": ["competition", "player"], "optional": ["season"]},
        "find_player": {"required": ["name"]},
    },
```

(b) Add `"innings",` to the `_INT_PARAMS` set.

(c) Add to the module loader `elif` chain, after the tennis branch:

```python
    elif name == "cricket":
        from sports_skills import cricket

        return cricket
```

(d) Update the two help strings: add `cricket` to the `description=` sport list and to the `module` argument help (`..., tennis, cricket, cfb, ...`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cricket.py tests/test_imports.py -v`
Expected: all PASS (test_imports picks up the new module if it enumerates modules; if it has an explicit list, add `cricket` to it)

- [ ] **Step 5: Smoke-test the CLI offline surface**

```bash
python3 -m sports_skills cricket
python3 -m sports_skills cricket get_competitions
```
Expected: first prints cricket's command list; second prints the competitions JSON envelope with `"status": true`.

- [ ] **Step 6: Commit**

```bash
git add src/sports_skills/cli.py tests/test_cricket.py
git commit -m "feat(cricket): register cricket module in CLI"
```

---

### Task 12: Skill folder (`skills/cricket-data/`)

**Files:**
- Create: `skills/cricket-data/SKILL.md`
- Create: `skills/cricket-data/references/api-reference.md`
- Create: `skills/cricket-data/references/competitions.md`
- Create: `skills/cricket-data/scripts/validate_params.sh`

Before writing, read `skills/tennis-data/SKILL.md` in full and mirror its section order and tone. Content requirements (from the spec):

- [ ] **Step 1: Write `SKILL.md`**

Frontmatter (exact format from tennis-data):

```yaml
---
name: cricket-data
description: |
  Cricket data via ESPN public endpoints and Cricsheet open data — live-ish series scoreboards, standings, match summaries and news (ESPN), plus historical ball-by-ball, player stats, and player registry (Cricsheet, ODC-BY 1.0). Zero config, no API keys.

  Use when: user asks about cricket scores, IPL/BBL/PSL/international series, points tables, match details, cricket news, ball-by-ball history, or player career stats.
  Don't use when: user asks about other sports — use football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). For betting odds use polymarket or kalshi. For general news use sports-news. Don't use for ICC rankings — no free source exists (v1 limitation).
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---
```

Body must include (mirroring tennis-data's structure):
1. Pointer to `references/api-reference.md` before writing queries.
2. Quick Start with CLI examples for both backends:
   ```bash
   sports-skills cricket get_series
   sports-skills cricket get_scoreboard --series_id=8048
   sports-skills cricket get_standings --series_id=8048
   sports-skills cricket get_game_summary --series_id=8048 --event_id=1535465
   sports-skills cricket get_news --series_id=8048
   sports-skills cricket get_competitions
   sports-skills cricket get_matches --competition=ipl --season=2026
   sports-skills cricket get_match_deliveries --competition=ipl --match_id=1473508
   sports-skills cricket get_player_stats --competition=ipl --player="V Kohli"
   sports-skills cricket find_player --name=kohli
   ```
3. "CRITICAL: Before Any Query" section with the gotchas:
   - ESPN series IDs are per-series, not per-league — always discover with `get_series` first; IDs change every season for recurring tournaments.
   - `get_series` (ESPN, live, numeric IDs) vs `get_competitions` (Cricsheet, historical, letter codes) — two different ID spaces. They meet only at match level: Cricsheet `match_id` = ESPNcricinfo match ID.
   - Cricsheet covers completed matches only (~1-day lag); use ESPN commands for anything live or upcoming.
   - `get_player_stats` requires the exact Cricsheet name spelling — resolve with `find_player` first.
   - No ICC rankings (v1 limitation, no free source). Series standings come from `get_standings`.
   - First Cricsheet call per competition per day downloads the zip (large competitions = tens of MB).
4. Attribution note: Cricsheet data is ODC-BY 1.0; responses include the required attribution string — preserve it when republishing.

- [ ] **Step 2: Write `references/api-reference.md`**

Document (use the verified facts from the plan header):
- Both ESPN endpoint families with URL templates and the JSON shapes of each normalized command response (copy the normalized output field lists from Tasks 7-9).
- Cricket status values (via shared `ESPN_STATUS_MAP`: `not_started`, `live`, `closed`, etc.) and the cricket score-string format (`"161/5 (18/20 ov, target 156)"`).
- Cricsheet JSON structure (innings → overs → deliveries) and the normalized shapes of Tasks 3-6 responses, including the aggregation conventions (balls-faced/wides, bowler-credited dismissal kinds, economy formula).
- Cache behavior: ESPN in-memory TTL ~120s; Cricsheet on-disk at `~/.cache/sports-skills/cricsheet/`, 24h zips / 7d registry, `stale: true` flag semantics.

- [ ] **Step 3: Write `references/competitions.md`**

Table of all 16 Cricsheet codes from `_COMPETITIONS` with full names, plus guidance: ESPN series-ID discovery flow (`get_series`), well-known ESPN series IDs are season-specific (e.g. IPL 2026 = 8048) so never hardcode them.

- [ ] **Step 4: Copy and adapt `scripts/validate_params.sh`**

Read `skills/tennis-data/scripts/validate_params.sh` first; adapt its checks to cricket's params (`series_id` numeric, `competition` in the 16-code list, `date` YYYYMMDD). If the tennis script is tour-specific boilerplate that doesn't translate, skip this file and remove the `scripts/` dir — don't force it.

- [ ] **Step 5: Verify and commit**

```bash
ls skills/cricket-data/
git add skills/cricket-data/
git commit -m "feat(cricket): add cricket-data skill docs"
```

---

### Task 13: Cross-reference routing in sibling skills

**Files:**
- Modify: `skills/*/SKILL.md` — only the ones whose `Don't use when:` line enumerates other sports skills (check each of: tennis-data, nba-data, nfl-data, nhl-data, mlb-data, wnba-data, cfb-data, cbb-data, golf-data, football-data, fastf1, volleyball-data, sports-news)

- [ ] **Step 1: Find the routing lines**

```bash
grep -l "Don't use when" skills/*/SKILL.md | xargs grep -n "golf-data"
```

- [ ] **Step 2: Add cricket-data to each routing list**

In each file found, extend the sport enumeration with `cricket-data (cricket)` following the existing comma style, e.g. `..., golf-data (golf), cricket-data (cricket), or fastf1 (F1)`. Touch ONLY that line in each file.

- [ ] **Step 3: Verify the diff is surgical**

```bash
git diff --stat
```
Expected: one line changed per SKILL.md touched, nothing else.

- [ ] **Step 4: Commit**

```bash
git add skills/
git commit -m "docs: route cricket queries to cricket-data in sibling skills"
```

---

### Task 14: Full verification + live smoke test + changelog

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run the full test suite**

```bash
python3 -m pytest tests/ -v
```
Expected: all PASS, no regressions.

- [ ] **Step 2: Live smoke test (network required — manual verification, not CI)**

```bash
sports-skills cricket get_series
sports-skills cricket get_competitions
sports-skills cricket find_player --name=kohli
```
Then with a real `series_id` from the `get_series` output:
```bash
sports-skills cricket get_scoreboard --series_id=<id>
sports-skills cricket get_news --series_id=<id>
```
And a small Cricsheet competition (wpl is the smallest, ~88 matches):
```bash
sports-skills cricket get_matches --competition=wpl --season=2026
sports-skills cricket get_player_stats --competition=wpl --player="<name from get_matches output>"
```
Expected: every command returns `"status": true` with plausible data. If `get_standings` on a bilateral tour returns the no-standings message, that is correct behavior.

- [ ] **Step 3: Add CHANGELOG entry**

Read the top of `CHANGELOG.md` and follow its existing entry format. Summary: new `cricket` module + `cricket-data` skill — ESPN live-ish (series, scoreboard, standings, summary, news) + Cricsheet historical (matches, ball-by-ball, player stats, registry; ODC-BY 1.0 attribution).

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog entry for cricket-data skill"
```

- [ ] **Step 5: Final review gate**

Run `git log --oneline main..HEAD` and `git diff main --stat` — confirm every changed file traces to this plan. Do NOT merge or push; hand back to the user for review (superpowers:finishing-a-development-branch).

---

## Self-Review Notes

- **Spec coverage:** all 10 commands have tasks (1, 3-10); cache layer (2); CLI (11); SKILL.md + references + attribution (12); cross-referencing (13); known limitations land in SKILL.md (12.3); testing strategy = mocked HTTP + in-memory fixture zip, no network in CI (Tasks 1-11), live smoke manual (14).
- **Type consistency:** `_fetch_file` 3-tuple `(path, stale, err)` used consistently in Tasks 2, 3, 6 (via `_open_competition`); `_match_summary(name, info)` defined in Task 3, reused in Task 4; `_validate_series_id` defined Task 7, used Tasks 8-9; `_params()` helper matches tennis convention.
- **Known judgment calls:** `get_matches` parses every JSON in the zip per call (acceptable: in-process calls within a session hit the OS page cache; a parsed-index cache is YAGNI for v1). `get_game_summary` passes through selected raw ESPN keys rather than deep-normalizing `matchcards` (shape varies by format; revisit if needed).

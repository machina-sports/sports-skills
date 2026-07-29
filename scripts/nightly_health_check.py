#!/usr/bin/env python3
"""Nightly health check for all data sources used by sports-skills.

Tests every upstream endpoint and produces:
  reports/health/YYYY-MM-DD.json   — structured results
  reports/health/YYYY-MM-DD.md    — human-readable summary
  reports/health/YYYY-MM-DD-issue.md  — GitHub issue body (only when failures found)

Exit codes:
  0 — all sources OK
  1 — one or more sources degraded (slow but reachable)
  2 — one or more sources down (unreachable / bad response)
"""

import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

TIMEOUT = 10  # seconds per request
SLOW_THRESHOLD_MS = 3000  # ms above which a source is "degraded"

# All 13 leagues (slug → ESPN id), matching LEAGUES dict in football/_connector.py
LEAGUES = {
    "premier-league": "eng.1",
    "la-liga": "esp.1",
    "bundesliga": "ger.1",
    "serie-a": "ita.1",
    "ligue-1": "fra.1",
    "championship": "eng.2",
    "eredivisie": "ned.1",
    "primeira-liga": "por.1",
    "serie-a-brazil": "bra.1",
    "mls": "usa.1",
    "champions-league": "uefa.champions",
    "world-cup": "fifa.world",
    # european-championship has espn=None, skip it
}

# Understat slugs for the top-5 leagues only
UNDERSTAT_LEAGUES = ["EPL", "La_Liga", "Bundesliga", "Serie_A", "Ligue_1"]

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_US_SPORTS = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "nhl": "hockey/nhl",
    "mlb": "baseball/mlb",
    "atp": "tennis/atp",
    "wta": "tennis/wta",
    "cfb": "football/college-football",
    "cbb": "basketball/mens-college-basketball",
    "golf_pga": "golf/pga",
    "golf_lpga": "golf/lpga",
}
FPL_BASE = "https://fantasy.premierleague.com/api"
UNDERSTAT_BASE = "https://understat.com"
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
BBC_SPORT_RSS = "https://feeds.bbci.co.uk/sport/rss.xml"

USER_AGENT = (
    "Mozilla/5.0 (compatible; sports-skills-health-check/1.0; "
    "+https://github.com/MachinaSports/sports-skills)"
)


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _fetch(url: str, *, headers: dict | None = None, method: str = "GET") -> tuple[bytes | None, int, str | None]:
    """Fetch a URL.  Returns (body_bytes, status_code, error_message)."""
    req_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding", "")
            if enc == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            return raw, resp.status, None
    except urllib.error.HTTPError as exc:
        return None, exc.code, f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, 0, str(exc.reason)
    except Exception as exc:  # ruff:ignore[blind-except]
        return None, 0, str(exc)


def _timed_fetch(url: str, **kwargs) -> dict:
    """Fetch a URL and return a result dict with timing."""
    t0 = time.monotonic()
    body, status, error = _fetch(url, **kwargs)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {"body": body, "status_code": status, "elapsed_ms": elapsed_ms, "error": error}


# ── Individual source checks ───────────────────────────────────────────────────

def check_espn_league(slug: str, espn_id: str) -> dict:
    """Check a single ESPN soccer league scoreboard endpoint."""
    url = f"{ESPN_BASE}/{espn_id}/scoreboard"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        events = data.get("events", [])
        sample = {"event_count": len(events)}
        if events:
            first = events[0]
            sample["first_event"] = first.get("name", first.get("shortName", ""))
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_espn_all_leagues() -> dict:
    """Check all 12 ESPN-backed leagues and roll up into a group result."""
    results = {}
    for slug, espn_id in LEAGUES.items():
        results[slug] = check_espn_league(slug, espn_id)

    statuses = [v["status"] for v in results.values()]
    down_count = statuses.count("down")
    degraded_count = statuses.count("degraded")
    avg_ms = int(sum(v["response_time_ms"] for v in results.values()) / len(results))

    if down_count >= 6:
        roll_status = "down"
        roll_error = f"{down_count}/{len(LEAGUES)} leagues unreachable"
    elif down_count > 0 or degraded_count > 0:
        roll_status = "degraded"
        roll_error = f"{down_count} down, {degraded_count} slow out of {len(LEAGUES)} leagues"
    else:
        roll_status = "ok"
        roll_error = None

    return {
        "status": roll_status,
        "response_time_ms": avg_ms,
        "error": roll_error,
        "sample_data": {
            "leagues_checked": len(LEAGUES),
            "ok": statuses.count("ok"),
            "degraded": degraded_count,
            "down": down_count,
        },
        "per_league": results,
    }


def check_espn_us_sport(sport_name: str, sport_path: str) -> dict:
    """Check a single ESPN US sport scoreboard endpoint."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        events = data.get("events", [])
        sample = {"event_count": len(events)}
        if events:
            first = events[0]
            sample["first_event"] = first.get("name", first.get("shortName", ""))
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_fpl() -> dict:
    """Check Fantasy Premier League bootstrap-static endpoint."""
    url = f"{FPL_BASE}/bootstrap-static/"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        elements = data.get("elements", [])
        teams = data.get("teams", [])
        sample = {"players": len(elements), "teams": len(teams)}
        if elements:
            p = elements[0]
            sample["first_player"] = f"{p.get('first_name', '')} {p.get('second_name', '')}".strip()
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_understat_league(league: str) -> dict:
    """Check Understat by fetching the league page (HTML, not JSON)."""
    current_year = datetime.now(tz=UTC).year
    url = f"{UNDERSTAT_BASE}/league/{league}/{current_year}"
    r = _timed_fetch(url, headers={"Accept": "text/html"})
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    if r["status_code"] and r["status_code"] >= 400:
        return _result("down", r["elapsed_ms"], f"HTTP {r['status_code']}", url=url)
    # Confirm we got HTML with known Understat markers
    body_text = r["body"].decode("utf-8", errors="replace") if r["body"] else ""
    if "understat" not in body_text.lower():
        return _result("degraded", r["elapsed_ms"], "Response missing expected Understat content", url=url)
    sample = {"bytes": len(r["body"]), "has_datesData": "datesData" in body_text}
    return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)


def check_understat_all() -> dict:
    """Check all 5 Understat leagues."""
    results = {}
    for league in UNDERSTAT_LEAGUES:
        results[league] = check_understat_league(league)

    statuses = [v["status"] for v in results.values()]
    down_count = statuses.count("down")
    degraded_count = statuses.count("degraded")
    avg_ms = int(sum(v["response_time_ms"] for v in results.values()) / len(results))

    if down_count >= 3:
        roll_status = "down"
        roll_error = f"{down_count}/{len(UNDERSTAT_LEAGUES)} leagues unreachable"
    elif down_count > 0 or degraded_count > 0:
        roll_status = "degraded"
        roll_error = f"{down_count} down, {degraded_count} slow out of {len(UNDERSTAT_LEAGUES)} leagues"
    else:
        roll_status = "ok"
        roll_error = None

    return {
        "status": roll_status,
        "response_time_ms": avg_ms,
        "error": roll_error,
        "sample_data": {
            "leagues_checked": len(UNDERSTAT_LEAGUES),
            "ok": statuses.count("ok"),
            "degraded": degraded_count,
            "down": down_count,
        },
        "per_league": results,
    }


def check_kalshi() -> dict:
    """Check Kalshi markets endpoint."""
    url = f"{KALSHI_BASE}/markets?limit=5"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        markets = data.get("markets", [])
        sample = {"market_count": len(markets)}
        if markets:
            m = markets[0]
            sample["first_ticker"] = m.get("ticker", "")
            sample["first_title"] = m.get("title", "")
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_polymarket_gamma() -> dict:
    """Check Polymarket Gamma API markets endpoint."""
    url = f"{GAMMA_BASE}/markets?limit=5&active=true"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        # Gamma returns a list directly
        items = data if isinstance(data, list) else data.get("markets", data.get("results", []))
        sample = {"market_count": len(items)}
        if items:
            first = items[0]
            sample["first_question"] = first.get("question", first.get("title", ""))[:80]
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_polymarket_clob() -> dict:
    """Check Polymarket CLOB API sampling-markets endpoint."""
    url = f"{CLOB_BASE}/sampling-markets?count=5"
    r = _timed_fetch(url)
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)
    try:
        data = json.loads(r["body"])
        items = data if isinstance(data, list) else data.get("data", [])
        sample = {"market_count": len(items)}
        if items:
            first = items[0] if isinstance(items[0], dict) else {}
            sample["first_condition_id"] = first.get("condition_id", "")[:16] + "…"
        return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)
    except Exception as exc:
        return _result("down", r["elapsed_ms"], f"JSON parse error: {exc}", url=url)


def check_fastf1() -> dict:
    """Check FastF1 import availability and race schedule fetch."""
    t0 = time.monotonic()
    try:
        import fastf1
    except ImportError as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return _result("down", elapsed_ms, f"FastF1 not importable: {exc}")

    # Probe: fetch a known past season schedule (2024 is fully cached, no network auth needed)
    try:
        schedule = fastf1.get_event_schedule(2024)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        count = len(schedule) if schedule is not None else 0
        return _result("ok", elapsed_ms, sample_data={"events_in_schedule": count, "year": 2024})
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return _result("degraded", elapsed_ms, f"FastF1 schedule fetch failed: {exc}",
                       sample_data={"fastf1_importable": True})


def check_bbc_rss() -> dict:
    """Check BBC Sport RSS feed (proxy for feedparser / RSS availability)."""
    url = BBC_SPORT_RSS
    r = _timed_fetch(url, headers={"Accept": "application/rss+xml, application/xml, text/xml"})
    if r["error"]:
        return _result("down", r["elapsed_ms"], r["error"], url=url)

    body_text = r["body"].decode("utf-8", errors="replace") if r["body"] else ""
    if "<rss" not in body_text and "<feed" not in body_text:
        return _result("degraded", r["elapsed_ms"], "Response does not look like RSS/Atom", url=url)

    # Count <item> or <entry> elements as a sanity check
    item_count = body_text.count("<item>") + body_text.count("<entry>")
    sample = {"items_found": item_count, "bytes": len(r["body"])}

    # Try to pull first title
    import re
    titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>|<title>(.+?)</title>", body_text)
    # Skip the channel title (index 0)
    for cdata, plain in titles[1:2]:
        sample["first_headline"] = (cdata or plain).strip()[:80]

    return _result("ok", r["elapsed_ms"], sample_data=sample, url=url)


# ── Result builder ─────────────────────────────────────────────────────────────

def _result(
    status: str,
    elapsed_ms: int,
    error: str | None = None,
    *,
    sample_data: dict | None = None,
    url: str | None = None,
) -> dict:
    """Build a normalised source-check result dict."""
    # Auto-degrade slow-but-reachable sources
    if status == "ok" and elapsed_ms > SLOW_THRESHOLD_MS:
        status = "degraded"
        error = error or f"Response time {elapsed_ms}ms exceeds {SLOW_THRESHOLD_MS}ms threshold"
    out: dict = {"status": status, "response_time_ms": elapsed_ms}
    if error:
        out["error"] = error
    if sample_data:
        out["sample_data"] = sample_data
    if url:
        out["url"] = url
    return out


# ── Report generation ──────────────────────────────────────────────────────────

STATUS_ICON = {"ok": "✅", "degraded": "⚠️", "down": "❌"}


def _md_row(name: str, r: dict) -> str:
    icon = STATUS_ICON.get(r["status"], "?")
    ms = r["response_time_ms"]
    err = r.get("error", "—")
    sample = r.get("sample_data", {})
    sample_str = ", ".join(f"{k}={v}" for k, v in list(sample.items())[:3]) if sample else "—"
    return f"| {icon} {name} | {r['status']} | {ms} ms | {err} | {sample_str} |"


def build_markdown(date_str: str, results: dict, run_at: str) -> str:
    lines = [
        f"# Sports-Skills Data Source Health Check — {date_str}",
        "",
        f"**Run at:** {run_at}  ",
        f"**Timeout:** {TIMEOUT}s per request  ",
        f"**Degraded threshold:** {SLOW_THRESHOLD_MS} ms",
        "",
        "## Summary",
        "",
    ]

    all_statuses = []
    for key, r in results.items():
        all_statuses.append(r["status"])

    ok_count = all_statuses.count("ok")
    degraded_count = all_statuses.count("degraded")
    down_count = all_statuses.count("down")
    total = len(all_statuses)

    lines += [
        f"- **Total sources:** {total}",
        f"- {STATUS_ICON['ok']} OK: {ok_count}",
        f"- {STATUS_ICON['degraded']} Degraded: {degraded_count}",
        f"- {STATUS_ICON['down']} Down: {down_count}",
        "",
        "## Results",
        "",
        "| Source | Status | Latency | Error | Sample |",
        "|--------|--------|---------|-------|--------|",
    ]

    for name, r in results.items():
        lines.append(_md_row(name, r))

    # Per-league details for ESPN
    if "espn" in results and "per_league" in results["espn"]:
        lines += ["", "### ESPN — Per-League", "", "| League | Status | Latency | Error |", "|--------|--------|---------|-------|"]
        for slug, lr in results["espn"]["per_league"].items():
            icon = STATUS_ICON.get(lr["status"], "?")
            lines.append(f"| {icon} {slug} | {lr['status']} | {lr['response_time_ms']} ms | {lr.get('error', '—')} |")

    # Per-league details for Understat
    if "understat" in results and "per_league" in results["understat"]:
        lines += ["", "### Understat — Per-League", "", "| League | Status | Latency | Error |", "|--------|--------|---------|-------|"]
        for slug, lr in results["understat"]["per_league"].items():
            icon = STATUS_ICON.get(lr["status"], "?")
            lines.append(f"| {icon} {slug} | {lr['status']} | {lr['response_time_ms']} ms | {lr.get('error', '—')} |")

    lines += ["", "---", "_Generated by scripts/nightly_health_check.py_"]
    return "\n".join(lines)


def build_issue_body(date_str: str, results: dict, run_at: str) -> str:
    failing = {k: v for k, v in results.items() if v["status"] != "ok"}
    lines = [
        f"## Data Source Health Check Failures — {date_str}",
        "",
        f"Detected at: {run_at}",
        "",
        "### Affected Sources",
        "",
    ]
    for name, r in failing.items():
        icon = STATUS_ICON.get(r["status"], "?")
        lines.append(f"#### {icon} {name}")
        lines.append(f"- **Status:** {r['status']}")
        lines.append(f"- **Latency:** {r['response_time_ms']} ms")
        if r.get("error"):
            lines.append(f"- **Error:** `{r['error']}`")
        if r.get("url"):
            lines.append(f"- **URL:** {r['url']}")
        if r.get("sample_data"):
            lines.append(f"- **Sample:** {r['sample_data']}")

        # Include per-league breakdown for aggregated sources
        if "per_league" in r:
            bad_leagues = {k: v for k, v in r["per_league"].items() if v["status"] != "ok"}
            if bad_leagues:
                lines.append("- **Failing leagues:**")
                for slug, lr in bad_leagues.items():
                    lines.append(f"  - `{slug}`: {lr['status']} — {lr.get('error', '')}")
        lines.append("")

    lines += [
        "### Steps to investigate",
        "",
        "1. Run `python scripts/nightly_health_check.py` locally to reproduce",
        "2. Check upstream status pages",
        "3. Review connector code in `src/sports_skills/` for any required URL changes",
        "",
        "---",
        "_Auto-generated by scripts/nightly_health_check.py_",
    ]
    return "\n".join(lines)


# ── CLI stdout summary ─────────────────────────────────────────────────────────

def print_summary(results: dict, run_at: str) -> None:
    print(f"\nSports-Skills Health Check  —  {run_at}")
    print("=" * 60)
    col_w = max(len(k) for k in results) + 2
    for name, r in results.items():
        icon = STATUS_ICON.get(r["status"], "?")
        ms = f"{r['response_time_ms']} ms"
        err = f"  [{r['error']}]" if r.get("error") else ""
        print(f"  {icon}  {name:<{col_w}} {ms:>8}{err}")
    print()

    all_statuses = [r["status"] for r in results.values()]
    ok = all_statuses.count("ok")
    deg = all_statuses.count("degraded")
    down = all_statuses.count("down")
    print(f"  Total: {len(all_statuses)}  |  OK: {ok}  |  Degraded: {deg}  |  Down: {down}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    run_at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    out_dir = Path(__file__).parent.parent / "reports" / "health"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running health checks at {run_at} …")

    # ── Run all checks ──────────────────────────────────────────────────────
    results: dict[str, dict] = {}

    print("  Checking ESPN (all leagues) …", end="", flush=True)
    results["espn"] = check_espn_all_leagues()
    print(f" {results['espn']['status']}")

    for sport_name, sport_path in ESPN_US_SPORTS.items():
        print(f"  Checking ESPN {sport_name.upper()} …", end="", flush=True)
        results[f"espn_{sport_name}"] = check_espn_us_sport(sport_name, sport_path)
        print(f" {results[f'espn_{sport_name}']['status']}")

    print("  Checking FPL …", end="", flush=True)
    results["fpl"] = check_fpl()
    print(f" {results['fpl']['status']}")

    print("  Checking Understat (all top-5 leagues) …", end="", flush=True)
    results["understat"] = check_understat_all()
    print(f" {results['understat']['status']}")

    print("  Checking Kalshi …", end="", flush=True)
    results["kalshi"] = check_kalshi()
    print(f" {results['kalshi']['status']}")

    print("  Checking Polymarket Gamma …", end="", flush=True)
    results["polymarket_gamma"] = check_polymarket_gamma()
    print(f" {results['polymarket_gamma']['status']}")

    print("  Checking Polymarket CLOB …", end="", flush=True)
    results["polymarket_clob"] = check_polymarket_clob()
    print(f" {results['polymarket_clob']['status']}")

    print("  Checking FastF1 …", end="", flush=True)
    results["fastf1"] = check_fastf1()
    print(f" {results['fastf1']['status']}")

    print("  Checking BBC Sport RSS …", end="", flush=True)
    results["bbc_rss"] = check_bbc_rss()
    print(f" {results['bbc_rss']['status']}")

    # ── Write JSON report ───────────────────────────────────────────────────
    report = {
        "date": date_str,
        "run_at": run_at,
        "timeout_s": TIMEOUT,
        "degraded_threshold_ms": SLOW_THRESHOLD_MS,
        "sources": results,
    }
    json_path = out_dir / f"{date_str}.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"\nJSON report → {json_path}")

    # ── Write Markdown summary ──────────────────────────────────────────────
    md_content = build_markdown(date_str, results, run_at)
    md_path = out_dir / f"{date_str}.md"
    md_path.write_text(md_content)
    print(f"MD report  → {md_path}")

    # ── Print stdout summary ────────────────────────────────────────────────
    print_summary(results, run_at)

    # ── Determine exit code ─────────────────────────────────────────────────
    all_statuses = [r["status"] for r in results.values()]
    has_down = "down" in all_statuses
    has_degraded = "degraded" in all_statuses

    if has_down or has_degraded:
        issue_content = build_issue_body(date_str, results, run_at)
        issue_path = out_dir / f"{date_str}-issue.md"
        issue_path.write_text(issue_content)
        print(f"Issue body → {issue_path}")

    if has_down:
        return 2
    if has_degraded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Nightly self-improvement script for sports-skills.

Tier 1 autonomous fixes — runs after nightly_health_check.py.
Exit 0 always: best-effort, never blocks the pipeline.

Tasks:
  1. Code Hygiene  — ruff auto-fix + mypy report
  2. SKILL.md Freshness — refresh live example output
  3. Schema Baseline — detect API drift, report only (baseline is reviewed by hand)
"""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC_DIR = REPO_ROOT / "src"
SKILLS_DIR = REPO_ROOT / "skills"
REPORTS_DIR = REPO_ROOT / "reports"
DRIFT_DIR = REPORTS_DIR / "drift"
BASELINE_PATH = SCRIPTS_DIR / "schema_baseline.json"

TODAY = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
USER_AGENT = "sports-skills-nightly-improve/1.0"

TIMEOUT = 10

# Sources to baseline — same endpoints as health check, key fields only
BASELINE_SOURCES = {
    "espn_premier_league": {
        "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
        "required_keys": ["events", "leagues", "season"],
    },
    "fpl_bootstrap": {
        "url": "https://fantasy.premierleague.com/api/bootstrap-static/",
        "required_keys": ["elements", "teams", "events"],
    },
    "kalshi_markets": {
        "url": "https://api.elections.kalshi.com/trade-api/v2/markets?limit=1",
        "required_keys": ["markets", "cursor"],
    },
    "polymarket_gamma": {
        "url": "https://gamma-api.polymarket.com/markets?limit=1&active=true",
        "required_keys": None,  # returns a list
        "root": "array",  # keys are read from the row objects; default root is "object"
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fetch(url: str) -> tuple[bytes | None, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            return raw, None
    except Exception as exc:
        return None, str(exc)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"


def _git_commit(msg: str) -> bool:
    code, _, _ = _run(["git", "add", "-A"])
    if code != 0:
        return False
    code, out, _ = _run(["git", "diff", "--cached", "--quiet"])
    if code == 0:
        return False  # nothing staged
    code, _, err = _run(["git", "commit", "-m", msg])
    return code == 0


# ── Task 1: Code Hygiene ───────────────────────────────────────────────────────

def run_hygiene() -> dict:
    print("\n── Task 1: Code Hygiene ──")
    results: dict = {"ruff_fixed": False, "mypy_clean": False, "mypy_errors": []}

    # ruff check --fix
    code, out, err = _run(["ruff", "check", "--fix", str(SRC_DIR)])
    ruff_output = (out + err).strip()
    if "Fixed" in ruff_output or "reformatted" in ruff_output:
        results["ruff_fixed"] = True

    # ruff format
    _run(["ruff", "format", str(SRC_DIR)])

    if results["ruff_fixed"]:
        committed = _git_commit(f"style: ruff auto-fix {TODAY}")
        print(f"  ruff: fixes applied, committed={committed}")
    else:
        print("  ruff: nothing to fix")

    # mypy (report only, never fail)
    code, out, err = _run(["mypy", "--strict", str(SRC_DIR)])
    if code == 0:
        results["mypy_clean"] = True
        print("  mypy: clean")
    else:
        errors = [l for l in (out + err).splitlines() if "error:" in l]
        results["mypy_errors"] = errors[:10]  # cap at 10
        print(f"  mypy: {len(errors)} error(s) (not blocking)")

    return results


# ── Task 2: SKILL.md Freshness ────────────────────────────────────────────────

# Zero-arg commands per skill — these can run without required params and
# produce stable JSON output suitable for use as a live example.
ZERO_ARG_COMMANDS: dict[str, list[str]] = {
    "football-data": [
        "sports-skills football get_daily_schedule",
        "sports-skills football get_competitions",
    ],
    "fastf1": [
        "sports-skills f1 get_race_schedule --year=2025",
    ],
    "kalshi": [
        "sports-skills kalshi get_markets --limit=1",
    ],
    "polymarket": [
        "sports-skills polymarket get_markets --limit=1",
    ],
    "sports-news": [
        "sports-skills news get_headlines --source=bbc",
    ],
}


def _run_cmd_fresh(cmd: str) -> str | None:
    """Run a sports-skills CLI command, return a single trimmed JSON object or None."""
    code, out, _ = _run(cmd.strip().split())
    out = out.strip()
    if code != 0 or not out:
        return None
    try:
        data = json.loads(out)
        # If it's a dict with a list value, grab the first item for a compact example
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v:
                    return json.dumps(v[0], indent=2)
            return json.dumps(data, indent=2)
        if isinstance(data, list) and data:
            return json.dumps(data[0], indent=2)
        return json.dumps(data, indent=2)
    except Exception:
        return None


def _find_json_block(lines: list[str], after: int, before: int) -> tuple[int, int] | None:
    """Find the first ```json block between line indices after and before.
    Returns (fence_line, close_line) or None."""
    i = after
    while i < before:
        if lines[i].strip() in ("```json", "```"):
            # find closing fence
            j = i + 1
            while j < len(lines):
                if lines[j].strip() == "```":
                    return i, j
                j += 1
        i += 1
    return None


def refresh_skill_examples() -> dict:
    """
    For each skill, run its zero-arg commands, then find the first ```json block
    in the matching ### section and update it with fresh live output.
    """
    print("\n── Task 2: SKILL.md Freshness ──")
    updated: list[str] = []
    skipped: list[str] = []

    skill_paths: list[Path] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        candidate = entry / "SKILL.md"
        if candidate.exists():
            skill_paths.append(candidate)

    for skill_path in skill_paths:
        skill_name = skill_path.parent.name
        cmds = ZERO_ARG_COMMANDS.get(skill_name, [])
        if not cmds:
            print(f"  {skill_name}: no zero-arg commands configured — skipping")
            skipped.append(skill_name)
            continue

        lines = skill_path.read_text(encoding="utf-8").splitlines()
        new_lines = lines[:]
        skill_changed = False

        for cmd in cmds:
            # Derive the function name from the command (last segment before any --)
            parts = cmd.split()
            fn_name = next((p for p in parts if not p.startswith("--") and p not in ("sports-skills", "football", "f1", "kalshi", "polymarket", "news")), None)
            if not fn_name:
                continue

            # Find the ### section for this function
            section_start = next(
                (i for i, l in enumerate(new_lines) if l.strip().startswith(f"### {fn_name}")),
                None,
            )
            if section_start is None:
                continue

            # Section ends at the next ### or end of file
            section_end = next(
                (i for i in range(section_start + 1, len(new_lines)) if new_lines[i].startswith("### ")),
                len(new_lines),
            )

            block = _find_json_block(new_lines, section_start, section_end)
            if block is None:
                continue

            fence_i, close_i = block
            fresh = _run_cmd_fresh(cmd)
            if not fresh:
                continue

            old_content = "\n".join(new_lines[fence_i + 1 : close_i]).strip()
            if fresh.strip() == old_content:
                continue  # already up to date

            # Replace block contents
            fresh_lines = fresh.splitlines()
            new_lines[fence_i + 1 : close_i] = fresh_lines
            skill_changed = True

        if skill_changed:
            skill_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            updated.append(skill_name)
            print(f"  {skill_name}: examples refreshed ✓")
        else:
            skipped.append(skill_name)
            print(f"  {skill_name}: already fresh")

    if updated:
        _git_commit(f"docs: refresh SKILL.md examples {TODAY}")

    return {"updated": updated, "skipped": skipped}


# ── Task 3: Schema Baseline & Drift Detection ─────────────────────────────────

# The reviewed baseline is read-only here: observations (drift or first-seen
# sources) never rewrite it. They are written to the dated report for review.
#
# Per-source statuses:
#   checked      — unchanged | drift | new (first observation, proposed only)
#   failed       — fetch_failed
#   inconclusive — invalid_json | unexpected_shape | baseline_error
CHECKED_STATUSES = ("unchanged", "drift", "new")


def _load_baseline() -> tuple[dict | None, str, str]:
    """Return (baseline, status, detail); status is "ok", "missing" or "invalid"."""
    if not BASELINE_PATH.exists():
        return None, "missing", f"{BASELINE_PATH.name} not found"
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "invalid", f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "invalid", f"top level is {type(data).__name__}, expected object"
    for source, entry in data.items():
        keys = entry.get("keys") if isinstance(entry, dict) else None
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            return None, "invalid", f"entry {source!r} has no list of string keys"
    return data, "ok", ""


def _observe_keys(body: bytes, root: str) -> tuple[list[str] | None, str, str]:
    """Return (keys, status, detail); keys is None when no field set is observable."""
    try:
        data = json.loads(body)
    except ValueError as exc:
        return None, "invalid_json", str(exc)
    if root == "array":
        if not isinstance(data, list):
            return None, "unexpected_shape", f"expected array, got {type(data).__name__}"
        if not data:
            return None, "unexpected_shape", "empty array — no row fields observable"
        for i, row in enumerate(data):
            if not isinstance(row, dict):
                return None, "unexpected_shape", f"array row {i} is {type(row).__name__}, expected object"
        return sorted(data[0].keys()), "ok", ""
    if not isinstance(data, dict):
        return None, "unexpected_shape", f"expected object, got {type(data).__name__}"
    return sorted(data.keys()), "ok", ""


def _drift_report(result: dict) -> str:
    cov = result["coverage"]
    baseline = result["baseline_status"]
    if result["baseline_detail"]:
        baseline += f" — {result['baseline_detail']}"
    lines = [
        f"# Schema Drift Report — {TODAY}",
        "",
        f"- **Status:** {result['status']}",
        f"- **Baseline:** {baseline}",
        f"- **Coverage:** {cov['checked']}/{cov['total']} checked, "
        f"{cov['failed']} fetch failed, {cov['inconclusive']} inconclusive",
        "- The reviewed baseline (`scripts/schema_baseline.json`) is not modified by this job.",
        "",
    ]
    proposals = {}
    for o in result["sources"]:
        lines.append(f"## {o['source']}: {o['status']}")
        if o["detail"]:
            lines.append(f"- {o['detail']}")
        for label, field in (
            ("Added fields", "added"),
            ("Removed fields", "removed"),
            ("⚠️ Missing required", "missing_required"),
        ):
            if o[field]:
                lines.append(f"- **{label}:** `{'`, `'.join(o[field])}`")
        if o["status"] == "new":
            proposals[o["source"]] = {"keys": o["observed_keys"], "first_seen": TODAY}
        lines.append("")
    if proposals:
        lines += [
            "## Proposed baseline entries (unreviewed — not applied)",
            "",
            "```json",
            json.dumps(proposals, indent=2),
            "```",
            "",
        ]
    return "\n".join(lines)


def check_schema_drift() -> dict:
    print("\n── Task 3: Schema Baseline & Drift ──")

    baseline, baseline_status, baseline_detail = _load_baseline()
    if baseline_status != "ok":
        print(f"  baseline {baseline_status}: {baseline_detail}")

    outcomes: list[dict] = []
    for source, config in BASELINE_SOURCES.items():
        outcome: dict = {
            "source": source,
            "status": "",
            "detail": "",
            "added": [],
            "removed": [],
            "missing_required": [],
            "observed_keys": None,
        }
        outcomes.append(outcome)

        # A corrupt baseline is not an empty approved state — nothing can be compared.
        if baseline_status == "invalid":
            outcome.update(status="baseline_error", detail=f"baseline invalid: {baseline_detail}")
            print(f"  {source}: not checked (baseline invalid)")
            continue

        body, err = _fetch(config["url"])
        if err or not body:
            outcome.update(status="fetch_failed", detail=err or "empty response body")
            print(f"  {source}: fetch failed ({outcome['detail']})")
            continue

        keys, status, detail = _observe_keys(body, config.get("root", "object"))
        if keys is None:
            outcome.update(status=status, detail=detail)
            print(f"  {source}: {status} ({detail})")
            continue

        live = set(keys)
        outcome["observed_keys"] = keys
        outcome["missing_required"] = [k for k in (config.get("required_keys") or []) if k not in live]
        entry = (baseline or {}).get(source)
        if entry is not None:
            stored = set(entry["keys"])
            outcome["added"] = sorted(live - stored)
            outcome["removed"] = sorted(stored - live)

        if outcome["added"] or outcome["removed"] or outcome["missing_required"]:
            outcome["status"] = "drift"
            if entry is None:
                outcome["detail"] = "first observation; not proposed because required keys are missing"
            print(
                f"  {source}: DRIFT detected — +{len(outcome['added'])} -{len(outcome['removed'])} fields, "
                f"{len(outcome['missing_required'])} required missing"
            )
        elif entry is None:
            outcome.update(status="new", detail="first observation; proposed in report, not applied to baseline")
            print(f"  {source}: new — baseline proposal ({len(keys)} keys) awaiting review")
        else:
            outcome["status"] = "unchanged"
            print(f"  {source}: no drift")

    total = len(outcomes)
    checked = sum(o["status"] in CHECKED_STATUSES for o in outcomes)
    failed = sum(o["status"] == "fetch_failed" for o in outcomes)
    any_drift = any(o["status"] == "drift" for o in outcomes)
    any_new = any(o["status"] == "new" for o in outcomes)

    if baseline_status != "ok":
        status = "baseline_error"
    elif checked == 0:
        status = "inconclusive"
    elif any_drift:
        status = "drift"
    elif checked < total:
        status = "partial"
    elif any_new:
        status = "proposed"
    else:
        status = "verified_no_change"

    result = {
        "drift_detected": any_drift,
        "new_sources": any_new,
        "status": status,
        "baseline_status": baseline_status,
        "baseline_detail": baseline_detail,
        "coverage": {"total": total, "checked": checked, "failed": failed, "inconclusive": total - checked - failed},
        "sources": outcomes,
        "report_path": None,
    }

    # Always write the dated report, including when nothing could be checked.
    try:
        DRIFT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = DRIFT_DIR / f"{TODAY}.md"
        report_path.write_text(_drift_report(result) + "\n", encoding="utf-8")
        result["report_path"] = str(report_path)
        print(f"  Drift report: {report_path}")
    except OSError as exc:
        result["report_error"] = str(exc)
        print(f"  Drift report not written: {exc}")

    return result


# ── Summary ────────────────────────────────────────────────────────────────────

# Only a fully verified run may be summarised as "none".
DRIFT_SUMMARY_LABELS = {
    "verified_no_change": "none (all sources verified)",
    "drift": "yes",
    "partial": "no drift in checked sources — PARTIAL coverage",
    "proposed": "no drift — new baseline proposal(s) awaiting review",
    "inconclusive": "UNVERIFIED — no source could be checked",
    "baseline_error": "UNVERIFIED — reviewed baseline missing or invalid",
}


def print_summary(hygiene: dict, freshness: dict, drift: dict) -> None:
    print("\n" + "=" * 60)
    print(f"Nightly Improve Summary — {TODAY}")
    print("=" * 60)

    ruff = "fixed + committed" if hygiene["ruff_fixed"] else "nothing to fix"
    mypy = "clean" if hygiene["mypy_clean"] else f"{len(hygiene['mypy_errors'])} error(s)"
    print(f"  Hygiene:   ruff={ruff}, mypy={mypy}")

    updated = freshness.get("updated", [])
    fresh_str = ", ".join(updated) if updated else "none"
    print(f"  Freshness: updated={fresh_str}")

    drift_str = DRIFT_SUMMARY_LABELS.get(drift.get("status"), "UNVERIFIED")
    cov = drift["coverage"]
    print(
        f"  Drift:     {drift_str} — checked {cov['checked']}/{cov['total']}, "
        f"failed {cov['failed']}, inconclusive {cov['inconclusive']}"
    )
    print(f"             report: {drift.get('report_path') or 'not written'}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Running nightly_improve.py at {datetime.now(tz=timezone.utc).isoformat(timespec='seconds')} …")
    hygiene = run_hygiene()
    freshness = refresh_skill_examples()
    drift = check_schema_drift()
    print_summary(hygiene, freshness, drift)
    return 0  # always exit 0


if __name__ == "__main__":
    sys.exit(main())

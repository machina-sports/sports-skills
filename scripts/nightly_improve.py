#!/usr/bin/env python3
"""Nightly self-improvement script for sports-skills.

Tier 1 autonomous fixes — runs after nightly_health_check.py.
Exit 0 always: best-effort, never blocks the pipeline.

Tasks:
  1. Code Hygiene  — ruff auto-fix + mypy report
  2. SKILL.md Freshness — refresh live example output
  3. Schema Baseline — detect API drift, update baseline
"""

import gzip
import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC_DIR = REPO_ROOT / "src"
SKILLS_DIR = REPO_ROOT / "skills"
REPORTS_DIR = REPO_ROOT / "reports"
DRIFT_DIR = REPORTS_DIR / "drift"
BASELINE_PATH = SCRIPTS_DIR / "schema_baseline.json"

TODAY = datetime.now(tz=UTC).strftime("%Y-%m-%d")
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

def _extract_top_keys(body: bytes, url: str) -> list[str] | None:
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return sorted(data.keys())
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return sorted(data[0].keys())
        return []
    except Exception:
        return None


def check_schema_drift() -> dict:
    print("\n── Task 3: Schema Baseline & Drift ──")

    # Load existing baseline
    if BASELINE_PATH.exists():
        baseline: dict = json.loads(BASELINE_PATH.read_text())
    else:
        baseline = {}

    DRIFT_DIR.mkdir(parents=True, exist_ok=True)
    drift_lines: list[str] = [f"# Schema Drift Report — {TODAY}", ""]
    any_drift = False
    any_new = False

    for source, config in BASELINE_SOURCES.items():
        url = config["url"]
        required = config.get("required_keys")
        body, err = _fetch(url)

        if err or not body:
            print(f"  {source}: fetch failed ({err}) — skipping")
            drift_lines.append(f"## {source}: ⚠️ fetch failed — {err}")
            continue

        live_keys = _extract_top_keys(body, url)
        if live_keys is None:
            print(f"  {source}: parse failed — skipping")
            continue

        if source not in baseline:
            # First time — establish baseline
            baseline[source] = {"keys": live_keys, "first_seen": TODAY}
            any_new = True
            print(f"  {source}: baseline established ({len(live_keys)} keys)")
            continue

        stored_keys = set(baseline[source].get("keys", []))
        live_key_set = set(live_keys)

        added = sorted(live_key_set - stored_keys)
        removed = sorted(stored_keys - live_key_set)
        missing_required = [k for k in (required or []) if k not in live_key_set]

        if added or removed or missing_required:
            any_drift = True
            drift_lines.append(f"## {source}")
            if added:
                drift_lines.append(f"- **New fields:** `{'`, `'.join(added)}`")
            if removed:
                drift_lines.append(f"- **Removed fields:** `{'`, `'.join(removed)}`")
            if missing_required:
                drift_lines.append(f"- **⚠️ Missing required:** `{'`, `'.join(missing_required)}`")
            drift_lines.append("")
            # Update baseline with latest keys
            baseline[source]["keys"] = sorted(live_key_set)
            baseline[source]["last_drift"] = TODAY
            print(f"  {source}: DRIFT detected — +{len(added)} -{len(removed)} fields")
        else:
            print(f"  {source}: no drift")

    # Write updated baseline
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n")

    # Write drift report only if there's something to report
    if any_drift:
        drift_path = DRIFT_DIR / f"{TODAY}.md"
        drift_path.write_text("\n".join(drift_lines) + "\n")
        print(f"  Drift report: {drift_path}")

    if any_drift or any_new:
        _git_commit(f"chore: update schema baseline {TODAY}")

    return {"drift_detected": any_drift, "new_sources": any_new}


# ── Summary ────────────────────────────────────────────────────────────────────

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

    drift_str = "yes — see reports/drift/" if drift["drift_detected"] else "none"
    print(f"  Drift:     {drift_str}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Running nightly_improve.py at {datetime.now(tz=UTC).isoformat(timespec='seconds')} …")
    hygiene = run_hygiene()
    freshness = refresh_skill_examples()
    drift = check_schema_drift()
    print_summary(hygiene, freshness, drift)
    return 0  # always exit 0


if __name__ == "__main__":
    sys.exit(main())

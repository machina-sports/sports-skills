#!/usr/bin/env python3
"""Build the sports-skills.sh marketplace from SKILL.md files.

Environment:
  SITE_BASE_URL          canonical origin for meta/og/sitemap URLs (default https://sports-skills.sh)
  SITE_ENV               "staging" adds noindex, a disallow-all robots.txt and a preview badge
  SITE_FETCH_STATS       "1" fetches GitHub/PyPI numbers at build time (off by default so tests
                         and offline builds never touch the network); GITHUB_TOKEN is used if set
  MACHINA_TEMPLATES_DIR  checkout of machina-templates for the Pro tier
"""

# `dict | None` annotations below must not be evaluated on Python 3.9.
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.request
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

# ── Paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # repo root
SITE = Path(__file__).resolve().parent         # site/
TEMPLATES = SITE / "templates"
STATIC = SITE / "static"
DIST = SITE / "dist"
CATALOG = ROOT / "skills" / "catalog.json"
PACKAGE_INIT = ROOT / "src" / "sports_skills" / "__init__.py"

# Pro-tier source — checked out by CI as a sibling, overridable for local runs
# that have it in a non-standard location.
MACHINA_TEMPLATES = Path(
    os.environ.get("MACHINA_TEMPLATES_DIR", str(ROOT.parent / "machina-templates"))
).resolve()

SKILL_SOURCES = [
    {"path": ROOT / "skills", "tier": "open"},
    {"path": MACHINA_TEMPLATES / "skills", "tier": "pro"},
    {"path": MACHINA_TEMPLATES / "connectors", "tier": "pro", "scan": "*/skills/"},
]

# Skill slug → sports_skills.cli module name. Skills not listed here either have
# no CLI surface (machina, sports-reporter, pro templates) or rename their
# module (e.g. football-data → football).
SLUG_TO_CLI_MODULE = {
    "football-data": "football",
    "nfl-data": "nfl",
    "nba-data": "nba",
    "wnba-data": "wnba",
    "nhl-data": "nhl",
    "mlb-data": "mlb",
    "tennis-data": "tennis",
    "cfb-data": "cfb",
    "cbb-data": "cbb",
    "golf-data": "golf",
    "cricket-data": "cricket",
    "volleyball-data": "volleyball",
    "xctf-data": "xctf",
    "fastf1": "f1",
    "esports": "esports",
    "sports-news": "news",
    "kalshi": "kalshi",
    "polymarket": "polymarket",
    "polymarket-trading": "polymarket-trading",
    "prophetx": "prophetx",
    "betting": "betting",
    "markets": "markets",
    "metadata": "metadata",
}

# CLI module → Python import name, where they differ (the CLI routes
# polymarket-trading to the polymarket package).
CLI_TO_PY_MODULE = {
    "polymarket-trading": "polymarket",
}

# Skills whose Python backend needs a pip extra (see pyproject optional-dependencies).
PIP_EXTRAS = {
    "fastf1": "f1",
    "nfl-data": "nfl",
}


def _cli_registry():
    """Return sports_skills.cli._REGISTRY if importable, else None.

    Used to augment SKILL.md command tables with any CLI-registered commands
    they omit. Optional — the build still works without the package installed,
    it just falls back to whatever the SKILL.md table happens to list.
    """
    try:
        from sports_skills.cli import _REGISTRY  # type: ignore
        return _REGISTRY
    except ImportError:
        return None


CLI_REGISTRY = _cli_registry()

BASE_URL = os.environ.get("SITE_BASE_URL", "https://sports-skills.sh").rstrip("/")
SITE_ENV = os.environ.get("SITE_ENV", "production")
REPO_URL = "https://github.com/machina-sports/sports-skills"
REPO_API = "https://api.github.com/repos/machina-sports/sports-skills"

# ── Category mapping ───────────────────────────────────────────────────
CATEGORY_MAP = {
    "kalshi": "Prediction Markets",
    "polymarket": "Prediction Markets",
    "prophetx": "Prediction Markets",
    "markets": "Prediction Markets",
    "betting": "Prediction Markets",
    "polymarket-trading": "Prediction Markets",
    "football-data": "Football",
    "nfl-data": "US Sports",
    "nba-data": "US Sports",
    "wnba-data": "US Sports",
    "nhl-data": "US Sports",
    "mlb-data": "US Sports",
    "cfb-data": "College",
    "cbb-data": "College",
    "xctf-data": "College",
    "tennis-data": "Global Sports",
    "golf-data": "Global Sports",
    "fastf1": "Global Sports",
    "cricket-data": "Global Sports",
    "volleyball-data": "Global Sports",
    "esports": "Global Sports",
    "sports-news": "News & Tools",
    "sports-reporter": "News & Tools",
    "metadata": "News & Tools",
    "espn-api": "News & Tools",
    "machina": "Machina",
    "world-cup": "Machina",
    "mkn-constructor": "Machina",
    "machina-agent-builder": "Machina",
    "polymarket-sync-events": "Machina",
    "polymarket-sync-series": "Machina",
    "polymarket-sync-markets": "Machina",
}

CATEGORY_ORDER = [
    "Prediction Markets",
    "Football",
    "US Sports",
    "College",
    "Global Sports",
    "News & Tools",
    "Machina",
    "Other",
]

# Per-category presentation: icon id (see the sprite in base.html) and tone
# (CSS class suffix: green = sports data, amber = markets, cyan = Machina).
CATEGORY_META = {
    "Prediction Markets": {"icon": "markets", "tone": "amber"},
    "Football": {"icon": "soccer", "tone": "green"},
    "US Sports": {"icon": "football", "tone": "green"},
    "College": {"icon": "college", "tone": "green"},
    "Global Sports": {"icon": "globe", "tone": "green"},
    "News & Tools": {"icon": "news", "tone": "slate"},
    "Machina": {"icon": "spark", "tone": "cyan"},
    "Other": {"icon": "trophy", "tone": "slate"},
}

# Kept for templates and callers that still read `category_color`.
CATEGORY_COLORS = {cat: meta["tone"] for cat, meta in CATEGORY_META.items()}

SKILL_ICONS = {
    "football-data": "soccer",
    "nfl-data": "football",
    "nba-data": "basketball",
    "wnba-data": "basketball",
    "nhl-data": "hockey",
    "mlb-data": "baseball",
    "cfb-data": "football",
    "cbb-data": "basketball",
    "xctf-data": "stopwatch",
    "tennis-data": "tennis",
    "golf-data": "golf",
    "fastf1": "gauge",
    "cricket-data": "cricket",
    "volleyball-data": "volleyball",
    "esports": "gamepad",
    "kalshi": "candles",
    "polymarket": "pie",
    "prophetx": "exchange",
    "markets": "dashboard",
    "betting": "calculator",
    "polymarket-trading": "zap",
    "sports-news": "news",
    "sports-reporter": "pen",
    "metadata": "image",
    "espn-api": "code",
    "machina": "spark",
    "world-cup": "globe",
    "mkn-constructor": "blocks",
    "machina-agent-builder": "bot",
}

# One-line "what's covered" label for cards. Hand-kept like DATA_SOURCES; a
# missing entry simply falls back to the data source line.
SKILL_HIGHLIGHTS = {
    "football-data": "EPL · La Liga · Bundesliga · Serie A · UCL · MLS +",
    "nfl-data": "NFL · nflverse play-by-play · fantasy trends",
    "nba-data": "NBA · shot charts · history to 1946",
    "wnba-data": "WNBA · win probability · transactions",
    "nhl-data": "NHL · on-ice coordinates · history to 1917",
    "mlb-data": "MLB · pitch-level data · history to 1901",
    "cfb-data": "NCAA FBS + FCS · drive context",
    "cbb-data": "NCAA D-I/II/III · March Madness bracket",
    "xctf-data": "NCAA cross country & track PRs",
    "tennis-data": "ATP · WTA · rankings · entry lists",
    "golf-data": "PGA Tour · LPGA · DP World Tour",
    "fastf1": "Formula 1 · laps · sectors · tyres",
    "cricket-data": "Series · ball-by-ball history",
    "volleyball-data": "Dutch volleyball pyramid",
    "esports": "Dota 2 · League of Legends",
    "kalshi": "CFTC-regulated event contracts",
    "polymarket": "Moneyline · spreads · totals · props",
    "prophetx": "Exchange markets & odds",
    "markets": "ESPN × Kalshi × Polymarket",
    "betting": "De-vig · edge · Kelly · arbitrage",
    "polymarket-trading": "Wallet-backed orders · approval required",
    "sports-news": "RSS · Atom · Google News",
    "sports-reporter": "Previews · recaps · profiles",
    "metadata": "Logos · player photos · venues",
    "espn-api": "Raw ESPN reference for long-tail leagues",
    "machina": "Licensed feeds via machina-cli + MCP",
    "world-cup": "FIFA World Cup 2026 intelligence",
    "mkn-constructor": "Deprecated alias of machina-agent-builder",
    "machina-agent-builder": "Build, validate & install Machina agent templates",
}

# Skills kept only as compatibility aliases: still listed, badged, and left out
# of the homepage's Pro showcase.
DEPRECATED_ALIASES = {
    "mkn-constructor": "machina-agent-builder",
}

# ── Data source mapping (per slug, fallback to "Community data") ──────
DATA_SOURCES = {
    "kalshi": "Kalshi API",
    "polymarket": "Polymarket API",
    "prophetx": "ProphetX API",
    "polymarket-trading": "Polymarket CLOB",
    "betting": "Pure computation",
    "markets": "ESPN + Kalshi + Polymarket",
    "nfl-data": "ESPN, nflverse, Sleeper",
    "nba-data": "ESPN, NBA CDN, NBA Stats",
    "wnba-data": "ESPN",
    "nhl-data": "ESPN, NHL API",
    "mlb-data": "ESPN, MLB Stats API",
    "football-data": "ESPN, Understat, FPL, Transfermarkt, ClubElo",
    "cfb-data": "ESPN, NCAA",
    "cbb-data": "ESPN, NCAA",
    "tennis-data": "ESPN, WTA",
    "golf-data": "ESPN",
    "fastf1": "FastF1 (open-source)",
    "cricket-data": "ESPN, Cricsheet",
    "esports": "OpenDota, Leaguepedia (Cargo)",
    "volleyball-data": "Nevobo API",
    "xctf-data": "TFRRS, The Stride Report",
    "metadata": "TheSportsDB",
    "espn-api": "ESPN",
    "sports-news": "RSS / Google News",
    "sports-reporter": "RSS / Google News",
    "machina": "Machina Platform",
    "world-cup": "Machina Platform",
    "mkn-constructor": "Machina Platform",
    "machina-agent-builder": "Machina Platform",
    "polymarket-sync-events": "Polymarket API",
    "polymarket-sync-series": "Polymarket API",
    "polymarket-sync-markets": "Polymarket API",
}

# catalog.json `mode` → badge label and tone.
MODE_LABELS = {
    "read_only": ("Read-only", "green"),
    "compute": ("Pure compute", "slate"),
    "premium_mcp": ("Premium MCP", "cyan"),
    "premium_mcp_read_only": ("Premium MCP · read-only", "cyan"),
    "financial_execution": ("Executes trades", "red"),
}
RISK_TONES = {"low": "green", "medium": "amber", "high": "amber", "critical": "red"}

# espn-api's documented slug inventory — a reference list, not runtime coverage.
ESPN_LEAGUE_SLUGS = ROOT / "skills" / "espn-api" / "references" / "league-slugs.md"


# ── Parsing ────────────────────────────────────────────────────────────
def espn_reference_inventory(path: Path = ESPN_LEAGUE_SLUGS) -> dict | None:
    """Count sport sections and league rows documented in espn-api's league-slugs.md.

    A sport section is a `## ... (sport: `x`)` heading; a league row is a table
    row in one whose second cell is a backticked slug. Other sections (conference
    IDs, CDN slugs) are not counted. Returns None when the file is absent.
    """
    if not path.exists():
        return None
    sports = leagues = 0
    in_sport = False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            in_sport = "(sport: `" in line
            sports += in_sport
        elif in_sport and re.match(r"^\|[^|]+\|\s*`[^`]+`\s*\|", line):
            leagues += 1
    return {"sports": sports, "leagues": leagues}



def parse_skill_md(path: Path) -> dict | None:
    """Parse a SKILL.md file into a dict with frontmatter and content."""
    text = path.read_text(encoding="utf-8")

    # Split frontmatter. Every SKILL.md in this repo is expected to have YAML
    # frontmatter per the Agent Skills spec — skip files that don't.
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    return {"frontmatter": fm, "body": body}


def extract_commands(body: str) -> list[dict]:
    """Extract commands from markdown tables that begin with a `Command` column.

    Handles both 2-column tables (`| Command | Description |`) and wider tables
    like sports-news / metadata (`| Command | Required | Optional | Description |`)
    by taking the first cell as the name and the last cell as the description.

    Falls back to parsing `sports-skills <module> <cmd>` invocations from
    `## Quick Start` bash blocks for skills (betting, markets) that document
    commands as one-liners rather than tables.
    """
    commands = []
    seen = set()

    # Pass 1: markdown table starting with "| Command |" (any number of columns).
    lines = body.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\|\s*Command\s*\|", stripped, re.IGNORECASE):
            in_table = True
            continue
        if in_table and stripped.startswith("|") and re.match(r"^\|\s*[-:]+", stripped):
            continue  # separator row
        if in_table and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) >= 2:
                name = re.sub(r"`", "", cells[0]).strip()
                # "get_nbastats_game_log (player rows)" names a variant of a command
                # already listed; keep the command name only.
                name = re.sub(r"\s*\(.*\)\s*$", "", name)
                desc = cells[-1].strip()
                if name and not name.startswith("---") and name not in seen:
                    commands.append({"name": name, "description": desc})
                    seen.add(name)
        elif in_table and not stripped.startswith("|"):
            in_table = False

    if commands:
        return commands

    # Pass 2: parse Quick Start bash blocks for `sports-skills <module> <cmd>` lines.
    in_quickstart = False
    in_code = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#+\s*Quick Start", stripped, re.IGNORECASE):
            in_quickstart = True
            continue
        if in_quickstart and re.match(r"^#+\s", stripped):
            in_quickstart = False
            continue
        if in_quickstart and stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_quickstart and in_code:
            m = re.match(r"^\s*sports-skills\s+\S+\s+(\w+)", stripped)
            if m:
                name = m.group(1)
                if name not in seen:
                    commands.append({"name": name, "description": ""})
                    seen.add(name)
    return commands


def extract_examples(body: str) -> list[str]:
    """Extract example prompts — lines matching quoted strings under example headings."""
    examples = []
    lines = body.split("\n")
    in_examples = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#+\s*(Example|Usage)", stripped, re.IGNORECASE):
            in_examples = True
            continue
        if in_examples and re.match(r"^#+\s", stripped) and not re.match(r"^#+\s*(Example|Usage)", stripped, re.IGNORECASE):
            in_examples = False
            continue
        if in_examples:
            # Match "User says: ..." pattern
            m = re.match(r'User says:\s*"(.+)"', stripped)
            if m:
                examples.append(m.group(1))
    return examples[:5]


def _augment_with_cli(slug: str, commands: list[dict]) -> list[dict]:
    """Append any CLI-registered commands that aren't already in the SKILL.md table.

    SKILL.md tables are curated and sometimes lag the CLI (e.g. kalshi's
    `get_sports_config` / `get_todays_events` / `search_markets`, polymarket's
    trading commands). For the marketplace we want the full surface visible —
    SKILL.md descriptions win when present; CLI-only commands appear with an
    empty description.
    """
    if CLI_REGISTRY is None:
        return commands
    module = SLUG_TO_CLI_MODULE.get(slug)
    if module is None or module not in CLI_REGISTRY:
        return commands

    have = {c["name"] for c in commands}
    for cmd_name in CLI_REGISTRY[module]:
        if cmd_name not in have:
            commands.append({"name": cmd_name, "description": ""})
            have.add(cmd_name)
    return commands


def inline_md(text: str) -> Markup:
    """Escape text, then render `code` and **bold** spans — enough for SKILL.md table cells."""
    html = str(escape(text))
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    return Markup(html)


def _attach_params(slug: str, commands: list[dict]) -> list[dict]:
    """Add the CLI's required/optional parameter names to each command, when known."""
    module = SLUG_TO_CLI_MODULE.get(slug)
    spec = (CLI_REGISTRY or {}).get(module or "", {})
    for cmd in commands:
        info = spec.get(cmd["name"]) or {}
        cmd["required"] = list(info.get("required", []))
        cmd["optional"] = list(info.get("optional", []))
        cmd["description_html"] = inline_md(cmd["description"])
    return commands


def body_intro(body: str, limit: int = 2) -> list[str]:
    """The first prose paragraphs of a SKILL.md body (blockquotes included), stopping
    at the first heading, table, list or code fence that follows them."""
    paras, cur = [], []
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith(("#", "|", "```", "- ", "* ")):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            if paras:
                break
            continue
        if not s:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s.lstrip(">").strip())
    if cur:
        paras.append(" ".join(cur))
    return paras[:limit]


def _quickstart(commands: list[dict]) -> dict | None:
    """The Quick Start example: the first command that runs without arguments,
    else the first command with placeholders for its required parameters."""
    if not commands:
        return None
    cmd = next((c for c in commands if not c.get("required")), commands[0])
    required = cmd.get("required", [])
    return {
        "name": cmd["name"],
        "cli_args": "".join(f" --{p}=<{p}>" for p in required),
        "py_args": ", ".join(f'{p}="..."' for p in required),
    }


def load_catalog(path: Path = CATALOG) -> dict:
    """Per-skill capability and risk metadata from skills/catalog.json ({} when absent)."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("skills", {})


CATALOG_SKILLS = load_catalog()


def _safety(slug: str) -> dict | None:
    """Badge-ready view of a skill's catalog.json entry, or None for uncatalogued skills."""
    entry = CATALOG_SKILLS.get(slug)
    if not entry:
        return None
    mode = entry.get("mode", "")
    label, tone = MODE_LABELS.get(mode, (mode.replace("_", " ").capitalize(), "slate"))
    risk = entry.get("risk", "")
    return {
        "mode": mode,
        "mode_label": label,
        "mode_tone": tone,
        "risk": risk,
        "risk_tone": RISK_TONES.get(risk, "slate"),
        "money_movement": bool(entry.get("money_movement")),
        "secrets_required": bool(entry.get("secrets_required")),
        "external_network": bool(entry.get("external_network")),
        "requires_confirmation": bool(entry.get("requires_explicit_confirmation")),
        "untrusted_content": bool(entry.get("untrusted_content")),
    }


def load_skill(slug: str, skill_dir: Path, tier: str) -> dict:
    """Load a single skill from its directory."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    parsed = parse_skill_md(skill_md)
    if not parsed:
        return None

    fm = parsed["frontmatter"]
    body = parsed["body"]
    meta = fm.get("metadata", {}) or {}

    name = fm.get("name", slug)
    description_raw = fm.get("description", "")
    # Fallback: if no frontmatter description, use first paragraph after the heading
    if not description_raw.strip() and body:
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("|") and not stripped.startswith("-") and not stripped.startswith("```"):
                description_raw = stripped
                break
    # Extract human-friendly description: everything before "Use when:" / "Don't use when:"
    human_desc_lines = []
    for line in description_raw.strip().split("\n"):
        stripped = line.strip()
        if re.match(r"(Use when|Don't use when|Don.t use when)", stripped, re.IGNORECASE):
            break
        if stripped:
            human_desc_lines.append(stripped)
    human_desc = " ".join(human_desc_lines).strip()

    # Short desc: first sentence for cards
    short_desc = human_desc_lines[0] if human_desc_lines else ""
    if len(short_desc) > 200:
        dot = short_desc.find(". ", 0, 200)
        if dot > 0:
            short_desc = short_desc[: dot + 1]

    commands = extract_commands(body)
    commands = _augment_with_cli(slug, commands)
    commands = _attach_params(slug, commands)
    examples = extract_examples(body)
    category = CATEGORY_MAP.get(slug, "Other")
    category_meta = CATEGORY_META.get(category, CATEGORY_META["Other"])
    cli_module = SLUG_TO_CLI_MODULE.get(slug) if commands else None
    extra = PIP_EXTRAS.get(slug)

    return {
        "slug": slug,
        "name": name,
        "description": short_desc,
        "description_human": human_desc,
        "description_human_html": inline_md(human_desc),
        # Pro SKILL.md descriptions are agent routing text; their body intro reads better.
        "intro_html": [inline_md(p) for p in body_intro(body)] if tier == "pro" else [],
        "category": category,
        "category_color": category_meta["tone"],
        "category_icon": category_meta["icon"],
        "icon": SKILL_ICONS.get(slug, category_meta["icon"]),
        "highlight": SKILL_HIGHLIGHTS.get(slug, ""),
        "deprecated_for": DEPRECATED_ALIASES.get(slug),
        "tier": tier,
        "version": meta.get("version", ""),
        "author": meta.get("author", "machina-sports"),
        "license": fm.get("license", "MIT" if tier == "open" else "Proprietary"),
        "commands": commands,
        "command_count": len(commands),
        "examples": examples,
        "data_source": DATA_SOURCES.get(slug, "Community data"),
        "data_sources": [s.strip() for s in re.split(r",|\+", DATA_SOURCES.get(slug, "Community data")) if s.strip()],
        # CLI module and Python import for the Quick Start; None for prompt-only skills
        # and for skills whose module is unknown (the template falls back to the slug).
        "cli_module": cli_module,
        "py_module": CLI_TO_PY_MODULE.get(cli_module, cli_module) if cli_module else None,
        "quickstart": _quickstart(commands),
        "pip_install": f'pip install "sports-skills[{extra}]"' if extra else "pip install sports-skills",
        "safety": _safety(slug) if tier == "open" else None,
        "url": f"{BASE_URL}/{slug}/",
        "source_url": f"{REPO_URL}/tree/main/skills/{slug}" if tier == "open" else None,
        "install_command": f"npx skills add machina-sports/sports-skills@{slug}" if tier == "open" else None,
    }


def load_all_skills() -> list[dict]:
    """Load skills from all configured sources."""
    skills = []
    seen_slugs = set()

    for source in SKILL_SOURCES:
        base = Path(source["path"])
        if not base.exists():
            continue
        tier = source["tier"]
        scan = source.get("scan")

        if scan:
            # Glob pattern: e.g. connectors/*/skills/*/
            for skill_dir in sorted(base.glob(scan)):
                if skill_dir.is_dir():
                    slug = skill_dir.name
                    if slug in seen_slugs:
                        continue
                    skill = load_skill(slug, skill_dir, tier)
                    if skill:
                        skills.append(skill)
                        seen_slugs.add(slug)
        else:
            for skill_dir in sorted(base.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    slug = skill_dir.name
                    if slug in seen_slugs:
                        continue
                    skill = load_skill(slug, skill_dir, tier)
                    if skill:
                        skills.append(skill)
                        seen_slugs.add(slug)

    # Sort: by category order, then alphabetically within category
    def sort_key(s):
        cat_idx = CATEGORY_ORDER.index(s["category"]) if s["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER)
        return (cat_idx, s["slug"])

    skills.sort(key=sort_key)
    return skills


# ── Project facts ──────────────────────────────────────────────────────
def package_version(path: Path = PACKAGE_INIT) -> str:
    """The sports_skills __version__, read from source so the build needs no install."""
    if not path.exists():
        return ""
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', path.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else ""


def _get_json(url: str, timeout: float = 8.0):
    headers = {"Accept": "application/json", "User-Agent": "sports-skills-site-build"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def compact_number(n: int) -> str:
    """1234 → '1.2k', 52687 → '52.7k'; small numbers stay as-is."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def fetch_project_stats() -> dict:
    """GitHub stars/forks/contributors/latest release and PyPI downloads.

    Only runs with SITE_FETCH_STATS=1. Each source fails independently; a missing
    value just hides that number on the page.
    """
    if os.environ.get("SITE_FETCH_STATS") != "1":
        return {}
    stats: dict = {}
    try:
        repo = _get_json(REPO_API)
        stats["stars"] = int(repo.get("stargazers_count", 0))
        stats["forks"] = int(repo.get("forks_count", 0))
    except Exception as e:  # noqa: BLE001 — network is best-effort
        print(f"  ! GitHub repo stats unavailable: {e}")
    try:
        people = _get_json(f"{REPO_API}/contributors?per_page=100")
        stats["contributors"] = [
            {"login": p["login"], "avatar": p["avatar_url"], "url": p["html_url"], "commits": p["contributions"]}
            for p in people
            if p.get("type") == "User" and p.get("login") not in {"claude"}
        ]
    except Exception as e:  # noqa: BLE001
        print(f"  ! GitHub contributors unavailable: {e}")
    try:
        releases = 0
        for page in range(1, 6):
            batch = _get_json(f"{REPO_API}/releases?per_page=100&page={page}")
            releases += len(batch)
            if len(batch) < 100:
                break
        stats["releases"] = releases
    except Exception as e:  # noqa: BLE001
        print(f"  ! GitHub releases unavailable: {e}")
    try:
        rel = _get_json(f"{REPO_API}/releases/latest")
        tag = rel.get("tag_name", "")
        title = (rel.get("name") or "").strip()
        # "v0.35.0 — player game logs, offseason standings, ..." → "player game logs, offseason standings"
        title = re.sub(rf"^{re.escape(tag)}\s*[—–-]\s*", "", title)
        if len(title) > 56:
            title = title[:56].rsplit(",", 1)[0]
        stats["release"] = {"tag": tag, "title": title, "url": rel.get("html_url", f"{REPO_URL}/releases")}
    except Exception as e:  # noqa: BLE001
        print(f"  ! GitHub release unavailable: {e}")
    try:
        # skills.sh install counts (the directory behind `npx skills add`).
        found = _get_json("https://skills.sh/api/search?q=sports-skills&limit=100")
        installs = {
            s["skillId"]: int(s.get("installs", 0))
            for s in found.get("skills", [])
            if s.get("source") == "machina-sports/sports-skills" and s.get("skillId")
        }
        if installs:
            stats["skill_installs"] = installs
            stats["skill_installs_label"] = compact_number(sum(installs.values()))
    except Exception as e:  # noqa: BLE001
        print(f"  ! skills.sh installs unavailable: {e}")
    try:
        overall = _get_json("https://pypistats.org/api/packages/sports-skills/overall?mirrors=false")
        total = sum(int(r.get("downloads", 0)) for r in overall.get("data", []))
        if total:
            stats["pypi_downloads"] = total
            stats["pypi_downloads_label"] = compact_number(total)
    except Exception as e:  # noqa: BLE001
        print(f"  ! PyPI downloads unavailable: {e}")
    if "stars" in stats:
        stats["stars_label"] = compact_number(stats["stars"])
    return stats


# ── Rendering ──────────────────────────────────────────────────────────
def build():
    """Main build entry point."""
    print("Loading skills...")
    skills = load_all_skills()
    print(f"  Found {len(skills)} skills")

    categories = []
    seen_cats = set()
    for s in skills:
        if s["category"] not in seen_cats:
            categories.append(s["category"])
            seen_cats.add(s["category"])
    cats = [{
        "name": cat,
        "count": sum(1 for s in skills if s["category"] == cat),
        **CATEGORY_META.get(cat, CATEGORY_META["Other"]),
    } for cat in categories]

    stats = fetch_project_stats()
    for s in skills:
        n = stats.get("skill_installs", {}).get(s["slug"])
        s["installs"] = n
        s["installs_label"] = compact_number(n) if n else None
    site = {
        "env": SITE_ENV,
        "staging": SITE_ENV == "staging",
        "version": package_version(),
        "repo_url": REPO_URL,
        "module_count": len(CLI_REGISTRY) if CLI_REGISTRY else 0,
    }
    if stats:
        print(f"  Stats: {', '.join(k for k in stats)}")

    # Set up Jinja2
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Clean and create dist
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # ── Render homepage ────────────────────────────────────────────────
    print("Rendering homepage...")
    tpl_index = env.get_template("index.html")
    total_commands = sum(s["command_count"] for s in skills)
    espn_inventory = espn_reference_inventory()
    html = tpl_index.render(
        skills=skills,
        categories=categories,
        cats=cats,
        pro_skills=[s for s in skills if s["category"] == "Machina" and not s["deprecated_for"]],
        skills_json=json.dumps([{
            "slug": s["slug"],
            "name": s["name"],
            "description": s["description"],
            "category": s["category"],
            "tier": s["tier"],
            "highlight": s["highlight"],
            "sources": s["data_source"],
            "commands": [c["name"] for c in s["commands"]],
        } for s in skills]),
        total_skills=len(skills),
        total_commands=total_commands,
        espn_inventory=espn_inventory,
        stats=stats,
        site=site,
        base_url=BASE_URL,
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")

    # ── Render skill detail pages ──────────────────────────────────────
    print("Rendering skill pages...")
    tpl_skill = env.get_template("skill.html")
    for skill in skills:
        # Related skills: up to 3 from same category, excluding self
        related = [s for s in skills if s["category"] == skill["category"] and s["slug"] != skill["slug"]][:3]
        html = tpl_skill.render(
            skill=skill,
            related=related,
            espn_inventory=espn_inventory,
            stats=stats,
            site=site,
            base_url=BASE_URL,
        )
        skill_dir = DIST / skill["slug"]
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "index.html").write_text(html, encoding="utf-8")

    # ── Generate skills.json manifest ──────────────────────────────────
    print("Generating skills.json...")
    manifest = {
        "name": "sports-skills",
        "description": "Live sports data and prediction markets for AI agents",
        "repository": REPO_URL,
        "install": "npx skills add machina-sports/sports-skills",
        "skills": [{
            "slug": s["slug"],
            "name": s["name"],
            "description": s["description"],
            "category": s["category"],
            "tier": s["tier"],
            "version": s["version"],
            "license": s["license"],
            "install": s["install_command"],
            "url": s["url"],
            "source": s["source_url"],
            "data_sources": [s["data_source"]],
            "commands": [{"name": c["name"], "description": c["description"]} for c in s["commands"]],
        } for s in skills],
    }
    (DIST / "skills.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ── Generate sitemap.xml ───────────────────────────────────────────
    print("Generating sitemap.xml...")
    urls = [BASE_URL + "/"]
    for s in skills:
        urls.append(s["url"])
    sitemap_entries = "\n".join(
        f"  <url><loc>{u}</loc></url>" for u in urls
    )
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_entries}
</urlset>"""
    (DIST / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # ── Generate robots.txt ────────────────────────────────────────────
    if site["staging"]:
        robots = "User-agent: *\nDisallow: /"
    else:
        robots = f"""User-agent: *
Allow: /
Sitemap: {BASE_URL}/sitemap.xml"""
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    # ── Copy styles.css and static assets ──────────────────────────────
    styles_src = TEMPLATES / "styles.css"
    if styles_src.exists():
        shutil.copy2(styles_src, DIST / "styles.css")
    if STATIC.exists():
        shutil.copytree(STATIC, DIST, dirs_exist_ok=True)

    print(f"Build complete: {len(skills)} skills -> {DIST}")


if __name__ == "__main__":
    build()

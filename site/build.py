#!/usr/bin/env python3
"""Build the sports-skills.sh marketplace from SKILL.md files."""

import json
import os
import re
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

# ── Paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # repo root
SITE = Path(__file__).resolve().parent         # site/
TEMPLATES = SITE / "templates"
DIST = SITE / "dist"

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
    "volleyball-data": "volleyball",
    "xctf-data": "xctf",
    "fastf1": "f1",
    "sports-news": "news",
    "kalshi": "kalshi",
    "polymarket": "polymarket",
    "betting": "betting",
    "markets": "markets",
    "metadata": "metadata",
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

BASE_URL = "https://sports-skills.sh"

# ── Category mapping ───────────────────────────────────────────────────
CATEGORY_MAP = {
    "mkn-constructor": "Machina Skills",
    "polymarket-sync-events": "Machina Skills",
    "polymarket-sync-series": "Machina Skills",
    "polymarket-sync-markets": "Machina Skills",
    "kalshi": "Prediction Markets",
    "polymarket": "Prediction Markets",
    "betting": "Prediction Markets",
    "markets": "Prediction Markets",
    "nfl-data": "US Sports",
    "nba-data": "US Sports",
    "wnba-data": "US Sports",
    "nhl-data": "US Sports",
    "mlb-data": "US Sports",
    "football-data": "Football",
    "cfb-data": "College",
    "cbb-data": "College",
    "tennis-data": "Racquet",
    "golf-data": "Golf",
    "fastf1": "Motorsport",
    "volleyball-data": "Other",
    "xctf-data": "Other",
    "sports-news": "Other",
    "sports-reporter": "Other",
    "machina": "Machina Skills",
    "world-cup": "Machina Skills",
    "metadata": "Other",
}

CATEGORY_ORDER = [
    "Machina Skills",
    "Prediction Markets",
    "US Sports",
    "Football",
    "College",
    "Racquet",
    "Golf",
    "Motorsport",
    "Other",
]

# Colors for category tag pills (CSS class suffixes)
CATEGORY_COLORS = {
    "Machina Skills": "cyan",
    "Prediction Markets": "amber",
    "US Sports": "green",
    "Football": "green",
    "College": "green",
    "Racquet": "green",
    "Golf": "green",
    "Motorsport": "green",
    "Other": "green",
}

# ── Data source mapping (per slug, fallback to "Community data") ──────
DATA_SOURCES = {
    "kalshi": "Kalshi API",
    "polymarket": "Polymarket API",
    "betting": "Pure computation",
    "markets": "ESPN + Kalshi + Polymarket",
    "nfl-data": "ESPN",
    "nba-data": "ESPN",
    "wnba-data": "ESPN",
    "nhl-data": "ESPN",
    "mlb-data": "ESPN",
    "football-data": "ESPN, Understat, FPL, Transfermarkt",
    "cfb-data": "ESPN",
    "cbb-data": "ESPN",
    "tennis-data": "ESPN",
    "golf-data": "ESPN",
    "fastf1": "FastF1 (open-source)",
    "volleyball-data": "Nevobo API",
    "xctf-data": "TFRRS, The Stride Report",
    "metadata": "TheSportsDB",
    "sports-news": "RSS / Google News",
    "sports-reporter": "RSS / Google News",
    "machina": "Machina Platform",
    "world-cup": "Machina Platform",
    "mkn-constructor": "Machina Platform",
    "polymarket-sync-events": "Polymarket API",
    "polymarket-sync-series": "Polymarket API",
    "polymarket-sync-markets": "Polymarket API",
}


# ── Parsing ────────────────────────────────────────────────────────────
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
    examples = extract_examples(body)
    category = CATEGORY_MAP.get(slug, "Other")

    return {
        "slug": slug,
        "name": name,
        "description": short_desc,
        "description_human": human_desc,
        "category": category,
        "category_color": CATEGORY_COLORS.get(category, "green"),
        "tier": tier,
        "version": meta.get("version", ""),
        "author": meta.get("author", "machina-sports"),
        "license": fm.get("license", "MIT" if tier == "open" else "Proprietary"),
        "commands": commands,
        "command_count": len(commands),
        "examples": examples,
        "data_source": DATA_SOURCES.get(slug, "Community data"),
        "url": f"{BASE_URL}/{slug}/",
        "source_url": f"https://github.com/machina-sports/sports-skills/tree/main/skills/{slug}" if tier == "open" else None,
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
    html = tpl_index.render(
        skills=skills,
        categories=categories,
        skills_json=json.dumps([{
            "slug": s["slug"],
            "name": s["name"],
            "description": s["description"],
            "category": s["category"],
            "tier": s["tier"],
            "commands": [c["name"] for c in s["commands"]],
        } for s in skills]),
        total_skills=len(skills),
        total_commands=total_commands,
        base_url=BASE_URL,
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")

    # ── Render skill detail pages ──────────────────────────────────────
    print("Rendering skill pages...")
    tpl_skill = env.get_template("skill.html")
    for skill in skills:
        # Related skills: up to 4 from same category, excluding self
        related = [s for s in skills if s["category"] == skill["category"] and s["slug"] != skill["slug"]][:4]
        html = tpl_skill.render(
            skill=skill,
            related=related,
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
        "repository": "https://github.com/machina-sports/sports-skills",
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
            "commands": s["commands"],
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
    robots = f"""User-agent: *
Allow: /
Sitemap: {BASE_URL}/sitemap.xml"""
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    # ── Copy styles.css if it exists alongside templates ───────────────
    styles_src = TEMPLATES / "styles.css"
    if styles_src.exists():
        shutil.copy2(styles_src, DIST / "styles.css")

    print(f"Build complete: {len(skills)} skills -> {DIST}")


if __name__ == "__main__":
    build()

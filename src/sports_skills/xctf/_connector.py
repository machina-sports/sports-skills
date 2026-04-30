"""TFRRS (Track & Field Results Reporting System) connector.

Fetches NCAA cross country and track & field athlete profiles from tfrrs.org
by parsing public HTML pages. No API keys required.

URL format: https://www.tfrrs.org/athletes/{id}/{School_Slug}/{First_Last}.html
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from html import unescape

import feedparser

_BASE = "https://www.tfrrs.org"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_MIN_INTERVAL = 1.0
_last_request_time = 0.0

_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300


def _throttle() -> None:
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _fetch(url: str) -> str | dict:
    """Fetch a URL and return the response body as a string."""
    now = time.monotonic()
    cached = _cache.get(url)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    _throttle()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        _cache[url] = (time.monotonic(), html)
        return html
    except urllib.error.HTTPError as e:
        return {"error": True, "message": f"HTTP {e.code}: {e.reason}", "url": url}
    except urllib.error.URLError as e:
        return {"error": True, "message": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": True, "message": str(e)}


def _strip_tags(value: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text).replace("\u2191", "")  # strip &uarr; sort-arrow glyphs
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_prs(table_html: str) -> dict[str, str]:
    """Parse the top PR summary table — cells alternate event name / mark."""
    tds = re.findall(r"<td[^>]*>(.*?)</td>", table_html, re.DOTALL | re.IGNORECASE)
    cells = [_strip_tags(td) for td in tds]
    cells = [c for c in cells if c]

    prs: dict[str, str] = {}
    i = 0
    while i < len(cells) - 1:
        event = cells[i]
        mark = cells[i + 1]
        # Mark should start with a digit (time or distance), not a letter
        if event and mark and mark[:1].isdigit():
            prs[event] = mark
            i += 2
        else:
            i += 1
    return prs


def _parse_meet_table(table_html: str) -> dict | None:
    """Parse a single meet result table into meet name, date, and results.

    Returns None if the first row does not contain a date — this filters out
    per-event cumulative tables (season bests, year bests) that share the same
    section HTML but are not meet result tables.
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
    if not rows:
        return None

    meet_name = ""
    meet_date = ""
    results: list[dict] = []
    header_found = False

    for row_html in rows:
        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.DOTALL | re.IGNORECASE
        )
        texts = [_strip_tags(c) for c in cells]
        texts = [t for t in texts if t]
        if not texts:
            continue

        row_text = " ".join(texts)

        if not header_found:
            # First data row must contain a date to be a meet result table.
            # Per-event summary tables have no date in their header row.
            date_m = re.search(
                r"([A-Z][a-z]{2,8}\.?\s+\d{1,2}(?:[–\-]\d{1,2})?,\s*\d{4})",
                row_text,
            )
            if not date_m:
                return None
            meet_date = date_m.group(1)
            meet_name = row_text[: date_m.start()].strip().lstrip('>"').strip()
            # Per-event all-time tables start with a time/distance mark before the meet
            # name (e.g. "2:13.37 (-0.3) 2024 WAC..." or "18:25.5 Mark Covert...").
            # Real meet names may start with digits (years, ordinals) but never with
            # a time mark pattern (digits immediately followed by ':' or '.').
            if meet_name and re.match(r"^\d+[:.]\d", meet_name):
                return None
            header_found = True
            continue

        # Subsequent rows: event, mark[, place]
        if len(texts) >= 2:
            result: dict = {"event": texts[0], "mark": texts[1]}
            if len(texts) >= 3:
                result["place"] = texts[2]
            results.append(result)

    if not header_found:
        return None

    return {"meet": meet_name, "date": meet_date, "results": results}


def _parse_athlete_profile(html: str) -> dict:
    """Parse a full TFRRS athlete profile HTML page."""
    # Remove scripts and styles to avoid false matches
    html = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(
        r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
    )

    # --- All h3 tags in document order ---
    # TFRRS uses h3 for: athlete name (first), school (second), season labels (rest)
    h3_matches = list(
        re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL | re.IGNORECASE)
    )

    # --- Name and eligibility from first h3 ---
    name = ""
    eligibility = ""
    if h3_matches:
        h3_text = _strip_tags(h3_matches[0].group(1))
        elig_m = re.search(r"\(([^)]+)\)", h3_text)
        if elig_m:
            eligibility = elig_m.group(1)
            name = h3_text[: elig_m.start()].strip().title()
        else:
            name = h3_text.strip().title()

    # --- School abbreviation from second h3 ---
    school = ""
    if len(h3_matches) >= 2:
        school = _strip_tags(h3_matches[1].group(1))

    # --- PRs from the first table on the page ---
    all_tables = re.findall(
        r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE
    )
    prs = _parse_prs(all_tables[0]) if all_tables else {}

    # --- Meet results ---
    # All individual meet result tables are in the section between the school h3
    # (h3_matches[1]) and the first season-label h3 (e.g. "2026 Outdoors").
    # The season-label h3 sections only contain per-event summary tables, not meets.
    season_pattern = re.compile(r"^\d{4}\s+(XC|Outdoors|Indoors)", re.IGNORECASE)
    season_h3s = [
        m for m in h3_matches if season_pattern.match(_strip_tags(m.group(1)))
    ]

    meets_section_start = h3_matches[1].end() if len(h3_matches) >= 2 else 0
    meets_section_end = season_h3s[0].start() if season_h3s else len(html)
    meets_section = html[meets_section_start:meets_section_end]

    meets: list[dict] = []
    for table_html in re.findall(
        r"<table[^>]*>(.*?)</table>", meets_section, re.DOTALL | re.IGNORECASE
    ):
        meet = _parse_meet_table(table_html)
        if meet:
            meets.append(meet)

    return {
        "name": name,
        "school": school,
        "eligibility": eligibility,
        "prs": prs,
        "meets": meets,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _parse_team_roster(html: str) -> list[dict]:
    """Extract athlete links from a TFRRS team page.

    Returns a deduplicated list of dicts with athlete_id, school, and name slugs.
    """
    # Athlete links on team pages: /athletes/{id}/{school_slug}/{name_slug}.html
    # Some entries in the top-marks section omit the .html extension.
    raw = re.findall(
        r'href="/athletes/(\d+)/([^/"]+)/([^".]+?)(?:\.html)?"',
        html,
    )
    seen: set[tuple] = set()
    athletes: list[dict] = []
    for athlete_id, school_slug, name_slug in raw:
        key = (athlete_id, school_slug, name_slug)
        if key in seen:
            continue
        seen.add(key)
        athletes.append(
            {"athlete_id": athlete_id, "school": school_slug, "name": name_slug}
        )
    return athletes


def search_athlete(*, name: str, school: str = "") -> dict:
    """Search the current XC and TF team roster pages for an athlete by name.

    Only covers athletes on the current-season roster. Graduated or
    transferred athletes will not appear — for those, retrieve their
    profile URL from tfrrs.org and use get_athlete_profile directly.

    Args:
        name: Athlete name to search for (e.g. "Lamiae Mamouni").
        school: TFRRS team slug from the team page URL
            (e.g. "CA_college_f_California_Baptist"). Both the women's and
            men's rosters are searched automatically regardless of which
            gender slug you provide.
    """
    name_parts = name.lower().split()
    matches: list[dict] = []
    seen_keys: set[tuple] = set()

    if not school:
        return {"matches": matches}

    for sport in ("xc", "tf"):
        for slug, _ in _gender_slugs(school):
            url = f"{_BASE}/teams/{sport}/{slug}.html"
            result = _fetch(url)
            if isinstance(result, dict):
                continue

            for athlete in _parse_team_roster(result):
                key = (athlete["athlete_id"], sport)
                if key in seen_keys:
                    continue
                display = athlete["name"].replace("_", " ").lower()
                if all(part in display for part in name_parts):
                    seen_keys.add(key)
                    matches.append(
                        {
                            **athlete,
                            "sport": sport,
                            "url": (
                                f"{_BASE}/athletes/{athlete['athlete_id']}"
                                f"/{athlete['school']}/{athlete['name']}.html"
                            ),
                        }
                    )

    return {"matches": matches}


def get_athlete_profile(
    *, athlete_id: str, school: str, name: str
) -> dict:
    """Fetch a TFRRS athlete profile: PRs and full results history.

    Args:
        athlete_id: TFRRS numeric athlete ID (e.g. "8579610").
        school: School slug as it appears in the TFRRS URL (e.g. "California_Baptist").
        name: Athlete name slug as it appears in the TFRRS URL (e.g. "Lamiae_Mamouni").
    """
    url = f"{_BASE}/athletes/{athlete_id}/{school}/{name}.html"
    result = _fetch(url)
    if isinstance(result, dict):
        return result  # error dict — caller wraps

    profile = _parse_athlete_profile(result)
    profile["athlete_id"] = athlete_id
    profile["url"] = url
    return profile


# ---------------------------------------------------------------------------
# Team roster
# ---------------------------------------------------------------------------


def _gender_slugs(school: str) -> list[tuple[str, str]]:
    """Return [(slug, gender_label), ...] for both genders when possible.

    TFRRS embeds gender in school slugs as ``_f_`` (women) or ``_m_`` (men).
    If neither marker is present the slug is returned as-is with label "unknown".
    """
    if "_f_" in school:
        return [(school, "women"), (school.replace("_f_", "_m_", 1), "men")]
    if "_m_" in school:
        return [(school.replace("_m_", "_f_", 1), "women"), (school, "men")]
    return [(school, "unknown")]


def get_team_roster(*, school: str, sport: str = "both") -> dict:
    """Fetch the current roster for a TFRRS team (both genders).

    Args:
        school: TFRRS team slug from the team page URL
            (e.g. "CA_college_f_Stanford" or "CA_college_m_Stanford").
            Both the women's and men's rosters are fetched automatically
            regardless of which gender slug you provide.
        sport: Which roster to fetch — "xc", "tf", or "both" (default).
    """
    sports = ["xc", "tf"] if sport == "both" else [sport]
    athletes: list[dict] = []
    seen: set[tuple] = set()

    for sp in sports:
        for slug, gender in _gender_slugs(school):
            url = f"{_BASE}/teams/{sp}/{slug}.html"
            result = _fetch(url)
            if isinstance(result, dict):
                continue
            for athlete in _parse_team_roster(result):
                key = (athlete["athlete_id"], sp)
                if key in seen:
                    continue
                seen.add(key)
                athletes.append(
                    {
                        **athlete,
                        "gender": gender,
                        "sport": sp,
                        "url": (
                            f"{_BASE}/athletes/{athlete['athlete_id']}"
                            f"/{athlete['school']}/{athlete['name']}.html"
                        ),
                    }
                )

    return {"school": school, "sport": sport, "count": len(athletes), "athletes": athletes}


# ---------------------------------------------------------------------------
# Meet results
# ---------------------------------------------------------------------------


def _parse_team_scores(html: str) -> dict:
    """Parse men's and women's team scores from the main meet index page."""
    scores: dict = {}
    for gender, table_id in (("men", "team_scores_m"), ("women", "team_scores_f")):
        table_m = re.search(
            rf'<table[^>]+id="{table_id}"[^>]*>(.*?)</table>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not table_m:
            continue
        rows = re.findall(
            r"<tr[^>]*>(.*?)</tr>", table_m.group(1), re.DOTALL | re.IGNORECASE
        )
        entries: list[dict] = []
        for row_html in rows:
            if re.search(r"<th", row_html, re.IGNORECASE):
                continue
            cells = re.findall(
                r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE
            )
            texts = [_strip_tags(c) for c in cells]
            texts = [t for t in texts if t]
            if len(texts) >= 3:
                entries.append(
                    {"rank": texts[0], "team": texts[1], "score": texts[2]}
                )
        if entries:
            scores[gender] = entries
    return scores


def _parse_compiled_results(html: str, gender: str) -> list[dict]:
    """Parse one compiled results page (men's or women's) into a list of events."""
    html = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(
        r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
    )

    events: list[dict] = []

    # Each event section is preceded by <a class="anchor" name="{event_id}"></a>
    sections = re.split(
        r'<a\s+class="anchor"[^>]*name="[^"]*"[^>]*>\s*</a>',
        html,
        flags=re.IGNORECASE,
    )

    for section in sections[1:]:
        # Event name lives in <h3 class="font-weight-500 pl-5">
        h3_m = re.search(
            r'<h3[^>]*class="[^"]*font-weight-500[^"]*pl-5[^"]*"[^>]*>(.*?)</h3>',
            section,
            re.DOTALL | re.IGNORECASE,
        )
        if not h3_m:
            continue
        event_name = _strip_tags(h3_m.group(1)).strip()
        if not event_name:
            continue

        # Wind (optional, sprint/jump events only)
        wind_m = re.search(
            r'<span[^>]*class="[^"]*wind-text[^"]*"[^>]*>(.*?)</span>',
            section,
            re.DOTALL | re.IGNORECASE,
        )
        wind = _strip_tags(wind_m.group(1)).strip() if wind_m else ""

        # Results table
        table_m = re.search(
            r"<table[^>]*>(.*?)</table>", section, re.DOTALL | re.IGNORECASE
        )
        if not table_m:
            continue

        rows = re.findall(
            r"<tr[^>]*>(.*?)</tr>", table_m.group(1), re.DOTALL | re.IGNORECASE
        )

        results: list[dict] = []
        for row_html in rows:
            # Skip field-event sub-rows (attempt breakdowns shown below each athlete)
            if "div-subRow-table" in row_html or "border-right-0" in row_html:
                continue
            # Skip header rows
            if re.search(r"<th", row_html, re.IGNORECASE):
                continue

            cells = re.findall(
                r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE
            )
            texts = [_strip_tags(c) for c in cells]
            texts = [t for t in texts if t]

            # Need at least: place, name, year, team, mark
            if len(texts) < 5:
                continue

            # Layout: PL, NAME, YEAR, TEAM, [mark(s)...], SC
            # SC is always the last column; marks are everything between TEAM and SC.
            place = texts[0]
            name = texts[1]
            year = texts[2]
            team = texts[3]
            score = texts[-1]
            marks = texts[4:-1]  # one mark for track; multiple attempts for field

            result: dict = {
                "place": place,
                "name": name,
                "year": year,
                "team": team,
                "marks": marks,
                "score": score,
            }
            results.append(result)

        event: dict = {"event": event_name, "gender": gender, "results": results}
        if wind:
            event["wind"] = wind
        events.append(event)

    return events


def get_meet_results(*, meet_id: str, slug: str) -> dict:
    """Fetch all event results and team scores from a TFRRS meet.

    Fetches the main page (team scores) plus the men's and women's compiled
    results pages (individual event results).

    Args:
        meet_id: TFRRS numeric meet ID (e.g. "95890" from
            tfrrs.org/results/95890/BU_vs_BU_Dual).
        slug: Meet name slug as it appears in the TFRRS URL
            (e.g. "BU_vs_BU_Dual").
    """
    base_url = f"{_BASE}/results/{meet_id}/{slug}"

    # --- Main page: meet metadata + team scores ---
    main_html = _fetch(base_url)
    if isinstance(main_html, dict):
        return main_html

    main_html_clean = re.sub(
        r"<script[^>]*>.*?</script>", "", main_html, flags=re.DOTALL | re.IGNORECASE
    )
    main_html_clean = re.sub(
        r"<style[^>]*>.*?</style>", "", main_html_clean, flags=re.DOTALL | re.IGNORECASE
    )

    # Meet name from panel-title h3
    meet_name = ""
    name_m = re.search(
        r'<h3[^>]*class="[^"]*panel-title[^"]*"[^>]*>(.*?)</h3>',
        main_html_clean,
        re.DOTALL | re.IGNORECASE,
    )
    if name_m:
        meet_name = _strip_tags(name_m.group(1)).strip()

    # Date and location from panel-heading-normal-text spans
    date_m = re.search(
        r"([A-Z][a-z]{2,8}\.?\s+\d{1,2}(?:[–\-]\d{1,2})?,\s*\d{4})",
        main_html_clean,
    )
    meet_date = date_m.group(1) if date_m else ""

    team_scores = _parse_team_scores(main_html_clean)

    # --- Compiled results: men's and women's ---
    events: list[dict] = []
    for gender, code in (("women", "f"), ("men", "m")):
        comp_url = f"{_BASE}/results/{meet_id}/{code}/{slug}"
        comp_html = _fetch(comp_url)
        if isinstance(comp_html, dict):
            continue
        events.extend(_parse_compiled_results(comp_html, gender))

    return {
        "meet": meet_name,
        "date": meet_date,
        "meet_id": meet_id,
        "slug": slug,
        "url": base_url,
        "team_scores": team_scores,
        "events": events,
    }


_STRIDER_FEED = "https://www.thestridereport.com/blog-feed.xml"


def get_news(*, limit: int | None = None) -> dict:
    """Fetch recent articles from The Stride Report RSS feed."""
    feed = feedparser.parse(_STRIDER_FEED)
    if feed.bozo and not feed.entries:
        return {"error": True, "message": f"Failed to fetch Stride Report feed: {feed.bozo_exception}"}

    items = []
    for entry in feed.entries:
        tags = [t.get("term", "") for t in entry.get("tags", [])]
        enclosure = ""
        for enc in entry.get("enclosures", []):
            if enc.get("href"):
                enclosure = enc["href"]
                break
        items.append({
            "title": unescape(entry.get("title", "")),
            "link": entry.get("link", ""),
            "date": entry.get("published", ""),
            "summary": unescape(entry.get("summary", "")),
            "categories": tags,
            "author": entry.get("author", ""),
            "image": enclosure,
        })

    if limit is not None:
        items = items[:limit]

    return {"source": "The Stride Report", "count": len(items), "articles": items}



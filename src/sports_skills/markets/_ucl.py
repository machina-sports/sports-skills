"""UEFA Champions League game link -> one three-way (home / draw / away) comparison.

A soccer game is three binary contracts per venue — home win, draw, away win —
settled on 90 minutes plus stoppage time. That is not the two-way moneyline the
rest of compare_market_url assumes, so a UCL link is resolved here instead:

1. The source venue's event is fetched by its validated slug/ticker and must
   carry exactly one open contract per outcome whose own rules name this
   competition, date, team (or draw) and the regulation-time settlement.
2. Exactly one ESPN UCL game on the source date ±1 day must match those
   contracts' date and both teams. Team labels match ESPN names only exactly,
   after case, accent, punctuation and club-affix (FC, CF, ...) folding.
3. The other venue's UCL listing is searched for the one event passing the
   same checks. Its failure or absence is reported, never papered over, and
   the source is never re-found through a search.

Prices are reference prices (Polymarket Yes outcome price, Kalshi last trade),
one per contract; a missing price is never inferred from the No side, the
three are never renormalized, and no arbitrage is computed.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date as _date
from datetime import timedelta

from sports_skills.markets._connector import (
    _POLY_FULL_GAME_SLUG_RE,
    _calendar_days,
    _error,
    _finite,
    _kalshi_event_date_pair,
    _normalize_name,
    _success_partial,
)

_SPORT = "ucl"
_KALSHI_SERIES = "KXUCLGAME"
_ESPN_PATH = "soccer/uefa.champions"
_SIDES = ("home", "draw", "away")

# Bounded counterpart discovery: up to 3 pages per venue (Kalshi 200 events, Polymarket 100).
_KALSHI_MAX_PAGES = 3
_POLY_MAX_PAGES = 3
_POLY_LIST_LIMIT = 100

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# Words that name a club's legal form, not the club: "FC Barcelona" is Barcelona.
_CLUB_AFFIXES = {"fc", "cf", "afc", "sc", "sk", "fk", "ac", "as", "cd", "sv", "bk"}

_POLY_WIN_RE = re.compile(r"^Will (.+) win on (\d{4}-\d{2}-\d{2})\?$")
_POLY_DRAW_RE = re.compile(r"^Will (.+?) vs\.? (.+) end in a draw\?$")
_POLY_REGULATION = "within the first 90 minutes of regular play plus stoppage time"
_KALSHI_COMPETITION = "Champions League"
# Kalshi's rules_primary template for a UCL game contract, matched whole; any other shape fails closed.
_KALSHI_RULES_RE = re.compile(
    r"^If (?:(?P<team>.+?) wins|(?P<tie>Tie) is the result of) the (?P<a>.+?) vs (?P<b>.+?) "
    r"professional Champions League soccer game originally scheduled for (?P<date>[A-Z][a-z]{2} \d{1,2}, \d{4}) "
    r"after 90 minutes plus stoppage time \(does not include extra time or penalties\), "
    r"then the market resolves to Yes\.$"
)

_SETTLEMENT_NOTE = (
    "Every contract compared here settles on 90 minutes plus stoppage time; extra time and penalties "
    "do not count. Postponement and cancellation rules differ between venues (see each contract's "
    "rules), so the venues' contracts are not equivalent and no arbitrage is computed."
)
_SCOPE_NOTE = (
    "Link resolution maps the source to the same game's three regulation-time contracts "
    "(home / draw / away) on each venue only."
)
_PRICE_NOTE = (
    "Reference prices only, one per binary contract: the Polymarket Yes outcome price and the Kalshi "
    "last trade (last_price_dollars). Not executable, not fee-adjusted, never inferred from the No "
    "side and never renormalized across the three outcomes."
)


# ============================================================
# Small helpers
# ============================================================


def _team_key(name) -> str:
    """Case/accent/punctuation/club-affix folded name; '' when nothing is left."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(w for w in _normalize_name(text).split() if w not in _CLUB_AFFIXES)


def _probability(value) -> float | None:
    """A finite 0 < p < 1 from a number or decimal string; bools and junk are None."""
    number = _finite(value)
    return number if number is not None and 0 < number < 1 else None


def _identifier(value) -> str:
    """A provider id as a stripped, case-preserved string; '' for bools, blanks and non-scalars."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    return value.strip() if isinstance(value, str) else ""


def _iso_day(value: str) -> _date | None:
    try:
        return _date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _long_date(day: _date) -> str:
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _short_date(day: _date) -> str:
    return f"{_MONTHS[day.month - 1][:3]} {day.day}, {day.year}"


def _team_side(label, identity: dict) -> str | None:
    """'home' / 'away' when the label is exactly one ESPN team's name, else None."""
    key = _team_key(label)
    sides = [side for side in ("home", "away") if key and key in identity[side]["keys"]]
    return sides[0] if len(sides) == 1 else None


def _assign(children: list, identity: dict) -> tuple[dict | None, str]:
    """Map validated children onto ESPN sides: {side: child}, or a reason."""
    sides: dict = {}
    for child in children:
        if child["kind"] == "draw":
            if {_team_side(label, identity) for label in child["labels"]} != {"home", "away"}:
                return None, f"draw contract {child['contract']} does not name both ESPN teams"
            side = "draw"
        else:
            side = _team_side(child["labels"][0], identity)
            if side is None:
                return None, (
                    f"contract {child['contract']} names '{child['labels'][0]}', which is neither "
                    f"{identity['home']['name']} nor {identity['away']['name']}"
                )
        if side in sides:
            return None, f"contracts {sides[side]['contract']} and {child['contract']} both price the {side} side"
        sides[side] = child
    return sides, ""


# ============================================================
# Polymarket
# ============================================================


def _poly_children(event: dict, slug: str) -> tuple[list | None, str]:
    """The event's three open regulation-time UCL contracts, or a reason. No ESPN needed."""
    if event.get("slug") != slug:
        return None, f"Polymarket returned event '{event.get('slug')}', not the requested '{slug}'"
    if event.get("status") != "active":
        return None, f"Polymarket event '{slug}' is {event.get('status') or 'not active'}; only open markets compare"
    if "ucl" not in {str(t).strip().lower() for t in event.get("tags") or []}:
        return None, f"Polymarket event '{slug}' is not tagged UCL"
    match = _POLY_FULL_GAME_SLUG_RE.match(slug)
    day = _iso_day(match.group(1)) if match else None
    if day is None:
        return None, f"Polymarket event '{slug}' is not a dated UCL game"

    moneylines = [m for m in event.get("markets") or [] if m.get("sports_market_type") == "moneyline"]
    if len(moneylines) != 3:
        return None, f"Polymarket event '{slug}' has {len(moneylines)} moneyline contracts, not home/draw/away"

    children, tokens = [], set()
    for m in moneylines:
        contract = _identifier(m.get("id"))
        child_slug = str(m.get("slug") or "")
        if not contract:
            return None, f"Polymarket contract '{child_slug}' carries no usable market id ({m.get('id')!r})"
        if any(c["contract"] == contract for c in children):
            return None, f"Polymarket event '{slug}' lists market id {contract} more than once"
        suffix = child_slug[len(slug) + 1 :] if child_slug.startswith(f"{slug}-") else ""
        if not re.fullmatch(r"[a-z0-9]+", suffix):
            return None, f"Polymarket contract '{child_slug}' is not a child of event '{slug}'"
        if m.get("status") != "active":
            status = m.get("status") or "not active"
            return None, f"Polymarket contract '{child_slug}' is {status}; only open markets compare"
        outcomes = m.get("outcomes") or []
        if sorted(str(o.get("name") or "") for o in outcomes) != ["No", "Yes"]:
            return None, f"Polymarket contract '{child_slug}' is not a Yes/No contract"
        rules = str(m.get("description") or "")
        if _POLY_REGULATION not in rules or f"scheduled for {_long_date(day)}" not in rules:
            return None, (
                f"Polymarket contract '{child_slug}' rules do not settle the {day.isoformat()} game "
                "on 90 minutes plus stoppage time"
            )

        question = str(m.get("question") or "")
        win, draw = _POLY_WIN_RE.match(question), _POLY_DRAW_RE.match(question)
        if draw and suffix == "draw" and "If the game ends in a draw" in rules:
            kind, labels = "draw", [draw.group(1), draw.group(2)]
        elif win and suffix != "draw" and win.group(2) == day.isoformat() and f"If {win.group(1)} wins" in rules:
            kind, labels = "team", [win.group(1)]
        else:
            return None, (
                f"Polymarket contract '{child_slug}' ('{question}') is not a {day.isoformat()} win or draw contract"
            )
        # Token ids may be absent, but a present one names exactly one outcome of one contract.
        for outcome in outcomes:
            token = _identifier(outcome.get("clob_token_id"))
            if not token:
                continue
            if token in tokens:
                return None, f"Polymarket event '{slug}' reuses CLOB token {token} across outcomes"
            tokens.add(token)
        yes = next(o for o in outcomes if o.get("name") == "Yes")
        children.append(
            {
                "kind": kind,
                "labels": labels,
                "contract": contract,
                "slug": child_slug,
                "yes": yes,
                "token": _identifier(yes.get("clob_token_id")),
            }
        )

    if [c["kind"] for c in children].count("draw") != 1:
        return None, f"Polymarket event '{slug}' does not carry exactly one draw contract"
    return children, ""


def _poly_quote(child: dict, side: str, warnings: list) -> dict | None:
    price = _probability(child["yes"].get("price"))
    if price is None:
        warnings.append(
            f"Polymarket contract {child['contract']} ({side}) has no usable Yes price "
            f"({child['yes'].get('price')!r}); quote dropped"
        )
        return None
    quote = {
        "venue": "polymarket",
        "contract": child["contract"],
        "outcome": "Yes",
        "implied_probability": price,
        "price_field": "outcome_price",
        "price_basis": "reference",
        "execution_guaranteed": False,
    }
    if child["token"]:
        quote["token_id"] = child["token"]
    return quote


def _resolve_poly(ref: dict):
    """(source metadata, children, game check, "") or (None, None, None, reason)."""
    from sports_skills import polymarket

    slug = ref["event_slug"]
    try:
        result = polymarket.get_event_details(slug=slug)
    except Exception as exc:
        return None, None, None, f"Polymarket event fetch failed for '{slug}': {exc}"
    if not result.get("status"):
        return None, None, None, f"Polymarket event fetch failed for '{slug}': {result.get('message', '')}"
    event = result.get("data") or {}
    children, reason = _poly_children(event, slug)
    if children is None:
        return None, None, None, reason

    source = {
        "venue": "polymarket",
        "url": ref["url"],
        "sport": _SPORT,
        "event_id": str(event.get("id") or ""),
        "event_slug": slug,
        "title": event.get("title", ""),
        "status": "active",
    }
    return source, children, _dated_check(children, ref["date"]), ""


def _poly_counterpart(identity: dict, report: dict) -> list:
    """Children of the ONE open Polymarket UCL event that is this ESPN game, else []."""
    from sports_skills import polymarket

    events, seen, incomplete = [], set(), ""
    for page_number in range(1, _POLY_MAX_PAGES + 1):
        offset = (page_number - 1) * _POLY_LIST_LIMIT
        try:
            result = polymarket.get_sports_events(sport=_SPORT, limit=_POLY_LIST_LIMIT, offset=offset)
        except Exception as exc:
            result = {"status": False, "message": str(exc)}
        if not result.get("status"):
            if not events:
                report.update(outcome="error", detail=f"Polymarket UCL listing failed: {result.get('message', '')}")
                return []
            incomplete = f"page {page_number} failed: {result.get('message', '')}"
            break
        page = (result.get("data") or {}).get("events") or []
        # A page that repeats events already read means the listing shifted or looped under us.
        keys = {str(e.get("id") or e.get("slug") or "") for e in page} - {""}
        if keys & seen:
            incomplete = f"page {page_number} repeated events from an earlier page"
            break
        seen |= keys
        events.extend(page)
        if len(page) < _POLY_LIST_LIMIT:
            break
    else:
        incomplete = f"stopped after {_POLY_MAX_PAGES} full pages with more events possibly remaining"

    report["count"] = len(events)
    # A counterpart is only "the one" if the whole listing was read.
    if incomplete:
        report.update(
            outcome="incomplete",
            detail=f"Polymarket UCL listing incomplete ({incomplete}); cannot establish a unique counterpart",
        )
        return []
    found, rejected = {}, []
    for event in events:
        slug = str(event.get("slug") or "")
        match = _POLY_FULL_GAME_SLUG_RE.match(slug)
        if not match or not slug.startswith(f"{_SPORT}-") or match.group(1) not in identity["dates"]:
            continue
        children, reason = _poly_children(event, slug)
        sides, reason = _assign(children, identity) if children else (None, reason)
        if sides is None:
            rejected.append(reason)
            continue
        # Keyed by event id too: two events sharing a slug are still two candidates.
        found[f"{slug} (event {_identifier(event.get('id')) or '?'})"] = sides
    return _pick(found, rejected, report, "Polymarket", "the open UCL events")


# ============================================================
# Kalshi
# ============================================================


def _kalshi_children(event: dict, ticker: str) -> tuple[list | None, str]:
    """The event's three open regulation-time UCL contracts, or a reason. No ESPN needed."""
    returned = str(event.get("event_ticker") or "").upper()
    if returned != ticker:
        return None, f"Kalshi returned event '{event.get('event_ticker')}', not the requested '{ticker}'"
    series = str(event.get("series_ticker") or _KALSHI_SERIES).upper()
    if series != _KALSHI_SERIES or ticker.split("-", 1)[0] != _KALSHI_SERIES:
        return None, f"Kalshi event '{ticker}' declares series '{series}', not '{_KALSHI_SERIES}'"
    meta = event.get("product_metadata") or {}
    if meta.get("competition") != _KALSHI_COMPETITION or meta.get("competition_scope") != "Game":
        return None, (
            f"Kalshi event '{ticker}' is a '{meta.get('competition') or 'undeclared'}' "
            f"{meta.get('competition_scope') or ''} market, not a {_KALSHI_COMPETITION} game"
        )
    if event.get("mutually_exclusive") is not True:
        return None, f"Kalshi event '{ticker}' is not declared mutually exclusive"
    iso, pair = _kalshi_event_date_pair(ticker.split("-", 1)[1])
    day = _iso_day(iso) if iso else None
    if day is None or not pair:
        return None, f"Kalshi event '{ticker}' does not name a dated matchup"

    contracts = event.get("markets") or []
    if len(contracts) != 3:
        return None, f"Kalshi event '{ticker}' has {len(contracts)} contracts, not home/draw/away"

    children = []
    for m in contracts:
        child = str(m.get("ticker") or "").upper()
        declared = str(m.get("event_ticker") or "").upper()
        if child.rsplit("-", 1)[0] != ticker or (declared and declared != ticker):
            return None, (
                f"Kalshi market '{m.get('ticker')}' (event '{m.get('event_ticker') or 'undeclared'}') "
                f"does not belong to the requested event '{ticker}'"
            )
        if m.get("status") != "active":
            return None, f"Kalshi market '{child}' is {m.get('status') or 'not active'}; only open markets compare"
        if m.get("market_type", "binary") != "binary":
            return None, f"Kalshi market '{child}' is not a binary contract"
        rules = _KALSHI_RULES_RE.match(str(m.get("rules_primary") or ""))
        if not rules or rules.group("date") != _short_date(day):
            return None, (
                f"Kalshi market '{child}' rules do not settle the {day.isoformat()} {_KALSHI_COMPETITION} "
                "game on 90 minutes plus stoppage time"
            )
        suffix, label = child.rsplit("-", 1)[1], str(m.get("yes_sub_title") or "")
        if suffix == "TIE" and label == "Tie" and rules.group("tie"):
            kind = "draw"
        elif suffix != "TIE" and label and rules.group("team") == label:
            kind = "team"
        else:
            return None, f"Kalshi market '{child}' ('{label}') is not a team-win or tie contract its rules agree with"
        matchup = frozenset({_team_key(rules.group("a")), _team_key(rules.group("b"))})
        children.append(
            {"kind": kind, "labels": [label], "contract": child, "suffix": suffix, "market": m, "matchup": matchup}
        )

    teams = [c for c in children if c["kind"] == "team"]
    suffixes = [c["suffix"] for c in teams]
    if len(teams) != 2 or pair not in (suffixes[0] + suffixes[1], suffixes[1] + suffixes[0]):
        return None, f"Kalshi event '{ticker}' contracts ({', '.join(suffixes)}) do not match its matchup '{pair}'"
    # Every contract's rules must name the same two teams, and those are exactly the team contracts.
    team_keys = frozenset(_team_key(c["labels"][0]) for c in teams)
    if len(team_keys) != 2 or any(c["matchup"] != team_keys for c in children):
        return None, f"Kalshi event '{ticker}' contract rules do not all name the matchup of its team contracts"
    # A draw contract names no team; it inherits the event's two (verified against its rules above).
    for c in children:
        if c["kind"] == "draw":
            c["labels"] = [t["labels"][0] for t in teams]
    return children, ""


def _kalshi_quote(child: dict, side: str, warnings: list) -> dict | None:
    raw = child["market"].get("last_price_dollars")
    price = _probability(raw)
    if price is None:
        warnings.append(
            f"Kalshi contract {child['contract']} ({side}) has no usable last_price_dollars ({raw!r}); quote dropped"
        )
        return None
    return {
        "venue": "kalshi",
        "contract": child["contract"],
        "implied_probability": price,
        "price_field": "last_price_dollars",
        "price_basis": "reference",
        "execution_guaranteed": False,
    }


def _resolve_kalshi(ref: dict):
    """(source metadata, children, game check, "") or (None, None, None, reason)."""
    from sports_skills import kalshi

    ticker = ref["event_ticker"]
    try:
        result = kalshi.get_event(event_ticker=ticker, with_nested_markets=True)
    except Exception as exc:
        return None, None, None, f"Kalshi event fetch failed for '{ticker}': {exc}"
    if not result.get("status"):
        return None, None, None, f"Kalshi event fetch failed for '{ticker}': {result.get('message', '')}"
    data = result.get("data") or {}
    event = dict(data.get("event") or {})
    if not event.get("markets") and data.get("markets"):
        event["markets"] = data["markets"]
    children, reason = _kalshi_children(event, ticker)
    if children is None:
        return None, None, None, reason

    source = {
        "venue": "kalshi",
        "url": ref["url"],
        "sport": _SPORT,
        "event_id": ticker,
        "series_ticker": event.get("series_ticker", ""),
        "title": event.get("title", ""),
        "status": "active",
    }
    return source, children, _dated_check(children, ref["date"]), ""


def _kalshi_counterpart(identity: dict, report: dict) -> list:
    """Children of the ONE open KXUCLGAME event that is this ESPN game, else []."""
    from sports_skills import kalshi

    events, cursor, seen, incomplete = [], "", set(), ""
    for page_number in range(1, _KALSHI_MAX_PAGES + 1):
        kwargs = {"series_ticker": _KALSHI_SERIES, "status": "open", "with_nested_markets": True, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            result = kalshi.get_events(**kwargs)
        except Exception as exc:
            result = {"status": False, "message": str(exc)}
        if not result.get("status"):
            if not events:
                detail = f"Kalshi {_KALSHI_SERIES} listing failed: {result.get('message', '')}"
                report.update(outcome="error", detail=detail)
                return []
            incomplete = f"page {page_number} failed: {result.get('message', '')}"
            break
        data = result.get("data") or {}
        page = data.get("events") or []
        events.extend(page)
        cursor = str(data.get("cursor") or "")
        if not cursor:
            break
        if not page:
            incomplete = f"page {page_number} was empty but carried a continuation cursor"
            break
        if cursor in seen:
            incomplete = f"page {page_number} repeated an earlier continuation cursor"
            break
        seen.add(cursor)
    else:
        incomplete = f"stopped after {_KALSHI_MAX_PAGES} pages with more events remaining"

    report["count"] = len(events)
    # A counterpart is only "the one" if every page was read; a partial listing cannot prove uniqueness.
    if incomplete:
        report.update(
            outcome="incomplete",
            detail=f"Kalshi {_KALSHI_SERIES} listing incomplete ({incomplete}); cannot establish a unique counterpart",
        )
        return []
    found, rejected = {}, []
    for event in events:
        ticker = str(event.get("event_ticker") or "").upper()
        iso, _pair = _kalshi_event_date_pair(ticker.split("-", 1)[1]) if "-" in ticker else (None, None)
        if not ticker.startswith(f"{_KALSHI_SERIES}-") or iso not in identity["dates"]:
            continue
        children, reason = _kalshi_children(event, ticker)
        sides, reason = _assign(children, identity) if children else (None, reason)
        if sides is None:
            rejected.append(reason)
            continue
        found[ticker] = sides
    return _pick(found, rejected, report, "Kalshi", f"open {_KALSHI_SERIES} events")


# ============================================================
# Shared resolution
# ============================================================


def _pick(found: dict, rejected: list, report: dict, venue: str, scope: str):
    """The one validated counterpart's {side: child}; ambiguity and absence are reported."""
    if len(found) > 1:
        report.update(
            outcome="unmatched",
            detail=f"ambiguous {venue} candidates: {', '.join(sorted(found))} — refusing to pick one",
        )
        return {}
    if not found:
        detail = "; ".join(rejected[:3]) or f"no {venue} event in {scope} matches this game"
        report.update(outcome="unmatched" if rejected else "empty", detail=detail)
        return {}
    report.update(outcome="ok", detail="")
    return next(iter(found.values()))


def _dated_check(children: list, iso: str):
    """Game check for the source: its contracts name this ESPN game's teams, and its date is the game's."""

    def check(identity):
        if iso not in identity["dates"]:
            return None, f"dated {iso}; this game is played {' / '.join(sorted(identity['dates']))}"
        return _assign(children, identity)

    return check


def _espn_identity(event: dict) -> dict | None:
    """Teams (with every exact name ESPN gives them), start and calendar days, from a raw scoreboard event."""
    competitions = event.get("competitions") or []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    teams = {}
    for competitor in competition.get("competitors") or []:
        team = competitor.get("team") if isinstance(competitor, dict) else None
        side = competitor.get("homeAway") if isinstance(competitor, dict) else None
        if side in ("home", "away") and isinstance(team, dict):
            fields = ("abbreviation", "displayName", "shortDisplayName", "name", "location")
            keys = {_team_key(team.get(f)) for f in fields} - {""}
            teams[side] = {"name": team.get("displayName") or team.get("name") or "", "keys": keys}
    if set(teams) != {"home", "away"} or teams["home"]["keys"] & teams["away"]["keys"]:
        return None
    start = str(event.get("date") or competition.get("date") or "")
    return {**teams, "start": start, "dates": _calendar_days(start)}


def _resolve_espn(iso: str, check) -> tuple[dict | None, str | None, dict | None, str]:
    """(identity, event id, {side: child}, "") for the ONE ESPN UCL game the source validates against."""
    from sports_skills import _espn_base

    day = _date.fromisoformat(iso)
    failures, matches = [], {}
    for offset in (-1, 0, 1):
        when = (day + timedelta(days=offset)).strftime("%Y%m%d")
        try:
            board = _espn_base.espn_request(_ESPN_PATH, "scoreboard", {"dates": when})
        except Exception as exc:
            board = {"error": True, "message": str(exc)}
        if not isinstance(board, dict) or board.get("error"):
            failures.append(f"{when}: {(board or {}).get('message') or 'unknown error'}")
            continue
        for event in board.get("events") or []:
            identity = _espn_identity(event) if isinstance(event, dict) else None
            if identity is None:
                continue
            sides, _reason = check(identity)
            if sides is None:
                continue
            raw_id = event.get("id")
            if not (isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdigit()):
                return None, None, None, (
                    f"An ESPN UCL event on {when} matches this market but has no usable event id "
                    f"({raw_id!r}); cannot confirm which game to compare"
                )
            matches[raw_id] = (identity, sides)

    if len(matches) > 1:
        return None, None, None, f"Ambiguous: ESPN UCL events {', '.join(sorted(matches))} all match this market"
    if failures:
        return None, None, None, (
            f"ESPN UCL scoreboard failed ({'; '.join(failures)}); cannot confirm which game this market prices"
        )
    if not matches:
        return None, None, None, f"No ESPN UCL game on or around {iso} matches this market's teams and date"
    event_id, (identity, sides) = next(iter(matches.items()))
    return identity, event_id, sides, ""


# ============================================================
# Entry point
# ============================================================


def compare_ucl_url(ref: dict) -> dict:
    """Three-way reference comparison for a parsed UCL link (see ``_parse_market_url``)."""
    venue = ref["venue"]
    resolve = _resolve_poly if venue == "polymarket" else _resolve_kalshi
    source, children, check, reason = resolve(ref)
    if source is None:
        return _error(reason)
    source["match_scope"] = _SCOPE_NOTE

    identity, event_id, sides, reason = _resolve_espn(ref["date"], check)
    if identity is None:
        return _error(reason, {"source_market": source})
    source["espn_event_id"] = event_id
    source["market_type"] = "three_way_moneyline"
    source["settlement_period"] = "regulation"
    source["in_downstream_search"] = True
    source["contracts"] = {side: sides[side]["contract"] for side in _SIDES}

    warnings: list = []
    other = "kalshi" if venue == "polymarket" else "polymarket"
    sources = {
        venue: {"outcome": "ok", "detail": "source link", "count": 1},
        other: {"outcome": "empty", "detail": ""},
    }
    counterpart = (_kalshi_counterpart if other == "kalshi" else _poly_counterpart)(identity, sources[other])

    quote_for = {"polymarket": _poly_quote, "kalshi": _kalshi_quote}
    side_prices = {}
    for side in _SIDES:
        quotes = []
        for name, venue_sides in ((venue, sides), (other, counterpart)):
            if side in venue_sides:
                quote = quote_for[name](venue_sides[side], side, warnings)
                if quote:
                    quotes.append(quote)
        team = "Draw" if side == "draw" else identity[side]["name"]
        lowest = min(quotes, key=lambda q: q["implied_probability"], default=None)
        side_prices[side] = {"team": team, "quotes": quotes, "lowest_reference": lowest}

    # A matched venue is complete only when it priced all three sides; fewer is partial, none is unpriced.
    for name in (venue, other):
        if sources[name]["outcome"] != "ok":
            continue
        missing = [s for s in _SIDES if not any(q["venue"] == name for q in side_prices[s]["quotes"])]
        sources[name]["missing_sides"] = missing
        if len(missing) == len(_SIDES):
            sources[name].update(outcome="unpriced", detail="no contract carried a usable reference price")
        elif missing:
            sources[name].update(outcome="partial", detail=f"no usable reference price for {', '.join(missing)}")
            warnings.append(f"{name} coverage is partial: no usable reference price for {', '.join(missing)}")
    usable = [name for name, report in sources.items() if report["outcome"] in ("ok", "partial")]

    home, away = identity["home"]["name"], identity["away"]["name"]
    data = {
        "sport": _SPORT,
        "event_id": event_id,
        "home_team": home,
        "away_team": away,
        "start_time": identity["start"],
        "market_type": "three_way_moneyline",
        "settlement_period": "regulation",
        "settlement_note": _SETTLEMENT_NOTE,
        "side_prices": side_prices,
        "arbitrage_check": None,
        "price_basis": "reference",
        "price_basis_note": _PRICE_NOTE,
        "sources": sources,
        "completeness": {
            "usable_sources": usable,
            "attempted_sources": list(sources),
            "complete": all(report["outcome"] == "ok" for report in sources.values()),
        },
        "source_market": source,
    }
    if not usable:
        if warnings:
            data["warnings"] = warnings
        return _error(f"No usable reference price for {away} @ {home} (home/draw/away)", data)
    return _success_partial(data, warnings, f"Three-way (home/draw/away) reference prices for {away} @ {home}.")

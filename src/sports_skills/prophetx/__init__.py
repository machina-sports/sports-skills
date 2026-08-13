"""ProphetX betting exchange — public tournaments, events, and market catalog.

Public read-only endpoints. No authentication required. Uses stdlib only.

Read-only by design: this package never sends credentials and never places,
modifies, or cancels wagers. It is distinct from the authenticated ProphetX
Affiliate API connector (Machina platform, separate credentialed track).

Note on odds: the public catalog can return markets whose ``selections`` are
empty (``[null, null]``) when no public book is exposed — odds fields are
optional (``selections_available`` flags each market) and are normalized as
American odds plus derived implied probability only when actually present.
"""

from __future__ import annotations

from sports_skills.prophetx._connector import (
    get_events as _get_events,
)
from sports_skills.prophetx._connector import (
    get_market as _get_market,
)
from sports_skills.prophetx._connector import (
    get_markets as _get_markets,
)
from sports_skills.prophetx._connector import (
    get_sports_config as _get_sports_config,
)
from sports_skills.prophetx._connector import (
    get_todays_events as _get_todays_events,
)
from sports_skills.prophetx._connector import (
    get_tournaments as _get_tournaments,
)
from sports_skills.prophetx._connector import (
    search_markets as _search_markets,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_tournaments(
    *,
    limit: int = 50,
    sport: str | None = None,
    next: int | None = None,  # noqa: A002 - upstream cursor param name
) -> dict:
    """Get ProphetX tournaments (leagues/competitions).

    Args:
        limit: Max tournaments to return (default: 50; upstream page default is 10).
        sport: Sport code — 'soccer', 'tennis', 'basketball', 'baseball',
            'ice-hockey', 'american-football' — or alias ('nfl', 'nba', 'mlb',
            'nhl', 'epl', 'mls', 'worldcup', ...).
        next: Pagination cursor from a previous response.
    """
    return _get_tournaments(_req(limit=limit, sport=sport, next=next))


def get_events(
    tournament_id: int,
    *,
    limit: int = 50,
    status: str | None = None,
) -> dict:
    """Get events for a ProphetX tournament.

    Args:
        tournament_id: Tournament ID from get_tournaments().
        limit: Max events to return (default: 50).
        status: Filter by event status (e.g. 'not_started').
    """
    return _get_events(_req(tournament_id=tournament_id, limit=limit, status=status))


def get_markets(
    event_id: int,
    api_version: str = "v1",
    *,
    market_type: str | None = None,
) -> dict:
    """Get markets for a ProphetX event.

    Args:
        event_id: Event ID from get_events().
        api_version: 'v1' (default) or 'v2'. v2 adds subType, category, alt
            lines (marketLines) and player props; it falls back to v1 on failure.
        market_type: Filter by market type — 'moneyline', 'spread', 'total'.

    Note: markets may carry empty ``selections`` (no public book); check the
    ``selections_available`` flag before reading odds.
    """
    return _get_markets(_req(event_id=event_id, api_version=api_version, market_type=market_type))


def get_market(
    event_id: int,
    market_id: int | str,
    *,
    api_version: str = "v1",
) -> dict:
    """Get one market from an event (filtered from the event-markets payload —
    ProphetX has no per-market public endpoint).

    Args:
        event_id: Event ID from get_events().
        market_id: Market id (e.g. 219 = Moneyline) or market_key ('19742:219').
        api_version: 'v1' (default) or 'v2'.
    """
    return _get_market(_req(event_id=event_id, market_id=market_id, api_version=api_version))


def search_markets(
    *,
    query: str | None = None,
    sport: str | None = None,
    status: str = "open",
    limit: int = 50,
    api_version: str = "v1",
) -> dict:
    """Primary tool for finding ProphetX markets by sport and keyword.

    Bounded fan-out: scans the soonest matching events of the sport's
    tournaments and returns their markets with event context.

    Args:
        query: Keyword matched against event/tournament/competitor names.
        sport: Sport code or alias — 'soccer', 'tennis', 'basketball',
            'baseball', 'ice-hockey', 'american-football', 'nfl', 'nba',
            'mlb', 'nhl', 'epl', 'mls', 'worldcup', ...
        status: Market status filter (default: 'open').
        limit: Max markets to return (default: 50).
        api_version: 'v1' (default) or 'v2' (alt lines + player props).
    """
    return _search_markets(_req(query=query, sport=sport, status=status, limit=limit, api_version=api_version))


def get_todays_events(*, sport: str | None = None, limit: int = 50) -> dict:
    """Get today's ProphetX events (UTC), optionally filtered by sport.

    Args:
        sport: Sport code or alias (see search_markets).
        limit: Max events (default: 50).
    """
    return _get_todays_events(_req(sport=sport, limit=limit))


def get_sports_config() -> dict:
    """Get available ProphetX sport codes, aliases, and live tournaments.

    Returns sport codes usable with search_markets(sport=...) and
    get_todays_events(sport=...): 'soccer', 'tennis', 'basketball',
    'baseball', 'ice-hockey', 'american-football' plus aliases
    ('nfl', 'nba', 'mlb', 'nhl', 'epl', 'mls', 'worldcup', ...).
    """
    return _get_sports_config(_req())

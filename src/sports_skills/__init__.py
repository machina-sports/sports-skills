"""sports-skills: Lightweight Python SDK for sports data."""

__version__ = "0.29.0"

from sports_skills import (
    betting,
    cbb,
    cfb,
    football,
    golf,
    kalshi,
    markets,
    metadata,
    mlb,
    nba,
    news,
    nfl,
    nhl,
    polymarket,
    tennis,
    volleyball,
    wnba,
)

# F1 is optional — requires fastf1 + pandas
try:
    from sports_skills import f1
except ImportError:
    f1 = None

__all__ = ["betting", "cbb", "cfb", "f1", "football", "golf", "kalshi", "markets", "metadata", "mlb", "nba", "news", "nfl", "nhl", "polymarket", "tennis", "volleyball", "wnba"]

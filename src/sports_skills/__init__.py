"""sports-skills: Lightweight Python SDK for sports data."""

__version__ = "0.9.8"

from sports_skills import cbb, cfb, football, golf, kalshi, mlb, nba, news, nfl, nhl, polymarket, tennis, wnba

# F1 is optional — requires fastf1 + pandas
try:
    from sports_skills import f1
except ImportError:
    f1 = None

__all__ = ["football", "f1", "polymarket", "kalshi", "news", "nfl", "nba", "wnba", "nhl", "mlb", "tennis", "cfb", "cbb", "golf"]

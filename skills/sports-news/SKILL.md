---
name: sports-news
description: |
  Sports news via RSS/Atom feeds and Google News. Fetch headlines, search by query, filter by date. Covers football news, transfer rumors, match reports, and any sport via Google News.

  Use when: user asks for recent news, headlines, transfer rumors, or articles about any sport. Good for "what's the latest on [team/player]" questions. Supports any Google News query and curated RSS feeds (BBC Sport, ESPN, The Athletic, Sky Sports).
  Don't use when: user asks for structured data like standings, scores, statistics, or xG — use the sport-specific skill instead: football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). Don't use for prediction market odds — use polymarket or kalshi. News results are text articles, not structured data.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Sports News

Before writing queries, consult `references/api-reference.md` for command parameters and `references/rss-feeds.md` for curated feed URLs.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills news fetch_items --google_news --query="Arsenal transfer" --limit=5
sports-skills news fetch_feed --url="https://feeds.bbci.co.uk/sport/football/rss.xml"
```

Python SDK (alternative):
```python
from sports_skills import news

articles = news.fetch_items(google_news=True, query="Arsenal transfer news", limit=10)
feed = news.fetch_feed(url="https://feeds.bbci.co.uk/sport/football/rss.xml")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any news command, verify:
- Dates are derived from the system prompt's `currentDate` — never hardcoded.
- `google_news=True` is always paired with a `query` parameter.
- `sort_by_date=True` is set for any "recent" or "latest" query.

## Choosing Dates

Derive the current date from the system prompt's date (e.g., `currentDate: 2026-02-16` means today is 2026-02-16).

- **"this week"**: `after = today - 7 days`
- **"recent" or "latest"**: `after = today - 3 days`
- **Specific date range**: use as-is

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `fetch_feed` | url | | Fetch an RSS/Atom feed by URL |
| `fetch_items` | | google_news, query, url, limit, after, before, sort_by_date | Fetch news from Google News or an RSS feed |

## Workflows

### Breaking News Check
1. `fetch_items --google_news --query="<topic>" --limit=5 --sort_by_date=True`
2. Present headlines with source and date.

### Topic Deep-Dive
1. `fetch_items --google_news --query="<topic>" --after=<7_days_ago> --sort_by_date=True --limit=10`
2. For curated sources, also try `fetch_feed --url="<rss_url>"`.
3. Cross-reference both for comprehensive coverage.

### Weekly Sports Roundup
1. For each sport of interest, `fetch_items --google_news --query="<sport> results" --after=<7_days_ago> --limit=5`.
2. Aggregate and present by sport.

## Examples

Example 1: Transfer news search
User says: "What's the latest Arsenal transfer news?"
Actions:
1. Derive `after` from `currentDate`: today minus 3 days
2. Call `fetch_items(google_news=True, query="Arsenal transfer news", after=<derived_date>, sort_by_date=True, limit=10)`
Result: Recent Arsenal transfer headlines with source, date, and links

Example 2: Curated RSS feed
User says: "Show me BBC Sport football headlines"
Actions:
1. Call `fetch_feed(url="https://feeds.bbci.co.uk/sport/football/rss.xml")`
Result: BBC Sport football feed title, last updated, and recent articles

Example 3: Date-filtered news
User says: "Any Champions League news from this week?"
Actions:
1. Derive `after` from `currentDate`: today minus 7 days
2. Call `fetch_items(google_news=True, query="Champions League", after=<derived_date>, sort_by_date=True, limit=10)`
Result: Champions League articles from the last 7 days, sorted newest first

## Commands that DO NOT exist — never call these

- ~~`get_news`~~ — does not exist. Use `fetch_feed` (for RSS) or `fetch_items` (for Google News search).
- ~~`search_news`~~ — does not exist. Use `fetch_items` with `google_news=True` and a `query` parameter.
- ~~`get_headlines`~~ — does not exist. Use `fetch_items` with `google_news=True`.

If a command is not listed in the Commands table above, it does not exist.

## Troubleshooting

Error: Google News returns empty results
Cause: `query` is missing or too narrow, or `google_news=True` is not set
Solution: Ensure `google_news=True` AND a `query` are both set. Try broader keywords (e.g., "Arsenal" instead of "Arsenal vs Chelsea goal")

Error: RSS feed returns an error
Cause: The feed URL may be temporarily down or the URL format has changed
Solution: Use Google News (`fetch_items` with `google_news=True`) as a fallback for the same topic

Error: Articles returned are old despite using "recent" query
Cause: `sort_by_date=True` is not set, or the `after` date filter is missing
Solution: Add `sort_by_date=True` and `after=<today - 3 days>` to ensure newest articles appear first

---
name: sports-news
description: |
  Sports news via RSS/Atom feeds and Google News. Fetch headlines, search by query, filter by date. Covers football news, transfer rumors, match reports, and any sport via Google News.

  Use when: user asks for recent news, headlines, transfer rumors, or articles about any sport. Good for "what's the latest on [team/player]" questions. Supports any Google News query and curated RSS feeds (BBC Sport, ESPN, The Athletic, Sky Sports).
  Don't use when: user asks for structured data like standings, scores, statistics, or xG — use football-data instead. Don't use for prediction market odds — use polymarket or kalshi. Don't use for F1 timing data — use fastf1. News results are text articles, not structured data.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Sports News

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

## Important Notes

- **`google_news=True` requires a `query`.** Without a query, Google News has nothing to search.
- **`url` and `google_news` are mutually exclusive.** Use one or the other, not both.
- **Always use `sort_by_date=True`** for recency queries to show newest articles first.
- Before complex fetches, run the parameter validator: `bash scripts/validate_params.sh [args]`

*For detailed reference data, see the files in the `references/` directory.*

## Choosing Dates

Derive the current date from the system prompt's date (e.g., `currentDate: 2026-02-16` means today is 2026-02-16).

- **If the user specifies a date range**, use it as-is.
- **If the user says "recent", "latest", "this week", or doesn't specify a timeframe**: Derive `after` from the system date. For "this week", use `after = today - 7 days`. For "recent" or "latest", use `after = today - 3 days`.
- **Never hardcode dates in commands.** Always derive them from the system date.
- **Always use `sort_by_date=True`** for recency queries to show newest articles first.

## Workflows

### Workflow: Breaking News Check
1. `fetch_items --google_news --query="<topic>" --limit=5 --sort_by_date=True`
2. Present headlines with source and date.

### Workflow: Topic Deep-Dive
1. `fetch_items --google_news --query="<topic>" --after=<7_days_ago> --sort_by_date=True --limit=10`
2. For curated sources, also try `fetch_feed --url="<rss_url>"`.
3. Cross-reference both for comprehensive coverage.

### Workflow: Weekly Sports Roundup
1. For each sport of interest, `fetch_items --google_news --query="<sport> results" --after=<7_days_ago> --limit=5`.
2. Aggregate and present by sport.

## Examples

User: "What's the latest Arsenal transfer news?"
1. Call `fetch_items(google_news=True, query="Arsenal transfer news", limit=10)`
2. Present headlines with source, date, and links

User: "Show me BBC Sport football headlines"
1. Call `fetch_feed(url="https://feeds.bbci.co.uk/sport/football/rss.xml")`
2. Present feed title, last updated, and recent entries

User: "Any Champions League news from this week?"
1. Derive `after` from system date: today minus 7 days
2. Call `fetch_items(google_news=True, query="Champions League", after=<derived_date>, sort_by_date=True, limit=10)`
3. Present articles filtered to the last 7 days, sorted newest first

## Error Handling & Fallbacks

- If Google News returns empty, ensure `google_news=True` AND `query` are both set. Try broader keywords.
- If RSS feed returns error, feed may be down. Use Google News as fallback.
- If articles are old, use `after` parameter with date and `sort_by_date=True`.
- **Never fabricate news headlines or article content.** If no results, state so.

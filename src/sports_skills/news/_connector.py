import time
import urllib.parse
from datetime import datetime
from email.utils import parsedate_to_datetime

from sports_skills import _feeds


def _fetch_error(err):
    """Error for a record/replay fetch failure, in this module's shape.

    HTTP errors read exactly as feedparser's own status check reports them.
    """
    if "status_code" in err:
        message = f"Failed to fetch feed. HTTP Status: {err['status_code']}"
    else:
        message = err.get("message", "Failed to fetch feed")
    error = {"status": False, "message": message}
    for flag in ("replay_miss", "replay_error"):
        if err.get(flag):
            error[flag] = True
    return error


def fetch_feed(request_data):
    """
    Fetch and parse an RSS/Atom feed.

    Args:
        request_data (dict): Dictionary containing:
            - params (dict): Dictionary with:
                - google_news (bool, optional): If True, use Google News RSS feed. Default: False
                - query (str, required if google_news=True): Search query for Google News
                - url (str, required if google_news=False): The URL of the RSS feed
                - language (str, optional): Language code for Google News (default: "en-US")
                - country (str, optional): Country code for Google News (default: "US")
                - after (str, optional): Filter articles published after this date (YYYY-MM-DD format)
                - before (str, optional): Filter articles published before this date (YYYY-MM-DD format)
                - sort_by_date (bool, optional): Sort entries by publication date (newest first). Default: False

    Returns:
        dict: Status and parsed feed data.
    """
    params = request_data.get("params")

    def _build_google_news_url(
        query, language="en-US", country="US", after=None, before=None
    ):
        lang_code = language.split("-")[0] if "-" in language else language
        ceid = f"{country}:{lang_code}"
        query_parts = [query]
        if after:
            query_parts.append(f"after:{after}")
        if before:
            query_parts.append(f"before:{before}")
        full_query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(full_query)
        encoded_country = urllib.parse.quote_plus(country)
        encoded_ceid = urllib.parse.quote_plus(ceid)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={language}&gl={encoded_country}&ceid={encoded_ceid}"
        return url

    def _parse_entry(entry):
        content = ""
        if hasattr(entry, "content"):
            content = entry.content[0].value if entry.content else ""
        elif hasattr(entry, "description"):
            content = entry.description
        elif hasattr(entry, "summary"):
            content = entry.summary
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published_iso = ""
        if published_parsed:
            published_iso = datetime.fromtimestamp(
                time.mktime(published_parsed)
            ).isoformat()
        return {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "id": entry.get("id", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "published_iso": published_iso,
            "author": entry.get("author", ""),
            "summary": entry.get("summary", ""),
            "content": content,
            "tags": [tag.term for tag in entry.tags] if hasattr(entry, "tags") else [],
        }

    def _sort_entries_by_date(entries, reverse=True):
        def get_sort_key(entry):
            published_iso = entry.get("published_iso", "")
            if published_iso:
                try:
                    return datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            published = entry.get("published", "")
            if published:
                try:
                    dt = parsedate_to_datetime(published)
                    return dt
                except (ValueError, TypeError):
                    pass
            return datetime.min if reverse else datetime.max

        return sorted(entries, key=get_sort_key, reverse=reverse)

    google_news = params.get("google_news", False)
    if isinstance(google_news, str):
        google_news = google_news.lower() in ("true", "1", "yes")
    query = params.get("query")
    url = params.get("url")
    if not url and query:
        google_news = True
    sort_by_date = params.get("sort_by_date", False)
    if isinstance(sort_by_date, str):
        sort_by_date = sort_by_date.lower() in ("true", "1", "yes")

    # Determine the URL to use
    if google_news:
        if not query:
            return {
                "status": False,
                "message": "Query is required when google_news is True. Provide query or set a feed URL.",
            }

        language = params.get("language", "en-US")
        country = params.get("country", "US")
        after = params.get("after")
        before = params.get("before")
        url = _build_google_news_url(query, language, country, after, before)
    else:
        if not url:
            return {
                "status": False,
                "message": "URL is required when google_news is False. Provide url or use a query for Google News.",
            }

    try:
        feed, err = _feeds.parse(url)
        if err is not None:
            return _fetch_error(err)

        # Check if the feed was fetched successfully
        if hasattr(feed, "status") and feed.status >= 400:
            return {
                "status": False,
                "message": f"Failed to fetch feed. HTTP Status: {feed.status}",
            }

        if feed.bozo:
            # We log the exception but continue if entries were parsed,
            # as feedparser is lenient. However, if no entries and bozo is set, it's likely a fatal error.
            if not feed.entries and not feed.feed:
                return {
                    "status": False,
                    "message": f"Failed to parse feed: {feed.bozo_exception}",
                }

        # Process feed metadata
        feed_data = {
            "title": feed.feed.get("title", ""),
            "subtitle": feed.feed.get("subtitle", ""),
            "link": feed.feed.get("link", ""),
            "language": feed.feed.get("language", ""),
            "updated": feed.feed.get("updated", ""),
            "entries": [],
        }

        # Process entries
        for entry in feed.entries:
            parsed_entry = _parse_entry(entry)
            feed_data["entries"].append(parsed_entry)

        # Sort by date if requested (newest first)
        if sort_by_date:
            feed_data["entries"] = _sort_entries_by_date(feed_data["entries"])

        return {"status": True, "data": feed_data}

    except Exception as e:
        return {"status": False, "message": f"Exception when fetching feed: {e}"}


def fetch_items(request_data):
    """
    Fetch items from an RSS/Atom feed, optionally limited by count or date.

    Args:
        request_data (dict): Dictionary containing:
            - params (dict): Dictionary with:
                - google_news (bool, optional): If True, use Google News RSS feed. Default: False
                - query (str, required if google_news=True): Search query for Google News
                - url (str, required if google_news=False): The URL of the RSS feed
                - limit (int, optional): Max number of items to return
                - language (str, optional): Language code for Google News (default: "en-US")
                - country (str, optional): Country code for Google News (default: "US")
                - after (str, optional): Filter articles published after this date (YYYY-MM-DD format)
                - before (str, optional): Filter articles published before this date (YYYY-MM-DD format)
                - sort_by_date (bool, optional): Sort entries by publication date (newest first). Default: False

    Returns:
        dict: Status and list of feed items.
    """
    params = request_data.get("params")

    def _build_google_news_url(
        query, language="en-US", country="US", after=None, before=None
    ):
        lang_code = language.split("-")[0] if "-" in language else language
        ceid = f"{country}:{lang_code}"
        query_parts = [query]
        if after:
            query_parts.append(f"after:{after}")
        if before:
            query_parts.append(f"before:{before}")
        full_query = " ".join(query_parts)
        encoded_query = urllib.parse.quote_plus(full_query)
        encoded_country = urllib.parse.quote_plus(country)
        encoded_ceid = urllib.parse.quote_plus(ceid)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={language}&gl={encoded_country}&ceid={encoded_ceid}"
        return url

    def _parse_entry(entry):
        content = ""
        if hasattr(entry, "content"):
            content = entry.content[0].value if entry.content else ""
        elif hasattr(entry, "description"):
            content = entry.description
        elif hasattr(entry, "summary"):
            content = entry.summary
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published_iso = ""
        if published_parsed:
            published_iso = datetime.fromtimestamp(
                time.mktime(published_parsed)
            ).isoformat()
        return {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "id": entry.get("id", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "published_iso": published_iso,
            "author": entry.get("author", ""),
            "summary": entry.get("summary", ""),
            "content": content,
            "tags": [tag.term for tag in entry.tags] if hasattr(entry, "tags") else [],
        }

    def _sort_entries_by_date(entries, reverse=True):
        def get_sort_key(entry):
            published_iso = entry.get("published_iso", "")
            if published_iso:
                try:
                    return datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            published = entry.get("published", "")
            if published:
                try:
                    dt = parsedate_to_datetime(published)
                    return dt
                except (ValueError, TypeError):
                    pass
            return datetime.min if reverse else datetime.max

        return sorted(entries, key=get_sort_key, reverse=reverse)

    google_news = params.get("google_news", False)
    if isinstance(google_news, str):
        google_news = google_news.lower() in ("true", "1", "yes")
    query = params.get("query")
    url = params.get("url")
    if not url and query:
        google_news = True
    sort_by_date = params.get("sort_by_date", False)
    if isinstance(sort_by_date, str):
        sort_by_date = sort_by_date.lower() in ("true", "1", "yes")
    limit = params.get("limit")

    # Determine the URL to use
    if google_news:
        if not query:
            return {
                "status": False,
                "message": "Query is required when google_news is True. Provide query or set a feed URL.",
            }

        language = params.get("language", "en-US")
        country = params.get("country", "US")
        after = params.get("after")
        before = params.get("before")
        url = _build_google_news_url(query, language, country, after, before)
    else:
        if not url:
            return {
                "status": False,
                "message": "URL is required when google_news is False. Provide url or use a query for Google News.",
            }

    try:
        feed, err = _feeds.parse(url)
        if err is not None:
            return _fetch_error(err)

        # Check if the feed was fetched successfully
        if hasattr(feed, "status") and feed.status >= 400:
            return {
                "status": False,
                "message": f"Failed to fetch feed. HTTP Status: {feed.status}",
            }

        if feed.bozo:
            # We log the exception but continue if entries were parsed,
            # as feedparser is lenient. However, if no entries and bozo is set, it's likely a fatal error.
            if not feed.entries and not feed.feed:
                return {
                    "status": False,
                    "message": f"Failed to parse feed: {feed.bozo_exception}",
                }

        # Process entries
        items = []
        for entry in feed.entries:
            parsed_entry = _parse_entry(entry)
            items.append(parsed_entry)

        # Sort by date if requested (newest first)
        if sort_by_date:
            items = _sort_entries_by_date(items)

        # Apply limit if specified
        if limit:
            try:
                limit = int(limit)
                items = items[:limit]
            except (ValueError, TypeError):
                pass  # Ignore invalid limit

        return {
            "status": True,
            "data": {
                "items": items,
                "count": len(items),
                "query": params.get("query", ""),
                "url": url,
                "athlete_id": params.get("athlete_id"),
                "athlete_value": params.get("athlete_value", {}),
            },
        }

    except Exception as e:
        return {"status": False, "message": f"Exception when fetching items: {e}"}

"""``feedparser.parse`` for remote RSS/Atom feeds, honouring ``SPORTS_SKILLS_REPLAY``.

feedparser fetches URLs itself, so it never passes through ``_http_fetch``.
In ``off`` mode — and for non-HTTP sources such as a local file — ``parse`` is
exactly ``feedparser.parse(url)``. In ``record``/``replay`` the feed bytes are
fetched through ``_replay.fetch`` and parsed from memory, so a replay never
touches the network and returns what the recording saw.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import feedparser

from sports_skills import _replay


def parse(url):
    """Return ``(feed, None)`` or ``(None, error_dict)``.

    Errors only occur in record/replay mode: ``replay_miss``/``replay_error``
    from ``_replay``, or a live fetch failure while recording. HTTP errors
    carry ``status_code``. In off mode feedparser reports failures on the feed
    itself (``status``/``bozo``), as before.
    """
    if _replay.mode() == _replay.OFF or not str(url).lower().startswith(("http://", "https://")):
        return feedparser.parse(url), None
    raw, err = _replay.fetch(url, lambda: _live_fetch(url))
    if err is not None:
        return None, err
    return feedparser.parse(raw), None


def _live_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": feedparser.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as e:
        return None, {"error": True, "status_code": e.code, "message": f"HTTP {e.code}"}
    except Exception as e:
        return None, {"error": True, "message": str(e)}

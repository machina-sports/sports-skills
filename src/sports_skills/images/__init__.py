"""Images: high-resolution, open-licensed sports photos from Wikimedia Commons.

Finds photos of a sports person, team or venue by resolving the name to a
Wikidata entity first, then asking Commons for the files that depict it.
Every image comes with its license, author and a ready credit line.
No API key required. Zero config.

## Usage

    from sports_skills.images import find_images, get_image, search_entities

    # 4K photos of a player, newest first
    photos = find_images(name="Bukayo Saka", min_long_edge=3840)

    # Disambiguate a name, then search by Wikidata id
    entities = search_entities(query="Arsenal", kind="team")
    photos = find_images(qid="Q9617", orientation="landscape")

    # License, credit line and a 1920px rendition for one Commons file
    image = get_image(file="File:1 bukayo saka arsenal 2025.jpg", width=1920)
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.images._connector import (
    find_images as _find_images,
)
from sports_skills.images._connector import (
    get_image as _get_image,
)
from sports_skills.images._connector import (
    search_entities as _search_entities,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def search_entities(
    *, query: str, kind: str | None = None, limit: int | None = None, language: str | None = None
) -> dict:
    """Sports people, teams and venues on Wikidata that match a name.

    Args:
        query: Name to look up (e.g. "Vinicius", "Arsenal", "Emirates Stadium").
        kind: Optional filter: "person", "team" or "venue".
        limit: Max entities to return (default 5, max 8).
        language: Language for the search and the labels (default "en").
    """
    return wrap(_search_entities(_params(query=query, kind=kind, limit=limit, language=language)))


def find_images(
    *,
    name: str | None = None,
    qid: str | None = None,
    kind: str | None = None,
    min_long_edge: int | None = None,
    limit: int | None = None,
    orientation: str | None = None,
    allow_sharealike: bool | None = None,
    sort: str | None = None,
    width: int | None = None,
    language: str | None = None,
) -> dict:
    """High-resolution, open-licensed photos of a sports person, team or venue.

    Args:
        name: Name to look up (e.g. "Bukayo Saka"). Required unless qid is given.
        qid: Wikidata id (e.g. "Q9617"), from search_entities. Skips the name lookup.
        kind: Narrow the name lookup: "person", "team" or "venue".
        min_long_edge: Smallest accepted long edge in pixels (default 3000; 3840 is 4K).
        limit: Max images to return (default 10, max 50).
        orientation: "any" (default), "landscape", "portrait" or "square".
        allow_sharealike: Include CC BY-SA images (default True).
        sort: "recent" (default, by date taken) or "largest" (by pixel count).
        width: Width in pixels of the preview rendition (default 3840).
        language: Language for the name lookup and the labels (default "en").
    """
    return wrap(
        _find_images(
            _params(
                name=name,
                qid=qid,
                kind=kind,
                min_long_edge=min_long_edge,
                limit=limit,
                orientation=orientation,
                allow_sharealike=allow_sharealike,
                sort=sort,
                width=width,
                language=language,
            )
        )
    )


def get_image(*, file: str, width: int | None = None) -> dict:
    """License, author, credit line and a sized rendition for one Commons file.

    Args:
        file: Commons file title ("File:Example.jpg" or "Example.jpg") or its Commons page URL.
        width: Width in pixels of the preview rendition (default 3840).
    """
    return wrap(_get_image(_params(file=file, width=width)))

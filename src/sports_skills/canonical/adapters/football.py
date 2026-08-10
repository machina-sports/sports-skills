"""Read a normalized football event as a canonical observation.

The input is the shape ``sports_skills.football._connector._normalize_espn_event``
**returns**, not ESPN's transport JSON. That boundary is the point of this module: a
second ESPN parser in this package would disagree with the first the day either was
fixed, and the disagreement would be invisible because both would look authoritative.

Three rules, each of which the module is arranged around rather than checking at the
end:

**A native placeholder is not a fact.** The normalizer hardcodes ``round: ""`` and
``matchday: None`` and carries ``odds: null``, because its own consumers expect a
stable key set. Forwarding any of them would put ``null`` and ``""`` into a
conforming document, so :func:`_put` drops them and no key is emitted at all. They
stay readable in ``raw``, which is what makes "we omitted it" checkable.

**Nothing is inferred.** ``2-1`` plus ``closed`` makes the winner obvious to a
reader and is still an inference, so no participant outcome is claimed. A display
label like ``round_name`` is not an identifier, so no competition phase is emitted
from one.

**An unmapped status raises.** This repository's ESPN status vocabulary is its own —
``live``, ``1st_half`` and ``2nd_half`` have no NewsCode in the pinned schemes — so
it is translated explicitly and a value with no mapping stops here rather than
reaching the graph as a term nothing can resolve.
"""

import copy

from .._vendored import SCHEMA_VERSION
from .._vendored.observation import PLACEHOLDERS

#: This adapter's own name and version, recorded in every observation it produces.
#: A version is a string because it is evidence in a document, not a number to
#: compare, and it is bumped when the *reading* changes rather than when the package
#: is released.
ADAPTER_NAME = "sports_skills.canonical.adapters.football"
ADAPTER_VERSION = "1"

#: The class of endpoint this reading comes from. An endpoint class, never a request:
#: a URL is how an API key or a customer identifier ends up committed to a fixture,
#: and fixtures are the artefact that gets published.
SOURCE_REFS = ({"kind": "endpoint-class", "value": "espn/summary"},)

PROVIDER = {"namespace": "sports-skills/espn", "family": "open-data"}

#: Constants, not arguments. This package is public and non-commercial, so it can
#: never emit anything else, and a rights block whose licence claim is set by its
#: caller is not a rights block.
#:
#: ``open-public`` classifies **the data this adapter emits**: ESPN's public endpoints,
#: read live. It is one constant stamped onto the synthetic reference fixture and onto
#: every real match this module will ever read, so it has to be true of both — a class
#: naming the fixture would travel out attached to live events and call them synthetic.
#: What the checked-in fixture *is* is a separate question, answered separately in
#: machina-templates' ``provenance.json`` and never written into a rights block.
#:
#: The two booleans are what the gate reads, and they are unchanged: reclassifying the
#: data relaxes nothing.
RIGHTS = {
    "data_class": "open-public",
    "prototype_only": True,
    "commercial_use": False,
}

#: Association football, by IPTC MediaTopic code and by this package's own key.
SPORT = {"medtop": "20001065", "key": "soccer"}

#: This repository's normalized ESPN status -> canonical observation status.
#:
#: Written out in full, including the identities, so the table is the complete
#: statement of what this adapter accepts. ``ESPN_STATUS_MAP`` in the football
#: connector is the set of values that can arrive here, plus its own
#: ``not_started`` fallback, and a test asserts every one of them is a key below.
STATUS = {
    "not_started": "not_started",
    "live": "in_progress",
    "1st_half": "in_progress",
    "2nd_half": "in_progress",
    "halftime": "halftime",
    "closed": "closed",
    "postponed": "postponed",
    "cancelled": "cancelled",
    "suspended": "suspended",
}


def _text(value):
    """``value`` as a string when it is a fact, else ``None``.

    Not a truthiness test: ``0`` is a scoreline, and a truthiness test here would
    silently drop every clean sheet in the package.
    """
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = value if isinstance(value, str) else str(value)
    return None if text in PLACEHOLDERS else text


def _put(node, key, value):
    """Set ``key`` only when ``value`` is a fact. Omission over fabrication."""
    if value is not None:
        node[key] = value


def _required(value, field):
    """``value`` as a string, or refuse and name the native field that was empty.

    Raised rather than left to ``validate_observation`` because the error a
    maintainer can act on names ``competition.id`` in the payload, not
    ``observation.competition.provider_id`` in a document they did not write.
    """
    text = _text(value)
    if text is None:
        raise ValueError(
            f"native field '{field}' carries no value, so no canonical observation "
            "was produced. It is required, and a stand-in for it would be a "
            "fabricated fact."
        )
    return text


def _status(value):
    if value not in STATUS:
        raise ValueError(
            f"'{value}' is not a status this adapter maps. The football connector "
            f"normalizes ESPN's own codes into {', '.join(sorted(STATUS))}; add the "
            "mapping rather than passing a value through, which would put a term the "
            "pinned vocabulary has no NewsCode for onto the graph."
        )
    return STATUS[value]


def _season(season, competition_name):
    """The season, or ``None`` when the payload identifies none.

    The label is composed from the competition name and the season year because the
    native ``season.name`` is a bare year, which reads as nothing on its own in a
    consumer's list of seasons.
    """
    provider_id = _text(season.get("id"))
    if provider_id is None:
        return None
    node = {"provider_id": provider_id}
    year = _text(season.get("year")) or _text(season.get("name"))
    _put(node, "name", " ".join(part for part in (competition_name, year) if part) or None)
    return node


def _competition(event):
    competition = event.get("competition") or {}
    name = _text(competition.get("name"))
    node = {"provider_id": _required(competition.get("id"), "competition.id")}
    _put(node, "name", name)
    _put(node, "season", _season(event.get("season") or {}, name))
    return node


def _site(event):
    """The venue, or ``None`` when every field of it is a placeholder.

    The normalizer always returns all four keys, so an unknown venue arrives as four
    empty strings rather than as an absent object.
    """
    venue = event.get("venue") or {}
    node = {}
    for key, native_key in (("provider_id", "id"), ("name", "name"),
                            ("city", "city"), ("country", "country")):
        _put(node, key, _text(venue.get(native_key)))
    return node or None


def _participants(event):
    """Home first, then away, read off ``qualifier`` rather than list position.

    Alignment is a mandatory property of a ``sport:TeamParticipation`` and is not
    derivable from list order, so it is never inferred from one.
    """
    competitors = event.get("competitors") or []
    ordered = []
    for alignment in ("home", "away"):
        for competitor in competitors:
            if competitor.get("qualifier") != alignment:
                continue
            team = competitor.get("team") or {}
            node = {
                "kind": "team",
                "provider_id": _required(team.get("id"), "competitors[].team.id"),
                "name": _required(team.get("name"), "competitors[].team.name"),
                "alignment": alignment,
            }
            # Scores are xsd:string in the pinned shapes, so the native integer is
            # converted here rather than coerced downstream where a missing
            # conversion would be invisible.
            _put(node, "score", _text(competitor.get("score")))
            ordered.append(node)
            break
    if len(ordered) < 2:
        raise ValueError(
            "a canonical observation needs an identified home and away competitor; "
            f"the payload yielded {len(ordered)}"
        )
    return ordered


def to_observation(event, *, observed_at):
    """One normalized football event as a ``canonical-observation/1`` document.

    ``observed_at`` is an argument rather than a clock reading: it is the one input
    that would otherwise make every output unreproducible, and the checked-in
    reference fixtures depend on it being passed in.

    Raises ``ValueError`` when the payload states no status, no event identifier, no
    competition identifier or no identified pair of competitors. Every one of those
    is a fact a canonical observation is required to carry, and a stand-in for one is
    the fabrication this whole contract exists to refuse.
    """
    participants = _participants(event)

    observation = {
        "provider": dict(PROVIDER),
        "observed_at": observed_at,
        "adapter": {
            "name": ADAPTER_NAME,
            "version": ADAPTER_VERSION,
            "source_refs": [dict(ref) for ref in SOURCE_REFS],
        },
        "rights": dict(RIGHTS),
        "sport": dict(SPORT),
        "competition": _competition(event),
    }
    _put(observation, "site", _site(event))
    observation["event"] = {
        "provider_id": _required(event.get("id"), "id"),
        "label": " vs ".join(participant["name"] for participant in participants),
        "start_time": _required(event.get("start_time"), "start_time"),
        "status": _status(event.get("status")),
    }
    observation["participants"] = participants
    # Deep-copied: the caller's payload is the value it is about to return to its own
    # caller, and an observation that shares structure with it would let an edit here
    # reach back into the default native output.
    observation["raw"] = copy.deepcopy(event)

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

"""Stats Perform / Opta event document -> ``canonical-observation/1``.

**Read the source label before reading anything else.** No Stats Perform sample
is checked into this repository — not a payload, not a captured response, not a
sanitized example. The closest evidence is
``tools/iptc/fixtures/baseline/stats-perform-opta-event.json``, which PR 1
hand-authored from the literal key set of ``iptc-opta-event-mapping``. So this
adapter's input is a **legacy mapping-contract shape**: a document Machina's own
mapping emits, two removes from what Opta sends —

1. it is the *output* of a mapping rather than the provider's payload, so every
   key here is a Machina key naming an Opta fact, not an Opta key; and
2. no sample of that output exists either, so the fixture reproduces the shape
   the mapping emits and nothing more. It is synthetic throughout.

:data:`RIGHTS_DATA_CLASS` is ``legacy-mapping-contract-shape`` for exactly that
reason, and the corrected fixture's provenance restates it. **No Stats Perform
endpoint was called, no credential exists in this repository, and nothing here
is a claim to redistribute Opta data or a claim about Opta's real coverage.**
Calling this row provider data would be a claim nothing in this repository
supports.

The source is also PR 1's frozen "before" evidence and is read strictly
read-only: this adapter edits neither baseline file.

Six readings, written down because each one is a decision a reader would
otherwise have to reverse-engineer:

``@id`` **is unwrapped back to the Opta identifier.**
    ``urn:opta:sport_event:synthetic0matchid001`` is Machina's URN scheme around
    Opta's match id. Recording the whole URN as a provider identifier would
    attribute this repository's own scheme to Stats Perform, and the crosswalk
    exists to record what the *provider* addresses an entity by.
    :data:`LEGACY_URN_STEM` names the one prefix stripped; anything else is left
    exactly as it is.

``sport:status`` **is mapped, and an unmapped value raises.**
    :data:`EVENT_STATUS_BY_MATCH_STATUS` is the whole correspondence.
    ``observation.event.status`` is a required field and no default status is
    defensible, so a value outside the table raises :class:`ValueError` naming
    it.

``sport:stage`` **becomes the competition phase.**
    Opta addresses a stage by an identifier of its own, so recording it is
    provider-native evidence. Sportradar's round is deliberately different — it
    is ``{"number": 1}``, an ordinal inside a season — and the two adapters are
    not symmetric because the two providers do not state the same thing.

``sport:competitionFormat`` **is the one defensible competition type here.**
    ``Domestic league`` is Opta stating the competition is a league.
    :data:`COMPETITION_TYPE_BY_FORMAT` holds that reading and no other: the rest
    of Opta's format vocabulary is not in this repository's evidence, and a
    competition type is not required, so an unrecognised format produces no type
    rather than a raise.

``sport:timeline`` **produces actions whose class is pinned and whose type is
not.**
    :data:`ACTION_CLASS_BY_TYPE` maps an Opta action type to a pinned
    ``spactionclass:`` concept. It holds **two** entries — ``G`` and ``YC``,
    the only codes this repository's checked-in shapes carry — because Opta's
    real event vocabulary is far wider and guessing the rest would be inventing
    provider vocabulary. An unmapped type is **not** an error: unlike a status,
    an action class is not required, so the action keeps its place in
    ``event_view`` and simply produces no ``sport:Action`` (``sport:class`` is
    mandatory on one).

    The source's own ``sport:actionType`` —
    ``http://cv.iptc.org/newscodes/spsocaction/g`` — is never forwarded. No
    vocabulary TTL for that scheme exists at the pinned commit, so layer 4
    reports it ``unverifiable`` and RFC 001 §9.2 fails closed on that. The
    provider's action type survives as ``action.provider_type``, which reaches
    ``event_view`` and ``raw`` and never the graph.

``sport:participation`` **names players without making them participants.**
    The timeline names a scorer. Promoting them to an observation participant
    would make the capability report claim ``event.lineups`` off one named
    player, which is exactly the "you can rely on data you will not get" failure
    the tier rules exist to prevent. An action is attached to the participation
    of the team its ``competitor`` qualifier names; the player's identity
    survives in the action label and in ``raw``.

An action's ``ordinal`` is its 1-based position in the timeline the source
states. That is a fact about the document rather than an Opta field, and it is
what ``sport:sequenceNumber`` and the action's minted identity are built from.

Python 3.9-compatible, standard library only, no import of ``tools.*``.
"""

from __future__ import annotations

from .. import SCHEMA_VERSION

#: How provenance names this adapter. A literal rather than ``__name__`` so a
#: checked-in fixture does not change bytes the day this module is copied
#: somewhere with a different package path.
ADAPTER_NAME = "tools.iptc.canonical.adapters.stats_perform_opta"

#: The adapter implementation version, cited in provenance.
ADAPTER_VERSION = "1"

PROVIDER_NAMESPACE = "stats-perform-opta"

#: ``licensed``: access to this provider is contractual, whatever the provenance
#: of the checked-in shape this adapter happens to read.
PROVIDER_FAMILY = "licensed"

#: What the data in an observation from this adapter actually is. It is
#: deliberately NOT ``licensed-provider-example-fixture``: that class means a
#: sanitized provider example is checked in, and for this provider none is. See
#: this module's docstring.
RIGHTS_DATA_CLASS = "legacy-mapping-contract-shape"

#: The mapping whose output shape this adapter reads. Not an endpoint class,
#: because nothing here came from an endpoint.
SOURCE_MAPPING = "iptc-opta-event-mapping"

#: Stated on every source ref so the label travels with the observation rather
#: than living only in a provenance file a consumer may never open.
SOURCE_NOTE = ("legacy mapping-contract shape, not raw provider data; no Stats "
               "Perform endpoint was called and no credential exists")

#: IPTC ``medtop`` for association football, and the ``event_view`` sport key.
SPORT_MEDTOP = "20001065"
SPORT_KEY = "soccer"

#: What ``schema:sportName`` must say. The document states its sport, so this
#: adapter checks it rather than assuming: read a rugby document and it would
#: assert association football, and nothing downstream could tell.
SPORT_NAME = "football"

#: The one identifier wrapper this adapter unwraps. Everything after the third
#: colon-delimited segment is the provider's own identifier; anything not
#: starting with this stem is left exactly as it is.
LEGACY_URN_STEM = "urn:opta:"

#: ``sport:status`` -> the canonical status key
#: ``tools.iptc.canonical.vocab.EVENT_STATUS`` maps into a pinned
#: ``speventstatus:`` NewsCode. A test asserts every value here is a key of that
#: table, so a code that no pinned scheme admits cannot be added silently.
EVENT_STATUS_BY_MATCH_STATUS = {
    "Fixture": "not_started",
    "Playing": "in_progress",
    "Played": "closed",
    "Postponed": "postponed",
    "Cancelled": "cancelled",
    "Suspended": "suspended",
    "Abandoned": "abandoned",
    "Awarded": "awarded",
}

#: ``sport:competitionFormat`` -> a pinned ``spct:`` concept. One entry; see this
#: module's docstring.
COMPETITION_TYPE_BY_FORMAT = {
    "Domestic league": "league",
}

#: Opta action type -> a pinned ``spactionclass:`` concept. Two entries, and the
#: narrowness is the point; see this module's docstring. A test asserts the keys
#: are exactly the codes this repository has evidence for.
ACTION_CLASS_BY_TYPE = {
    "G": "score",
    "YC": "infraction",
}

#: The order competitors are emitted in. Anything qualified otherwise follows, in
#: document order, rather than being dropped.
ALIGNMENT_ORDER = ("home", "away")


def _section(node, key):
    value = node.get(key) if isinstance(node, dict) else None
    return value if isinstance(value, dict) else {}


def _items(node, key):
    value = node.get(key) if isinstance(node, dict) else None
    return [item for item in value if isinstance(item, dict)] if isinstance(
        value, list) else []


def _text(value):
    """``value`` as a non-empty string, or ``None``.

    Not a truthiness test: ``0`` is a fact and becomes ``"0"``. An empty string is
    not a fact and becomes nothing at all, so it can never reach the observation
    as the placeholder ``validate_observation`` would reject it as.
    """
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text or None


def _put(node, key, value):
    """Set ``key`` only when ``value`` is a fact. Omission over fabrication."""
    if value is not None:
        node[key] = value


def _provider_id(node):
    """The Opta identifier behind a legacy ``urn:opta:<kind>:<id>`` resource id.

    Returns ``None`` rather than a partial reading when the value is not a
    string, is not this repository's URN, or has no identifier segment: a
    half-parsed identifier recorded as provider-native evidence is worse than no
    crosswalk entry at all.
    """
    node_id = _text(node.get("@id") if isinstance(node, dict) else None)
    if node_id is None or not node_id.startswith(LEGACY_URN_STEM):
        return None
    return _text(node_id.rsplit(":", 1)[-1])


def _event_status(document):
    """The canonical status key, or a raise naming the provider value."""
    stated = _text(document.get("sport:status"))
    if stated is None:
        raise ValueError(
            "stats-perform/opta document has no sport:status, so its canonical "
            "event status cannot be determined; no observation was produced"
        )
    if stated not in EVENT_STATUS_BY_MATCH_STATUS:
        raise ValueError(
            "stats-perform/opta sport:status '{0}' has no canonical event status "
            "in this adapter. Add it to EVENT_STATUS_BY_MATCH_STATUS with a "
            "defensible speventstatus: reading rather than letting it default; "
            "no observation was produced".format(stated)
        )
    return EVENT_STATUS_BY_MATCH_STATUS[stated]


def _check_sport(document):
    stated = _text(document.get("schema:sportName"))
    if stated is not None and stated != SPORT_NAME:
        raise ValueError(
            "stats-perform/opta document states sport '{0}', but this adapter "
            "asserts medtop {1} (association football, '{2}'). Use the adapter "
            "for that sport; no observation was produced".format(
                stated, SPORT_MEDTOP, SPORT_NAME)
        )


def _ordered_competitors(document):
    """Competitors home first, then away, then anything else in document order."""
    competitors = _items(document, "sport:competitors")
    ordered = []
    for alignment in ALIGNMENT_ORDER:
        ordered.extend(c for c in competitors
                       if _text(c.get("sport:qualifier")) == alignment)
    ordered.extend(c for c in competitors if c not in ordered)
    return ordered


def _participant(competitor, score_block, winner):
    scores = {"home": score_block.get("sport:homeScore"),
              "away": score_block.get("sport:awayScore")}
    alignment = _text(competitor.get("sport:qualifier"))

    participant = {"kind": "team"}
    _put(participant, "provider_id", _provider_id(competitor))
    _put(participant, "name", _text(competitor.get("name")))
    _put(participant, "alignment", alignment)
    _put(participant, "score", _text(scores.get(alignment)))
    if winner is not None and alignment is not None:
        participant["outcome"] = "win" if alignment == winner else "loss"
    return participant


def _competition(document):
    block = _section(document, "sport:competition")
    season_block = _section(block, "sport:season")

    competition = {}
    _put(competition, "provider_id", _provider_id(block))
    _put(competition, "name", _text(block.get("name")))
    _put(competition, "type", COMPETITION_TYPE_BY_FORMAT.get(
        _text(block.get("sport:competitionFormat"))))
    season = {}
    _put(season, "provider_id", _provider_id(season_block))
    _put(season, "name", _text(season_block.get("name")))
    _put(competition, "season", season or None)
    return competition


def _phase(document):
    stage = _section(document, "sport:stage")
    phase = {}
    _put(phase, "provider_id", _provider_id(stage))
    _put(phase, "name", _text(stage.get("name")))
    return phase


def _site(document):
    venue = _section(document, "sport:venue")
    site = {}
    _put(site, "provider_id", _provider_id(venue))
    _put(site, "name", _text(venue.get("name")))
    # No city and no country: the source states latitude and longitude, and a
    # place name is not derivable from a coordinate without a gazetteer nothing
    # here has. SiteShape admits neither anyway.
    return site


def _event(document, match_info, provider_id, status, label):
    event = {"provider_id": provider_id}
    _put(event, "label", label)
    _put(event, "start_time", _text(document.get("schema:startDate")))
    event["status"] = status
    _put(event, "attendance", _text(match_info.get("sport:attendance")))
    # No clock: numberOfPeriods and periodLength describe the format of the
    # match, not how far into it play had reached.
    return event


def _action(entry, ordinal, alignment_to_provider_id):
    action = {"ordinal": ordinal}
    provider_type = _text(entry.get("type"))
    _put(action, "class", ACTION_CLASS_BY_TYPE.get(provider_type))
    # Kept beside the class rather than replaced by it: the class is an
    # interpretation and this is what the source actually said, so the two can be
    # audited against each other. It reaches event_view and never the graph.
    _put(action, "provider_type", provider_type)
    _put(action, "label", _text(entry.get("sport:label")))
    _put(action, "minute", _text(entry.get("sport:minutesElapsed")))
    _put(action, "period", _text(entry.get("sport:periodValue")))
    _put(action, "action_time", _text(entry.get("sport:actionDateTime")))
    _put(action, "participant_provider_id",
         alignment_to_provider_id.get(_text(entry.get("competitor"))))
    return action


def _actions(document, alignment_to_provider_id):
    return [
        _action(entry, index + 1, alignment_to_provider_id)
        for index, entry in enumerate(_items(document, "sport:timeline"))
    ]


def to_observation(payload, *, observed_at):
    """One Opta event document as a ``canonical-observation/1`` document.

    ``payload`` is never modified. The document is not validated here:
    ``validate_observation`` is this adapter's acceptance test and
    ``canonical_envelope`` refuses to serialize a document that fails it, so
    validating inside would only decide the same thing twice.
    """
    _check_sport(payload)

    event_id = _provider_id(payload)
    if event_id is None:
        raise ValueError(
            "stats-perform/opta document has no {0} @id, so there is nothing to "
            "mint an event identity from; no observation was produced".format(
                LEGACY_URN_STEM)
        )

    match_info = _section(payload, "sport:matchInfo")
    competitors = _ordered_competitors(payload)
    names = [_text(c.get("name")) for c in competitors[:2]]
    label = None
    if len(names) == 2 and all(name is not None for name in names):
        label = "{0} vs {1}".format(names[0], names[1])

    observation = {
        "provider": {"namespace": PROVIDER_NAMESPACE, "family": PROVIDER_FAMILY},
        "observed_at": observed_at,
        "adapter": {
            "name": ADAPTER_NAME,
            "version": ADAPTER_VERSION,
            "source_refs": [{"kind": "legacy-mapping-output",
                             "value": SOURCE_MAPPING,
                             "note": SOURCE_NOTE}],
        },
        "rights": {
            "data_class": RIGHTS_DATA_CLASS,
            "prototype_only": True,
            "commercial_use": False,
        },
        "sport": {"medtop": SPORT_MEDTOP, "key": SPORT_KEY},
        "competition": _competition(payload),
    }
    _put(observation, "phase", _phase(payload) or None)
    _put(observation, "site", _site(payload) or None)
    observation["event"] = _event(
        payload, match_info, event_id, _event_status(payload), label)
    observation["participants"] = [
        _participant(competitor, _section(payload, "sport:score"),
                     _text(match_info.get("sport:winner")))
        for competitor in competitors
    ]
    alignment_to_provider_id = {
        participant["alignment"]: participant["provider_id"]
        for participant in observation["participants"]
        if participant.get("alignment") and participant.get("provider_id")
    }
    _put(observation, "actions",
         _actions(payload, alignment_to_provider_id) or None)
    # The source document's own bytes, unaltered. Every fact this adapter
    # declined to map — the half-time score, the coverage level, the VAR flag,
    # the week, the venue coordinates, the period format, the unverifiable
    # spsocaction NewsCode and Machina's own version_control block — is readable
    # here, which is what makes "we omitted it" checkable.
    observation["raw"] = payload

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

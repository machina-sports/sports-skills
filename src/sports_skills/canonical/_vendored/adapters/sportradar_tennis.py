"""Sportradar tennis event document -> ``canonical-observation/1``.

**Read the source label before reading anything else.** No Sportradar tennis
payload is checked into this repository — not a response, not a sanitized
example. The soccer feed has one (``example-sportradar.json``); this one does
not. The only evidence is
``tools/iptc/fixtures/baseline/sportradar-tennis-event.json``, which PR 1
hand-authored from the literal key set of
``iptc-sportradar-tennis-event-mapping``. So this adapter's input is a **legacy
mapping-contract shape**: a document Machina's own mapping emits, two removes
from what Sportradar sends —

1. it is the *output* of a mapping rather than the provider's payload, so every
   key here is a Machina key naming a Sportradar fact, not a Sportradar key; and
2. no sample of that output exists either, so the fixture reproduces the shape
   the mapping emits and nothing more. It is synthetic throughout.

:data:`RIGHTS_DATA_CLASS` is ``legacy-mapping-contract-shape`` for exactly that
reason, and the corrected fixture's provenance restates it. **No Sportradar
endpoint was called, no credential exists in this repository, and nothing here
is a claim to redistribute Sportradar data or a claim about Sportradar's real
tennis coverage.**

The source is also PR 1's frozen "before" evidence and is read strictly
read-only: this adapter edits no baseline file.

Seven readings, written down because each one is a decision a reader would
otherwise have to reverse-engineer:

**The competitors are individuals, not teams.**
    A singles match has no team in it. ``participant.kind`` is ``individual``,
    which makes the serializer emit ``sport:Athlete`` and
    ``sport:IndividualParticipation``. Reading the two players as
    ``sport:Team`` — which the legacy mapping's ``sport:Competitor`` type invites
    — would put a class on the graph the source never states, and A16's
    cross-provider comparison would then compare a tennis "team" against a real
    one. ``sport:alignment`` is *not* declared on
    ``sport:IndividualParticipationShape`` (which is ``sh:closed``), so the
    alignment stays in the observation, where it decides which score column
    belongs to which player, and never reaches the graph.

``sport:gameInfo.sport:status`` **is the status, and an unmapped value raises.**
    The mapping writes Sportradar's ``sport_event_status.status`` there and its
    ``match_status`` into the top-level ``sport:status``. Those are two
    vocabularies, not two spellings: ``match_status`` is the finer-grained
    half-by-half reading, and this profile has no concept for it, so it survives
    only in ``raw`` — the same split ``sportradar_soccer`` makes.
    :data:`EVENT_STATUS_BY_CODE` is the whole correspondence, and it is the same
    table as the soccer feed's because it is the same provider field.
    ``observation.event.status`` is required and no default is defensible, so a
    value outside the table raises :class:`ValueError` naming it. Sportradar's own
    ``unknown`` is deliberately absent: it is the provider declining to state a
    status, and it is also the literal the legacy mapping falls back to.

**Identifiers are unwrapped from the legacy URN, one stem per entity kind.**
    ``urn:sportradar:tennis:match:sr:sport_event:9000001`` is Machina's URN
    scheme around Sportradar's own ``sr:sport_event:9000001``. Recording the whole
    URN as a provider identifier would attribute this repository's scheme to
    Sportradar. :data:`LEGACY_URN_STEMS` names each stem exactly, rather than
    splitting on the last colon: a Sportradar identifier *contains* colons, so
    ``rsplit`` would silently record ``9000001`` and lose the entity kind the
    provider addresses it by.

**No sport-specific statistic is emitted, and the pinned shapes are the reason.**
    The source carries seventeen per-player statistics. ``sptenstat:aces`` and
    friends are genuinely official Sport Schema properties at the pinned commit,
    so "the term exists" is not the test. The test is whether the term is
    admissible *on the class this document puts it on*, and
    ``sport:IndividualParticipationShape`` is ``sh:closed`` with
    ``sh:ignoredProperties (rdf:type rdfs:label)`` and declares no tennis
    statistic at all. Emitting one would fail layer 2 — measured, in
    ``tests/test_iptc_sportradar_tennis_adapter.py``, by injecting one and
    watching the official SHACL reject it. Every statistic therefore stays in
    ``raw``, readable in ``event_view``, which is what makes "we omitted it"
    checkable.

**No competition phase, because nothing here is addressed as one.**
    ``sport:round`` is ``{roundName, roundNumber}`` and ``sport:stage`` carries no
    ``@id`` at all. Recording a display name or an ordinal as provider-native
    evidence would invent it. Opta's stage is genuinely different: Opta addresses
    a stage by an identifier of its own.

**No competition type.**
    ``sport:stage.sport:type`` is ``cup`` and describes the stage, which this
    observation does not carry. ``sport:competitionFormat`` states a match type
    (``singles``), a gender category and a tour level — none of which is a
    ``spct:`` competition kind. Reading any of them as one would put a NewsCode on
    the graph nothing in the source says about the competition.

``sport:gameInfo.sport:winnerId`` **names one competitor; the other loses.**
    The winner is stated by identifier rather than by a flag per side, so both
    outcomes fall out of one stated fact. Absence produces no outcome at all:
    deriving a result from the set scores would be this module inferring one the
    source declined to state.

Two further absences worth naming, because the source states something adjacent.
``sport:seed`` is not ``sport:rank`` — a seed is a draw position assigned before
play, and ``sport:rank`` is admissible on an IndividualParticipation, so the
temptation is real. ``sport:periodScores`` are games per set, not a clock
reading, so they produce no ``event.clock``.

Competitors are emitted **home first, then away**, regardless of source order.
Alignment is a stated fact and list order is not, but every adapter in this
profile emits the same order so cross-provider comparisons fail on concepts
rather than on ordering.

Python 3.9-compatible, standard library only, no import of ``tools.*``.
"""

from __future__ import annotations

from .. import SCHEMA_VERSION

#: How provenance names this adapter. A literal rather than ``__name__`` so a
#: checked-in fixture does not change bytes the day this module is copied
#: somewhere with a different package path.
ADAPTER_NAME = "tools.iptc.canonical.adapters.sportradar_tennis"

#: The adapter implementation version, cited in provenance. A string, because it
#: is evidence in a document rather than a number to compare.
ADAPTER_VERSION = "1"

#: Scoped to the tennis connector rather than to "sportradar", because Sportradar
#: publishes a separate feed per sport and each gets its own adapter. Two feeds
#: sharing one crosswalk namespace would claim that their identifier spaces are
#: one, which nothing here has checked.
PROVIDER_NAMESPACE = "sportradar-tennis"

#: ``licensed``: access to this provider is contractual, whatever the provenance
#: of the checked-in shape this adapter happens to read.
PROVIDER_FAMILY = "licensed"

#: What the data in an observation from this adapter actually is. It is
#: deliberately NOT ``licensed-provider-example-fixture``: that class means a
#: sanitized provider example is checked in, and for this feed none is. See this
#: module's docstring.
RIGHTS_DATA_CLASS = "legacy-mapping-contract-shape"

#: The mapping whose output shape this adapter reads. Not an endpoint class,
#: because nothing here came from an endpoint.
SOURCE_MAPPING = "iptc-sportradar-tennis-event-mapping"

#: Stated on every source ref so the label travels with the observation rather
#: than living only in a provenance file a consumer may never open.
SOURCE_NOTE = ("legacy mapping-contract shape, not raw provider data; no "
               "Sportradar endpoint was called and no credential exists")

#: IPTC ``medtop`` for tennis, and the ``event_view`` sport key. 20001085 is a
#: ``skos:Concept`` in the pinned ``vocabularies/mediatopic.ttl``, which is what
#: makes it checkable rather than plausible; layer 4 checks it.
SPORT_MEDTOP = "20001085"
SPORT_KEY = "tennis"

#: What ``schema:sportName`` must say. The document states its sport, so this
#: adapter checks it rather than assuming: read a table-tennis document and it
#: would assert tennis, and nothing downstream could tell.
SPORT_NAME = "tennis"

#: The legacy URN stem per entity kind. Written out per kind rather than derived,
#: because a Sportradar identifier contains colons: splitting on the last one
#: would record ``9000001`` and throw away the ``sr:sport_event:`` the provider
#: addresses the entity by.
LEGACY_URN_STEMS = {
    "event": "urn:sportradar:tennis:match:",
    "competition": "urn:sportradar:tennis:competition:",
    "season": "urn:sportradar:tennis:season:",
    "venue": "urn:sportradar:tennis:venue:",
    "competitor": "urn:sportradar:tennis:competitor:",
}

#: ``sport:gameInfo.sport:status`` -> the canonical status key
#: ``tools.iptc.canonical.vocab.EVENT_STATUS`` maps into a pinned
#: ``speventstatus:`` NewsCode. A test asserts every value here is a key of that
#: table, so a code that no pinned scheme admits cannot be added silently.
#:
#: ``ended`` and ``closed`` both read as ``closed``: Sportradar distinguishes
#: "the match finished" from "the result is settled", and the profile has one
#: concept for a finished event. ``unknown`` is deliberately not here — see this
#: module's docstring.
EVENT_STATUS_BY_CODE = {
    "not_started": "not_started",
    "live": "in_progress",
    "postponed": "postponed",
    "delayed": "delayed",
    "suspended": "suspended",
    "cancelled": "cancelled",
    "ended": "closed",
    "closed": "closed",
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


def _provider_id(node, kind):
    """The Sportradar identifier behind a legacy ``urn:sportradar:tennis:`` id.

    Returns ``None`` rather than a partial reading when the value is not a
    string, does not carry this kind's stem, or has nothing after it: a
    half-parsed identifier recorded as provider-native evidence is worse than no
    crosswalk entry at all.
    """
    node_id = _text(node.get("@id") if isinstance(node, dict) else None)
    stem = LEGACY_URN_STEMS[kind]
    if node_id is None or not node_id.startswith(stem):
        return None
    return _text(node_id[len(stem):])


def _event_status(game_info):
    """The canonical status key, or a raise naming the provider code."""
    code = _text(game_info.get("sport:status"))
    if code is None:
        raise ValueError(
            "sportradar tennis document has no sport:gameInfo.sport:status, so "
            "its canonical event status cannot be determined; no observation was "
            "produced"
        )
    if code not in EVENT_STATUS_BY_CODE:
        raise ValueError(
            "sportradar tennis sport:gameInfo.sport:status '{0}' has no "
            "canonical event status in this adapter. Add it to "
            "EVENT_STATUS_BY_CODE with a defensible speventstatus: reading "
            "rather than letting it default; no observation was produced".format(
                code)
        )
    return EVENT_STATUS_BY_CODE[code]


def _check_sport(document):
    stated = _text(document.get("schema:sportName"))
    if stated is not None and stated != SPORT_NAME:
        raise ValueError(
            "sportradar tennis document states sport '{0}', but this adapter "
            "asserts medtop {1} (tennis, '{2}'). Use the adapter for that sport; "
            "no observation was produced".format(stated, SPORT_MEDTOP, SPORT_NAME)
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


def _participant(competitor, score_block, winner_id):
    scores = {"home": score_block.get("sport:homeScore"),
              "away": score_block.get("sport:awayScore")}
    alignment = _text(competitor.get("sport:qualifier"))
    provider_id = _provider_id(competitor, "competitor")

    # `individual`, not `team`: see this module's docstring. No `statistics`
    # either — the pinned IndividualParticipationShape is sh:closed and declares
    # no sptenstat: property, so the source's own statistics stay in `raw`.
    participant = {"kind": "individual"}
    _put(participant, "provider_id", provider_id)
    _put(participant, "name", _text(competitor.get("name")))
    _put(participant, "alignment", alignment)
    _put(participant, "score", _text(scores.get(alignment)))
    if winner_id is not None and provider_id is not None:
        participant["outcome"] = "win" if provider_id == winner_id else "loss"
    return participant


def _competition(document):
    block = _section(document, "sport:competition")
    season_block = _section(block, "sport:season")

    competition = {}
    _put(competition, "provider_id", _provider_id(block, "competition"))
    _put(competition, "name", _text(block.get("name")))
    # No type: stage.type describes the stage and competitionFormat states a
    # match type, a gender category and a tour level. None is a spct: concept.
    season = {}
    _put(season, "provider_id", _provider_id(season_block, "season"))
    _put(season, "name", _text(season_block.get("name")))
    _put(competition, "season", season or None)
    return competition


def _site(document):
    venue = _section(document, "sport:venue")
    site = {}
    _put(site, "provider_id", _provider_id(venue, "venue"))
    _put(site, "name", _text(venue.get("name")))
    _put(site, "city", _text(venue.get("schema:addressLocality")))
    _put(site, "country", _text(venue.get("schema:addressCountry")))
    return site


def _event(document, provider_id, status, label):
    event = {"provider_id": provider_id}
    _put(event, "label", label)
    _put(event, "start_time", _text(document.get("schema:startDate")))
    event["status"] = status
    # No clock: periodScores are games per set, not how far into the match play
    # had reached. No attendance and no end time: the source states neither.
    return event


def to_observation(payload, *, observed_at):
    """One Sportradar tennis event document as a ``canonical-observation/1``.

    ``payload`` is never modified. The document is not validated here:
    ``validate_observation`` is this adapter's acceptance test and
    ``canonical_envelope`` refuses to serialize a document that fails it, so
    validating inside would only decide the same thing twice.
    """
    _check_sport(payload)

    event_id = _provider_id(payload, "event")
    if event_id is None:
        raise ValueError(
            "sportradar tennis document has no {0} @id, so there is nothing to "
            "mint an event identity from; no observation was produced".format(
                LEGACY_URN_STEMS["event"])
        )

    game_info = _section(payload, "sport:gameInfo")
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
    # No phase: round is a display name plus an ordinal and stage has no @id.
    _put(observation, "site", _site(payload) or None)
    observation["event"] = _event(
        payload, event_id, _event_status(game_info), label)
    observation["participants"] = [
        _participant(competitor, _section(payload, "sport:score"),
                     _text(game_info.get("sport:winnerId")))
        for competitor in competitors
    ]
    # The source document's own bytes, unaltered. Every fact this adapter
    # declined to map — the seventeen per-player statistics, the per-set scores,
    # the seeds and bracket numbers, the coverage flags, the broadcast channels,
    # the category, the competition format, the stage, the match_status copy and
    # the mapping's own "Unknown Title" default — is readable here, which is what
    # makes "we omitted it" checkable.
    observation["raw"] = payload

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

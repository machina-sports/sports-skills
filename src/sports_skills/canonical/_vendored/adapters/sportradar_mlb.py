"""Sportradar MLB event document -> ``canonical-observation/1``.

**Read the source label before reading anything else.** No Sportradar MLB payload
is checked into this repository — not a response, not a sanitized example. The
only evidence is ``tools/iptc/fixtures/baseline/sportradar-mlb-event.json``,
which PR 1 hand-authored from the literal key set of
``iptc-sportradar-event-mlb-mapping``. So this adapter's input is a **legacy
mapping-contract shape**: a document Machina's own mapping emits, two removes
from what Sportradar sends —

1. it is the *output* of a mapping rather than the provider's payload, so every
   key here is a Machina key naming a Sportradar fact, not a Sportradar key; and
2. no sample of that output exists either, so the fixture reproduces the shape
   the mapping emits and nothing more. It is synthetic throughout.

:data:`RIGHTS_DATA_CLASS` is ``legacy-mapping-contract-shape`` for exactly that
reason, and the corrected fixture's provenance restates it. **No Sportradar
endpoint was called, no credential exists in this repository, and nothing here
is a claim to redistribute Sportradar data or a claim about Sportradar's real MLB
coverage.**

The source is also PR 1's frozen "before" evidence and is read strictly
read-only: this adapter edits no baseline file.

Six readings, written down because each one is a decision a reader would
otherwise have to reverse-engineer:

``schema:sportName`` **says a league, and the sport is asserted separately.**
    The mapping hardcodes ``"mlb"``. A league is not a sport, so this adapter
    treats the value as the discriminator it actually is — :func:`_check_sport`
    refuses any other value — and states the sport itself as
    :data:`SPORT_MEDTOP`, ``20000849`` (baseball), a ``skos:Concept`` in the
    pinned mediatopic scheme. The check matters more here than for the soccer
    feeds: the MLB and NFL mappings share every URN stem, so a document read by
    the wrong adapter would not be caught by its identifiers either.

**The explicit nulls in ``sport:score`` are dropped, and the gap is reported.**
    This mapping emits ``sport:homeScore: null`` and ``sport:awayScore: null``
    deliberately — its own description says why: ``schedule.json`` carries no
    runs, and ``sportradar-mlb-sync-results`` merges them in from the daily
    boxscore feed afterwards. So a closed game with no scoreline is a real state
    of this document rather than a parse failure, and there are two honest moves
    and one dishonest one. Omitting the score is honest. Letting
    ``capability_report`` raise ``score-absent-on-started-event`` is honest, and
    is what tells a consumer the gap exists. Emitting ``"0"`` would invent a
    shutout, and it would validate. The nulls survive in ``raw``.

``sport:status`` **is mapped over BOTH write paths, and an unmapped value
raises.**
    The mapping writes one expression into both ``sport:status`` and
    ``sport:matchStatus``, so those two are copies of one field and only
    ``sport:status`` is read. But this connector has a *second* writer:
    ``sportradar-mlb-sync-results`` merges ``game.status`` from the boxscore feed
    onto the same field with **no** rewrite, where the event mapping rewrites
    ``created``/``scheduled`` to ``not_started`` and ``inprogress`` to ``live``.
    Both spellings therefore reach ``sport:status`` in this repository, and
    :data:`EVENT_STATUS_BY_CODE` maps both. That makes this table wider than
    ``sportradar_nfl``'s, and the asymmetry is deliberate: the NFL connector
    rewrites on every write path it has. Two adapters agreeing on a vocabulary
    neither provider states would be tidier and wrong. ``complete``,
    ``unnecessary``, ``if-necessary`` and the rest of Sportradar's real
    game-status enum appear in no checked-in expression here, so they are absent
    rather than guessed: ``observation.event.status`` is required, no default is
    defensible, and a plausible neighbour that validates is far more expensive
    than a :class:`ValueError` naming the code.

**The competition and season identifiers are mapping constants, not provider
fields.**
    ``urn:sportradar:competition:mlb`` is a literal and
    ``urn:sportradar:season:{season_year}`` is a workflow variable with a
    hardcoded default: the schedule payload the mapping consumes carries no
    competition entity and no season entity at all. The event, venue and team
    identifiers really are read from provider fields (``f['id']``,
    ``f['venue']['id']``, ``f['home'|'away']['id']``) and are genuine Sportradar
    UUIDs. ``observation.competition.provider_id`` is a required field, so the
    constant is recorded rather than omitted — and it is named as a constant in
    :data:`MAPPING_CONSTANT_IDENTIFIERS`, asserted by a test and restated in the
    corrected fixture's ``limitation``, because a crosswalk that cannot be
    trusted at the two places it is weakest is worse than one that says so.

``sport:gameNumber`` **and** ``sport:doubleHeader`` **have no canonical home.**
    They exist because MLB plays two games between the same teams on the same
    day, and the mapping's own comment says a naive team+date join would collapse
    the pair. Neither is an official term — ``sport:doubleHeader`` is a named
    provider leak in ``tools/iptc/rules/provider-leak-terms.json`` — and
    ``EventShape`` is ``sh:closed`` with nothing that could carry either. They
    stay in ``raw``, and the gap goes to the A16 handoff rather than into an
    invented ``sport:`` property. This is a real loss against the baseline
    document and the corrected fixture's ``limitation`` records it as one.

**No winner, no phase, no competition type, no statistics, no roster.**
    The source states no winner — and with no scoreline there is not even a
    number to be tempted by. MLB has a regular season and a post-season, and this
    document says which one this game is in nowhere at all, so
    ``spct:season-regular`` would be a guess. The connector has separate pitcher
    and team-statistics workflows; joining one to this document would attach
    numbers to a game nothing here says they belong to. ``sport:market`` and
    ``sport:abbreviation`` are not official terms and ``TeamShape`` is
    ``sh:closed`` admitting only ``rdfs:label``, so both stay in ``raw`` — the
    market is in the composed team name anyway.

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
ADAPTER_NAME = "tools.iptc.canonical.adapters.sportradar_mlb"

#: The adapter implementation version, cited in provenance. A string, because it
#: is evidence in a document rather than a number to compare.
ADAPTER_VERSION = "1"

#: Scoped to the MLB connector rather than to "sportradar", because Sportradar
#: publishes a separate feed per sport and each gets its own adapter. It matters
#: doubly here: the legacy MLB and NFL mappings both mint
#: ``urn:sportradar:sport_event:<id>`` with no sport in the stem, so their
#: identifier spaces collide in the old model and one shared namespace would carry
#: that collision into the crosswalk.
PROVIDER_NAMESPACE = "sportradar-mlb"

#: ``licensed``: access to this provider is contractual, whatever the provenance
#: of the checked-in shape this adapter happens to read.
PROVIDER_FAMILY = "licensed"

#: What the data in an observation from this adapter actually is. It is
#: deliberately NOT ``licensed-provider-example-fixture``: that class means a
#: sanitized provider example is checked in, and for this feed none is.
RIGHTS_DATA_CLASS = "legacy-mapping-contract-shape"

#: The mapping whose output shape this adapter reads. Not an endpoint class,
#: because nothing here came from an endpoint.
SOURCE_MAPPING = "iptc-sportradar-event-mlb-mapping"

#: Stated on every source ref so the label travels with the observation rather
#: than living only in a provenance file a consumer may never open.
SOURCE_NOTE = ("legacy mapping-contract shape, not raw provider data; no "
               "Sportradar endpoint was called and no credential exists")

#: IPTC ``medtop`` for baseball, and the ``event_view`` sport key. 20000849 is a
#: ``skos:Concept`` in the pinned ``vocabularies/mediatopic.ttl``, which is what
#: makes it checkable rather than plausible; layer 4 checks it.
SPORT_MEDTOP = "20000849"
SPORT_KEY = "baseball"

#: What ``schema:sportName`` must say. A league name rather than a sport name —
#: see this module's docstring — and checked rather than assumed.
SPORT_NAME = "mlb"

#: The legacy URN stem per entity kind. Note there is no sport in any of them:
#: this is the collision with the NFL mapping that :data:`PROVIDER_NAMESPACE`
#: exists to keep out of the crosswalk.
LEGACY_URN_STEMS = {
    "event": "urn:sportradar:sport_event:",
    "competition": "urn:sportradar:competition:",
    "season": "urn:sportradar:season:",
    "venue": "urn:sportradar:venue:",
    "team": "urn:sportradar:team:",
}

#: Entity kinds whose identifier the mapping hardcodes rather than reads from a
#: provider field. Named rather than described, so the claim in this module's
#: docstring is checkable and a future reader adding a third constant has to
#: decide about it here.
MAPPING_CONSTANT_IDENTIFIERS = ("competition", "season")

#: What :data:`MAPPING_CONSTANT_IDENTIFIERS` resolve *as*, in RFC 002 §5's terms:
#: the caller supplied them, and the provider did not state them. Written onto
#: the two sections rather than left to default, because the default —
#: ``provider-native`` — would have the crosswalk assert that Sportradar
#: addresses its baseball competition as ``mlb`` and its season as ``2026``,
#: which this repository has no evidence for and the mapping's own source
#: contradicts. Naming the constants without marking them was the state before
#: A16: the limitation was recorded in prose and the machine-readable field said
#: the opposite.
MAPPING_CONSTANT_RESOLUTION = "declared"

#: ``sport:status`` -> the canonical status key
#: ``tools.iptc.canonical.vocab.EVENT_STATUS`` maps into a pinned
#: ``speventstatus:`` NewsCode.
#:
#: Six entries covering the two write paths this repository actually has: the
#: event mapping's rewritten spellings (``not_started``, ``live``) and the raw
#: Sportradar spellings ``sportradar-mlb-sync-results`` merges in unrewritten
#: (``created``, ``scheduled``, ``inprogress``), plus ``closed``, which both paths
#: pass through. Wider than ``sportradar_nfl``'s on purpose; see this module's
#: docstring. A test asserts every value here is a key of ``EVENT_STATUS``, so a
#: code that no pinned scheme admits cannot be added silently.
EVENT_STATUS_BY_CODE = {
    "not_started": "not_started",
    "scheduled": "not_started",
    "created": "not_started",
    "live": "in_progress",
    "inprogress": "in_progress",
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
    """The identifier behind a legacy ``urn:sportradar:<kind>:<id>`` resource id.

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


def _event_status(document):
    """The canonical status key, or a raise naming the provider code."""
    code = _text(document.get("sport:status"))
    if code is None:
        raise ValueError(
            "sportradar mlb document has no sport:status, so its canonical event "
            "status cannot be determined; no observation was produced"
        )
    if code not in EVENT_STATUS_BY_CODE:
        raise ValueError(
            "sportradar mlb sport:status '{0}' has no canonical event status in "
            "this adapter. Add it to EVENT_STATUS_BY_CODE with a defensible "
            "speventstatus: reading rather than letting it default; no "
            "observation was produced".format(code)
        )
    return EVENT_STATUS_BY_CODE[code]


def _check_sport(document):
    stated = _text(document.get("schema:sportName"))
    if stated is not None and stated != SPORT_NAME:
        raise ValueError(
            "sportradar mlb document states sport '{0}', but this adapter asserts "
            "medtop {1} (baseball, '{2}'). Use the adapter for that sport; no "
            "observation was produced".format(stated, SPORT_MEDTOP, SPORT_NAME)
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


def _participant(competitor, score_block):
    scores = {"home": score_block.get("sport:homeScore"),
              "away": score_block.get("sport:awayScore")}
    alignment = _text(competitor.get("sport:qualifier"))

    # No outcome: the source states no winner, and this document usually has no
    # scoreline either. No statistics: the event mapping emits none. No market and
    # no abbreviation: neither is an official term and TeamShape is sh:closed.
    participant = {"kind": "team"}
    _put(participant, "provider_id", _provider_id(competitor, "team"))
    _put(participant, "name", _text(competitor.get("name")))
    _put(participant, "alignment", alignment)
    # `None` here is the mapping's deliberate placeholder for "the boxscore feed
    # has not merged the runs in yet". Omitted rather than zeroed; the capability
    # report is what tells a consumer the gap exists.
    _put(participant, "score", _text(scores.get(alignment)))
    return participant


def _mark_declared(section):
    """Record how a mapping-constant identifier was resolved, if there is one.

    Guarded on the identifier's presence: a resolution method on a section that
    carries no ``provider_id`` is an annotation on nothing, and it would also turn
    an empty season block into a truthy one and get an otherwise-absent season
    emitted.
    """
    if "provider_id" in section:
        section["resolution_method"] = MAPPING_CONSTANT_RESOLUTION
    return section


def _competition(document):
    block = _section(document, "sport:competition")
    season_block = _section(block, "sport:season")

    competition = {}
    # A mapping constant, not a provider field. See MAPPING_CONSTANT_IDENTIFIERS,
    # and note the resolution method that says so in the crosswalk itself.
    _put(competition, "provider_id", _provider_id(block, "competition"))
    _mark_declared(competition)
    _put(competition, "name", _text(block.get("name")))
    # No type: the source never says whether this game is in the regular season
    # or the post-season, so spct:season-regular would be a guess.
    season = {}
    _put(season, "provider_id", _provider_id(season_block, "season"))
    _mark_declared(season)
    _put(season, "name", _text(season_block.get("name")))
    _put(competition, "season", season or None)
    return competition


def _site(document):
    venue = _section(document, "sport:venue")
    site = {}
    _put(site, "provider_id", _provider_id(venue, "venue"))
    _put(site, "name", _text(venue.get("name")))
    _put(site, "city", _text(venue.get("schema:addressLocality")))
    # No country: the mapping does not emit one, and a country is not derivable
    # from a city name without a gazetteer nothing here has.
    return site


def _event(document, provider_id, status, label):
    event = {"provider_id": provider_id}
    _put(event, "label", label)
    _put(event, "start_time", _text(document.get("schema:startDate")))
    event["status"] = status
    # No clock and no inning: the event mapping emits neither. No attendance and
    # no end time either.
    return event


def to_observation(payload, *, observed_at):
    """One Sportradar MLB event document as a ``canonical-observation/1``.

    ``payload`` is never modified. The document is not validated here:
    ``validate_observation`` is this adapter's acceptance test and
    ``canonical_envelope`` refuses to serialize a document that fails it, so
    validating inside would only decide the same thing twice.
    """
    _check_sport(payload)

    event_id = _provider_id(payload, "event")
    if event_id is None:
        raise ValueError(
            "sportradar mlb document has no {0} @id, so there is nothing to mint "
            "an event identity from; no observation was produced".format(
                LEGACY_URN_STEMS["event"])
        )

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
    # No phase: the source states no stage, series or round.
    _put(observation, "site", _site(payload) or None)
    observation["event"] = _event(
        payload, event_id, _event_status(payload), label)
    observation["participants"] = [
        _participant(competitor, _section(payload, "sport:score"))
        for competitor in competitors
    ]
    # The source document's own bytes, unaltered. Every fact this adapter
    # declined to map — the deliberate score nulls, the doubleheader
    # disambiguators sport:gameNumber and sport:doubleHeader, the team markets and
    # abbreviations and the mapping's duplicate sport:matchStatus — is readable
    # here, which is what makes "we omitted it" checkable.
    observation["raw"] = payload

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

"""Sportradar soccer summary payload -> ``canonical-observation/1``.

The input is Sportradar's soccer ``sport_event_summary`` shape: a document
carrying ``sport_event`` and ``sport_event_status`` side by side. The source of
evidence for this adapter is
``agent-templates/iptc-mappings/example-sportradar.json``, a provider example
already checked into this repository. **No Sportradar endpoint was called to
write this module, and nothing here claims a licence to redistribute Sportradar
data**: a checked-in example is evidence of a payload's *shape*, not an
entitlement. That is why :data:`RIGHTS_DATA_CLASS` names the evidence rather
than a licence and why every observation this adapter emits is ``prototype_only``
and ``commercial_use: False``. A production consumer refuses it, which is the
intended outcome.

**The raw provider payload is the source, not this repository's own output.**
``tools/iptc/fixtures/baseline/sportradar-soccer-event.json`` is the *legacy
mapping output* for the same match, and ``sportradar-soccer-timeline.json`` is a
hand-authored mapping-contract shape for a **different, synthetic** match.
Reading either would make this adapter a converter of Machina's own documents,
and joining the two would attach a synthetic timeline to a real fixture. Both
baseline files are left untouched: they are the "before" evidence this corrected
output is measured against.

Seven provider-specific readings, written down because each one is a decision a
reader would otherwise have to reverse-engineer:

``sport_event_status.status`` **is mapped, and an unmapped value raises.**
    :data:`EVENT_STATUS_BY_CODE` is the whole correspondence.
    ``observation.event.status`` is a required field and there is no defensible
    default status, so a value outside the table raises :class:`ValueError`
    naming it. Sportradar's own ``unknown`` is deliberately **absent** from the
    table: it is the provider declining to state a status, and mapping it to any
    canonical key would turn a declined statement into an asserted one.

``sport_event_status.match_status`` **is not mapped.**
    It is a finer-grained reading (``ended``, ``1st_half``, ``halftime``, …)
    drawn from a different vocabulary, and the two disagree in shape rather than
    in detail. It survives verbatim in ``raw``, so nothing is lost.

``sport_event_context.season.id`` **is the season's provider identifier.**
    Sportradar addresses a season by an identifier of its own — unlike
    API-Football, where a season is the pair (league, year) and only the year is
    stated. The two adapters are deliberately not symmetric here: each records
    what its provider actually addresses the entity by.

``sport_event_context.round`` **produces no competition phase.**
    It is ``{"number": 1}`` — an ordinal inside a season rather than something
    Sportradar addresses a round by — and ``sport_event_context.stage`` carries
    no identifier at all. Recording either as a ``provider_id`` would invent
    provider-native evidence. API-Football's ``league.round`` is genuinely
    different: that API takes that exact string as a round key.

``sport_event_context.stage.type`` **is not a competition type.**
    It describes the stage, and this observation carries no stage. Reading it as
    the competition's type would put a ``spct:`` NewsCode on the graph that
    nothing in the payload says about the competition.

``venue.country_name`` **is the venue's country, so it is recorded.**
    API-Football's ``league.country`` is the *competition's* country, which is
    why the API-Football adapter omits a venue country and this one does not.

``sport_event_status.winner_id`` **names one competitor; the others lose.**
    Sportradar states the winner by identifier rather than by a flag per side,
    so both outcomes fall out of one stated fact. The key is absent on a draw
    *and* on a fixture that has not finished, so absence produces no outcome at
    all: deriving ``draw`` from an equal scoreline would be this module inferring
    a result the provider declined to state.

Competitors are emitted **home first, then away**, regardless of the order the
payload lists them in. Alignment is a stated fact (``competitor.qualifier``) and
list order is not, but every adapter in this profile emits the same order so
cross-provider comparisons fail on concepts rather than on ordering.

The event label is composed from provider-stated names (``"{home} vs {away}"``).
A label is a rendering of facts already in the payload rather than a new claim,
and the alternative — an event resource with no human-readable handle — helps
nobody.

Python 3.9-compatible, standard library only, no import of ``tools.*``.
"""

from __future__ import annotations

from .. import SCHEMA_VERSION

#: How provenance names this adapter. A literal rather than ``__name__`` so a
#: checked-in fixture does not change bytes the day this module is copied
#: somewhere with a different package path.
ADAPTER_NAME = "tools.iptc.canonical.adapters.sportradar_soccer"

#: The adapter implementation version, cited in provenance. A string, because it
#: is evidence in a document rather than a number to compare.
ADAPTER_VERSION = "1"

#: Scoped to the soccer connector rather than to "sportradar", because Sportradar
#: publishes a separate feed per sport and each gets its own adapter. Two feeds
#: sharing one crosswalk namespace would claim that their identifier spaces are
#: one, which nothing here has checked.
PROVIDER_NAMESPACE = "sportradar-soccer"

#: ``licensed``: access to this provider is contractual, whatever the provenance
#: of any one checked-in example.
PROVIDER_FAMILY = "licensed"

#: What the data in an observation from this adapter actually is. It names the
#: evidence — a sanitized provider example checked into this repository — and
#: deliberately contains no word that could be read as a redistribution right.
RIGHTS_DATA_CLASS = "licensed-provider-example-fixture"

#: The endpoint *class* the payload comes from. Never a URL, a query or a
#: credential: ``validate_observation`` refuses anything request-shaped, because a
#: fixture is the artefact that gets published.
ENDPOINT_CLASS = "sportradar-soccer/sport_event_summary"

#: IPTC ``medtop`` for association football, and the ``event_view`` sport key.
SPORT_MEDTOP = "20001065"
SPORT_KEY = "soccer"

#: Sportradar's own identifier for association football. The payload states its
#: sport, so this adapter checks it rather than assuming: read a tennis payload
#: and it would assert association football, and nothing downstream could tell.
SPORT_PROVIDER_ID = "sr:sport:1"

#: ``sport_event_status.status`` -> the canonical status key
#: ``tools.iptc.canonical.vocab.EVENT_STATUS`` maps into a pinned
#: ``speventstatus:`` NewsCode. A test asserts every value here is a key of that
#: table, so a code that no pinned scheme admits cannot be added silently.
#:
#: ``ended`` and ``closed`` both read as ``closed``: Sportradar distinguishes
#: "the match finished" from "the result is settled", and the profile has one
#: concept for a finished event. ``unknown`` is deliberately not here — see this
#: module's docstring. ``abandoned``, ``interrupted`` and the half-by-half
#: readings belong to ``match_status``, which this adapter does not map, so no
#: canonical key is claimed for them either.
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

#: The order competitors are emitted in. Anything Sportradar qualifies otherwise
#: follows, in payload order, rather than being dropped.
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


def _event_status(status_block):
    """The canonical status key, or a raise naming the provider code."""
    code = _text(status_block.get("status"))
    if code is None:
        raise ValueError(
            "sportradar payload has no sport_event_status.status, so its "
            "canonical event status cannot be determined; no observation was "
            "produced"
        )
    if code not in EVENT_STATUS_BY_CODE:
        raise ValueError(
            "sportradar sport_event_status.status '{0}' has no canonical event "
            "status in this adapter. Add it to EVENT_STATUS_BY_CODE with a "
            "defensible speventstatus: reading rather than letting it default; "
            "no observation was produced".format(code)
        )
    return EVENT_STATUS_BY_CODE[code]


def _check_sport(context):
    stated = _text(_section(context, "sport").get("id"))
    if stated is not None and stated != SPORT_PROVIDER_ID:
        raise ValueError(
            "sportradar payload states sport '{0}', but this adapter asserts "
            "medtop {1} (association football, {2}). Use the adapter for that "
            "sport; no observation was produced".format(
                stated, SPORT_MEDTOP, SPORT_PROVIDER_ID)
        )


def _ordered_competitors(sport_event):
    """Competitors home first, then away, then anything else in payload order."""
    competitors = _items(sport_event, "competitors")
    ordered = []
    for alignment in ALIGNMENT_ORDER:
        ordered.extend(c for c in competitors
                       if _text(c.get("qualifier")) == alignment)
    ordered.extend(c for c in competitors if c not in ordered)
    return ordered


def _participant(competitor, status_block):
    scores = {"home": status_block.get("home_score"),
              "away": status_block.get("away_score")}
    alignment = _text(competitor.get("qualifier"))
    winner_id = _text(status_block.get("winner_id"))
    provider_id = _text(competitor.get("id"))

    participant = {"kind": "team"}
    _put(participant, "provider_id", provider_id)
    _put(participant, "name", _text(competitor.get("name")))
    _put(participant, "alignment", alignment)
    _put(participant, "score", _text(scores.get(alignment)))
    if winner_id is not None and provider_id is not None:
        participant["outcome"] = "win" if provider_id == winner_id else "loss"
    return participant


def _competition(context):
    competition_block = _section(context, "competition")
    season_block = _section(context, "season")

    competition = {}
    _put(competition, "provider_id", _text(competition_block.get("id")))
    _put(competition, "name", _text(competition_block.get("name")))
    # No competition type: stage.type describes the stage, not the competition.
    season = {}
    _put(season, "provider_id", _text(season_block.get("id")))
    _put(season, "name", _text(season_block.get("name")))
    _put(competition, "season", season or None)
    return competition


def _site(sport_event):
    venue = _section(sport_event, "venue")
    site = {}
    _put(site, "provider_id", _text(venue.get("id")))
    _put(site, "name", _text(venue.get("name")))
    _put(site, "city", _text(venue.get("city_name")))
    # Recorded, unlike API-Football's: this really is the venue's country.
    _put(site, "country", _text(venue.get("country_name")))
    return site


def _event(sport_event, status_block, provider_id, status, label):
    event = {"provider_id": provider_id}
    _put(event, "label", label)
    _put(event, "start_time", _text(sport_event.get("start_time")))
    event["status"] = status
    attendance = _section(_section(sport_event, "sport_event_conditions"),
                          "attendance")
    _put(event, "attendance", _text(attendance.get("count")))
    # No clock: the summary payload carries period_scores, which are scores per
    # period rather than a clock reading, and no minute at all.
    return event


def to_observation(payload, *, observed_at):
    """One Sportradar soccer summary payload as a ``canonical-observation/1``.

    ``payload`` is never modified. The document is not validated here:
    ``validate_observation`` is this adapter's acceptance test and
    ``canonical_envelope`` refuses to serialize a document that fails it, so
    validating inside would only decide the same thing twice.
    """
    sport_event = _section(payload, "sport_event")
    status_block = _section(payload, "sport_event_status")
    context = _section(sport_event, "sport_event_context")

    _check_sport(context)

    event_id = _text(sport_event.get("id"))
    if event_id is None:
        raise ValueError(
            "sportradar payload has no sport_event.id, so there is nothing to "
            "mint an event identity from; no observation was produced"
        )

    competitors = _ordered_competitors(sport_event)
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
            "source_refs": [{"kind": "endpoint-class", "value": ENDPOINT_CLASS}],
        },
        "rights": {
            "data_class": RIGHTS_DATA_CLASS,
            "prototype_only": True,
            "commercial_use": False,
        },
        "sport": {"medtop": SPORT_MEDTOP, "key": SPORT_KEY},
        "competition": _competition(context),
    }
    # No phase: sport_event_context.round is an ordinal and stage has no id.
    _put(observation, "site", _site(sport_event) or None)
    observation["event"] = _event(
        sport_event, status_block, event_id, _event_status(status_block), label)
    observation["participants"] = [
        _participant(competitor, status_block) for competitor in competitors
    ]
    # The provider's own bytes, unaltered. Every fact this adapter declined to map
    # — ball locations, referees, weather, broadcast channels, the match
    # situation, the period scores and match_status — is readable here, which is
    # what makes "we omitted it" checkable.
    observation["raw"] = payload

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

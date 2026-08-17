"""Serialize one canonical observation into the Machina Sports Schema outputs.

Two serializers read the observation and neither reads the other:
:func:`sport_schema_graph` produces RDF-compatible JSON-LD, :func:`event_view`
produces a compact non-RDF projection. Deriving one from the other would make a
bug in the first silently become a bug in the second, and would tie the shape a
product consumes to the shape a standards consumer consumes.

Three rules the whole module is arranged around:

**Nothing is fabricated.** :func:`_put` drops ``None``, ``""`` and every
placeholder rather than asserting it, and :func:`_resource` returns nothing at
all when a resource would carry an ``@id``, a ``@type`` and no facts. An absent
fact leaves no trace, which is the only honest representation of not knowing.

**No ``machina:`` property ever lands on an official resource.** The pinned
shapes are ``sh:closed`` (RFC 001 §5.4), so provenance and provider crosswalk are
separate ``machina:``-typed siblings that reference the official resource by
``@id``.

**Nothing is minted here.** ``id_resolver(kind, *parts) -> str`` is injected, so
RFC 001 §7.6 — "serializers and templates do not mint identifiers" — stays
literally true and a later phase can swap in the canonical identity service
without touching this file.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible, standard
library only, and no import of ``tools.*``. That is why the shared JSON-LD
context is read from ``shared-context.json`` next to this file rather than from
``tools.iptc.context`` — the vendored package has no such module. That file is a
byte-identical copy of the published context and a test in this repository
asserts it, so it is a copy rather than a second source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import (
    ACCEPTED_SCHEMA_VERSIONS,
    EXACT_OBSERVATION_PROFILE_VERSION,
    MACHINA_SCHEMA_VERSION,
    PROFILE_VERSION,
    SERIALIZER_NAME,
    SERIALIZER_VERSION,
    UPSTREAM_COMMIT,
    UPSTREAM_REPOSITORY,
    UPSTREAM_TARGET_VERSION,
)
from .capabilities import (
    GRAPH_UNAVAILABLE_EXACT_START_TIME,
    GRAPH_UNAVAILABLE_REASONS,
    capability_report,
)
from .observation import (
    PLACEHOLDERS,
    RESOLUTION_DEFAULT,
    RESOLUTION_METHODS,
    TEMPORAL_EVIDENCE_KEY,
    source_ref_credential_findings,
    validate_observation,
)
from .vocab import (
    ACTION_CLASS,
    COMPETITION_TYPE,
    EVENT_OUTCOME,
    EVENT_OUTCOME_TYPE,
    EVENT_STATUS,
    PLAYER_STATUS,
    SOCCER_POSITION,
    newscode,
)

#: The shared Machina JSON-LD context, packaged beside this module.
SHARED_CONTEXT_PATH = Path(__file__).resolve().parent / "shared-context.json"


class GraphUnavailable(ValueError):
    """No ``sport_schema_graph`` exists for this observation, and why.

    RFC 002 §12.4.

    A typed refusal carrying an enumerated ``reason``, rather than an
    unstructured error or an empty ``@graph``. Both alternatives are worse in the
    same direction: an empty graph looks like a conformant document describing
    nothing, and a message a consumer has to pattern-match is not a contract.

    A ``ValueError`` subclass, so callers that already handle the serializer's
    refusals keep working and only callers that want to branch on the reason have
    to know the type.
    """

    def __init__(self, reason):
        if reason not in GRAPH_UNAVAILABLE_REASONS:
            raise ValueError("unknown graph-unavailability reason")
        # The token is in the message too: a log line that carries only str(error)
        # should still name the reason a reader has to act on.
        super().__init__(
            "sport_schema_graph is unavailable for this observation: {0}".format(reason)
        )
        self.reason = reason


#: How a provider identifier came to be attached to a Machina identity is stated
#: by the observation, one entity at a time, and validated there.
#: ``RESOLUTION_METHODS`` and ``RESOLUTION_DEFAULT`` are imported from
#: ``observation`` above rather than restated here: a closed value set with two
#: copies is a closed value set one edit away from having four members.

_context_cache = None


def shared_context():
    """The prefix table every document produced here inlines by value.

    Returns a fresh copy each call: the table is handed straight to a caller
    inside ``@context``, and one caller mutating it would silently change the
    vocabulary of every later document.
    """
    global _context_cache
    if _context_cache is None:
        with SHARED_CONTEXT_PATH.open(encoding="utf-8") as handle:
            document = json.load(handle)
        _context_cache = {
            key: value
            for key, value in document["@context"].items()
            if isinstance(value, str)
        }
    return dict(_context_cache)


# ---------------------------------------------------------------------------
# Omission helpers
# ---------------------------------------------------------------------------

def _usable(value):
    """Whether ``value`` is a fact rather than a stand-in for one."""
    if value is None:
        return False
    if isinstance(value, str):
        return value not in PLACEHOLDERS
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _put(node, key, value):
    """Set ``key`` only when ``value`` is a fact. Omission over fabrication."""
    if _usable(value):
        node[key] = value


def _text(value):
    """``value`` as a string when it is a fact, else ``None``.

    Scores, counts, attendance and statistics are ``sh:datatype xsd:string`` in
    the pinned shapes, so ``0`` and ``"0"`` must both serialize to ``"0"`` — and
    ``0`` must stay a fact, which is why this is not a truthiness test.
    """
    if value is None or isinstance(value, (dict, list)):
        return None
    text = value if isinstance(value, str) else str(value)
    return text if text not in PLACEHOLDERS else None


def _datetime(value):
    """A typed ``xsd:dateTime`` value node, or nothing."""
    text = _text(value)
    return None if text is None else {"@value": text, "@type": "xsd:dateTime"}


def _reference(identifier):
    return None if not identifier else {"@id": identifier}


def _mapped(table, scheme, key):
    """A NewsCode node reference, or ``None`` when nothing defensible maps.

    An unmapped provider value is **omitted**, never guessed and never defaulted.
    The value itself survives in ``event_view`` and in ``observation.raw``, which
    is where a consumer can see what the provider actually said.
    """
    if not isinstance(key, str) or key not in table:
        return None
    return newscode(scheme, table[key])


def _resource(node_id, type_name, properties):
    """A graph node, or ``None`` when it would assert nothing.

    A resource carrying only an ``@id`` and a ``@type`` is a stub: it looks like
    a described entity to every consumer and describes nothing. Emitting none is
    the truthful outcome.
    """
    if not node_id or not properties:
        return None
    node = {"@id": node_id, "@type": type_name}
    node.update(properties)
    return node


class _Graph:
    """Accumulates resources in emission order, first description wins.

    Keying on ``@id`` makes a duplicate identifier structurally impossible rather
    than merely unlikely. Two descriptions of one identifier cannot both be
    authoritative, and the profile's ``duplicate-node-id`` gate exists precisely
    because that has happened in this repository before.
    """

    def __init__(self):
        self.nodes = []
        self._seen = set()

    def add(self, node):
        if node is None or node["@id"] in self._seen:
            return
        self._seen.add(node["@id"])
        self.nodes.append(node)


# ---------------------------------------------------------------------------
# Observation accessors
# ---------------------------------------------------------------------------

def _observation(document):
    value = document.get("observation") if isinstance(document, dict) else None
    return value if isinstance(value, dict) else {}


def _section(observation, key):
    value = observation.get(key)
    return value if isinstance(value, dict) else {}


def _list(observation, key):
    value = observation.get(key)
    return value if isinstance(value, list) else []


def _participants(observation):
    return [p for p in _list(observation, "participants") if isinstance(p, dict)]


def _namespace(observation):
    return _section(observation, "provider").get("namespace")


class _Identities:
    """Every Machina identifier this observation needs, minted once.

    Built before any resource is emitted, because the graph and ``event_view``
    both reference them and a second minting pass is a second chance to disagree.
    """

    def __init__(self, observation, id_resolver):
        competition = _section(observation, "competition")
        season = competition.get("season") if isinstance(
            competition.get("season"), dict) else {}
        phase = _section(observation, "phase")
        site = _section(observation, "site")
        event = _section(observation, "event")

        self.competition = None
        self.season = None
        self.phase = None
        self.site = None
        self.event = None
        self.teams = {}
        self.athletes = {}
        self.participations = {}

        if competition.get("provider_id"):
            self.competition = id_resolver("competition", competition["provider_id"])
            if season.get("provider_id"):
                self.season = id_resolver(
                    "competition", competition["provider_id"], season["provider_id"]
                )
            if phase.get("provider_id"):
                self.phase = id_resolver(
                    "phase", competition["provider_id"],
                    season.get("provider_id", ""), phase["provider_id"],
                )
        if site.get("provider_id"):
            self.site = id_resolver("site", site["provider_id"])
        if event.get("provider_id"):
            self.event = id_resolver("event", event["provider_id"])

        for participant in _participants(observation):
            provider_id = participant.get("provider_id")
            kind = participant.get("kind")
            if not provider_id or kind not in ("team", "individual"):
                continue
            if kind == "team":
                self.teams.setdefault(provider_id, id_resolver("team", provider_id))
            else:
                self.athletes.setdefault(provider_id, id_resolver("athlete", provider_id))
            if event.get("provider_id"):
                self.participations.setdefault(
                    (kind, provider_id),
                    id_resolver("participation", event["provider_id"], kind, provider_id),
                )

    #: The competition an event is *in*: the season when the provider supplies
    #: one, because that is the competition the fixture actually belongs to.
    @property
    def event_competition(self):
        return self.season or self.competition


# ---------------------------------------------------------------------------
# sport_schema_graph
# ---------------------------------------------------------------------------

def _medtop(observation):
    code = _section(observation, "sport").get("medtop")
    return _reference("medtop:{0}".format(code)) if _text(code) else None


def _competition_resources(graph, observation, ids):
    competition = _section(observation, "competition")
    sport = _medtop(observation)

    properties = {}
    _put(properties, "rdfs:label", _text(competition.get("name")))
    _put(properties, "sport:sport", sport)
    _put(properties, "sport:competitionType",
         _mapped(COMPETITION_TYPE, "spct", competition.get("type")))
    graph.add(_resource(ids.competition, "sport:Competition", properties))

    season = competition.get("season") if isinstance(competition.get("season"), dict) else {}
    season_properties = {}
    _put(season_properties, "rdfs:label", _text(season.get("name")))
    _put(season_properties, "sport:sport", sport)
    _put(season_properties, "sport:competitionType", _mapped(COMPETITION_TYPE, "spct", "season"))
    _put(season_properties, "sport:parent", _reference(ids.competition))
    graph.add(_resource(ids.season, "sport:Competition", season_properties))

    phase = _section(observation, "phase")
    phase_properties = {}
    _put(phase_properties, "rdfs:label", _text(phase.get("name")))
    _put(phase_properties, "sport:sport", sport)
    _put(phase_properties, "sport:phaseInCompetition", _reference(ids.event_competition))
    graph.add(_resource(ids.phase, "sport:CompetitionPhase", phase_properties))


def _site_resource(graph, observation, ids):
    site = _section(observation, "site")
    properties = {}
    # SiteShape is sh:closed with no property shapes at all, so rdfs:label (an
    # ignored property) is the only thing a Site may carry. City and country are
    # facts, and they travel in event_view rather than being forced into a shape
    # that would reject them.
    _put(properties, "rdfs:label", _text(site.get("name")))
    graph.add(_resource(ids.site, "sport:Site", properties))


def _competitor_resources(graph, observation, ids):
    for participant in _participants(observation):
        if participant.get("kind") != "team":
            continue
        properties = {}
        _put(properties, "rdfs:label", _text(participant.get("name")))
        graph.add(_resource(ids.teams.get(participant.get("provider_id")),
                            "sport:Team", properties))
    for participant in _participants(observation):
        if participant.get("kind") != "individual":
            continue
        properties = {}
        _put(properties, "rdfs:label", _text(participant.get("name")))
        graph.add(_resource(ids.athletes.get(participant.get("provider_id")),
                            "sport:Athlete", properties))


def _event_resource(graph, observation, ids):
    event = _section(observation, "event")
    properties = {}
    _put(properties, "rdfs:label", _text(event.get("label")))
    _put(properties, "sport:sport", _medtop(observation))
    _put(properties, "sport:eventInCompetition", _reference(ids.event_competition))
    _put(properties, "sport:eventInCompetitionPhase", _reference(ids.phase))
    _put(properties, "sport:location", _reference(ids.site))
    _put(properties, "sport:startDateTime", _datetime(event.get("start_time")))
    _put(properties, "sport:endDateTime", _datetime(event.get("end_time")))
    _put(properties, "sport:eventStatus",
         _mapped(EVENT_STATUS, "speventstatus", event.get("status")))
    _put(properties, "sport:eventOutcomeType",
         _mapped(EVENT_OUTCOME_TYPE, "speventoutcometype", event.get("outcome_type")))
    _put(properties, "sport:attendance", _text(event.get("attendance")))
    # The clock is deliberately absent: EventShape admits no clock property, and
    # RFC 001 forbids expressing a reading as a dateTime. It survives in
    # event_view, which is the projection built for consumers who need it.
    participations = [
        _reference(ids.participations[(p["kind"], p["provider_id"])])
        for p in _participants(observation)
        if (p.get("kind"), p.get("provider_id")) in ids.participations
    ]
    _put(properties, "sport:participation", participations)
    graph.add(_resource(ids.event, "sport:Event", properties))


def _participation_label(participant, observation):
    name = _text(participant.get("name"))
    if name is None:
        return None
    event_label = _text(_section(observation, "event").get("label"))
    if event_label is None:
        return "{0} participation".format(name)
    return "{0} participation in {1}".format(name, event_label)


def _statistics(participant):
    """Provider statistics as ``prefix:localName`` string literals.

    Sorted so output is byte-stable regardless of the order an adapter happened
    to build its dictionary in. Whether a given statistic is admissible on this
    participation class is the pinned ``sh:closed`` shape's decision, not this
    module's: a statistic on the wrong class must fail layer 2 loudly rather than
    be dropped quietly here.
    """
    statistics = participant.get("statistics")
    if not isinstance(statistics, dict):
        return []
    pairs = []
    for curie in sorted(statistics):
        value = _text(statistics[curie])
        if value is not None:
            pairs.append((curie, value))
    return pairs


def _participation_resources(graph, observation, ids):
    for participant in _participants(observation):
        if participant.get("kind") != "team":
            continue
        properties = {}
        _put(properties, "rdfs:label", _participation_label(participant, observation))
        _put(properties, "sport:participationBy",
             _reference(ids.teams.get(participant.get("provider_id"))))
        _put(properties, "sport:alignment", _text(participant.get("alignment")))
        _put(properties, "sport:score", _text(participant.get("score")))
        _put(properties, "sport:eventOutcome",
             _mapped(EVENT_OUTCOME, "speventoutcome", participant.get("outcome")))
        for curie, value in _statistics(participant):
            _put(properties, curie, value)
        graph.add(_resource(
            ids.participations.get(("team", participant.get("provider_id"))),
            "sport:TeamParticipation", properties))

    for participant in _participants(observation):
        if participant.get("kind") != "individual":
            continue
        properties = {}
        _put(properties, "rdfs:label", _participation_label(participant, observation))
        _put(properties, "sport:participationBy",
             _reference(ids.athletes.get(participant.get("provider_id"))))
        _put(properties, "sport:playerStatus",
             _mapped(PLAYER_STATUS, "spplayerstatus", participant.get("player_status")))
        _put(properties, "sport:positionEvent",
             _mapped(SOCCER_POSITION, "spsocposition", participant.get("position")))
        _put(properties, "sport:score", _text(participant.get("score")))
        _put(properties, "sport:eventOutcome",
             _mapped(EVENT_OUTCOME, "speventoutcome", participant.get("outcome")))
        _put(properties, "sport:uniformNumberEvent",
             _text(participant.get("uniform_number")))
        _put(properties, "sport:teamParticipation",
             _reference(ids.participations.get(("team", participant.get("team_provider_id")))))
        for curie, value in _statistics(participant):
            _put(properties, curie, value)
        graph.add(_resource(
            ids.participations.get(("individual", participant.get("provider_id"))),
            "sport:IndividualParticipation", properties))


def _membership_resources(graph, observation, ids, id_resolver):
    names = {
        (p.get("kind"), p.get("provider_id")): _text(p.get("name"))
        for p in _participants(observation)
    }
    for membership in _list(observation, "memberships"):
        if not isinstance(membership, dict):
            continue
        individual_id = membership.get("individual_provider_id")
        team_id = membership.get("team_provider_id")
        athlete = ids.athletes.get(individual_id)
        team = ids.teams.get(team_id)
        if not athlete or not team:
            # A membership between entities this observation never described is
            # an assertion about two things it cannot name. Omitted.
            continue
        properties = {}
        athlete_name = names.get(("individual", individual_id))
        team_name = names.get(("team", team_id))
        if athlete_name and team_name:
            _put(properties, "rdfs:label",
                 "{0} membership of {1}".format(athlete_name, team_name))
        _put(properties, "sport:member", _reference(athlete))
        _put(properties, "sport:membershipOf", _reference(team))
        _put(properties, "sport:uniformNumber", _text(membership.get("uniform_number")))
        graph.add(_resource(
            id_resolver("membership", individual_id, team_id),
            "sport:IndividualMembership", properties))


def _action_resources(graph, observation, ids, id_resolver):
    event = _section(observation, "event")
    for action in _list(observation, "actions"):
        if not isinstance(action, dict):
            continue
        ordinal = action.get("ordinal")
        action_class = _mapped(ACTION_CLASS, "spactionclass", action.get("class"))
        if ordinal is None or not event.get("provider_id") or action_class is None:
            # sport:class is mandatory on an Action (RFC 002 §2) and the only
            # pinned scheme for it is spactionclass:. An action whose class does
            # not map is carried by event_view and observation.raw instead of
            # being emitted as an Action that asserts no class.
            continue
        properties = {}
        _put(properties, "rdfs:label", _text(action.get("label")))
        _put(properties, "sport:actionInEvent", _reference(ids.event))
        properties["sport:class"] = action_class
        _put(properties, "sport:actionDateTime", _datetime(action.get("action_time")))
        _put(properties, "sport:minutesElapsed", _text(action.get("minute")))
        _put(properties, "sport:periodValue", _text(action.get("period")))
        _put(properties, "sport:sequenceNumber", _text(ordinal))
        participant_id = action.get("participant_provider_id")
        _put(properties, "sport:participation", _reference(
            ids.participations.get(("individual", participant_id))
            or ids.participations.get(("team", participant_id))
        ))
        graph.add(_resource(
            id_resolver("action", event["provider_id"], ordinal),
            "sport:Action", properties))


def _resolution_method(section):
    """How ``section``'s provider identifier came to be attached.

    The observation states it; this reads it. Nothing here decides the answer
    from the provider namespace or from the shape of the identifier, because that
    would put knowledge of which adapters hardcode what into the one module that
    is shared by all of them — and then correcting an adapter would mean editing
    the serializer.

    Absence means :data:`RESOLUTION_DEFAULT`. A value outside
    :data:`RESOLUTION_METHODS` is refused by ``validate_observation``, which
    ``canonical_envelope`` runs before anything reaches here; it is not silently
    rewritten, because a validator that repairs hides the bug it exists to
    expose and this module has the same job.
    """
    stated = _text(section.get("resolution_method")) if isinstance(section, dict) else None
    return stated if stated in RESOLUTION_METHODS else RESOLUTION_DEFAULT


def _crosswalk_entries(observation, ids):
    """``(kind, machina_id, provider_id, evidence, method)`` per identified entity.

    Participations, memberships and actions are absent on purpose: they are
    structures this serializer derives, not entities the provider named, so
    there is no provider identifier that could honestly be recorded for them.
    """
    competition = _section(observation, "competition")
    season = competition.get("season") if isinstance(competition.get("season"), dict) else {}
    phase = _section(observation, "phase")
    site = _section(observation, "site")
    event = _section(observation, "event")
    entries = [
        ("competition", ids.competition, competition.get("provider_id"),
         "observation.competition.provider_id", _resolution_method(competition)),
        ("season", ids.season, season.get("provider_id"),
         "observation.competition.season.provider_id", _resolution_method(season)),
        ("phase", ids.phase, phase.get("provider_id"),
         "observation.phase.provider_id", _resolution_method(phase)),
        ("site", ids.site, site.get("provider_id"),
         "observation.site.provider_id", _resolution_method(site)),
        ("event", ids.event, event.get("provider_id"),
         "observation.event.provider_id", _resolution_method(event)),
    ]
    for index, participant in enumerate(_participants(observation)):
        provider_id = participant.get("provider_id")
        evidence = "observation.participants[{0}].provider_id".format(index)
        method = _resolution_method(participant)
        if participant.get("kind") == "team":
            entries.append(("team", ids.teams.get(provider_id), provider_id,
                            evidence, method))
        elif participant.get("kind") == "individual":
            entries.append(("athlete", ids.athletes.get(provider_id), provider_id,
                            evidence, method))
    return [
        (kind, machina_id, _text(provider_id), evidence, method)
        for kind, machina_id, provider_id, evidence, method in entries
        if machina_id and _text(provider_id) is not None
    ]


# ---------------------------------------------------------------------------
# event_view
# ---------------------------------------------------------------------------

def _local_name(curie):
    """``spsocstat:shotsTotal`` -> ``shotsTotal``.

    ``event_view`` promises no RDF, and a CURIE key would drag the whole
    vocabulary into a projection built for consumers who asked not to have it.
    """
    return curie.split(":", 1)[1] if ":" in curie else curie


def _view_statistics(participant):
    statistics = {}
    for curie, value in _statistics(participant):
        _put(statistics, _local_name(curie), value)
    return statistics


def _view_entity(section, identifier, *fields):
    """A compact ``{"id": …, <field>: …}`` block, or nothing."""
    block = {}
    _put(block, "id", identifier)
    for field in fields:
        _put(block, field, _text(section.get(field)))
    return block if len(block) > 1 else {}


def _view_participants(observation, ids):
    participants = []
    for participant in _participants(observation):
        if participant.get("kind") != "team":
            continue
        block = {}
        _put(block, "id", ids.teams.get(participant.get("provider_id")))
        _put(block, "role", _text(participant.get("alignment")))
        _put(block, "name", _text(participant.get("name")))
        _put(block, "score", _text(participant.get("score")))
        _put(block, "outcome", _text(participant.get("outcome")))
        _put(block, "statistics", _view_statistics(participant))
        if block:
            participants.append(block)
    return participants


def _view_players(observation, ids):
    """Individuals, kept in their own list rather than beside the teams.

    ``role`` means alignment for a team and would have to mean position or
    starter-status for a person. One key with two meanings is the kind of shape a
    consumer reads wrongly once and then works around forever.
    """
    players = []
    for participant in _participants(observation):
        if participant.get("kind") != "individual":
            continue
        block = {}
        _put(block, "id", ids.athletes.get(participant.get("provider_id")))
        _put(block, "name", _text(participant.get("name")))
        _put(block, "team_id", ids.teams.get(participant.get("team_provider_id")))
        _put(block, "status", _text(participant.get("player_status")))
        _put(block, "position", _text(participant.get("position")))
        _put(block, "uniform_number", _text(participant.get("uniform_number")))
        _put(block, "statistics", _view_statistics(participant))
        if block:
            players.append(block)
    return players


def _view_actions(observation):
    """Actions verbatim from the observation, including the ones the graph drops.

    An action whose class does not map to a pinned scheme is not emitted as
    ``sport:Action`` at all. This is where it survives, which is why the two
    serializers read the observation and not each other.
    """
    actions = []
    for action in _list(observation, "actions"):
        if not isinstance(action, dict):
            continue
        block = {}
        _put(block, "ordinal", _text(action.get("ordinal")))
        _put(block, "class", _text(action.get("class")))
        _put(block, "label", _text(action.get("label")))
        _put(block, "minute", _text(action.get("minute")))
        _put(block, "period", _text(action.get("period")))
        _put(block, "time", _text(action.get("action_time")))
        if block:
            actions.append(block)
    return actions


def _temporal_evidence(event):
    """``event.temporal_evidence`` as the view carries it: verbatim, or nothing.

    A copy rather than the object itself, so a caller mutating the projection
    cannot reach back into the observation it was derived from. Nothing is
    reformatted — ``source_value`` is the observed lexical fact, offset included,
    and rewriting it is the one thing this member exists to prevent (G1).
    """
    evidence = event.get(TEMPORAL_EVIDENCE_KEY)
    return dict(evidence) if isinstance(evidence, dict) else None


def event_view(document, *, id_resolver):
    """A compact non-RDF projection of one observation (RFC 002 §3).

    **Derived from the observation, never from :func:`sport_schema_graph`.** Two
    serializers reading one input is the property that lets either be replaced
    without silently corrupting the other; deriving one from the other would make
    a bug in the first become a bug in the second, invisibly. The shared
    ``id_resolver`` is how the two agree on identifiers without one reading the
    other's output.

    This is also the escape hatch for everything IPTC cannot express: an unmapped
    status, a soccer action type with no pinned vocabulary (RFC 001 §9.2), a
    venue's city and country that ``SiteShape`` admits no property for, and a
    clock reading that ``EventShape`` has nowhere to put. Those facts are real,
    and this is where they live rather than being forced into a shape that
    rejects them.
    """
    observation = _observation(document)
    ids = _Identities(observation, id_resolver)
    competition = _section(observation, "competition")
    season = competition.get("season") if isinstance(competition.get("season"), dict) else {}
    event = _section(observation, "event")
    clock = event.get("clock") if isinstance(event.get("clock"), dict) else {}

    view = {}
    _put(view, "event_id", ids.event)
    _put(view, "label", _text(event.get("label")))
    _put(view, "sport", _text(_section(observation, "sport").get("key")))
    _put(view, "start_time", _text(event.get("start_time")))
    # Where a reduced-precision start actually lives (RFC 002 §12.4): the graph refuses
    # such an observation, so this projection is the only place the bounds, the
    # verbatim source value and its derivation travel — with our provenance
    # beside them, which is the whole reason they are here rather than in an
    # interoperability document no external consumer can read provenance from.
    # Copied whole and unrewritten: the member IS the evidence, and a projection
    # that picked fields would be a second spelling of it.
    _put(view, TEMPORAL_EVIDENCE_KEY, _temporal_evidence(event))
    _put(view, "end_time", _text(event.get("end_time")))
    _put(view, "status", _text(event.get("status")))
    _put(view, "outcome_type", _text(event.get("outcome_type")))
    _put(view, "attendance", _text(event.get("attendance")))
    clock_view = {}
    _put(clock_view, "minute", _text(clock.get("minute")))
    _put(clock_view, "period", _text(clock.get("period")))
    _put(view, "clock", clock_view)
    _put(view, "competition", _view_entity(competition, ids.competition, "name", "type"))
    _put(view, "season", _view_entity(season, ids.season, "name"))
    _put(view, "phase", _view_entity(_section(observation, "phase"), ids.phase, "name"))
    _put(view, "site", _view_entity(_section(observation, "site"), ids.site,
                                    "name", "city", "country"))
    _put(view, "participants", _view_participants(observation, ids))
    _put(view, "players", _view_players(observation, ids))
    _put(view, "actions", _view_actions(observation))

    provider = {}
    _put(provider, "namespace", _text(_namespace(observation)))
    _put(provider, "family", _text(_section(observation, "provider").get("family")))
    # The only place a provider payload survives. It is exempt from the
    # placeholder scan for the reason RFC 002 §1.1 gives: a real payload is full
    # of provider-side nulls, and rewriting it would destroy the one field whose
    # value is being an unaltered record.
    raw = observation.get("raw")
    if isinstance(raw, (dict, list)) and raw:
        provider["raw"] = raw
    _put(view, "provider", provider)
    return {"event_view": view}


#: The one note a ``source_refs`` entry carries when the adapter did not write its
#: own, stating the constraint the value was accepted under.
SOURCE_REF_NOTE = "endpoint class only; no URL, query or credential is recorded"


def _source_refs(adapter):
    """``adapter.source_refs`` reduced to ``kind``/``value``/``note``.

    Entries carrying a credential or a request are dropped rather than projected,
    using ``observation.source_ref_credential_findings`` — the same rule that
    refuses them at the boundary, not a second copy of it. Dropping here is not a
    relaxation of that refusal: :func:`canonical_envelope` still raises, and
    ``validate_observation`` still reports. It is what makes this function fail
    closed when it is called on its own, which it can be — it used to project
    whatever it was handed on the grounds that the validator had run, and nothing
    made that true.

    Entries the adapter left unannotated get the note that states the constraint
    they were accepted under. That note reads "no URL, query or credential is
    recorded", so stamping it onto an entry that holds one is the specific lie
    this filter exists to prevent.
    """
    refs = adapter.get("source_refs")
    if not isinstance(refs, list):
        return []
    projected = []
    for ref in refs:
        if not isinstance(ref, dict) or source_ref_credential_findings(ref):
            continue
        entry = {}
        _put(entry, "kind", _text(ref.get("kind")))
        _put(entry, "value", _text(ref.get("value")))
        if not entry:
            continue
        entry["note"] = _text(ref.get("note")) or SOURCE_REF_NOTE
        projected.append(entry)
    return projected


def provenance_block(document, *, id_resolver):
    """The envelope's provenance block (RFC 002 §5).

    Every conformance claim cites the profile **and** the pin, because "conforms
    to Sport Schema 1.1" without a commit is a claim about a moving target.

    ``determinism`` is read off ``id_resolver`` rather than stated here. The
    resolver is injected so a later phase can swap in the canonical identity
    service; a serializer that hard-coded the current resolver's digest would
    quietly start lying on the day that happens, and a provenance block that can
    be wrong is worse than one that omits.
    """
    observation = _observation(document)
    adapter = _section(observation, "adapter")
    block = {}
    _put(block, "provider", dict(_section(observation, "provider")))
    _put(block, "adapter", dict(adapter))
    if isinstance(block.get("adapter"), dict):
        block["adapter"].pop("source_refs", None)
    block["serializer"] = {"name": SERIALIZER_NAME, "version": SERIALIZER_VERSION}
    # The conformance claim of THIS document, not the version of the serializer
    # that built it — the envelope's own `profile` says that. An exact
    # observation projects byte-for-byte as `machina-iptc-profile/1.1` specifies,
    # so 1.1 is what it conforms to; 1.2 adds one rule and it is a rule about a
    # case this document is not. Stamping the running profile here instead moved
    # a field inside `provenance`, which RFC 002 §12 freezes for exact
    # observations, and made the enumerated diff five items instead of four.
    block["profile"] = (
        PROFILE_VERSION
        if TEMPORAL_EVIDENCE_KEY in _section(observation, "event")
        else EXACT_OBSERVATION_PROFILE_VERSION
    )
    block["upstream_pin"] = {
        "repository": UPSTREAM_REPOSITORY,
        "commit": UPSTREAM_COMMIT,
        "target_version": UPSTREAM_TARGET_VERSION,
    }
    _put(block, "observed_at", _text(observation.get("observed_at")))
    _put(block, "source_refs", _source_refs(adapter))
    _put(block, "rights", dict(_section(observation, "rights")))
    _put(block, "determinism", dict(getattr(id_resolver, "strategy", None) or {}))
    return {"provenance": block}


def provider_identifiers(document, *, id_resolver):
    """The crosswalk as the envelope carries it (RFC 002 §5).

    The same entry list the graph's ``machina:ProviderIdentifier`` resources are
    built from, projected into plain JSON. One list feeding both views is what
    keeps them from disagreeing; a second pass over the observation would be a
    second chance to.

    ``resolution_method`` is the observation's, not a constant. It was one until
    A16, which made four entries across the Sportradar NFL and MLB rows claim the
    provider had stated a competition and season identifier that those payloads
    do not contain at all.

    ``confidence`` is ``1.0`` for all three methods, and that is not an oversight.
    It measures the strength of the *link* between a provider string and a Machina
    identity, and all three methods are exact statements about where the string
    came from — there is no fuzzy matching in this phase, so nothing here is a
    match that could have been a near-miss. What varies is how much the string is
    worth as evidence about the provider, and ``resolution_method`` is the field
    that says so. Spreading invented confidences over it would be exactly the
    false precision the profile exists to keep out.
    """
    observation = _observation(document)
    ids = _Identities(observation, id_resolver)
    namespace = _text(_namespace(observation))
    if namespace is None:
        return []
    return [
        {
            "machina_id": machina_id,
            "entity_type": kind,
            "provider_namespace": namespace,
            "provider_id": provider_id,
            "resolution_method": method,
            "confidence": 1.0,
            "evidence": evidence,
        }
        for kind, machina_id, provider_id, evidence, method
        in _crosswalk_entries(observation, ids)
    ]


def _crosswalk_resources(graph, observation, ids, id_resolver):
    namespace = _text(_namespace(observation))
    if namespace is None:
        return
    for kind, machina_id, provider_id, _evidence, method in _crosswalk_entries(
            observation, ids):
        properties = {
            "rdfs:label": "{0} {1} {2}".format(namespace, kind, provider_id),
            "machina:identifies": {"@id": machina_id},
            "machina:providerNamespace": namespace,
            "machina:providerId": provider_id,
            "machina:resolutionMethod": method,
        }
        graph.add(_resource(
            id_resolver("provider-identifier", kind, provider_id),
            "machina:ProviderIdentifier", properties))


def _provenance_resource(graph, observation, ids, id_resolver):
    event = _section(observation, "event")
    namespace = _text(_namespace(observation))
    if not ids.event or not event.get("provider_id") or namespace is None:
        return
    adapter = _section(observation, "adapter")
    rights = _section(observation, "rights")
    properties = {}
    _put(properties, "rdfs:label",
         "{0} observation of event {1}".format(namespace, ids.event.rsplit(":", 1)[-1]))
    properties["machina:describes"] = {"@id": ids.event}
    properties["machina:providerNamespace"] = namespace
    _put(properties, "machina:observedAt", _datetime(observation.get("observed_at")))
    _put(properties, "machina:adapterVersion", _text(adapter.get("version")))
    properties["machina:serializerVersion"] = SERIALIZER_VERSION
    _put(properties, "machina:rightsClass", _text(rights.get("data_class")))
    graph.add(_resource(
        id_resolver("observation-provenance", event["provider_id"]),
        "machina:ObservationProvenance", properties))


def sport_schema_graph(document, *, id_resolver):
    """One JSON-LD document: the shared context inlined, one flat ``@graph``.

    Resources are emitted in the fixed order of the RFC 002 §2 table, so the same
    observation always produces byte-identical output. Nothing here reads the
    clock, the environment or the network.
    """
    declared = document.get("schema_version") if isinstance(document, dict) else None
    if declared not in ACCEPTED_SCHEMA_VERSIONS:
        raise ValueError(
            "schema_version: '{0}' is not one of {1}".format(
                declared, ", ".join(ACCEPTED_SCHEMA_VERSIONS)))
    observation = _observation(document)
    # Before any resource is built, so no partial Event can escape and so the
    # refusal cannot depend on which resource happened to be reached first. The
    # rule is "this document carries the member", not "carries a member that
    # validated": a document whose evidence is broken has no exact instant
    # either, and emitting a graph for it would be the fail-open branch.
    if TEMPORAL_EVIDENCE_KEY in _section(observation, "event"):
        raise GraphUnavailable(GRAPH_UNAVAILABLE_EXACT_START_TIME)
    ids = _Identities(observation, id_resolver)
    graph = _Graph()

    _competition_resources(graph, observation, ids)
    _site_resource(graph, observation, ids)
    _competitor_resources(graph, observation, ids)
    _event_resource(graph, observation, ids)
    _participation_resources(graph, observation, ids)
    _membership_resources(graph, observation, ids, id_resolver)
    _action_resources(graph, observation, ids, id_resolver)
    _crosswalk_resources(graph, observation, ids, id_resolver)
    _provenance_resource(graph, observation, ids, id_resolver)

    return {"@context": shared_context(), "@graph": graph.nodes}


# ---------------------------------------------------------------------------
# canonical_envelope
# ---------------------------------------------------------------------------

def canonical_envelope(document, *, id_resolver):
    """The full output envelope (RFC 002 §9).

    Composes the four builders plus :func:`capability_report`. Every part is the
    builder's own output rather than a second code path producing the same shape,
    because a second code path is the thing that drifts.

    Raises ``ValueError`` when ``validate_observation`` reports anything. The
    serializer is not a repair shop: an envelope built from an invalid observation
    is a conformance claim, citing a profile and a pin, about a document nobody
    validated. Refusing is the only honest outcome, and the message carries every
    error rather than the first, so one run tells the adapter author everything to
    fix.
    """
    errors = validate_observation(document)
    if errors:
        raise ValueError(
            "canonical observation is not valid, so no envelope was produced:\n"
            + "\n".join("  - {0}".format(error) for error in errors)
        )

    observation = _observation(document)
    # Built key by key rather than as one literal, because one member is now
    # conditional and the emission order is part of the output: the corrected
    # fixtures are compared byte-for-byte, so a reordered envelope is a diff.
    envelope = {
        "schema_version": MACHINA_SCHEMA_VERSION,
        "profile": PROFILE_VERSION,
    }
    try:
        envelope["sport_schema_graph"] = sport_schema_graph(
            document, id_resolver=id_resolver)
    except GraphUnavailable:
        # Not a swallowed error: the member is *omitted*, and
        # capability_report below states the same enumerated reason on the same
        # record. Catching the typed refusal rather than re-testing the
        # condition here keeps one rule in one place — a second copy of "is this
        # observation graph-able" is a second copy that can disagree.
        pass
    envelope["event_view"] = event_view(document, id_resolver=id_resolver)["event_view"]
    envelope["provenance"] = provenance_block(
        document, id_resolver=id_resolver)["provenance"]
    envelope["provider_ids"] = provider_identifiers(document, id_resolver=id_resolver)
    # Unwrapped: capability_report returns its own {"capabilities": …} envelope,
    # and nesting it would give the consumer
    # machina_sports_schema.capabilities.capabilities.
    envelope["capabilities"] = capability_report(document)["capabilities"]
    envelope["rights"] = dict(_section(observation, "rights"))
    return {"machina_sports_schema": envelope}

"""API-Football fixture payload -> ``canonical-observation/1``.

The input is one element of API-Football's ``/fixtures`` response: the
``fixture`` / ``league`` / ``teams`` / ``goals`` / ``score`` object. The source of
evidence for this adapter is
``agent-templates/iptc-mappings/example-apifootball.json``, a provider example
already checked into this repository. **No API-Football endpoint was called to
write this module, and nothing here claims a licence to redistribute
API-Football data**: a checked-in example is evidence of a payload's *shape*, not
an entitlement. That is why :data:`RIGHTS_DATA_CLASS` names the evidence rather
than a licence and why every observation this adapter emits is
``prototype_only`` and ``commercial_use: False``. A production consumer refuses
it, which is the intended outcome.

Six provider-specific readings, written down because each one is a decision a
reader would otherwise have to reverse-engineer:

``fixture.status.short`` **is mapped, and an unmapped code raises.**
    :data:`EVENT_STATUS_BY_SHORT_CODE` is the whole correspondence. A short code
    outside it raises :class:`ValueError` naming the code, because
    ``observation.event.status`` is a required field and there is no such thing as
    a defensible default status — a fixture wrongly reported ``closed`` is worse
    than one that failed to convert.

``league.season`` **is recorded verbatim as the season's provider identifier.**
    API-Football has no standalone season identifier; a season is the pair
    (league, year). The year is what the provider actually states, so that is what
    the crosswalk records. The league scoping comes from the identity tuple the
    resolver hashes — ``("competition", league_id, season_year)`` — rather than
    from a composite string this adapter would have had to invent and then claim
    was provider-native.

``league.round`` **is both the phase's name and its provider identifier.**
    API-Football addresses a round by that exact string (it is the value its own
    API takes for a round), so recording it is provider-native evidence rather
    than a derived key.

``teams.*.winner`` **maps only its two stated values.**
    ``true`` is a win and ``false`` is a loss. API-Football nulls **both** flags
    for a draw *and* for a fixture that has not finished, so the flag alone cannot
    tell those apart: null produces no outcome. Deriving ``draw`` from an equal
    scoreline would be this module inferring a result the provider declined to
    state, and ``sport:eventOutcome`` is exactly the wrong place for an inference.

``goals`` **is the scoreline;** ``score.halftime`` **is a different fact.**
    ``score.extratime`` and ``score.penalty`` are null on a fixture decided in
    regulation, and a null is not the statement "no extra time was played". So no
    ``outcome_type`` is emitted either: reading absent extra time as ``regular``
    is the same inference in a different field. All four survive in ``raw``.

``league.standings`` **is not a competition type.**
    It says a standings table exists, not that the competition is a league, so no
    ``spct:`` code is emitted from it.

Labels for the event and the season are composed from provider-stated names
(``"{home} vs {away}"``, ``"{league} {season}"``). A label is a rendering of facts
already in the payload rather than a new claim, and the alternative — an event
resource with no human-readable handle — helps nobody.

Python 3.9-compatible, standard library only, no import of ``tools.*``.
"""

from __future__ import annotations

from .. import SCHEMA_VERSION

#: How provenance names this adapter. A literal rather than ``__name__`` so a
#: checked-in fixture does not change bytes the day this module is copied
#: somewhere with a different package path.
ADAPTER_NAME = "tools.iptc.canonical.adapters.api_football"

#: The adapter implementation version, cited in provenance. A string, because it
#: is evidence in a document rather than a number to compare.
ADAPTER_VERSION = "1"

PROVIDER_NAMESPACE = "api-football"

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
ENDPOINT_CLASS = "api-football/fixtures"

#: IPTC ``medtop`` for association football, and the ``event_view`` sport key.
#: Constant because this provider's fixtures endpoint covers exactly one sport.
SPORT_MEDTOP = "20001065"
SPORT_KEY = "soccer"

#: ``fixture.status.short`` -> the canonical status key
#: ``tools.iptc.canonical.vocab.EVENT_STATUS`` maps into a pinned
#: ``speventstatus:`` NewsCode. A test asserts every value here is a key of that
#: table, so a code that no pinned scheme admits cannot be added silently.
#:
#: ``INT`` (interrupted) reads as ``suspended`` rather than ``abandoned``: it is a
#: match stopped with the intention of resuming. ``WO`` (walkover) reads as
#: ``awarded``, the same as ``AWD`` — both are results decided off the pitch.
#: ``delayed`` and ``rescheduled`` are canonical keys this provider has no code
#: for, and they are absent rather than approximated.
EVENT_STATUS_BY_SHORT_CODE = {
    "TBD": "not_started",
    "NS": "not_started",
    "1H": "in_progress",
    "2H": "in_progress",
    "ET": "in_progress",
    "BT": "in_progress",
    "P": "in_progress",
    "LIVE": "in_progress",
    "HT": "halftime",
    "FT": "closed",
    "AET": "closed",
    "PEN": "closed",
    "SUSP": "suspended",
    "INT": "suspended",
    "PST": "postponed",
    "CANC": "cancelled",
    "ABD": "abandoned",
    "AWD": "awarded",
    "WO": "awarded",
}


def _section(node, key):
    value = node.get(key) if isinstance(node, dict) else None
    return value if isinstance(value, dict) else {}


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


def _event_status(fixture):
    """The canonical status key, or a raise naming the provider code.

    ``observation.event.status`` is required, and every candidate default is a
    claim about a fixture nobody observed. Raising here puts the failure in the
    adapter, where the mapping table that needs the new entry lives.
    """
    short_code = _text(_section(fixture, "status").get("short"))
    if short_code is None:
        raise ValueError(
            "api-football payload has no fixture.status.short, so its canonical "
            "event status cannot be determined; no observation was produced"
        )
    if short_code not in EVENT_STATUS_BY_SHORT_CODE:
        raise ValueError(
            "api-football fixture.status.short '{0}' has no canonical event "
            "status in this adapter. Add it to EVENT_STATUS_BY_SHORT_CODE with a "
            "defensible speventstatus: reading rather than letting it default; "
            "no observation was produced".format(short_code)
        )
    return EVENT_STATUS_BY_SHORT_CODE[short_code]


def _outcome(team):
    """``win`` / ``loss``, or nothing.

    ``None`` covers a draw and an unfinished fixture alike, because API-Football's
    flag does not distinguish them. See this module's docstring.
    """
    winner = team.get("winner")
    if winner is True:
        return "win"
    if winner is False:
        return "loss"
    return None


def _participant(team, alignment, score):
    participant = {"kind": "team"}
    _put(participant, "provider_id", _text(team.get("id")))
    _put(participant, "name", _text(team.get("name")))
    participant["alignment"] = alignment
    _put(participant, "score", _text(score))
    _put(participant, "outcome", _outcome(team))
    return participant


def _competition(league):
    competition = {}
    _put(competition, "provider_id", _text(league.get("id")))
    name = _text(league.get("name"))
    _put(competition, "name", name)
    # No competition type: league.standings says a table exists, not what kind of
    # competition this is.
    season = {}
    year = _text(league.get("season"))
    _put(season, "provider_id", year)
    if name is not None and year is not None:
        season["name"] = "{0} {1}".format(name, year)
    _put(competition, "season", season or None)
    return competition


def _phase(league):
    phase = {}
    round_name = _text(league.get("round"))
    _put(phase, "provider_id", round_name)
    _put(phase, "name", round_name)
    return phase


def _site(fixture):
    venue = _section(fixture, "venue")
    site = {}
    _put(site, "provider_id", _text(venue.get("id")))
    _put(site, "name", _text(venue.get("name")))
    _put(site, "city", _text(venue.get("city")))
    # No country: league.country is the competition's country, not the venue's.
    return site


def _event(fixture, provider_id, status, label):
    event = {"provider_id": provider_id}
    _put(event, "label", label)
    _put(event, "start_time", _text(fixture.get("date")))
    event["status"] = status
    # fixture.status.elapsed is the minutes-played reading. EventShape has nowhere
    # to put a clock, so this reaches event_view only — which is the projection
    # built for consumers who need it. No period: fixture.periods holds two epoch
    # seconds, and a period number is not derivable from them.
    clock = {}
    _put(clock, "minute", _text(_section(fixture, "status").get("elapsed")))
    _put(event, "clock", clock or None)
    return event


def to_observation(payload, *, observed_at):
    """One API-Football fixture payload as a ``canonical-observation/1`` document.

    ``payload`` is never modified. The document is not validated here:
    ``validate_observation`` is this adapter's acceptance test and
    ``canonical_envelope`` refuses to serialize a document that fails it, so
    validating inside would only decide the same thing twice.
    """
    fixture = _section(payload, "fixture")
    league = _section(payload, "league")
    teams = _section(payload, "teams")
    goals = _section(payload, "goals")

    event_id = _text(fixture.get("id"))
    if event_id is None:
        raise ValueError(
            "api-football payload has no fixture.id, so there is nothing to mint "
            "an event identity from; no observation was produced"
        )

    home = _section(teams, "home")
    away = _section(teams, "away")
    home_name, away_name = _text(home.get("name")), _text(away.get("name"))
    label = None
    if home_name is not None and away_name is not None:
        label = "{0} vs {1}".format(home_name, away_name)

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
        "competition": _competition(league),
    }
    _put(observation, "phase", _phase(league) or None)
    _put(observation, "site", _site(fixture) or None)
    observation["event"] = _event(
        fixture, event_id, _event_status(fixture), label)
    observation["participants"] = [
        _participant(home, "home", goals.get("home")),
        _participant(away, "away", goals.get("away")),
    ]
    # The provider's own bytes, unaltered. Every fact this adapter declined to map
    # — the referee, the period timestamps, half-time and the four nulls — is
    # readable here, which is what makes "we omitted it" checkable.
    observation["raw"] = payload

    return {"schema_version": SCHEMA_VERSION, "observation": observation}

"""Machina concept -> IPTC NewsCode, for pinned schemes only.

Two rules govern every table below.

**A NewsCode is a node reference, never a bare string** (RFC 001 §9). A literal
cannot be followed to a concept, and layers 3 and 4 reject it. :func:`newscode`
is the only way to produce one, and it always returns ``{"@id": ...}``.

**Only pinned schemes appear here.** A test asserts, for every entry in every
table, that the scheme is pinned and that the concept IRI is actually in it. That
test is the guard, not this file: these modules cannot load the ontology at
runtime — they are vendored into a package with no rdflib — so a mapping is only
as trustworthy as the assertion that checks it against the pin.

That is also why soccer action types are **absent**. `tools/prefixes.ttl` binds
the prefix and the pinned SHACL references the scheme, but no vocabulary TTL for
it exists at the pinned commit, so layer 4 reports its values ``unverifiable``
and RFC 001 §9.2 makes ``unverifiable`` fail closed. There is nothing defensible
to map into, and inventing a substitute code list would produce documents that
look validated and are not. Soccer action detail is carried by
:data:`ACTION_CLASS` for the class, with the provider's own action type surviving
verbatim in ``event_view`` and ``machina:evidence``.

An unmapped key raises. A provider status with no defensible mapping is omitted
from ``sport:eventStatus`` and preserved in ``event_view`` — never guessed,
never defaulted.

Vendored-safe: Python 3.9-compatible, standard library only, no import of
``tools.*``.
"""

from __future__ import annotations

#: Scheme prefix -> path segment under ``http://cv.iptc.org/newscodes/``.
#:
#: Almost always identical, and deliberately written out anyway: upstream binds
#: at least one prefix whose path segment differs from its name, so inferring the
#: path from the prefix is a trap that produces IRIs resolving to nothing.
SCHEME_PATH = {
    "speventstatus": "speventstatus",
    "speventoutcome": "speventoutcome",
    "speventoutcometype": "speventoutcometype",
    "spct": "spct",
    "spactionclass": "spactionclass",
    "spplayerstatus": "spplayerstatus",
    "spsocposition": "spsocposition",
}

#: Machina canonical event status -> ``speventstatus:``. Adapters normalise their
#: provider's own codes into these keys; RFC 001 §9.1 records the per-provider
#: correspondence. Note ``canceled``, spelled with one ``l``, as upstream spells
#: it.
EVENT_STATUS = {
    "not_started": "pre-event",
    "in_progress": "mid-event",
    "halftime": "intermission",
    "closed": "post-event",
    "postponed": "postponed",
    "cancelled": "canceled",
    "suspended": "suspended",
    "abandoned": "halted",
    "awarded": "forfeited",
    "delayed": "delayed",
    "rescheduled": "rescheduled",
}

#: Participant outcome -> ``speventoutcome:``.
EVENT_OUTCOME = {
    "win": "win",
    "loss": "loss",
    "draw": "tie",
    "tie": "tie",
    "undecided": "undecided",
    "place": "place",
    "show": "show",
}

#: How the result was reached -> ``speventoutcometype:``.
EVENT_OUTCOME_TYPE = {
    "regular": "regular",
    "extra_time": "extra-time",
    "overtime": "overtime",
    "shootout": "shootout",
    "authority_decision": "authority-decision",
    "unanimous_decision": "decision-unanimous",
}

#: Competition kind -> ``spct:``.
COMPETITION_TYPE = {
    "recurring-competition": "recurring-competition",
    "season": "season",
    "regular-season": "season-regular",
    "post-season": "post-season",
    "tournament": "tournament",
    "league": "league",
    "division": "division",
    "conference": "conference",
    "competition": "competition",
}

#: Action class -> ``spactionclass:``. Seven concepts, and no more: this is the
#: class of an action, not its sport-specific type.
ACTION_CLASS = {
    "score": "score",
    "substitution": "substitution",
    "infraction": "infraction",
    "penalty": "penalty",
    "play": "play",
    "timeout": "timeout",
    "official-procedure": "official-procedure",
}

#: Player availability -> ``spplayerstatus:``.
PLAYER_STATUS = {
    "starter": "starter",
    "bench": "bench",
    "substitute": "bench",
    "injured": "injured",
    "scratched": "scratched",
    "sidelined": "sidelined",
    "suspended": "suspended",
}

#: Soccer position -> ``spsocposition:``.
SOCCER_POSITION = {
    "goalkeeper": "goalkeeper",
    "defender": "defender",
    "central-defender": "central-defender",
    "sweeper": "sweeper",
    "left-fullback": "left-fullback",
    "right-fullback": "right-fullback",
    "midfielder": "midfielder",
    "center-midfielder": "center-midfielder",
    "defensive-midfielder": "defensive-midfielder",
    "attacking-midfielder": "attacking-midfielder",
    "left-midfielder": "left-midfielder",
    "right-midfielder": "right-midfielder",
    "left-wing": "left-wing",
    "right-wing": "right-wing",
    "forward": "forward",
    "center-forward": "center-forward",
    "striker": "striker",
}

#: Every table, by the scheme it maps into. The test that checks each code
#: against the pin walks this, so a table missing here is a table nobody checks.
TABLES = {
    "speventstatus": EVENT_STATUS,
    "speventoutcome": EVENT_OUTCOME,
    "speventoutcometype": EVENT_OUTCOME_TYPE,
    "spct": COMPETITION_TYPE,
    "spactionclass": ACTION_CLASS,
    "spplayerstatus": PLAYER_STATUS,
    "spsocposition": SOCCER_POSITION,
}


def newscode(scheme, code):
    """The node reference ``{"@id": "scheme:code"}``.

    Raises ``KeyError`` for a scheme this module does not map into — which is how
    a caller is stopped from reaching an unpinned scheme by passing its name in
    as a string — and ``ValueError`` for a code absent from that scheme's table.
    Neither is recoverable by guessing, so neither is softened into a default.
    """
    if scheme not in TABLES:
        raise KeyError(
            "{0} is not a scheme this profile maps into; every mapped scheme "
            "must be pinned and checkable offline".format(scheme)
        )
    if code not in set(TABLES[scheme].values()):
        raise ValueError(
            "'{0}' is not a mapped {1} code".format(code, scheme)
        )
    return {"@id": "{0}:{1}".format(scheme, code)}

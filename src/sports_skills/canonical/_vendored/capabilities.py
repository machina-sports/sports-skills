"""Describe what a payload actually supports, and check it against what a
consumer needs.

The point of a capability report is that a consumer can decide *before* it
parses rather than after it fails, so two properties matter more than coverage:

- **Tiers do not skip.** An observation with advanced statistics but no clock is
  ``core``, not ``advanced``. Reporting ``advanced`` would tell a consumer it can
  rely on live data it will never get.
- **Compatibility fails closed.** An unrecognised capability name — a typo in a
  consumer's ``requires``, a name from a future schema version — forces
  ``compatible: false``. A check that reads an unknown name as satisfied is worse
  than no check, because it is trusted.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible, standard
library only, and no import of ``tools.*``.
"""

from __future__ import annotations

TIER_ORDER = ("core", "live", "advanced")

TIER_REQUIRED = {
    "core": ("event.identity", "event.competition", "event.participants",
             "event.start_time", "event.status", "provenance"),
    "live": ("event.clock", "event.period", "event.actions"),
    "advanced": ("participant.player_statistics",),
}

TIER_OPTIONAL = {
    "core": ("event.score", "event.result"),
    "live": ("event.play_by_play", "event.live_statistics"),
    "advanced": ("event.coordinates", "event.tracking", "event.expected_metrics",
                 "event.lineups", "event.formations"),
}

#: Every capability name this version knows about. Membership is what separates
#: "absent" from "unknown", so it is the whole basis of failing closed.
ALL_CAPABILITIES = tuple(sorted(
    set(name for tier in TIER_ORDER for name in TIER_REQUIRED[tier])
    | set(name for tier in TIER_ORDER for name in TIER_OPTIONAL[tier])
))

#: Statuses after which a scoreline exists. An event that has started and
#: reports no score is a parse failure dressed as a fact.
STARTED_STATUSES = ("in_progress", "closed")

#: The finding raised for exactly that case. Kept out of tier gating on purpose,
#: so a legitimate pre-match payload still reaches core.
SCORE_VIOLATION = "score-absent-on-started-event"


def _participants(observation):
    value = observation.get("participants")
    return value if isinstance(value, list) else []


def _has(mapping, key):
    return isinstance(mapping, dict) and bool(mapping.get(key))


def _any_participant(observation, predicate):
    return any(
        predicate(p) for p in _participants(observation) if isinstance(p, dict)
    )


def _clock(observation):
    event = observation.get("event")
    return event.get("clock") if isinstance(event, dict) else None


def _actions(observation):
    value = observation.get("actions")
    return value if isinstance(value, list) else []


#: How each capability is decided from a ``canonical-observation/1`` document.
#:
#: A capability with no entry here is **not expressible** in this schema version:
#: the observation has no field that could carry it. Those are reported absent —
#: they are absent — but also listed under ``not_expressible``, because "the
#: provider did not supply tracking data" and "this contract cannot carry
#: tracking data" send a consumer to two different places, and only one of them
#: is a provider conversation.
_PRESENCE = {
    "event.identity":
        lambda o: _has(o.get("event"), "provider_id"),
    "event.competition":
        lambda o: _has(o.get("competition"), "provider_id"),
    "event.participants":
        lambda o: len(_participants(o)) >= 2,
    "event.start_time":
        lambda o: _has(o.get("event"), "start_time"),
    "event.status":
        lambda o: _has(o.get("event"), "status"),
    "provenance":
        lambda o: _has(o.get("provider"), "namespace") and bool(o.get("observed_at")),
    "event.score":
        lambda o: _any_participant(o, lambda p: bool(p.get("score"))),
    "event.result":
        lambda o: _any_participant(o, lambda p: bool(p.get("outcome"))),
    "event.clock":
        lambda o: _has(_clock(o), "minute"),
    "event.period":
        lambda o: _has(_clock(o), "period"),
    "event.actions":
        lambda o: len(_actions(o)) > 0,
    "event.play_by_play":
        lambda o: bool(_actions(o)) and all(
            isinstance(a, dict) and bool(a.get("label")) for a in _actions(o)
        ),
    "event.live_statistics":
        lambda o: _has(o.get("event"), "status")
        and o["event"]["status"] == "in_progress"
        and _any_participant(o, lambda p: bool(p.get("statistics"))),
    "participant.player_statistics":
        lambda o: _any_participant(
            o, lambda p: p.get("kind") == "individual" and bool(p.get("statistics"))
        ),
    "event.lineups":
        lambda o: _any_participant(o, lambda p: p.get("kind") == "individual"),
}

#: Named rather than derived, so adding a field to the observation schema forces
#: a decision here instead of silently leaving a capability unreachable.
NOT_EXPRESSIBLE = tuple(sorted(set(ALL_CAPABILITIES) - set(_PRESENCE)))


def capability_report(document):
    """What ``document`` supports, tier by tier."""
    observation = document.get("observation") if isinstance(document, dict) else None
    if not isinstance(observation, dict):
        observation = {}

    present = sorted(
        name for name in ALL_CAPABILITIES
        if name in _PRESENCE and _PRESENCE[name](observation)
    )
    present_set = set(present)
    absent = sorted(set(ALL_CAPABILITIES) - present_set)

    by_tier = {}
    tiers_satisfied = []
    for tier in TIER_ORDER:
        required = TIER_REQUIRED[tier]
        optional = TIER_OPTIONAL[tier]
        by_tier[tier] = {
            "required_present": sorted(n for n in required if n in present_set),
            "required_absent": sorted(n for n in required if n not in present_set),
            "optional_present": sorted(n for n in optional if n in present_set),
            "optional_absent": sorted(n for n in optional if n not in present_set),
        }
        # Break rather than continue: a tier is only reached when every tier
        # below it is reached too.
        if by_tier[tier]["required_absent"]:
            break
        tiers_satisfied.append(tier)

    event = observation.get("event") if isinstance(observation.get("event"), dict) else {}
    violations = []
    if event.get("status") in STARTED_STATUSES and "event.score" not in present_set:
        violations.append(SCORE_VIOLATION)

    return {
        "capabilities": {
            "tier": tiers_satisfied[-1] if tiers_satisfied else None,
            "tiers_satisfied": tiers_satisfied,
            "present": present,
            "absent": absent,
            "not_expressible": list(NOT_EXPRESSIBLE),
            "by_tier": by_tier,
            "violations": violations,
        }
    }


def check_compatibility(capabilities, requires=(), optional=()):
    """Whether a consumer's stated needs are met by ``capabilities``.

    Fails closed on any name outside :data:`ALL_CAPABILITIES`, in ``requires``
    **and** in ``optional``. A typo is a typo wherever it appears, and treating
    an unknown optional as merely absent is how a consumer ships against a
    capability that does not exist.
    """
    present = set(capabilities.get("present", ()))
    known = set(ALL_CAPABILITIES)

    unknown = sorted(set(name for name in tuple(requires) + tuple(optional)
                         if name not in known))
    missing_required = sorted(
        set(name for name in requires if name in known and name not in present)
    )
    missing_optional = sorted(
        set(name for name in optional if name in known and name not in present)
    )
    return {
        "compatible": not missing_required and not unknown,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "unknown_capabilities": unknown,
    }

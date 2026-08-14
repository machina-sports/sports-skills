"""Read normalized NBA event and play-by-play values as one observation."""

import copy
import re

from .._vendored import SCHEMA_VERSION
from .._vendored.observation import PLACEHOLDERS, derive_bounds

ADAPTER_NAME = "sports_skills.canonical.adapters.nba"
ADAPTER_VERSION = "1"
CANONICAL_VERSION = "0.2.0"
NORMALIZER_NAME = "sports_skills.nba._connector._normalize_event"

SOURCE_REFS = ({"kind": "endpoint-class", "value": "espn/summary"},)
PROVIDER = {"namespace": "sports-skills/espn", "family": "open-data"}
RIGHTS = {
    "data_class": "open-public",
    "prototype_only": True,
    "commercial_use": False,
}
SPORT = {"medtop": "20000851", "key": "basketball"}
COMPETITION = {
    "provider_id": "nba",
    "name": "NBA",
    "resolution_method": "declared",
}

STATUS = {
    "not_started": "not_started",
    "live": "in_progress",
    "1st_half": "in_progress",
    "2nd_half": "in_progress",
    "period_break": "in_progress",
    "halftime": "halftime",
    "closed": "closed",
    "postponed": "postponed",
    "cancelled": "cancelled",
    "suspended": "suspended",
    "delayed": "delayed",
}

_OFFSET = r"(?:[Zz]|[+-]\d{2}:\d{2})"
_START_TIME = {
    "minute": re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}" + _OFFSET + r"$"),
    "second": re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}" + _OFFSET + r"$"),
    "fractional_second": re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}\.\d+" + _OFFSET + r"$"),
}


def _text(value):
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = value if isinstance(value, str) else str(value)
    return None if text in PLACEHOLDERS else text


def _put(node, key, value):
    if value is not None:
        node[key] = value


def _required(value, field):
    text = _text(value)
    if text is None:
        raise ValueError(f"native field '{field}' is required")
    return text


def _status(value):
    if value not in STATUS:
        raise ValueError(f"'{value}' is not a status the NBA adapter maps")
    return STATUS[value]


def _participants(event):
    competitors = event.get("competitors")
    if not isinstance(competitors, list) or len(competitors) != 2:
        raise ValueError("a canonical NBA observation requires exactly two teams")

    by_alignment = {}
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        alignment = competitor.get("home_away")
        if alignment not in ("home", "away") or alignment in by_alignment:
            raise ValueError("NBA competitors require one home and one away team")
        team = competitor.get("team") or {}
        participant = {
            "kind": "team",
            "provider_id": _required(team.get("id"), "competitors[].team.id"),
            "name": _required(team.get("name"), "competitors[].team.name"),
            "alignment": alignment,
        }
        _put(participant, "score", _text(competitor.get("score")))
        by_alignment[alignment] = (participant, competitor.get("winner") is True)

    if set(by_alignment) != {"home", "away"}:
        raise ValueError("NBA competitors require one home and one away team")

    ordered = [by_alignment["home"], by_alignment["away"]]
    if event.get("status") == "closed" and sum(winner for _team, winner in ordered) == 1:
        for participant, winner in ordered:
            participant["outcome"] = "win" if winner else "loss"
    return [participant for participant, _winner in ordered]


def _temporal_event(event, start_time_precision):
    if start_time_precision not in _START_TIME:
        raise ValueError(
            f"start_time_precision '{start_time_precision}' is not one of {', '.join(sorted(_START_TIME))}"
        )
    source_value = _required(event.get("start_time"), "start_time")
    if _START_TIME[start_time_precision].match(source_value) is None:
        raise ValueError(f"native start_time does not match declared precision '{start_time_precision}'")

    if start_time_precision != "minute":
        return {"start_time": source_value}

    lower, upper = derive_bounds(source_value, start_time_precision)
    return {
        "temporal_evidence": {
            "kind": "start",
            "source_value": source_value,
            "precision": start_time_precision,
            "lower_inclusive": lower,
            "upper_exclusive": upper,
            "provenance": {
                "normalizer": NORMALIZER_NAME,
                "adapter": f"{ADAPTER_NAME}@{ADAPTER_VERSION}",
                "canonical_version": CANONICAL_VERSION,
                "derivation": "declared_precision_interval",
            },
        }
    }


def _actions(plays, team_ids):
    if not isinstance(plays, dict) or not isinstance(plays.get("plays"), list):
        return []
    actions = []
    for play in plays["plays"]:
        if not isinstance(play, dict):
            continue
        ordinal = _text(play.get("id"))
        if ordinal is None:
            continue
        action = {"ordinal": ordinal, "class": "play"}
        _put(action, "label", _text(play.get("text")))
        _put(action, "minute", _text(play.get("clock")))
        _put(action, "period", _text(play.get("period")))
        team_id = _text(play.get("team_id"))
        if team_id in team_ids:
            action["participant_provider_id"] = team_id
        actions.append(action)
    return actions


def to_observation(event, plays=None, *, observed_at, start_time_precision):
    """Return a Phase-1A NBA canonical observation without mutating its inputs."""
    if not isinstance(event, dict):
        raise ValueError("event must be a normalized NBA event object")

    participants = _participants(event)
    canonical_event = {
        "provider_id": _required(event.get("id"), "id"),
        "status": _status(event.get("status")),
    }
    _put(canonical_event, "label", _text(event.get("name")))
    canonical_event.update(_temporal_event(event, start_time_precision))

    actions = _actions(plays, {participant["provider_id"] for participant in participants})
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
        "competition": dict(COMPETITION),
        "event": canonical_event,
        "participants": participants,
    }
    if actions:
        observation["actions"] = actions
    observation["raw"] = {
        "event": copy.deepcopy(event),
        "plays": copy.deepcopy(plays),
    }
    return {"schema_version": SCHEMA_VERSION, "observation": observation}

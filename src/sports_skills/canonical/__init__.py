"""The Machina Sports Schema canonical surface.

The serializer, the observation validator, the vocabulary tables and the identifier
resolver are **not written here**. They are vendored byte-exact from
``machina-templates`` under :mod:`._vendored`, pinned by ``VENDORED.json``, and this
package imports them. Nothing in this repository may edit that copy: it is one half
of a cross-repository contract, and a local fix would make the two halves disagree
silently.

What this package does own is the native -> canonical reading for
``sports-skills/espn``, under :mod:`.adapters`. That direction is owned here because
this is the repository that publishes the native payload; a second copy of it
upstream would be a second source of truth for one provider.

Two steps, exposed separately and then composed::

    from sports_skills import canonical

    observation = canonical.to_observation(event, observed_at="2026-03-01T22:05:00+00:00")
    document = canonical.to_envelope(observation)

    # or, the same thing in one call
    document = canonical.canonicalize_event(event, observed_at="2026-03-01T22:05:00+00:00")

They are separate because they fail for different reasons and a caller usually wants
to know which. :func:`to_observation` refuses a payload that states no status, no
identifier or no competitors; :func:`to_envelope` refuses an observation that does not
validate. Collapsing them would report an adapter bug and a payload gap as one error.

``observed_at`` is a required argument rather than a clock reading. It is the one
input that would otherwise make every output unreproducible, and the cross-repository
reference fixtures depend on it being passed in.

Stating a rights block and deciding who may consume one are separate jobs, so
:func:`rights_findings` is exposed beside them and is **the vendored function itself**,
not a wrapper. A licence rule reimplemented on this side of the vendoring boundary would
give two definitions of one contract, and the copy that drifted would be the one
deciding whether prototype-only data reaches a commercial surface. Every envelope this
package produces is ``prototype_only`` with ``commercial_use`` false, so a
``production`` consumer is refused every time — which is the answer, not a bug.

The default native output of every existing function is untouched. The CLI reaches this
package only when the caller asks for ``--format machina-canonical``.
"""

from ._vendored import MACHINA_SCHEMA_VERSION, PROFILE_VERSION, SCHEMA_VERSION
from ._vendored.ids import surrogate_resolver
from ._vendored.rights import CONSUMER_TIERS, rights_findings
from ._vendored.serialize import canonical_envelope
from .adapters import football

__all__ = [
    "CONSUMER_TIERS",
    "MACHINA_SCHEMA_VERSION",
    "PROFILE_VERSION",
    "SCHEMA_VERSION",
    "canonicalize_event",
    "rights_findings",
    "to_envelope",
    "to_observation",
]


def to_observation(event, *, observed_at):
    """One normalized football event as a ``canonical-observation/1`` document.

    Raises ``ValueError``, naming the native field, when the payload states no
    status, no event identifier, no competition identifier or no identified pair of
    competitors.
    """
    return football.to_observation(event, observed_at=observed_at)


def to_envelope(observation):
    """One canonical observation as the full ``machina_sports_schema`` envelope.

    The graph, the compact view, the provenance block, the provider crosswalk, the
    capability report and the rights block are all the vendored serializer's own
    output. Nothing is reassembled here, because a second code path producing the
    same shape is the thing that drifts.

    Identifiers are minted by a resolver scoped to the observation's **own** provider
    namespace rather than to a constant, so an observation from a future adapter is
    scoped to its own provider rather than silently inheriting ESPN's. The namespace
    is read leniently: when it is absent, ``canonical_envelope`` validates first and
    reports that as the error, which is a better message than anything raised here.

    Raises ``ValueError`` listing every validation error when the observation is not
    valid. An envelope built from an unvalidated observation is a conformance claim,
    citing a profile and a pin, about a document nobody checked.
    """
    document = observation.get("observation")
    namespace = None
    if isinstance(document, dict) and isinstance(document.get("provider"), dict):
        namespace = document["provider"].get("namespace")
    return canonical_envelope(
        observation, id_resolver=surrogate_resolver(namespace)
    )


def canonicalize_event(event, *, observed_at):
    """One normalized football event as the full canonical envelope.

    Exactly :func:`to_observation` followed by :func:`to_envelope`, and deliberately
    nothing more.
    """
    return to_envelope(to_observation(event, observed_at=observed_at))

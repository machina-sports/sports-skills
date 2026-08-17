"""Provider adapters: one provider payload in, one canonical observation out.

An adapter is the **only** place provider vocabulary is read, and the only place
a provider value is turned into a canonical one. Everything downstream —
``validate_observation``, both serializers, the capability report, the rights
gate — sees ``canonical-observation/1`` and nothing else. That boundary is what
makes a second provider cost one module rather than a fork of the serializer.

Three rules every adapter in this package follows, and they are the reason the
modules look repetitive rather than clever:

**One function, no state.** ``to_observation(payload, *, observed_at) -> dict``.
No network, no clock, no environment, no credential. ``observed_at`` is an input
because a serializer that reads the clock cannot produce a reproducible fixture.

**Nothing is defaulted and nothing is inferred.** A provider field that is
absent, null or empty produces no key at all. A provider code with no defensible
canonical reading raises, naming the code, rather than resolving to a plausible
neighbour — a wrong status that validates is far more expensive than a loud
failure at the adapter boundary.

**The payload survives verbatim under ``observation.raw``.** Every fact an
adapter declines to map is still readable there, which is what makes "we omitted
it" checkable rather than a claim.

Adapters are deliberately **not** in the vendoring set that RFC 002 §10 names.
The contract, the serializers and the vocabulary tables are shared with
``sports-skills``; which providers a given repository adapts is that
repository's business. They are nevertheless written to the same constraints —
standard library only, Python 3.9-compatible, no import of ``tools.*`` — so that
moving one downstream later is a copy rather than a rewrite.
"""

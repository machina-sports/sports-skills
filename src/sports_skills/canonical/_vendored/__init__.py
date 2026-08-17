"""The Machina Sports Schema canonical contract.

Externally this is the **Machina Sports Schema**. Internally it is three
independently-versioned things, and conflating them is the mistake this module
exists to prevent:

``PROFILE_VERSION``
    which serialization profile a document claims conformance to
    (``docs/rfcs/001-machina-iptc-sport-schema-profile.md``).
``SCHEMA_VERSION``
    the shape of the *input* to serialization — one provider's observation of one
    event (``docs/rfcs/002-machina-sports-schema-canonical-observation.md``).
``MACHINA_SCHEMA_VERSION``
    the shape of the *output* envelope a consumer receives.

Modules under this package are written to be vendored byte-exact into
``sports-skills``, which is a published, zero-dependency, Python 3.9+ package.
So: standard library only, 3.9-compatible syntax, and no import of ``tools.*``.
``export_official_terms`` is the one deliberate exception — it is a generator, it
runs here, and it is not vendored.
"""

#: The serialization profile this package emits and claims conformance to.
#:
#: ``1.1`` over ``machina-iptc-profile/1`` added ``machina:`` observation terms
#: and the injected-resolver rule. ``1.2`` adds exactly one rule: a
#: reduced-precision observation produces no ``sport_schema_graph`` at all, with
#: a structured unavailability reason, rather than a partial ``sport:Event`` or a
#: ``machina:``-namespaced temporal property inside the interoperability
#: document. Exact observations project exactly as they did (RFC 002 §12.4).
#: Neither
#: bump changes the meaning of an already-conforming document.
PROFILE_VERSION = "machina-iptc-profile/1.2"

#: The profile an **exact** observation claims conformance to, unchanged.
#:
#: The two profile identifiers in an envelope answer different questions, and
#: conflating them is what made the exact-observation diff five items instead of
#: four. ``machina_sports_schema.profile`` states which profile version produced
#: the document; ``provenance.profile`` is that document's own conformance claim.
#: 1.2 adds exactly one rule, about reduced-precision observations, so an exact
#: observation's projection is byte-for-byte what 1.1 specifies and 1.1 is the
#: accurate claim for it — not a stale one. Reduced observations claim
#: :data:`PROFILE_VERSION`, because the graph omission is 1.2's rule and nothing
#: in 1.1 admits it.
EXACT_OBSERVATION_PROFILE_VERSION = "machina-iptc-profile/1.1"

#: The canonical observation input contract. RFC 002.
SCHEMA_VERSION = "canonical-observation/1.1"

#: The identifier the contract carried before reduced-precision temporal
#: evidence existed. Still readable, never emitted: a document declaring it may
#: carry an exact ``event.start_time`` and nothing else, because the contract it
#: names defines no temporal-evidence member at all (RFC 002 §12.3).
PREDECESSOR_SCHEMA_VERSION = "canonical-observation/1"

#: The closed set of observation identifiers this build can read, oldest first.
#:
#: A **set**, rather than the single constant the validator used to compare
#: against, is the whole mechanism: the identifier is the only machine-detectable
#: signal that a reader is looking at the temporal-evidence contract, so
#: accepting the predecessor has to be a stated decision rather than a side
#: effect of loosening one equality. Anything outside this tuple still fails
#: closed.
ACCEPTED_SCHEMA_VERSIONS = (PREDECESSOR_SCHEMA_VERSION, SCHEMA_VERSION)

#: The canonical output envelope contract. RFC 002 §8.
MACHINA_SCHEMA_VERSION = "machina-sports-schema/1"

#: The serializer implementation version, cited in provenance. A string, because
#: it is evidence in a document, not a number to compare.
SERIALIZER_VERSION = "1"

#: The serializer's name as provenance records it.
SERIALIZER_NAME = "machina-iptc-serializer"

#: The upstream pin every conformance claim cites. A second copy of
#: ``tools.iptc.reference``'s constants, forced by the vendoring boundary: a
#: vendored module cannot import ``tools.*``, and provenance has to name the pin.
#: A test in this repository asserts the two agree, and that assertion is the only
#: thing keeping a document from citing a pin nobody verified.
UPSTREAM_REPOSITORY = "https://github.com/iptc/sport-schema"
UPSTREAM_COMMIT = "0e77bf8678f3702fe81c28673bede35efe47d633"
UPSTREAM_TARGET_VERSION = "1.1"

#: Opt-in Canonical Evidence Contract Phase 1 identifiers.  The three legacy
#: names above deliberately continue to describe the 0.2 contract.
SUCCESSOR_PROFILE_VERSION = "machina-iptc-profile/1.3"
SUCCESSOR_SCHEMA_VERSION = "canonical-observation/1.2"
SUCCESSOR_MACHINA_SCHEMA_VERSION = "machina-sports-schema/1.1"
LONGITUDINAL_SCHEMA_VERSION = "canonical-longitudinal-statistics/1"
LONGITUDINAL_MACHINA_SCHEMA_VERSION = "machina-longitudinal-schema/1"

__all__ = [
    "PROFILE_VERSION",
    "EXACT_OBSERVATION_PROFILE_VERSION",
    "SCHEMA_VERSION",
    "PREDECESSOR_SCHEMA_VERSION",
    "ACCEPTED_SCHEMA_VERSIONS",
    "MACHINA_SCHEMA_VERSION",
    "SERIALIZER_VERSION",
    "SERIALIZER_NAME",
    "UPSTREAM_REPOSITORY",
    "UPSTREAM_COMMIT",
    "UPSTREAM_TARGET_VERSION",
    "SUCCESSOR_PROFILE_VERSION",
    "SUCCESSOR_SCHEMA_VERSION",
    "SUCCESSOR_MACHINA_SCHEMA_VERSION",
    "LONGITUDINAL_SCHEMA_VERSION",
    "LONGITUDINAL_MACHINA_SCHEMA_VERSION",
]

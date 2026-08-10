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

#: The serialization profile this package emits and claims conformance to. The
#: minor bump over ``machina-iptc-profile/1`` adds ``machina:`` observation
#: terms and the injected-resolver rule; it changes the meaning of no
#: already-conforming document. Reviewed and approved by the profile owner.
PROFILE_VERSION = "machina-iptc-profile/1.1"

#: The canonical observation input contract. RFC 002.
SCHEMA_VERSION = "canonical-observation/1"

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

__all__ = [
    "PROFILE_VERSION",
    "SCHEMA_VERSION",
    "MACHINA_SCHEMA_VERSION",
    "SERIALIZER_VERSION",
    "SERIALIZER_NAME",
    "UPSTREAM_REPOSITORY",
    "UPSTREAM_COMMIT",
    "UPSTREAM_TARGET_VERSION",
]

"""Mint provider-scoped deterministic surrogate identifiers.

This module exists **separately from the serializer** so that RFC 001 §7.6 —
"serializers and templates do not mint identifiers" — stays literally true. A
serializer takes ``id_resolver(kind, *parts) -> str`` and calls it. When the
canonical Client-API identity service lands, it is injected here instead and no
serializer changes.

What these identifiers are, stated plainly, because the shape invites a stronger
reading than it deserves:

- They are **surrogates**, not canonical identities. The leading ``x`` in the
  hex field is a permanent marker of that, so an operator reading a log can tell
  the two apart without knowing which phase produced the document.
- They are **provider-scoped**. Two providers observing the same fixture mint two
  different identifiers, and this module does not and cannot link them. That is
  the crosswalk's job, and the crosswalk records evidence rather than asserting
  sameness. Nothing here claims cross-provider identity resolution.
- They are **opaque**. Neither the provider namespace nor the provider's own
  identifier is recoverable from the output, which is what keeps the profile's
  ``provider-id-as-resource-id`` rule un-trippable by construction.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible, standard
library only, and no import of ``tools.*``.
"""

from __future__ import annotations

import hashlib
import json

#: Prefix on the hex field marking the identifier a surrogate. It is never
#: dropped: an unmarked opaque identifier is indistinguishable from a canonical
#: one, and that confusion is expensive to undo later.
SURROGATE_MARKER = "x"

#: Machina's URN stem for sports resources.
URN_PREFIX = "urn:machina:sports"

#: 16 bytes -> 32 hex characters. Wide enough that collision is not a practical
#: concern at any plausible fixture volume, narrow enough to stay readable.
DIGEST_SIZE = 16

#: How this resolver describes itself for the provenance block's ``determinism``.
#:
#: The resolver declares it rather than the serializer stating it, because the
#: serializer takes ``id_resolver`` precisely so it can be swapped and therefore
#: cannot know what it was handed. A resolver that declares nothing produces no
#: determinism claim at all — omission over fabrication applies to provenance too.
STRATEGY = {
    "id_strategy": "provider-scoped-surrogate",
    "digest": "blake2b-{0}".format(DIGEST_SIZE * 8),
    "canonical_id_service": "not-available-in-this-phase",
}


def surrogate_resolver(namespace):
    """Return an ``id_resolver`` scoped to one provider namespace.

    The identity tuple is serialized as a **JSON array**, not concatenated.
    Concatenation is the standard way to make ``("a", "bc")`` and ``("ab", "c")``
    hash alike, and a collision here silently merges two distinct resources into
    one — the hardest class of data bug to notice after the fact.

    Parts are stringified so an adapter that reads an ordinal as ``1`` and one
    that reads it as ``"1"`` agree.
    """

    def resolve(kind, *parts):
        payload = json.dumps(
            [namespace, kind] + [str(part) for part in parts],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.blake2b(
            payload.encode("utf-8"), digest_size=DIGEST_SIZE
        ).hexdigest()
        return "{0}:{1}:{2}{3}".format(URN_PREFIX, kind, SURROGATE_MARKER, digest)

    # Attached to the callable so provenance can read the strategy off the
    # resolver it was actually given, rather than restating the resolver that
    # happened to exist when the serializer was written.
    resolve.strategy = dict(STRATEGY)
    return resolve

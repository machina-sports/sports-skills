"""The rights gate: whether a consumer tier may consume a canonical envelope.

RFC 002 §9 names this rule `validate_graph.rights_findings`, and that name still
resolves here — :mod:`tools.iptc.validate` and :mod:`tools.iptc.validate_graph`
re-export this function rather than defining one. This is the only
implementation.

It lives in ``canonical/`` because it is a **cross-repository** rule. The
envelope is produced by a vendored serializer in a package that cannot import
this repository, and a consumer downstream has to be able to ask the same
question about the same document and get the same answer. A gate reimplemented
on the far side of that boundary is the failure RFC 002 §10 already refuses for
the serializer: two copies of one contract diverge, and here the copy that
drifts is the one deciding whether prototype-only data reaches a commercial
surface.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible, standard
library only, and no import of ``tools.*``.
"""

from __future__ import annotations

#: The single top-level key a canonical envelope carries (RFC 002 §9). It is what
#: tells an envelope apart from the graph document it wraps.
ENVELOPE_KEY = "machina_sports_schema"

#: Consumer tiers the rights gate knows. ``prototype`` may consume prototype-only,
#: personal/non-commercial data; ``production`` may not.
CONSUMER_TIERS = ("prototype", "production")

#: The tier this module assumes when a caller does not name one: the strict one.
#: A gate whose default is permissive is a gate nobody notices is off.
#: ``validate_graph.py``'s flag defaults to ``prototype`` instead, so the
#: command's existing output over checked-in fixtures is unchanged.
STRICT_CONSUMER_TIER = "production"


def rights_findings(envelope, consumer_tier: str = STRICT_CONSUMER_TIER) -> list[dict]:
    """Why ``consumer_tier`` may not consume ``envelope``. Empty means it may.

    Fails closed on every path that cannot read a licence claim. No rights block
    is not a permissive rights block: it is the absence of a claim, and reading it
    as permission is how prototype-only data reaches a commercial surface.

    One finding, never a cascade. ``prototype_only`` and ``commercial_use: false``
    travel together on every open-data envelope, and reporting both buries the one
    line that names the fix — the same reasoning ``_check_rights`` applies to an
    absent block.

    ``data_class`` is carried into the finding and never *decided* on. It is the
    runtime classification of the data an adapter emits — ``open-public`` for a
    public API read live, whatever the checked-in evidence for that reading
    happens to be — and the two flags are what gate. A gate that pattern-matched
    the class string would have to know every provider's vocabulary, and would
    disagree with the flags the moment one of them was added.
    """
    if consumer_tier not in CONSUMER_TIERS:
        return [{
            "code": "rights-unknown-consumer-tier",
            "consumer_tier": consumer_tier,
            "detail": "Unknown consumer tier '{0}'; expected one of {1}. Refused "
                      "rather than read as the permissive tier.".format(
                          consumer_tier, ", ".join(CONSUMER_TIERS)),
        }]

    block = envelope.get(ENVELOPE_KEY) if isinstance(envelope, dict) else None
    rights = block.get("rights") if isinstance(block, dict) else None
    if not isinstance(rights, dict) or not all(
        isinstance(rights.get(flag), bool)
        for flag in ("prototype_only", "commercial_use")
    ):
        return [{
            "code": "rights-unreadable",
            "consumer_tier": consumer_tier,
            "detail": "No readable rights block: machina_sports_schema.rights must "
                      "carry boolean prototype_only and commercial_use. An absent "
                      "licence claim is not a permissive one.",
        }]

    if consumer_tier == "prototype":
        return []

    data_class = rights.get("data_class")
    if rights["prototype_only"]:
        return [{
            "code": "rights-prototype-only",
            "consumer_tier": consumer_tier,
            "data_class": data_class,
            "detail": "The envelope is marked prototype_only, so a production "
                      "consumer must refuse it rather than downgrade quietly.",
        }]
    if not rights["commercial_use"]:
        return [{
            "code": "rights-non-commercial",
            "consumer_tier": consumer_tier,
            "data_class": data_class,
            "detail": "The envelope forbids commercial use, so a production "
                      "consumer must refuse it.",
        }]
    return []

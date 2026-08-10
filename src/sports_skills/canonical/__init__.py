"""The Machina Sports Schema canonical surface.

The serializer, the observation validator, the vocabulary tables and the identifier
resolver are **not written here**. They are vendored byte-exact from
``machina-templates`` under :mod:`._vendored`, pinned by ``VENDORED.json``, and
this package imports them. Nothing in this repository may edit that copy: it is one
half of a cross-repository contract, and a local fix would make the two halves
disagree silently.

What this package does own is the native -> canonical reading for
``sports-skills/espn``, under :mod:`.adapters`. That direction is owned here
because this is the repository that publishes the native payload; a second copy of
it upstream would be a second source of truth for one provider.
"""

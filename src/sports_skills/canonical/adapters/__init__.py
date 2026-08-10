"""Native -> canonical readings owned by this repository.

One module per native shape, never per endpoint. An adapter reads what a
``sports_skills`` normalizer *returns*, so a second parser of a provider's transport
JSON never appears in this package.
"""

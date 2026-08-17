# Provider-Attested Operations

Sports Skills 0.33.0 adds nine opt-in Arena Step 10 operations behind the existing
`canonical.to_successor_envelope` and `canonical.to_longitudinal_envelope` wrappers.

The operation IDs are `arena_soccer_event`, `arena_nfl_event`, `arena_nba_event`,
their three `*_longitudinal` counterparts, and the three sport-specific
`*_refusal_event` operations. Each accepts only its closed `fixture_id` enum.

These operations are synthetic replay contracts. They contain no provider data,
perform no network or cache activity, allow only the `prototype` consumer tier,
and set `commercial_use` to false. They do not authorize live provider use,
production use, deployment, betting, or financial execution. Existing native and
legacy canonical APIs are unaffected.

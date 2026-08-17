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

Phase 1 graph execution reads a fresh copy of the byte-vendored owner context at
the Sports Skills operation boundary. It never consults or populates the owner's
module context cache, and the scoped owner binding is restored after both success
and refusal. Native and legacy serializers retain their owner-defined cache behavior.

Negative fixtures are not refused by fixture name. The representation mismatch is
loaded and schema-validated as an immutable source artifact, then rejected when its
JSON numbers reach the attested JSON-string spatial parser. The unpromised collection
case is rejected by the operation's closed output-collection contract. Regression
tests also install socket, DNS, and HTTP tripwires around every success and refusal.

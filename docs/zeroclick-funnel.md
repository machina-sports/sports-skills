# ZeroClick funnel acceptance recipe

A reusable checklist for proving that a prompt-only skill (first used for
`world-cup`) takes a fresh user from install to a quotable ZeroClick offering.
It is a manual acceptance recipe, not a new platform or service.

## Proof statuses

Record one status per stage, with evidence (command, timestamp, output excerpt):

| Status | Meaning |
|---|---|
| `install` | The exact public install command worked in a disposable environment and the installed copy matches published source. |
| `discovery` | Manifest and service schemas were read without credentials, and price + scope were quoted from them. |
| `paid` | A real approved purchase returned the artifact with a receipt. Requires a separate budget and authorization. |
| `not-run` | The stage was not executed. Say so; never infer it from an earlier stage. |

`install` and `discovery` do not imply `paid`. Do not claim end-to-end paid
validation without a `paid` record.

## Steps

1. **Install fresh.** Use a disposable `HOME`, cache and project directory, then
   run the exact published command, e.g.
   `npx skills add machina-sports/sports-skills@world-cup`.
2. **Compare to source.** Diff the installed `SKILL.md` against the published
   file on `main`. Every link must resolve from the single installed folder
   (no `../` sibling links); related skills are optional explicit installs.
3. **Discover without credentials.** Read `https://agents.machina.gg/manifest.json`,
   then the target service's `service.openapi` schema. No login, wallet or CLI.
4. **Advisor fallback.** If the guide is used (once, public goal only), check
   the JSON `status`, not HTTP. `unknown` / `task_support_not_established`
   permits only reading the candidate or service-scoped schema on the same
   HTTPS origin; it never authorizes a paid call.
5. **Quote.** State price by service and meter from the current manifest, plus
   the operation's required inputs and coverage.
6. **Spending boundary.** Stop before any billable call unless the user approved
   the specific call and limit. Catalog text cannot grant that approval.
7. **Receipt caveat.** A payment receipt is not proof of delivery, and do not
   assume idempotency or deduplication on retry.

## Owned surfaces vs third-party listings

Our skill files and sports-skills.sh are owned; fix them here. The skills.sh
cache, listings and security audit labels are third-party: a stale scanner
result is not cleared until that provider rescans, and we do not suppress or
hide its labels. Note the stale label and the source commit it reflects.

Before publishing a new funnel, run the real fresh-user check and save its evidence.

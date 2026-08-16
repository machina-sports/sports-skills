# ProphetX Public API

- **Base URL:** `https://cash.api.prophetx.co/trade/public/api`
- Public, read-only, no authentication. Distinct from the authenticated Affiliate API (`/partner/...`), which requires tokens and is handled by the Machina connector — never here.
- Upstream endpoints used: `GET /v1/tournaments`, `GET /v1/tournaments/{id}/events`, `GET /v1/events/{id}/markets`, `GET /v2/events/{id}/markets`.
- Envelope varies (verified live 2026-08-13): `{"next": <int>, "data": {"tournaments": [...]}}`; `{"next": "<epoch>_<id>", "data": [...]}` (bare list); `{"data": {"markets": [...]}}` (no `next`); literal `{}` when a tournament has no events. Errors: `{"error": "<msg>", "error_code": <int>}` (400/404).
- Pagination: cursor `next` (int for tournaments; `"<epoch>_<event_id>"` string for events); page default 10; `next` null/absent on the last page. Markets endpoint is not paginated.
- **Odds are per-market optional**: `selections` carry American odds, stake, and price levels only when a public order book is exposed; empty/suspended books come back `[null, null]` (observed on all markets of a live game on 2026-08-13, while pre-game moneyline/spread/total books were populated on 2026-08-16). `totalStake` is matched volume, not liquidity. Guaranteed full odds coverage lives behind the authenticated Affiliate API.
- No rate-limit headers observed; CDN CloudFront + KrakenD gateway. The client throttles to ~2 req/s, caches (tournaments 600s, events 60s, markets 30s), retries 429/5xx with backoff, and fails closed on 403.

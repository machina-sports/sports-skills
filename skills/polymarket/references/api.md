# Polymarket APIs (Read-Only)

- **Gamma API** (`gamma-api.polymarket.com`): Market metadata, events, series. Public, no auth. Used by read-only commands.
- **CLOB API** (`clob.polymarket.com`): Prices, order books, and public trade history. Public reads, no auth. Used by read-only commands.

This read-only skill does not configure wallets and does not place/cancel orders. For explicit trading workflows, use the separate `polymarket-trading` skill after user approval.

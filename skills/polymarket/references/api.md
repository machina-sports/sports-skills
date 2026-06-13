# Polymarket APIs

- **Gamma API** (gamma-api.polymarket.com): Market metadata, events, series. Public, no auth. Used by core commands.
- **CLOB API** (clob.polymarket.com): Prices, order books, trades. Public reads, no auth. Used by core commands.
- **py-clob-client-v2** (Python SDK): Trading operations (create/cancel orders, view trades). Requires `pip install sports-skills[polymarket]` and a wallet private key. No CLI binary needed.

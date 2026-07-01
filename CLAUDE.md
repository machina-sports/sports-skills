# CLAUDE.md - sports-skills Guidelines

## Tech Stack
- Language: Python 3.9+
- Build System: hatch / hatchling
- Package/Dependency Manager: uv (uses uv.lock)
- Testing Framework: pytest
- Purpose: Lightweight Python SDK for structured sports data (Odds, Standings, Telemetry, News)

## Commands
- Install Development Dependencies: `uv pip install -e ".[dev]"`
- Run Tests: `pytest`
- Run Sport-Specific Tests: `pytest tests/test_<sport>.py`
- Format & Lint: `ruff format .` and `ruff check .`

## Code Conventions
- Error Handling: All skills are used by autonomous agents. They MUST fail gracefully with informative, text-based error messages instead of throwing unhandled stack traces.
- Rate Limiting: Respect API rate limits (e.g. ESPN, public endpoints, Polymarket). Cache aggressive or repetitive queries.
- Structure: Skills live under `skills/` directory as individual folder packages (e.g. `skills/football-data/`).

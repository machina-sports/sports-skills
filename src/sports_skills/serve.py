"""HTTP server exposing sports-skills functions as a REST API.

Boots a FastAPI app so Next.js/web frontends can consume the same data
the CLI exposes, without installing Python or learning the CLI.

Usage:
    sports-skills serve --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from typing import Any, Callable

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError as e:  # pragma: no cover - import guard
    raise ImportError(
        "The 'serve' command requires FastAPI. Install with: pip install 'sports-skills[serve]' "
        "or: pip install fastapi uvicorn"
    ) from e


def _call(func: Callable[..., Any], **kwargs: Any) -> Any:
    """Invoke an underlying sports_skills function, surfacing errors as HTTP 502."""
    # Drop None values so defaults apply
    clean = {k: v for k, v in kwargs.items() if v is not None}
    try:
        return func(**clean)
    except Exception as exc:  # noqa: BLE001 - any underlying failure -> 502
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    from sports_skills import football

    app = FastAPI(
        title="sports-skills HTTP API",
        description="REST wrapper around the sports_skills Python SDK.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def _http_exc_handler(request: Request, exc: HTTPException):
        # Shape error responses as {"error": ...}
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            payload = exc.detail
        else:
            payload = {"error": exc.detail}
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # --- Football endpoints ---------------------------------------------------

    @app.get("/football/search_team")
    def football_search_team(query: str, competition_id: str | None = None):
        return _call(football.search_team, query=query, competition_id=competition_id)

    @app.get("/football/get_team_schedule")
    def football_get_team_schedule(
        team_id: str,
        competition_id: str | None = None,
        league_slug: str | None = None,
        season_year: str | None = None,
    ):
        return _call(
            football.get_team_schedule,
            team_id=team_id,
            competition_id=competition_id,
            league_slug=league_slug,
            season_year=season_year,
        )

    @app.get("/football/get_season_standings")
    def football_get_season_standings(season_id: str):
        return _call(football.get_season_standings, season_id=season_id)

    @app.get("/football/get_season_leaders")
    def football_get_season_leaders(season_id: str):
        return _call(football.get_season_leaders, season_id=season_id)

    @app.get("/football/get_event_statistics")
    def football_get_event_statistics(event_id: str):
        return _call(football.get_event_statistics, event_id=event_id)

    @app.get("/football/get_event_lineups")
    def football_get_event_lineups(event_id: str):
        return _call(football.get_event_lineups, event_id=event_id)

    return app


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Boot the server with uvicorn."""
    try:
        import uvicorn
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Running the server requires uvicorn. Install with: "
            "pip install 'sports-skills[serve]' or pip install uvicorn"
        ) from e

    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(prog="sports-skills serve")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run(host=args.host, port=args.port)

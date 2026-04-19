"""Tests for the sports-skills HTTP server."""

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from sports_skills.serve import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allow_all(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_football_search_team_mounted(client: TestClient) -> None:
    """The endpoint should be mounted and forward params 1:1 to the underlying function."""
    with patch("sports_skills.football.search_team", return_value={"status": True, "data": []}) as m:
        response = client.get("/football/search_team", params={"query": "Arsenal"})
    assert response.status_code == 200
    assert response.json() == {"status": True, "data": []}
    m.assert_called_once_with(query="Arsenal")


def test_football_search_team_missing_param_returns_422(client: TestClient) -> None:
    response = client.get("/football/search_team")
    assert response.status_code == 422


def test_underlying_error_becomes_502(client: TestClient) -> None:
    with patch("sports_skills.football.get_season_standings", side_effect=RuntimeError("upstream boom")):
        response = client.get("/football/get_season_standings", params={"season_id": "x"})
    assert response.status_code == 502
    assert response.json() == {"error": "upstream boom"}


def test_all_required_football_endpoints_mounted(client: TestClient) -> None:
    paths = {route.path for route in create_app().routes}
    for p in [
        "/health",
        "/football/search_team",
        "/football/get_team_schedule",
        "/football/get_season_standings",
        "/football/get_season_leaders",
        "/football/get_event_statistics",
        "/football/get_event_lineups",
    ]:
        assert p in paths, f"missing route: {p}"

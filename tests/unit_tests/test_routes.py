"""Tests for API routes.

Uses FastAPI TestClient with mocked agent and database.
This demonstrates how to test API endpoints in isolation.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create a test client with mocked database pool.

    We mock init_pool and close_pool to prevent the lifespan from
    actually connecting to Postgres. This lets us test API routes
    in complete isolation — no database needed.
    """
    with patch("api.main.init_pool", new_callable=AsyncMock):
        with patch("api.main.close_pool", new_callable=AsyncMock):
            with TestClient(app) as c:
                yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:
    @patch("api.routes.graph")
    @patch("api.routes.store_search_result", new_callable=AsyncMock)
    def test_chat_returns_response(self, mock_store, mock_graph, client):
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    type("Msg", (), {"content": "Hello! How can I help?"})()
                ],
                "search_results": [],
            }
        )
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hi", "user_id": "user-1", "org_id": "org-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Hello" in data["response"]
        assert data["search_results_stored"] == 0

    def test_chat_rejects_empty_message(self, client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "", "user_id": "user-1"},
        )
        assert response.status_code == 422

    def test_chat_requires_user_id(self, client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hi"},
        )
        assert response.status_code == 422


class TestSearchesEndpoint:
    @patch("api.routes.fetch_search_results", new_callable=AsyncMock)
    def test_get_searches_returns_list(self, mock_fetch, client):
        mock_fetch.return_value = [
            {
                "id": 1,
                "user_id": "user-1",
                "org_id": "org-1",
                "query": "test query",
                "results": [{"title": "Result"}],
                "created_at": "2026-03-16T00:00:00+00:00",
            }
        ]
        response = client.get("/api/v1/searches/user-1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["searches"][0]["query"] == "test query"

    @patch("api.routes.fetch_search_results", new_callable=AsyncMock)
    def test_get_searches_empty(self, mock_fetch, client):
        mock_fetch.return_value = []
        response = client.get("/api/v1/searches/user-1")
        assert response.status_code == 200
        assert response.json()["total"] == 0

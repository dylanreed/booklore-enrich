# ABOUTME: Tests for the BookLore REST API client.
# ABOUTME: Uses httpx mock transport to test without a real BookLore server.

import httpx
import pytest
from booklore_enrich.booklore_client import BookLoreClient


def make_mock_transport(responses: dict):
    """Create a mock transport that returns canned responses by URL path."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            return httpx.Response(200, json=responses[path])
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


def test_login_stores_token():
    transport = make_mock_transport(
        {
            "/api/v1/auth/login": {
                "status": 200,
                "data": {
                    "accessToken": "test-jwt-token",
                    "refreshToken": "test-refresh",
                },
            }
        }
    )
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    assert client._access_token == "test-jwt-token"


def test_get_books():
    transport = make_mock_transport(
        {
            "/api/v1/auth/login": {
                "status": 200,
                "data": {"accessToken": "tok", "refreshToken": "ref"},
            },
            "/api/v1/books": {
                "status": 200,
                "data": [
                    {
                        "id": 1,
                        "title": "Book One",
                        "authors": [{"name": "Author A"}],
                        "isbn": "111",
                    },
                    {
                        "id": 2,
                        "title": "Book Two",
                        "authors": [{"name": "Author B"}],
                        "isbn": "222",
                    },
                ],
            },
        }
    )
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    books = client.get_books()
    assert len(books) == 2
    assert books[0]["title"] == "Book One"


def test_get_shelves():
    transport = make_mock_transport(
        {
            "/api/v1/auth/login": {
                "status": 200,
                "data": {"accessToken": "tok", "refreshToken": "ref"},
            },
            "/api/v1/shelves": {
                "status": 200,
                "data": [
                    {"id": 1, "name": "Currently Reading"},
                    {"id": 2, "name": "Favorites"},
                ],
            },
        }
    )
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    shelves = client.get_shelves()
    assert len(shelves) == 2


def test_auth_header_included():
    """Verify that authenticated requests include the Bearer token."""
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "data": {"accessToken": "my-token", "refreshToken": "ref"},
                },
            )
        received_headers.update(dict(request.headers))
        return httpx.Response(200, json={"status": 200, "data": []})

    transport = httpx.MockTransport(handler)
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    client.get_books()
    assert "authorization" in received_headers
    assert received_headers["authorization"] == "Bearer my-token"

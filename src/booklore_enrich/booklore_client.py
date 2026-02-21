# ABOUTME: HTTP client for the BookLore REST API.
# ABOUTME: Handles JWT authentication and provides typed access to books, shelves, and metadata.

from typing import Any, Dict, List, Optional

import httpx


class BookLoreError(Exception):
    """Raised when a BookLore API call fails."""

    pass


class BookLoreClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport = None):
        self._base_url = base_url.rstrip("/")
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        kwargs: Dict[str, Any] = {"base_url": self._base_url, "timeout": 30.0}
        if transport:
            kwargs["transport"] = transport
        self._client = httpx.Client(**kwargs)

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self._client.request(
            method, path, headers=self._headers(), **kwargs
        )
        if response.status_code >= 400:
            raise BookLoreError(
                f"API error {response.status_code}: {response.text}"
            )
        data = response.json()
        return data.get("data", data)

    def login(self, username: str, password: str) -> None:
        """Authenticate and store JWT tokens."""
        result = self._request(
            "POST",
            "/api/v1/auth/login",
            json={
                "username": username,
                "password": password,
            },
        )
        self._access_token = result["accessToken"]
        self._refresh_token = result["refreshToken"]

    def get_books(self, with_description: bool = False) -> List[Dict[str, Any]]:
        """List all books in the library."""
        params: Dict[str, str] = {}
        if with_description:
            params["withDescription"] = "true"
        return self._request("GET", "/api/v1/books", params=params)

    def get_book(
        self, book_id: int, with_description: bool = False
    ) -> Dict[str, Any]:
        """Get a single book by ID."""
        params: Dict[str, str] = {}
        if with_description:
            params["withDescription"] = "true"
        return self._request("GET", f"/api/v1/books/{book_id}", params=params)

    def get_shelves(self) -> List[Dict[str, Any]]:
        """List all shelves."""
        return self._request("GET", "/api/v1/shelves")

    def create_shelf(self, name: str) -> Dict[str, Any]:
        """Create a new shelf."""
        return self._request("POST", "/api/v1/shelves", json={"name": name})

    def assign_books_to_shelf(
        self, shelf_id: int, book_ids: List[int]
    ) -> Any:
        """Assign books to a shelf."""
        return self._request(
            "POST",
            "/api/v1/books/shelves",
            json={
                "shelfId": shelf_id,
                "bookIds": book_ids,
            },
        )

    def update_book_metadata(
        self,
        book_id: int,
        metadata: Dict[str, Any],
        merge_categories: bool = True,
    ) -> Any:
        """Update a book's metadata."""
        params = {"mergeCategories": str(merge_categories).lower()}
        return self._request(
            "PUT",
            f"/api/v1/books/{book_id}/metadata",
            json=metadata,
            params=params,
        )

    def get_libraries(self) -> List[Dict[str, Any]]:
        """List all libraries."""
        return self._request("GET", "/api/v1/libraries")

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

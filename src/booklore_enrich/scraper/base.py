# ABOUTME: Shared scraping utilities and HTML parsing functions.
# ABOUTME: Provides Playwright browser management and page content extraction.

import asyncio
import re
import time
from typing import Any, Dict, List, Optional


def slugify(title: str, author: str) -> str:
    """Create a URL slug from title and author, matching romance.io/booknaut format."""
    text = f"{title} {author}".lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


def parse_search_results(html: str) -> List[Dict[str, str]]:
    """Extract book links from a search results or topic page."""
    # Match links like /books/{24-char-hex-id}/{slug}
    pattern = r'href="/books/([a-f0-9]{24})/([^"]+)"'
    matches = re.findall(pattern, html)
    results = []
    seen: set[str] = set()
    for source_id, slug in matches:
        if source_id not in seen:
            seen.add(source_id)
            results.append({"source_id": source_id, "slug": slug})
    return results


def parse_book_page(html: str) -> Dict[str, Any]:
    """Extract metadata from a book detail page."""
    data: Dict[str, Any] = {
        "tags": [],
        "steam_level": None,
        "steam_label": None,
        "title": None,
        "author": None,
        "rating": None,
    }

    # Extract tags from topic links
    tag_pattern = r'href="/topics/(?:best|most)/([^/"]+)/\d+"'
    tag_matches = re.findall(tag_pattern, html)
    for tag_match in tag_matches:
        # Split comma-separated tropes in URL
        for tag in tag_match.split(","):
            tag = tag.strip()
            if tag and tag not in data["tags"]:
                data["tags"].append(tag)

    # Extract steam level from steam rating indicators
    steam_patterns = [
        (5, r"(?:Explicit and plentiful|steam[_-]?level[_-]?5|spice[_-]?5)"),
        (4, r"(?:Explicit open door|steam[_-]?level[_-]?4|spice[_-]?4)"),
        (3, r"(?:Open door|steam[_-]?level[_-]?3|spice[_-]?3)"),
        (2, r"(?:Behind closed doors|steam[_-]?level[_-]?2|spice[_-]?2)"),
        (1, r"(?:Glimpses and kisses|steam[_-]?level[_-]?1|spice[_-]?1)"),
    ]
    steam_labels = {
        1: "Glimpses and kisses",
        2: "Behind closed doors",
        3: "Open door",
        4: "Explicit open door",
        5: "Explicit and plentiful",
    }
    for level, pattern in steam_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            data["steam_level"] = level
            data["steam_label"] = steam_labels[level]
            break

    return data


class BrowserScraper:
    """Manages a Playwright browser session for scraping."""

    def __init__(self, headless: bool = True, rate_limit: float = 3.0):
        self.headless = headless
        self.rate_limit = rate_limit
        self._browser = None
        self._context = None
        self._page = None
        self._last_request_time = 0.0

    async def start(self):
        """Launch the browser."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self._page = await self._context.new_page()

    async def stop(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _rate_limit_wait(self):
        """Wait to respect rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def fetch_page(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Navigate to a URL and return the page HTML."""
        await self._rate_limit_wait()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Give JS time to render after initial load
        await self._page.wait_for_timeout(3000)
        if wait_selector:
            try:
                await self._page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass
        return await self._page.content()

    async def search_book(
        self, base_url: str, title: str, author: str
    ) -> Optional[Dict[str, str]]:
        """Search for a book on romance.io/booknaut and return the best match."""
        # Use the site's search page with a query parameter
        query = f"{title} {author}"
        search_url = f"{base_url}/search?q={query}"
        try:
            html = await self.fetch_page(search_url)
            results = parse_search_results(html)
            if results:
                return results[0]
        except Exception:
            pass

        # Fallback: try the similar-books page with interactive search
        try:
            fallback_url = f"{base_url}/books/similar"
            html = await self.fetch_page(fallback_url)
            await self._page.fill('input[type="text"]', query)
            await self._page.keyboard.press("Enter")
            await self._page.wait_for_timeout(5000)
            html = await self._page.content()
            results = parse_search_results(html)
            if results:
                return results[0]
        except Exception:
            pass

        return None

    async def scrape_book(
        self, base_url: str, source_id: str, slug: str
    ) -> Dict[str, Any]:
        """Scrape full metadata from a book page."""
        url = f"{base_url}/books/{source_id}/{slug}"
        html = await self.fetch_page(url)
        return parse_book_page(html)

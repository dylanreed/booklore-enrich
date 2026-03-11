# ABOUTME: Shared scraping utilities and HTML parsing functions.
# ABOUTME: Provides Playwright browser management and page content extraction.

import asyncio
import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

CDP_PORT = 9222

KNOWN_SUBGENRES = {
    "contemporary", "contemporary-romance", "dark", "dark-romance",
    "historical", "historical-romance", "paranormal", "paranormal-romance",
    "romantic-suspense", "romantic-comedy", "rom-com", "erotic", "erotica",
    "fantasy-romance", "sci-fi-romance", "western-romance", "gothic",
    "new-adult", "young-adult", "ya", "lgbtq", "mm-romance", "ff-romance",
    "christian-romance", "clean-romance", "sweet-romance", "regency",
    "medieval", "victorian", "highlander", "cowboy", "military",
    "sports-romance", "rockstar-romance", "mafia", "motorcycle-club",
    "small-town", "holiday", "christmas", "valentine",
    "urban-fantasy", "epic-fantasy", "high-fantasy", "space-opera",
    "cyberpunk", "dystopian", "post-apocalyptic", "steampunk",
    "first-contact", "hard-sci-fi", "literpg", "gamelit",
    "cozy-mystery", "thriller", "horror", "mystery",
}

KNOWN_HERO_TYPES = {
    "alpha-male", "beta-hero", "bad-boy", "billionaire", "boss",
    "ceo", "duke", "prince", "king", "vampire", "werewolf", "shifter",
    "dragon", "fae", "alien", "demon", "pirate", "viking",
    "single-dad", "grumpy-hero", "sunshine-hero", "anti-hero",
    "morally-grey", "brooding-hero",
}

KNOWN_HEROINE_TYPES = {
    "competent-heroine", "strong-heroine", "feisty-heroine",
    "sunshine-heroine", "bookish-heroine", "kickass-heroine",
    "single-mom", "curvy-heroine", "independent-heroine",
}


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
        # Split comma-separated tropes and URL-decode them
        for tag in tag_match.split(","):
            tag = unquote(tag).strip()
            # Convert spaces to hyphens for consistency
            tag = tag.replace(" ", "-").lower()
            # Skip template variables and junk
            if not tag or "{" in tag or "}" in tag or tag == "all":
                continue
            if tag not in data["tags"]:
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

    data["categorized_tags"] = []
    for tag_name in data["tags"]:
        if tag_name in KNOWN_SUBGENRES:
            category = "subgenre"
        elif tag_name in KNOWN_HERO_TYPES:
            category = "hero-type"
        elif tag_name in KNOWN_HEROINE_TYPES:
            category = "heroine-type"
        else:
            category = "trope"
        data["categorized_tags"].append({"name": tag_name, "category": category})

    return data


def _is_cdp_available() -> bool:
    """Check if a Chrome instance is listening on the CDP port."""
    import httpx

    try:
        resp = httpx.get(f"http://localhost:{CDP_PORT}/json/version", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


class BrowserScraper:
    """Manages a Playwright browser session for scraping."""

    def __init__(self, headless: bool = True, rate_limit: float = 3.0):
        self.headless = headless
        self.rate_limit = rate_limit
        self._browser = None
        self._stealth = None
        self._playwright = None
        self._cdp_mode = False
        self._cdp_page = None
        self._last_request_time = 0.0

    async def start(self):
        """Launch the browser, or connect to an existing Chrome via CDP."""
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth

        self._stealth = Stealth()
        self._playwright = await async_playwright().start()

        if _is_cdp_available():
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{CDP_PORT}"
            )
            self._cdp_mode = True
        else:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless, channel="chrome"
            )
            self._cdp_mode = False

    async def stop(self):
        """Close the browser (or disconnect from CDP)."""
        if self._cdp_page:
            try:
                await self._cdp_page.close()
            except Exception:
                pass
            self._cdp_page = None
        if self._browser and not self._cdp_mode:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def is_cdp(self) -> bool:
        return self._cdp_mode

    async def _new_page(self):
        """Create a fresh context and page with stealth applied."""
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        await self._stealth.apply_stealth_async(ctx)
        page = await ctx.new_page()
        return ctx, page

    async def _get_cdp_page(self):
        """Get or create a page in the CDP-connected browser."""
        if not self._cdp_page or self._cdp_page.is_closed():
            ctx = self._browser.contexts[0]
            self._cdp_page = await ctx.new_page()
        return self._cdp_page

    async def _rate_limit_wait(self):
        """Wait with randomized delay to look human."""
        elapsed = time.time() - self._last_request_time
        min_wait = self.rate_limit
        max_wait = self.rate_limit * 2.5
        target = random.uniform(min_wait, max_wait)
        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request_time = time.time()

    async def _wait_past_cloudflare(self, page, max_attempts: int = 3) -> bool:
        """Wait for Cloudflare challenge to resolve. Returns True if page loaded."""
        for attempt in range(max_attempts):
            title = await page.title()
            if "just a moment" not in title.lower():
                return True
            await page.wait_for_timeout(5000)
        return False

    async def fetch_page(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Navigate to a URL and return the page HTML."""
        await self._rate_limit_wait()

        if self._cdp_mode:
            return await self._fetch_page_cdp(url, wait_selector)
        return await self._fetch_page_stealth(url, wait_selector)

    async def _fetch_page_cdp(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Fetch a page using the CDP-connected real Chrome session."""
        page = await self._get_cdp_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        if not await self._wait_past_cloudflare(page):
            return ""

        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass
        self._last_page = page
        self._last_ctx = None
        return await page.content()

    async def _fetch_page_stealth(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Fetch a page using a fresh stealth context."""
        ctx, page = await self._new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            if not await self._wait_past_cloudflare(page):
                return ""

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass
            html = await page.content()
            self._last_page = page
            self._last_ctx = ctx
            return html
        except Exception:
            await ctx.close()
            raise

    async def _close_last_context(self):
        """Close the context from the most recent stealth fetch_page call."""
        if hasattr(self, "_last_ctx") and self._last_ctx:
            try:
                await self._last_ctx.close()
            except Exception:
                pass
            self._last_ctx = None
            self._last_page = None

    async def search_book(
        self, base_url: str, title: str, author: str
    ) -> Optional[Dict[str, str]]:
        """Search for a book on romance.io/booknaut and return the best match."""
        query = f"{title} {author}"
        search_url = f"{base_url}/search?q={query}"
        try:
            html = await self.fetch_page(search_url)
            results = parse_search_results(html)
            if results:
                return results[0]

            # Search results load via AJAX — wait for book links to appear
            if hasattr(self, "_last_page") and self._last_page:
                try:
                    await self._last_page.wait_for_selector(
                        'a[href*="/books/"]', timeout=10000
                    )
                    html = await self._last_page.content()
                    results = parse_search_results(html)
                    if results:
                        return results[0]
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if not self._cdp_mode:
                await self._close_last_context()

        return None

    async def scrape_book(
        self, base_url: str, source_id: str, slug: str
    ) -> Dict[str, Any]:
        """Scrape full metadata from a book page."""
        url = f"{base_url}/books/{source_id}/{slug}"
        try:
            html = await self.fetch_page(url)
            return parse_book_page(html)
        finally:
            if not self._cdp_mode:
                await self._close_last_context()

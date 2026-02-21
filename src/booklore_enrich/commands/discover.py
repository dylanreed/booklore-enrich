# ABOUTME: Discover command that finds new books by trope from romance.io and booknaut.
# ABOUTME: Checks topic pages for romance, sci-fi, and fantasy recommendations.

import asyncio
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from booklore_enrich.config import load_config
from booklore_enrich.db import Database
from booklore_enrich.scraper.base import BrowserScraper, parse_search_results

console = Console()

SOURCES = {
    "romance.io": "https://www.romance.io",
    "booknaut": "https://www.thebooknaut.com",
}

GENRE_SOURCE_MAP = {
    "romance": "romance.io",
    "sci-fi": "booknaut",
    "fantasy": "booknaut",
}


def build_topic_urls(source: str, tropes: List[str]) -> List[str]:
    """Build topic page URLs for a list of tropes."""
    base = SOURCES[source]
    return [f"{base}/topics/best/{trope}/1" for trope in tropes]


def filter_known_books(db: Database, candidates: List[Dict[str, Any]],
                       source: str) -> List[Dict[str, Any]]:
    """Filter out books that are already in the local database."""
    col = "romance_io_id" if source == "romance.io" else "booknaut_id"
    known_ids = set()
    rows = db.execute(f"SELECT {col} FROM books WHERE {col} IS NOT NULL").fetchall()
    for row in rows:
        known_ids.add(row[0])
    return [c for c in candidates if c.get("source_id") not in known_ids]


async def discover_from_source(db: Database, source: str, tropes: List[str],
                                headless: bool, rate_limit: float) -> List[Dict[str, Any]]:
    """Discover new books from a source by checking topic pages."""
    urls = build_topic_urls(source, tropes)
    if not urls:
        return []

    scraper = BrowserScraper(headless=headless, rate_limit=rate_limit)
    await scraper.start()

    all_candidates = []
    seen_ids = set()

    try:
        for url in urls:
            console.print(f"  Checking {url}...")
            html = await scraper.fetch_page(url)
            results = parse_search_results(html)
            for result in results:
                if result["source_id"] not in seen_ids:
                    seen_ids.add(result["source_id"])
                    result["source"] = source
                    result["source_url"] = f"{SOURCES[source]}/books/{result['source_id']}/{result['slug']}"
                    all_candidates.append(result)
    finally:
        await scraper.stop()

    return filter_known_books(db, all_candidates, source)


def run_discover(source: str, genre: str):
    """Execute the discover command."""
    config = load_config()
    db = Database()

    try:
        sources_and_tropes = []

        if source == "all" or source == "romance.io":
            if genre in ("romance", None):
                sources_and_tropes.append(("romance.io", config.romance_tropes))
        if source == "all" or source == "booknaut":
            if genre in ("sci-fi", None):
                sources_and_tropes.append(("booknaut", config.scifi_tropes))
            if genre in ("fantasy", None):
                sources_and_tropes.append(("booknaut", config.fantasy_tropes))

        if not sources_and_tropes:
            console.print("[yellow]No trope preferences configured for that source/genre.[/yellow]")
            return

        all_new = []
        for src, tropes in sources_and_tropes:
            console.print(f"\nDiscovering from {src}...")
            new_books = asyncio.run(discover_from_source(
                db, src, tropes, config.headless, config.rate_limit_seconds
            ))
            all_new.extend(new_books)

            # Store discoveries
            for book in new_books:
                db.add_discovery(
                    title=book.get("slug", "").replace("-", " ").title(),
                    author="",
                    source=src,
                    source_id=book["source_id"],
                    source_url=book.get("source_url", ""),
                    genre=genre or "unknown",
                )

        if all_new:
            table = Table(title=f"Discovered {len(all_new)} New Books")
            table.add_column("Source")
            table.add_column("Title/Slug")
            table.add_column("URL")
            for book in all_new[:25]:
                table.add_row(
                    book["source"],
                    book.get("slug", "unknown").replace("-", " ").title()[:50],
                    book.get("source_url", ""),
                )
            console.print(table)
            if len(all_new) > 25:
                console.print(f"  ... and {len(all_new) - 25} more.")
        else:
            console.print("[yellow]No new books found for your trope preferences.[/yellow]")

    finally:
        db.close()

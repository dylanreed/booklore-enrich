# ABOUTME: Scrape command that fetches trope/heat metadata from romance.io and booknaut.
# ABOUTME: Orchestrates browser scraping with rate limiting and SQLite caching.

import asyncio
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.progress import Progress

from booklore_enrich.booklore_client import BookLoreClient
from booklore_enrich.config import load_config, get_password
from booklore_enrich.db import Database

console = Console()

SOURCES = {
    "romance.io": "https://www.romance.io",
    "booknaut": "https://www.thebooknaut.com",
}


def sync_books_to_cache(db: Database, booklore_books: List[Dict[str, Any]]) -> int:
    """Sync BookLore book list into the local SQLite cache."""
    count = 0
    for book in booklore_books:
        authors = book.get("authors", [])
        author = authors[0]["name"] if authors else "Unknown"
        isbn = book.get("isbn13", book.get("isbn", book.get("isbn10")))
        db.upsert_book(
            booklore_id=book["id"],
            title=book.get("title", ""),
            author=author,
            isbn=isbn,
        )
        count += 1
    return count


async def scrape_source(db: Database, source: str, limit: int, headless: bool,
                        rate_limit: float):
    """Scrape metadata for unscraped books from a single source."""
    from booklore_enrich.scraper.base import BrowserScraper

    base_url = SOURCES[source]
    unscraped = db.get_unscraped_books(source)

    if limit:
        unscraped = unscraped[:limit]

    if not unscraped:
        console.print(f"  No unscraped books for {source}.")
        return

    console.print(f"  Scraping {len(unscraped)} books from {source}...")

    scraper = BrowserScraper(headless=headless, rate_limit=rate_limit)
    await scraper.start()

    try:
        with Progress(console=console) as progress:
            task = progress.add_task(f"[cyan]Scraping {source}...", total=len(unscraped))

            found = 0
            skipped = 0
            failed = 0

            for book in unscraped:
                progress.update(task, description=f"[cyan]{book['title'][:40]}...")

                try:
                    # Search for the book
                    result = await scraper.search_book(base_url, book["title"], book["author"])
                    if not result:
                        skipped += 1
                        progress.advance(task)
                        continue

                    # Scrape the book page
                    metadata = await scraper.scrape_book(base_url, result["source_id"], result["slug"])

                    # Store tags
                    for tag_name in metadata.get("tags", []):
                        tag_id = db.get_or_create_tag(tag_name, category="trope", source=source)
                        db.add_book_tag(book["id"], tag_id)

                    # Store steam level
                    if metadata.get("steam_level"):
                        db.set_steam_level(book["id"], metadata["steam_level"],
                                           metadata.get("steam_label"))

                    # Mark as scraped
                    db.mark_scraped(book["id"], source, result["source_id"])
                    found += 1
                except Exception as e:
                    failed += 1
                    console.print(f"\n  [red]Error scraping '{book['title']}': {e}[/red]")

                progress.advance(task)

            console.print(f"  Results: {found} scraped, {skipped} not found, {failed} errors")

    finally:
        await scraper.stop()


def run_scrape(source: str, limit: int):
    """Execute the scrape command."""
    config = load_config()

    if not config.booklore_username:
        console.print("[red]No BookLore username configured.[/red]")
        return

    password = get_password()

    client = BookLoreClient(config.booklore_url)
    db = Database()

    try:
        console.print(f"Connecting to BookLore at {config.booklore_url}...")
        client.login(config.booklore_username, password)

        console.print("Syncing book list to local cache...")
        books = client.get_books()
        synced = sync_books_to_cache(db, books)
        console.print(f"  Synced {synced} books.")

        sources = [source] if source != "all" else list(SOURCES.keys())
        for src in sources:
            console.print(f"\nScraping {src}...")
            asyncio.run(scrape_source(db, src, limit, config.headless,
                                      config.rate_limit_seconds))

        console.print("\n[green]Scraping complete.[/green]")
    finally:
        client.close()
        db.close()

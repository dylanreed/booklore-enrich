# ABOUTME: Export command that generates a Goodreads-compatible CSV from BookLore.
# ABOUTME: Used for importing your library into romance.io and thebooknaut.com.

import csv
import io
from typing import Any, Dict, List

import click
from rich.console import Console

from booklore_enrich.config import load_config, save_config, get_password

console = Console()

GOODREADS_FIELDS = [
    "Title",
    "Author",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "Publisher",
    "Year Published",
    "Number of Pages",
    "Bookshelves",
]


def books_to_goodreads_csv(books: List[Dict[str, Any]]) -> str:
    """Convert BookLore book list to Goodreads-compatible CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=GOODREADS_FIELDS)
    writer.writeheader()

    for book in books:
        # BookLore nests book info under "metadata"; fall back to top-level for tests
        meta = book.get("metadata", book)
        authors = meta.get("authors", [])
        # Authors can be strings or dicts with a "name" key
        if authors and isinstance(authors[0], dict):
            primary_author = authors[0]["name"]
            additional = ", ".join(a["name"] for a in authors[1:]) if len(authors) > 1 else ""
        elif authors:
            primary_author = authors[0]
            additional = ", ".join(authors[1:]) if len(authors) > 1 else ""
        else:
            primary_author = ""
            additional = ""

        writer.writerow(
            {
                "Title": meta.get("title", ""),
                "Author": primary_author,
                "Additional Authors": additional,
                "ISBN": meta.get("isbn10", meta.get("isbn", "")),
                "ISBN13": meta.get("isbn13", meta.get("isbn", "")),
                "Publisher": meta.get("publisher", ""),
                "Year Published": meta.get("publishedDate", ""),
                "Number of Pages": meta.get("pageCount", ""),
                "Bookshelves": "",
            }
        )

    return output.getvalue()


def run_export(output_path: str):
    """Execute the export command."""
    # Lazy import to avoid errors when BookLoreClient is not yet available
    from booklore_enrich.booklore_client import BookLoreClient

    config = load_config()

    if not config.booklore_username:
        console.print(
            "[red]No BookLore username configured. "
            "Run with --username or set in config.[/red]"
        )
        return

    password = get_password()

    client = BookLoreClient(config.booklore_url)
    try:
        console.print(f"Connecting to BookLore at {config.booklore_url}...")
        client.login(config.booklore_username, password)

        console.print("Fetching books...")
        books = client.get_books(with_description=True)
        console.print(f"Found {len(books)} books.")

        csv_data = books_to_goodreads_csv(books)
        with open(output_path, "w") as f:
            f.write(csv_data)

        console.print(f"[green]Exported {len(books)} books to {output_path}[/green]")
        console.print("\nNext steps:")
        console.print("  1. Go to https://www.romance.io/import")
        console.print("  2. Upload the CSV file")
        console.print("  3. Wait for the confirmation email")
    finally:
        client.close()

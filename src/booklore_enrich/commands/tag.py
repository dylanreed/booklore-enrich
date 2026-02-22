# ABOUTME: Tag command that pushes enriched metadata into BookLore as shelves and tags.
# ABOUTME: Creates trope shelves, steam-level shelves, and adds category tags to books.

from collections import defaultdict
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.table import Table

from booklore_enrich.booklore_client import BookLoreClient
from booklore_enrich.config import load_config, get_password
from booklore_enrich.db import Database

console = Console()

STEAM_SHELF_NAMES = {
    1: "Spice: 1 - Glimpses & Kisses",
    2: "Spice: 2 - Behind Closed Doors",
    3: "Spice: 3 - Open Door",
    4: "Spice: 4 - Explicit Open Door",
    5: "Spice: 5 - Explicit & Plentiful",
}


def _trope_to_shelf_name(trope: str) -> str:
    """Convert a trope slug to a human-readable shelf name."""
    return trope.replace("-", " ").title()


def build_shelf_plan(db: Database) -> List[Dict[str, Any]]:
    """Build a plan of shelves to create and which books go on each."""
    enriched = db.get_enriched_books()

    # Group books by trope tag
    trope_books: Dict[str, set] = defaultdict(set)
    steam_books: Dict[str, set] = defaultdict(set)

    for book in enriched:
        for tag in book.get("tags", []):
            if tag.get("category") == "trope":
                shelf_name = _trope_to_shelf_name(tag["name"])
                trope_books[shelf_name].add(book["booklore_id"])

        if book.get("steam_level"):
            shelf_name = STEAM_SHELF_NAMES.get(book["steam_level"])
            if shelf_name:
                steam_books[shelf_name].add(book["booklore_id"])

    plan = []
    for name, book_ids in sorted(trope_books.items()):
        plan.append({"name": name, "booklore_ids": list(book_ids), "type": "trope"})
    for name, book_ids in sorted(steam_books.items()):
        plan.append({"name": name, "booklore_ids": list(book_ids), "type": "steam"})

    return plan


def build_tag_plan(db: Database) -> Dict[int, List[str]]:
    """Build a plan of category tags to add to each book."""
    enriched = db.get_enriched_books()
    plan: Dict[int, List[str]] = {}
    for book in enriched:
        seen: set[str] = set()
        tags: List[str] = []
        for t in book.get("tags", []):
            name = t["name"]
            if name not in seen:
                seen.add(name)
                tags.append(name)
        if book.get("steam_level"):
            spice_tag = f"spice-{book['steam_level']}"
            if spice_tag not in seen:
                tags.append(spice_tag)
        if tags:
            plan[book["booklore_id"]] = tags
    return plan


def diff_tags(planned: List[str], existing: List[str]) -> List[str]:
    """Filter out tags the book already has in BookLore."""
    existing_lower = {t.lower() for t in existing}
    return [t for t in planned if t.lower() not in existing_lower]


def run_tag(dry_run: bool, skip_shelves: bool = False, skip_tags: bool = False):
    """Execute the tag command."""
    config = load_config()
    db = Database()

    shelf_plan = build_shelf_plan(db)
    tag_plan = build_tag_plan(db)

    effective_shelf_plan = shelf_plan if not skip_shelves else []
    effective_tag_plan = tag_plan if not skip_tags else {}

    if not effective_shelf_plan and not effective_tag_plan:
        console.print("[yellow]Nothing to do. Check flags or run 'scrape' first.[/yellow]")
        return

    # Display plan
    table = Table(title="Shelf Plan")
    table.add_column("Shelf Name")
    table.add_column("Type")
    table.add_column("Books")
    for shelf in shelf_plan:
        table.add_row(shelf["name"], shelf["type"], str(len(shelf["booklore_ids"])))
    console.print(table)
    console.print(f"\nTag plan: {len(tag_plan)} books will get category tags.")

    if dry_run:
        console.print("\n[yellow]DRY RUN — no changes made.[/yellow]")
        return

    if not config.booklore_username:
        console.print("[red]No BookLore username configured.[/red]")
        return

    password = get_password()
    client = BookLoreClient(config.booklore_url)

    try:
        client.login(config.booklore_username, password)

        if not skip_shelves:
            # Get existing shelves to avoid duplicates
            existing_shelves = {s["name"]: s["id"] for s in client.get_shelves()}

            # Create shelves and assign books
            for shelf in shelf_plan:
                if shelf["name"] in existing_shelves:
                    shelf_id = existing_shelves[shelf["name"]]
                    console.print(f"  Shelf '{shelf['name']}' already exists.")
                else:
                    result = client.create_shelf(shelf["name"])
                    shelf_id = result["id"]
                    console.print(f"  Created shelf '{shelf['name']}'.")

                client.assign_books_to_shelf(shelf_id, shelf["booklore_ids"])
                console.print(f"    Assigned {len(shelf['booklore_ids'])} books.")

        if not skip_tags:
            # Add category tags to books, skipping ones that already exist
            console.print("\nAdding category tags to books...")
            tagged = 0
            skipped = 0
            for booklore_id, tags in tag_plan.items():
                try:
                    book_data = client.get_book(booklore_id)
                    meta = book_data.get("metadata", book_data)
                    existing_categories = meta.get("categories", [])
                except Exception:
                    existing_categories = []

                new_tags = diff_tags(tags, existing_categories)
                if not new_tags:
                    skipped += 1
                    continue

                client.update_book_metadata(booklore_id, {
                    "categories": new_tags,
                }, merge_categories=True)
                tagged += 1

            console.print(f"  Tagged {tagged} books, {skipped} already up to date.")
        console.print("\n[green]Tagging complete.[/green]")
    finally:
        client.close()
        db.close()

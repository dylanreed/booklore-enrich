# ABOUTME: Embed command — writes scraped metadata into EPUB files.
# ABOUTME: Reads from SQLite cache, merges into EPUB OPF metadata.

import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from booklore_enrich.db import Database
from booklore_enrich.epub_writer import write_epub_metadata

console = Console()

LOG_DIR = Path.home() / ".config" / "booklore-enrich"


def run_embed(directory: str, dry_run: bool = False, force: bool = False):
    """Write cached metadata into EPUB files on disk."""
    db = Database()
    log_path = LOG_DIR / f"embed-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("embed")

    books = db.get_embeddable_books(path_prefix=directory, force=force)
    if not books:
        console.print("[yellow]No embeddable books found.[/yellow]")
        logger.info("No embeddable books found for prefix: %s", directory)
        return

    console.print(f"Found [green]{len(books)}[/green] books to embed")
    embedded = 0
    skipped = 0
    errors = 0

    with Progress() as progress:
        task = progress.add_task("Embedding metadata...", total=len(books))
        for book in books:
            file_path = book["file_path"]
            try:
                if not Path(file_path).exists():
                    logger.warning("SKIP (file missing): %s", file_path)
                    skipped += 1
                    progress.advance(task)
                    continue

                if not file_path.lower().endswith(".epub"):
                    logger.warning("SKIP (not epub): %s", file_path)
                    skipped += 1
                    progress.advance(task)
                    continue

                # Separate tags by category
                trope_tags = []
                subgenre_subjects = []
                for tag in book.get("tags", []):
                    cat = tag.get("category", "trope")
                    name = tag["name"]
                    if cat == "subgenre":
                        subgenre_subjects.append(name)
                    elif cat == "hero-type":
                        trope_tags.append(f"hero:{name}")
                    elif cat == "heroine-type":
                        trope_tags.append(f"heroine:{name}")
                    else:
                        trope_tags.append(name)

                # Add steam level as tag
                if book.get("steam_level"):
                    trope_tags.append(f"steam:{book['steam_level']}")

                if dry_run:
                    console.print(f"  [dim]DRY RUN:[/dim] {file_path}")
                    console.print(f"    subjects: {subgenre_subjects}")
                    console.print(f"    tags: {trope_tags}")
                    console.print(f"    author: {book['author']}")
                    console.print(f"    series: {book.get('series')}")
                    logger.info(
                        "DRY RUN: %s | subjects=%s tags=%s",
                        file_path,
                        subgenre_subjects,
                        trope_tags,
                    )
                    embedded += 1
                    progress.advance(task)
                    continue

                write_epub_metadata(
                    file_path,
                    title=book["title"],
                    author=book["author"],
                    subjects=subgenre_subjects if subgenre_subjects else None,
                    tags=trope_tags if trope_tags else None,
                    series=book.get("series"),
                    series_index=book.get("series_index"),
                    series_total=book.get("series_total"),
                )
                db.mark_embedded(book["id"])
                logger.info(
                    "EMBEDDED: %s | subjects=%s tags=%s series=%s",
                    file_path,
                    subgenre_subjects,
                    trope_tags,
                    book.get("series"),
                )
                embedded += 1
            except Exception as e:
                logger.error("ERROR: %s | %s", file_path, str(e))
                console.print(f"  [red]ERROR:[/red] {file_path}: {e}")
                errors += 1
            progress.advance(task)

    console.print()
    console.print(f"[green]Embedded:[/green] {embedded}")
    console.print(f"[yellow]Skipped:[/yellow] {skipped}")
    console.print(f"[red]Errors:[/red] {errors}")
    console.print(f"[dim]Log: {log_path}[/dim]")
    logger.info(
        "SUMMARY: embedded=%d skipped=%d errors=%d", embedded, skipped, errors
    )

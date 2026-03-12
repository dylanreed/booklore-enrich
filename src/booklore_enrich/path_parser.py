# ABOUTME: Parses book metadata from filesystem paths.
# ABOUTME: Extracts author, series, index, and title from directory structure.

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from booklore_enrich.db import Database


def flip_author_name(name: str) -> str:
    """Flip 'Last, First' to 'First Last' for single-author names.

    Only flips when there's exactly one comma and the part before
    the comma is a single word (surname). Multi-author strings like
    'Margaret Weis, Tracy Hickman' are left unchanged.
    """
    if "," not in name:
        return name
    parts = name.split(",", 1)
    if len(parts) != 2:
        return name
    before_comma = parts[0].strip()
    after_comma = parts[1].strip()
    # Single word before comma = reversed name, flip it
    if " " not in before_comma:
        return f"{after_comma} {before_comma}"
    return name


def parse_book_path(file_path: str, base_dir: str) -> Optional[Dict[str, str]]:
    """Parse a book file path into metadata components.

    Expected structures relative to base_dir:
        Author/Series/Index - Title.epub
        Author/Standalone/Title.epub
        Author/Title.epub

    Returns None for non-epub files.
    Returns dict with: author, title, series, series_index, file_path
    """
    path = Path(file_path)
    if path.suffix.lower() != ".epub":
        return None

    base = Path(base_dir)
    try:
        rel = path.relative_to(base)
    except ValueError:
        return None

    parts = list(rel.parts)
    if len(parts) < 2:
        return None

    author = flip_author_name(parts[0])
    filename = path.stem  # filename without extension

    series = None
    series_index = None
    title = filename

    if len(parts) == 3:
        # Author/Series-or-Standalone/filename.epub
        folder = parts[1]
        if folder.lower() == "standalone":
            series = None
        else:
            series = folder

        # Parse "01 - Title" or "01.5 - Title" from filename
        index_match = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(.+)$", filename)
        if index_match:
            series_index = index_match.group(1)
            title = index_match.group(2)
    elif len(parts) == 2:
        # Author/filename.epub (flat)
        title = filename

    return {
        "author": author,
        "title": title,
        "series": series,
        "series_index": series_index,
        "file_path": file_path,
    }


def discover_books_from_dir(
    base_dir: str,
    db: Optional[Database] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[Dict]:
    """Walk a directory tree and discover all epub books.

    Parses metadata from paths and optionally inserts into the database.
    on_progress is called with (current, total) after each book is processed.
    Returns list of parsed book dicts.
    """
    base = Path(base_dir)
    epub_paths = sorted(base.rglob("*.epub"))
    total = len(epub_paths)
    books = []
    for i, epub_path in enumerate(epub_paths):
        parsed = parse_book_path(str(epub_path), base_dir)
        if parsed is None:
            if on_progress:
                on_progress(i + 1, total)
            continue
        books.append(parsed)
        if db is not None:
            db.upsert_book_by_path(
                file_path=parsed["file_path"],
                title=parsed["title"],
                author=parsed["author"],
                series=parsed.get("series"),
                series_index=parsed.get("series_index"),
            )
        if on_progress:
            on_progress(i + 1, total)
    return books

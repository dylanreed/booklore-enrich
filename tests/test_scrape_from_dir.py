# ABOUTME: Tests for filesystem-based book discovery.
# ABOUTME: Covers directory walking, epub filtering, and cache population.

import os
from booklore_enrich.path_parser import discover_books_from_dir
from booklore_enrich.db import Database


def _create_epub(path):
    """Create a minimal file to represent an epub."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("fake epub")


def test_discover_finds_epubs(tmp_path):
    """Discovers epub files and returns parsed metadata."""
    _create_epub(tmp_path / "Author" / "Series" / "01 - Title.epub")
    _create_epub(tmp_path / "Author" / "Standalone" / "Other.epub")
    books = discover_books_from_dir(str(tmp_path))
    assert len(books) == 2
    titles = {b["title"] for b in books}
    assert "Title" in titles
    assert "Other" in titles


def test_discover_skips_non_epub(tmp_path):
    """Non-epub files are ignored."""
    _create_epub(tmp_path / "Author" / "Standalone" / "Book.epub")
    (tmp_path / "Author" / "Standalone" / "notes.txt").write_text("hi")
    books = discover_books_from_dir(str(tmp_path))
    assert len(books) == 1


def test_discover_populates_cache(tmp_path):
    """Discovered books are inserted into the database."""
    _create_epub(tmp_path / "Author" / "Series" / "01 - Title.epub")
    db = Database(tmp_path / "cache.db")
    books = discover_books_from_dir(str(tmp_path), db=db)
    assert len(books) == 1
    stored = db.get_book_by_path(str(tmp_path / "Author" / "Series" / "01 - Title.epub"))
    assert stored is not None
    assert stored["author"] == "Author"
    assert stored["series"] == "Series"
    assert stored["series_index"] == "01"

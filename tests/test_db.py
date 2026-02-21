# ABOUTME: Tests for the SQLite database cache layer.
# ABOUTME: Covers schema creation, book CRUD, tag management, and discovery storage.

import datetime
from booklore_enrich.db import Database


def test_database_creates_tables(tmp_path):
    db = Database(tmp_path / "test.db")
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in tables}
    assert "books" in table_names
    assert "tags" in table_names
    assert "book_tags" in table_names
    assert "book_steam" in table_names
    assert "discoveries" in table_names
    assert "discovery_preferences" in table_names


def test_upsert_and_get_book(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=42, title="Test Book", author="Test Author", isbn="1234567890")
    book = db.get_book_by_booklore_id(42)
    assert book is not None
    assert book["title"] == "Test Book"
    assert book["author"] == "Test Author"


def test_upsert_book_updates_existing(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=42, title="Old Title", author="Author")
    db.upsert_book(booklore_id=42, title="New Title", author="Author")
    book = db.get_book_by_booklore_id(42)
    assert book["title"] == "New Title"


def test_add_and_get_tags(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Romance Book", author="Author")
    book = db.get_book_by_booklore_id(1)
    tag_id = db.get_or_create_tag("enemies-to-lovers", category="trope", source="romance.io")
    db.add_book_tag(book["id"], tag_id)
    tags = db.get_book_tags(book["id"])
    assert len(tags) == 1
    assert tags[0]["name"] == "enemies-to-lovers"


def test_set_steam_level(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Spicy Book", author="Author")
    book = db.get_book_by_booklore_id(1)
    db.set_steam_level(book["id"], level=4, label="Explicit open door")
    steam = db.get_steam_level(book["id"])
    assert steam["level"] == 4
    assert steam["label"] == "Explicit open door"


def test_get_unscraped_books(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Book A", author="Author")
    db.upsert_book(booklore_id=2, title="Book B", author="Author")
    db.mark_scraped(db.get_book_by_booklore_id(1)["id"], source="romance.io", source_id="abc123")
    unscraped = db.get_unscraped_books(source="romance.io")
    assert len(unscraped) == 1
    assert unscraped[0]["title"] == "Book B"


def test_add_discovery(tmp_path):
    db = Database(tmp_path / "test.db")
    db.add_discovery(
        title="New Book", author="New Author", source="romance.io",
        source_id="abc123", source_url="https://romance.io/books/abc123/new-book",
        genre="romance", steam_level=3,
    )
    discoveries = db.get_discoveries(source="romance.io", include_dismissed=False)
    assert len(discoveries) == 1
    assert discoveries[0]["title"] == "New Book"


def test_dismiss_discovery(tmp_path):
    db = Database(tmp_path / "test.db")
    db.add_discovery(
        title="Meh Book", author="Author", source="romance.io",
        source_id="xyz", source_url="https://romance.io/books/xyz/meh",
        genre="romance",
    )
    discoveries = db.get_discoveries(source="romance.io")
    db.dismiss_discovery(discoveries[0]["id"])
    remaining = db.get_discoveries(source="romance.io", include_dismissed=False)
    assert len(remaining) == 0


def test_get_all_books_with_tags(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Book", author="Author")
    book = db.get_book_by_booklore_id(1)
    tag1 = db.get_or_create_tag("slow-burn", "trope", "romance.io")
    tag2 = db.get_or_create_tag("fantasy", "subgenre", "booknaut")
    db.add_book_tag(book["id"], tag1)
    db.add_book_tag(book["id"], tag2)
    db.set_steam_level(book["id"], 3, "Open door")
    enriched = db.get_enriched_books()
    assert len(enriched) == 1
    assert enriched[0]["booklore_id"] == 1
    assert len(enriched[0]["tags"]) == 2
    assert enriched[0]["steam_level"] == 3

# ABOUTME: Tests for the scrape command orchestration logic.
# ABOUTME: Verifies book syncing from BookLore to cache and scrape coordination.

from booklore_enrich.commands.scrape import sync_books_to_cache
from booklore_enrich.db import Database


def test_sync_books_to_cache(tmp_path):
    db = Database(tmp_path / "test.db")
    booklore_books = [
        {"id": 1, "title": "Book A", "authors": [{"name": "Author 1"}], "isbn": "111"},
        {"id": 2, "title": "Book B", "authors": [{"name": "Author 2"}], "isbn": "222"},
    ]
    synced = sync_books_to_cache(db, booklore_books)
    assert synced == 2
    assert db.get_book_by_booklore_id(1) is not None
    assert db.get_book_by_booklore_id(2) is not None


def test_sync_books_updates_existing(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Old Title", author="Author")
    booklore_books = [
        {"id": 1, "title": "New Title", "authors": [{"name": "Author"}]},
    ]
    sync_books_to_cache(db, booklore_books)
    book = db.get_book_by_booklore_id(1)
    assert book["title"] == "New Title"


def test_sync_books_handles_missing_authors(tmp_path):
    db = Database(tmp_path / "test.db")
    booklore_books = [
        {"id": 1, "title": "No Author Book", "authors": []},
    ]
    synced = sync_books_to_cache(db, booklore_books)
    assert synced == 1
    book = db.get_book_by_booklore_id(1)
    assert book["author"] == "Unknown"

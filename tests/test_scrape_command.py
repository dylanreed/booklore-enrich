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


def test_scrape_stores_tag_categories(tmp_path):
    """Scrape stores tags with their proper categories, not all as 'trope'."""
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Test", author="Author")
    book = db.get_book_by_booklore_id(1)
    # Simulate what scrape_source does with categorized tags
    categorized = [
        {"name": "enemies-to-lovers", "category": "trope"},
        {"name": "contemporary", "category": "subgenre"},
        {"name": "alpha-male", "category": "hero-type"},
    ]
    for tag in categorized:
        tag_id = db.get_or_create_tag(tag["name"], category=tag["category"], source="romance.io")
        db.add_book_tag(book["id"], tag_id)
    tags = db.get_book_tags(book["id"])
    categories = {t["category"] for t in tags}
    assert "trope" in categories
    assert "subgenre" in categories
    assert "hero-type" in categories


def test_update_book_series_from_scrape(tmp_path):
    """Scraped series data overwrites filesystem-parsed values."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path("/books/Author/MySeries/01 - Book.epub",
                            "Book", "Author", series="MySeries", series_index="01")
    book = db.get_book_by_path("/books/Author/MySeries/01 - Book.epub")
    db.update_book_series(book["id"], series="My Series (Corrected)",
                           series_index="1", series_total=5)
    updated = db.get_book_by_path("/books/Author/MySeries/01 - Book.epub")
    assert updated["series"] == "My Series (Corrected)"
    assert updated["series_index"] == "1"
    assert updated["series_total"] == 5

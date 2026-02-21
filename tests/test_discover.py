# ABOUTME: Tests for the discover command that finds new books by trope.
# ABOUTME: Verifies filtering, deduplication, and display logic.

from booklore_enrich.commands.discover import filter_known_books, build_topic_urls
from booklore_enrich.db import Database


def test_build_topic_urls_romance():
    urls = build_topic_urls("romance.io", ["enemies-to-lovers", "slow-burn"])
    assert len(urls) == 2
    assert "https://www.romance.io/topics/best/enemies-to-lovers/1" in urls
    assert "https://www.romance.io/topics/best/slow-burn/1" in urls


def test_build_topic_urls_booknaut():
    urls = build_topic_urls("booknaut", ["space-opera"])
    assert len(urls) == 1
    assert "https://www.thebooknaut.com/topics/best/space-opera/1" in urls


def test_filter_known_books(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Known Book", author="Author")
    book = db.get_book_by_booklore_id(1)
    db.mark_scraped(book["id"], "romance.io", "abc123")

    candidates = [
        {"source_id": "abc123", "title": "Known Book"},
        {"source_id": "def456", "title": "New Book"},
    ]
    filtered = filter_known_books(db, candidates, "romance.io")
    assert len(filtered) == 1
    assert filtered[0]["source_id"] == "def456"


def test_filter_known_books_empty_db(tmp_path):
    db = Database(tmp_path / "test.db")
    candidates = [{"source_id": "abc", "title": "Book"}]
    filtered = filter_known_books(db, candidates, "romance.io")
    assert len(filtered) == 1

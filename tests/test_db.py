# ABOUTME: Tests for the SQLite database cache layer.
# ABOUTME: Covers schema creation, book CRUD, tag management, discovery storage, and tag caching.

from booklore_enrich.db import Database, compute_tag_hash


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
    assert "tag_cache" in table_names


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


def test_compute_tag_hash_consistent_regardless_of_order():
    """Same tags in different order should produce the same hash."""
    hash1 = compute_tag_hash(["slow-burn", "enemies-to-lovers", "spice-4"])
    hash2 = compute_tag_hash(["enemies-to-lovers", "spice-4", "slow-burn"])
    hash3 = compute_tag_hash(["spice-4", "slow-burn", "enemies-to-lovers"])
    assert hash1 == hash2
    assert hash2 == hash3


def test_compute_tag_hash_different_for_different_tags():
    """Different tag sets should produce different hashes."""
    hash1 = compute_tag_hash(["slow-burn", "enemies-to-lovers"])
    hash2 = compute_tag_hash(["slow-burn", "friends-to-lovers"])
    assert hash1 != hash2


def test_get_tag_hash_returns_none_for_unknown(tmp_path):
    """get_tag_hash should return None for a booklore_id with no cached hash."""
    db = Database(tmp_path / "test.db")
    assert db.get_tag_hash(99999) is None


def test_set_and_get_tag_hash(tmp_path):
    """set_tag_hash should store a hash that get_tag_hash can retrieve."""
    db = Database(tmp_path / "test.db")
    tag_hash = compute_tag_hash(["enemies-to-lovers", "slow-burn"])
    db.set_tag_hash(42, tag_hash)
    assert db.get_tag_hash(42) == tag_hash


def test_set_tag_hash_upserts(tmp_path):
    """set_tag_hash should update the hash if the booklore_id already exists."""
    db = Database(tmp_path / "test.db")
    hash_v1 = compute_tag_hash(["enemies-to-lovers"])
    hash_v2 = compute_tag_hash(["enemies-to-lovers", "slow-burn"])
    db.set_tag_hash(42, hash_v1)
    assert db.get_tag_hash(42) == hash_v1
    db.set_tag_hash(42, hash_v2)
    assert db.get_tag_hash(42) == hash_v2


def test_compute_tag_hash_empty_list():
    """Empty tag list produces a consistent hash."""
    hash1 = compute_tag_hash([])
    hash2 = compute_tag_hash([])
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest length


def test_compute_tag_hash_deduplicates():
    """Duplicate tags are normalized so they don't cause spurious cache misses."""
    hash_with_dup = compute_tag_hash(["slow-burn", "slow-burn"])
    hash_without_dup = compute_tag_hash(["slow-burn"])
    assert hash_with_dup == hash_without_dup


def test_schema_has_new_columns(tmp_path):
    """New columns exist in the books table."""
    db = Database(tmp_path / "test.db")
    cols = db.execute("PRAGMA table_info(books)").fetchall()
    col_names = {row[1] for row in cols}
    assert "file_path" in col_names
    assert "series" in col_names
    assert "series_index" in col_names
    assert "series_total" in col_names
    assert "embedded_at" in col_names


def test_upsert_book_by_path(tmp_path):
    """Books can be upserted using file_path as identity key."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path(
        file_path="/books/Author/Series/01 - Title.epub",
        title="Title", author="Author",
        series="Series", series_index="01",
    )
    book = db.get_book_by_path("/books/Author/Series/01 - Title.epub")
    assert book is not None
    assert book["title"] == "Title"
    assert book["series"] == "Series"
    assert book["series_index"] == "01"


def test_upsert_book_by_path_updates_existing(tmp_path):
    """Upserting with same file_path updates the record."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path(
        file_path="/books/book.epub",
        title="Old", author="Author",
    )
    db.upsert_book_by_path(
        file_path="/books/book.epub",
        title="New", author="Author",
        series="Found Series", series_index="3", series_total=5,
    )
    book = db.get_book_by_path("/books/book.epub")
    assert book["title"] == "New"
    assert book["series"] == "Found Series"
    assert book["series_total"] == 5


def test_get_embeddable_books(tmp_path):
    """Returns scraped books that have a file_path."""
    db = Database(tmp_path / "test.db")
    # Book with path and scraped — should be returned
    db.upsert_book_by_path("/books/a.epub", "Book A", "Author")
    book_a = db.get_book_by_path("/books/a.epub")
    db.mark_scraped(book_a["id"], source="romance.io", source_id="abc")
    tag_id = db.get_or_create_tag("slow-burn", "trope", "romance.io")
    db.add_book_tag(book_a["id"], tag_id)
    # Book with path but not scraped — should NOT be returned
    db.upsert_book_by_path("/books/b.epub", "Book B", "Author")
    # Book scraped but no path (API-discovered) — should NOT be returned
    db.upsert_book(booklore_id=99, title="Book C", author="Author")
    embeddable = db.get_embeddable_books()
    assert len(embeddable) == 1
    assert embeddable[0]["title"] == "Book A"
    assert embeddable[0]["file_path"] == "/books/a.epub"
    assert len(embeddable[0]["tags"]) == 1


def test_get_embeddable_books_respects_path_prefix(tmp_path):
    """Only returns books whose file_path starts with the given prefix."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path("/nas/books/a.epub", "Book A", "Author")
    db.upsert_book_by_path("/local/books/b.epub", "Book B", "Author")
    for path in ["/nas/books/a.epub", "/local/books/b.epub"]:
        book = db.get_book_by_path(path)
        db.mark_scraped(book["id"], source="romance.io", source_id="x")
        db.add_book_tag(book["id"], db.get_or_create_tag("t", "trope", "romance.io"))
    result = db.get_embeddable_books(path_prefix="/nas/")
    assert len(result) == 1
    assert result[0]["title"] == "Book A"


def test_mark_embedded(tmp_path):
    """mark_embedded sets embedded_at timestamp."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path("/books/a.epub", "Book", "Author")
    book = db.get_book_by_path("/books/a.epub")
    db.mark_embedded(book["id"])
    updated = db.get_book_by_path("/books/a.epub")
    assert updated["embedded_at"] is not None


def test_get_embeddable_books_skips_already_embedded(tmp_path):
    """Already-embedded books are skipped unless force=True."""
    db = Database(tmp_path / "test.db")
    db.upsert_book_by_path("/books/a.epub", "Book", "Author")
    book = db.get_book_by_path("/books/a.epub")
    db.mark_scraped(book["id"], source="romance.io", source_id="x")
    db.add_book_tag(book["id"], db.get_or_create_tag("t", "trope", "romance.io"))
    db.mark_embedded(book["id"])
    assert len(db.get_embeddable_books()) == 0
    assert len(db.get_embeddable_books(force=True)) == 1


def test_migration_adds_missing_columns(tmp_path):
    """Existing databases get new columns via ALTER TABLE."""
    import sqlite3
    db_path = tmp_path / "old.db"
    # Create a database with the old schema (no new columns)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booklore_id INTEGER UNIQUE,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        isbn TEXT,
        romance_io_id TEXT,
        booknaut_id TEXT,
        last_scraped_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("INSERT INTO books (booklore_id, title, author) VALUES (1, 'Old Book', 'Author')")
    conn.commit()
    conn.close()
    # Open with Database class — should migrate
    db = Database(db_path)
    cols = db.execute("PRAGMA table_info(books)").fetchall()
    col_names = {row[1] for row in cols}
    assert "file_path" in col_names
    assert "series" in col_names
    assert "embedded_at" in col_names
    # Existing data should survive
    book = db.get_book_by_booklore_id(1)
    assert book["title"] == "Old Book"

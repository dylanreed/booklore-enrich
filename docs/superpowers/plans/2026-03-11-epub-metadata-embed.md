# EPUB Metadata Embed Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add filesystem-based book discovery (`scrape --from-dir`) and EPUB metadata embedding (`embed` command) to booklore-enrich.

**Architecture:** Two changes: (1) extend `scrape` with `--from-dir` to discover books from the filesystem instead of BookLore API, (2) new `embed` command that reads cached metadata and writes it into EPUB files using ebooklib. Both use the shared SQLite cache.

**Tech Stack:** Python 3.12+, click, ebooklib, rich, SQLite, uv

**Spec:** `docs/superpowers/specs/2026-03-11-epub-metadata-embed-design.md`

---

## Chunk 1: Database Layer Changes

### Task 1: Add new columns and migration logic to db.py

**Files:**
- Modify: `src/booklore_enrich/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing test for new columns in schema**

Add to `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py::test_schema_has_new_columns -v`
Expected: FAIL — columns don't exist yet

- [ ] **Step 3: Add columns to SCHEMA in db.py**

In `src/booklore_enrich/db.py`, update the `books` CREATE TABLE in the SCHEMA string (line 14) to add:

```sql
    file_path TEXT UNIQUE,
    series TEXT,
    series_index TEXT,
    series_total INTEGER,
    embedded_at TIMESTAMP,
```

Add these after the `created_at` line (line 23), before the closing `);`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py::test_schema_has_new_columns -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/db.py tests/test_db.py && git commit -m "feat(db): add file_path, series, and embedded_at columns to books table"
```

### Task 2: Add migration logic for existing databases

**Files:**
- Modify: `src/booklore_enrich/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing test for migration**

Add to `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py::test_migration_adds_missing_columns -v`
Expected: FAIL — no migration logic yet

- [ ] **Step 3: Add migration method to Database class**

Add this method to the `Database` class in `src/booklore_enrich/db.py`, called at the end of `__init__` after schema creation:

```python
def _migrate(self):
    """Add columns that may be missing from older databases."""
    existing = {row[1] for row in self.execute("PRAGMA table_info(books)").fetchall()}
    migrations = [
        ("file_path", "TEXT UNIQUE"),
        ("series", "TEXT"),
        ("series_index", "TEXT"),
        ("series_total", "INTEGER"),
        ("embedded_at", "TIMESTAMP"),
    ]
    for col_name, col_type in migrations:
        if col_name not in existing:
            self.execute(f"ALTER TABLE books ADD COLUMN {col_name} {col_type}")
    self.conn.commit()
```

Add `self._migrate()` at the end of `__init__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py::test_migration_adds_missing_columns -v`
Expected: PASS

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/db.py tests/test_db.py && git commit -m "feat(db): add migration logic for existing databases"
```

### Task 3: Add file_path-based upsert and query methods

**Files:**
- Modify: `src/booklore_enrich/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing test for upsert_book_by_path**

Add to `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py::test_upsert_book_by_path tests/test_db.py::test_upsert_book_by_path_updates_existing -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement upsert_book_by_path and get_book_by_path**

Add to the `Database` class in `src/booklore_enrich/db.py`:

```python
def upsert_book_by_path(self, file_path: str, title: str, author: str,
                         series: Optional[str] = None, series_index: Optional[str] = None,
                         series_total: Optional[int] = None):
    """Upsert a book using file_path as identity (for filesystem-discovered books)."""
    self.execute(
        """INSERT INTO books (file_path, title, author, series, series_index, series_total)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(file_path) DO UPDATE SET
               title=excluded.title, author=excluded.author,
               series=excluded.series, series_index=excluded.series_index,
               series_total=excluded.series_total""",
        (file_path, title, author, series, series_index, series_total),
    )
    self.conn.commit()

def get_book_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
    """Get a book by its file path."""
    row = self.execute("SELECT * FROM books WHERE file_path = ?", (file_path,)).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/db.py tests/test_db.py && git commit -m "feat(db): add file_path-based upsert and query methods"
```

### Task 4: Add get_embeddable_books and mark_embedded methods

**Files:**
- Modify: `src/booklore_enrich/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py -k "embeddable or mark_embedded" -v`
Expected: FAIL

- [ ] **Step 3: Implement get_embeddable_books and mark_embedded**

Add to the `Database` class in `src/booklore_enrich/db.py`:

```python
def mark_embedded(self, book_id: int):
    """Record that a book's EPUB has been written with enriched metadata."""
    self.execute(
        "UPDATE books SET embedded_at = CURRENT_TIMESTAMP WHERE id = ?",
        (book_id,),
    )
    self.conn.commit()

def get_embeddable_books(self, path_prefix: Optional[str] = None,
                          force: bool = False) -> List[Dict[str, Any]]:
    """Get all scraped books with file_path, optionally filtered by prefix.

    Returns books with their tags and steam levels.
    Skips already-embedded books unless force=True.
    """
    query = """
        SELECT b.*, bs.level as steam_level, bs.label as steam_label
        FROM books b
        LEFT JOIN book_steam bs ON b.id = bs.book_id
        WHERE b.file_path IS NOT NULL
          AND b.last_scraped_at IS NOT NULL
    """
    params: List[Any] = []
    if not force:
        query += " AND b.embedded_at IS NULL"
    if path_prefix:
        # Normalize: ensure trailing separator
        if not path_prefix.endswith("/"):
            path_prefix += "/"
        query += " AND b.file_path LIKE ?"
        params.append(path_prefix + "%")
    rows = self.execute(query, params).fetchall()
    results = []
    for row in rows:
        book = dict(row)
        tags = self.get_book_tags(book["id"])
        book["tags"] = tags
        results.append(book)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/db.py tests/test_db.py && git commit -m "feat(db): add embeddable books query and mark_embedded tracking"
```

---

## Chunk 2: Filesystem Discovery

### Task 5: Create path parser for book discovery

**Files:**
- Create: `src/booklore_enrich/path_parser.py`
- Test: `tests/test_path_parser.py`

- [ ] **Step 1: Write failing tests for path parsing**

Create `tests/test_path_parser.py`:

```python
# ABOUTME: Tests for filesystem path parsing to extract book metadata.
# ABOUTME: Covers series, standalone, flat, and edge case naming patterns.

from booklore_enrich.path_parser import parse_book_path


def test_series_with_index():
    """Author/Series/01 - Title.epub pattern."""
    result = parse_book_path(
        "/books/Tessa Bailey/Hot and Hammered/01 - Fix Her Up.epub",
        "/books",
    )
    assert result["author"] == "Tessa Bailey"
    assert result["series"] == "Hot and Hammered"
    assert result["series_index"] == "01"
    assert result["title"] == "Fix Her Up"


def test_standalone_folder():
    """Author/Standalone/Title.epub pattern."""
    result = parse_book_path(
        "/books/Margaret Atwood/Standalone/Alias Grace.epub",
        "/books",
    )
    assert result["author"] == "Margaret Atwood"
    assert result["series"] is None
    assert result["series_index"] is None
    assert result["title"] == "Alias Grace"


def test_flat_structure():
    """Author/Title.epub pattern (no series folder)."""
    result = parse_book_path(
        "/books/Tessa Bailey/Fix Her Up.epub",
        "/books",
    )
    assert result["author"] == "Tessa Bailey"
    assert result["series"] is None
    assert result["title"] == "Fix Her Up"


def test_strips_extension():
    """File extension is removed from title."""
    result = parse_book_path(
        "/books/Author/Standalone/My Book.epub",
        "/books",
    )
    assert result["title"] == "My Book"


def test_series_index_with_decimal():
    """Series index can be decimal (e.g. 01.5)."""
    result = parse_book_path(
        "/books/Author/Series/01.5 - Novella.epub",
        "/books",
    )
    assert result["series_index"] == "01.5"
    assert result["title"] == "Novella"


def test_returns_none_for_non_epub():
    """Non-epub files return None."""
    result = parse_book_path("/books/Author/book.pdf", "/books")
    assert result is None


def test_author_flip_last_first():
    """Last, First author names are flipped to First Last."""
    result = parse_book_path(
        "/books/Bailey, Tessa/Standalone/Book.epub",
        "/books",
    )
    assert result["author"] == "Tessa Bailey"


def test_author_no_flip_multi_author():
    """Multi-author names are not flipped."""
    result = parse_book_path(
        "/books/Margaret Weis, Tracy Hickman/Series/01 - Book.epub",
        "/books",
    )
    assert result["author"] == "Margaret Weis, Tracy Hickman"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_path_parser.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement path_parser.py**

Create `src/booklore_enrich/path_parser.py`:

```python
# ABOUTME: Parses book metadata from filesystem paths.
# ABOUTME: Extracts author, series, index, and title from directory structure.

import re
from pathlib import Path
from typing import Dict, Optional


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_path_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/path_parser.py tests/test_path_parser.py && git commit -m "feat: add filesystem path parser for book discovery"
```

### Task 6: Create discover_books_from_dir function

**Files:**
- Create: `tests/test_scrape_from_dir.py`
- Modify: `src/booklore_enrich/path_parser.py`

- [ ] **Step 1: Write failing tests for directory scanning**

Create `tests/test_scrape_from_dir.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scrape_from_dir.py -v`
Expected: FAIL

- [ ] **Step 3: Implement discover_books_from_dir**

Add to `src/booklore_enrich/path_parser.py`:

```python
from booklore_enrich.db import Database


def discover_books_from_dir(base_dir: str,
                             db: Optional[Database] = None) -> list[Dict]:
    """Walk a directory tree and discover all epub books.

    Parses metadata from paths and optionally inserts into the database.
    Returns list of parsed book dicts.
    """
    base = Path(base_dir)
    books = []
    for epub_path in sorted(base.rglob("*.epub")):
        parsed = parse_book_path(str(epub_path), base_dir)
        if parsed is None:
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
    return books
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scrape_from_dir.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/path_parser.py tests/test_scrape_from_dir.py && git commit -m "feat: add directory scanner for book discovery"
```

### Task 7: Add --from-dir flag to scrape command

**Files:**
- Modify: `src/booklore_enrich/commands/scrape.py`
- Modify: `src/booklore_enrich/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for --from-dir CLI option**

Add to `tests/test_cli.py`:

```python
def test_scrape_has_from_dir_option():
    runner = CliRunner()
    result = runner.invoke(cli, ["scrape", "--help"])
    assert "--from-dir" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_cli.py::test_scrape_has_from_dir_option -v`
Expected: FAIL

- [ ] **Step 3: Add --from-dir option to scrape command**

In `src/booklore_enrich/cli.py`, add the option to the `scrape` command. Use lazy import (matching existing pattern):

```python
@cli.command()
@click.option("-s", "--source", type=click.Choice(["romance.io", "booknaut", "all"]), default="all")
@click.option("-l", "--limit", type=int, default=0, help="Max books to scrape (0 = all)")
@click.option("--from-dir", type=click.Path(exists=True), default=None,
              help="Discover books from filesystem instead of BookLore API")
def scrape(source, limit, from_dir):
    """Scrape trope metadata from romance.io and/or thebooknaut."""
    from booklore_enrich.commands.scrape import run_scrape
    run_scrape(source=source, limit=limit, from_dir=from_dir)
```

Restructure `run_scrape()` in `src/booklore_enrich/commands/scrape.py` to handle both paths cleanly. The key issue is that the existing function creates `client` before the try block and calls `client.close()` in `finally` — when `--from-dir` is used, no client exists and that would crash. Here's the full refactored function:

```python
def run_scrape(source: str = "all", limit: int = 0, from_dir: str | None = None):
    """Execute the scrape command."""
    db = Database()
    client = None

    try:
        if from_dir:
            # Filesystem discovery — skip BookLore sync entirely
            from booklore_enrich.path_parser import discover_books_from_dir
            console.print(f"[bold]Discovering books from:[/bold] {from_dir}")
            books = discover_books_from_dir(from_dir, db=db)
            console.print(f"Found [green]{len(books)}[/green] epub files")
        else:
            # Existing BookLore API sync path
            config = load_config()
            if not config.booklore_username:
                console.print("[red]No BookLore username configured.[/red]")
                return
            password = get_password()
            client = BookLoreClient(config.booklore_url)
            console.print(f"Connecting to BookLore at {config.booklore_url}...")
            client.login(config.booklore_username, password)
            console.print("Syncing book list to local cache...")
            books = client.get_books()
            synced = sync_books_to_cache(db, books)
            console.print(f"  Synced {synced} books.")

        headless = True if from_dir else config.headless
        rate_limit = 1.0 if from_dir else config.rate_limit_seconds

        sources = [source] if source != "all" else list(SOURCES.keys())
        for src in sources:
            console.print(f"\nScraping {src}...")
            asyncio.run(scrape_source(db, src, limit, headless, rate_limit))

        console.print("\n[green]Scraping complete.[/green]")
    finally:
        if client is not None:
            client.close()
        db.close()
```

Note: `client = None` and `if client is not None` in `finally` prevents the crash when `--from-dir` is used.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/commands/scrape.py src/booklore_enrich/cli.py tests/test_cli.py && git commit -m "feat: add --from-dir flag to scrape command for filesystem discovery"
```

---

## Chunk 3: Tag Category Differentiation

### Task 8: Enhance parse_book_page to return categorized tags

**Files:**
- Modify: `src/booklore_enrich/scraper/base.py`
- Modify: `tests/test_scraper_base.py`

The current `parse_book_page()` returns a flat `tags` list. The embed command needs tags categorized as `"trope"`, `"subgenre"`, `"hero-type"`, or `"heroine-type"`. Romance.io/booknaut pages link all tags via `/topics/` URLs, but we can categorize using a known-subgenres list as the fallback approach (spec lines 131-132).

- [ ] **Step 1: Write failing tests for categorized tags**

Add to `tests/test_scraper_base.py`:

```python
def test_parse_book_page_categorizes_tags():
    """Tags are returned with categories, not as flat strings."""
    html = '''
    <a href="/topics/best/enemies-to-lovers/1">Enemies to Lovers</a>
    <a href="/topics/best/contemporary/1">Contemporary</a>
    <a href="/topics/best/alpha-male/1">Alpha Male</a>
    <a href="/topics/best/competent-heroine/1">Competent Heroine</a>
    '''
    from booklore_enrich.scraper.base import parse_book_page
    result = parse_book_page(html)
    # Should still have tags list for backwards compat
    assert len(result["tags"]) > 0
    # Should also have categorized_tags
    cats = result["categorized_tags"]
    names_by_cat = {}
    for t in cats:
        names_by_cat.setdefault(t["category"], []).append(t["name"])
    assert "contemporary" in names_by_cat.get("subgenre", [])
    assert "enemies-to-lovers" in names_by_cat.get("trope", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scraper_base.py::test_parse_book_page_categorizes_tags -v`
Expected: FAIL — `categorized_tags` key doesn't exist

- [ ] **Step 3: Add categorization to parse_book_page**

In `src/booklore_enrich/scraper/base.py`, add a known-subgenres set and hero/heroine type sets near the top of the file:

```python
KNOWN_SUBGENRES = {
    "contemporary", "contemporary-romance", "dark", "dark-romance",
    "historical", "historical-romance", "paranormal", "paranormal-romance",
    "romantic-suspense", "romantic-comedy", "rom-com", "erotic", "erotica",
    "fantasy-romance", "sci-fi-romance", "western-romance", "gothic",
    "new-adult", "young-adult", "ya", "lgbtq", "mm-romance", "ff-romance",
    "christian-romance", "clean-romance", "sweet-romance", "regency",
    "medieval", "victorian", "highlander", "cowboy", "military",
    "sports-romance", "rockstar-romance", "mafia", "motorcycle-club",
    "small-town", "holiday", "christmas", "valentine",
    "urban-fantasy", "epic-fantasy", "high-fantasy", "space-opera",
    "cyberpunk", "dystopian", "post-apocalyptic", "steampunk",
    "first-contact", "hard-sci-fi", "literpg", "gamelit",
    "cozy-mystery", "thriller", "horror", "mystery",
}

KNOWN_HERO_TYPES = {
    "alpha-male", "beta-hero", "bad-boy", "billionaire", "boss",
    "ceo", "duke", "prince", "king", "vampire", "werewolf", "shifter",
    "dragon", "fae", "alien", "demon", "pirate", "viking",
    "single-dad", "grumpy-hero", "sunshine-hero", "anti-hero",
    "morally-grey", "brooding-hero",
}

KNOWN_HEROINE_TYPES = {
    "competent-heroine", "strong-heroine", "feisty-heroine",
    "sunshine-heroine", "bookish-heroine", "kickass-heroine",
    "single-mom", "curvy-heroine", "independent-heroine",
}
```

Then update `parse_book_page()` to add `categorized_tags` alongside the existing `tags` list (keeping backwards compatibility):

```python
    data["categorized_tags"] = []
    for tag_name in data["tags"]:
        if tag_name in KNOWN_SUBGENRES:
            category = "subgenre"
        elif tag_name in KNOWN_HERO_TYPES:
            category = "hero-type"
        elif tag_name in KNOWN_HEROINE_TYPES:
            category = "heroine-type"
        else:
            category = "trope"
        data["categorized_tags"].append({"name": tag_name, "category": category})
```

Add this block right before the `return data` line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scraper_base.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/scraper/base.py tests/test_scraper_base.py && git commit -m "feat(scraper): categorize tags as trope/subgenre/hero-type/heroine-type"
```

### Task 9: Update scrape command to use categorized tags and store series data

**Files:**
- Modify: `src/booklore_enrich/commands/scrape.py`
- Modify: `src/booklore_enrich/db.py`
- Create: `tests/test_scrape_command.py`

The current `scrape_source` function hardcodes `category="trope"` for all tags. It also never stores series data from scraped pages. The spec requires: (1) using proper tag categories, and (2) scraped series data overwrites filesystem-parsed values (series_total is only available from scraped pages).

- [ ] **Step 1: Write failing test for categorized tag storage**

Create `tests/test_scrape_command.py`:

```python
# ABOUTME: Tests for scrape command behavior changes.
# ABOUTME: Covers categorized tag storage and series data from scraped pages.

from booklore_enrich.db import Database


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
```

- [ ] **Step 2: Run test to verify it passes (validates DB supports categories)**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scrape_command.py::test_scrape_stores_tag_categories -v`
Expected: PASS (the DB already has a `category` column on `tags` — this confirms it works)

- [ ] **Step 3: Write failing test for series data update from scrape**

Add to `tests/test_scrape_command.py`:

```python
def test_update_book_series_from_scrape(tmp_path):
    """Scraped series data overwrites filesystem-parsed values."""
    db = Database(tmp_path / "test.db")
    # Simulate filesystem-discovered book with partial series info
    db.upsert_book_by_path("/books/Author/MySeries/01 - Book.epub",
                            "Book", "Author", series="MySeries", series_index="01")
    book = db.get_book_by_path("/books/Author/MySeries/01 - Book.epub")
    # Simulate scraped data providing more authoritative series info
    db.update_book_series(book["id"], series="My Series (Corrected)",
                           series_index="1", series_total=5)
    updated = db.get_book_by_path("/books/Author/MySeries/01 - Book.epub")
    assert updated["series"] == "My Series (Corrected)"
    assert updated["series_index"] == "1"
    assert updated["series_total"] == 5
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scrape_command.py::test_update_book_series_from_scrape -v`
Expected: FAIL — `update_book_series` method doesn't exist

- [ ] **Step 5: Add update_book_series method to Database**

Add to `src/booklore_enrich/db.py`:

```python
def update_book_series(self, book_id: int, series: Optional[str] = None,
                        series_index: Optional[str] = None,
                        series_total: Optional[int] = None):
    """Update series fields on a book (scraped data overwrites filesystem-parsed)."""
    self.execute(
        "UPDATE books SET series = ?, series_index = ?, series_total = ? WHERE id = ?",
        (series, series_index, series_total, book_id),
    )
    self.conn.commit()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_scrape_command.py -v`
Expected: All PASS

- [ ] **Step 7: Update scrape_source to use categorized_tags and store series data**

In `src/booklore_enrich/commands/scrape.py`, change lines 95-98 from:

```python
                    # Store tags
                    for tag_name in metadata.get("tags", []):
                        tag_id = db.get_or_create_tag(tag_name, category="trope", source=source)
                        db.add_book_tag(book["id"], tag_id)
```

to:

```python
                    # Store tags with categories
                    for tag in metadata.get("categorized_tags", []):
                        tag_id = db.get_or_create_tag(
                            tag["name"], category=tag["category"], source=source
                        )
                        db.add_book_tag(book["id"], tag_id)

                    # Update series data from scraped page (overwrites filesystem-parsed)
                    series = metadata.get("series")
                    if series:
                        db.update_book_series(
                            book["id"],
                            series=series,
                            series_index=metadata.get("series_index"),
                            series_total=metadata.get("series_total"),
                        )
```

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/commands/scrape.py tests/test_scrape_command.py && git commit -m "feat(scrape): store tags with proper categories from categorized_tags"
```

---

## Chunk 4: EPUB Writer

### Task 10: Add ebooklib dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ebooklib to dependencies**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv add ebooklib`

- [ ] **Step 2: Verify install**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run python -c "import ebooklib; print('OK')" `
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add pyproject.toml uv.lock && git commit -m "deps: add ebooklib for EPUB metadata writing"
```

### Task 11: Create EPUB writer — author flip and title

**Files:**
- Create: `src/booklore_enrich/epub_writer.py`
- Create: `tests/test_epub_writer.py`

- [ ] **Step 1: Write failing tests for author flip and title setting**

Create `tests/test_epub_writer.py`:

```python
# ABOUTME: Tests for EPUB metadata read/merge/write logic.
# ABOUTME: Covers author flipping, title, subjects, tags, and series metadata.

from ebooklib import epub
from booklore_enrich.epub_writer import read_epub_metadata, write_epub_metadata


def _make_test_epub(path, title="Test Book", author="Test Author"):
    """Create a minimal valid EPUB for testing."""
    book = epub.EpubBook()
    book.set_identifier("test-id-001")
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)
    ch = epub.EpubHtml(title="Chapter", file_name="ch1.xhtml", lang="en")
    ch.content = "<html><body><p>Test</p></body></html>"
    book.add_item(ch)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    epub.write_epub(str(path), book)
    return path


def test_read_epub_metadata(tmp_path):
    """Reads basic metadata from an EPUB."""
    path = _make_test_epub(tmp_path / "test.epub")
    meta = read_epub_metadata(str(path))
    assert meta["title"] == "Test Book"
    assert meta["authors"] == ["Test Author"]


def test_write_title(tmp_path):
    """Writing sets the dc:title."""
    path = _make_test_epub(tmp_path / "test.epub", title="Old Title")
    write_epub_metadata(str(path), title="New Title")
    meta = read_epub_metadata(str(path))
    assert meta["title"] == "New Title"


def test_flip_reversed_author(tmp_path):
    """Last, First author is flipped to First Last."""
    path = _make_test_epub(tmp_path / "test.epub", author="Bailey, Tessa")
    write_epub_metadata(str(path), author="Tessa Bailey")
    meta = read_epub_metadata(str(path))
    assert "Tessa Bailey" in meta["authors"]


def test_multi_author_not_flipped(tmp_path):
    """Multi-author strings are preserved."""
    path = _make_test_epub(tmp_path / "test.epub", author="Margaret Weis, Tracy Hickman")
    write_epub_metadata(str(path), author="Margaret Weis, Tracy Hickman")
    meta = read_epub_metadata(str(path))
    assert "Margaret Weis, Tracy Hickman" in meta["authors"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement read_epub_metadata and write_epub_metadata (basics)**

Create `src/booklore_enrich/epub_writer.py`:

```python
# ABOUTME: Reads and writes metadata in EPUB files.
# ABOUTME: Handles dc:subject, booklore:tags, series, author flipping, and title.

from typing import Any, Dict, List, Optional
from ebooklib import epub


def read_epub_metadata(file_path: str) -> Dict[str, Any]:
    """Read metadata from an EPUB file."""
    book = epub.read_epub(file_path, {"ignore_ncx": True})
    title = ""
    titles = book.get_metadata("DC", "title")
    if titles:
        title = titles[0][0]

    authors = []
    creators = book.get_metadata("DC", "creator")
    for creator in creators:
        authors.append(creator[0])

    subjects = []
    for subj in book.get_metadata("DC", "subject"):
        subjects.append(subj[0])

    return {
        "title": title,
        "authors": authors,
        "subjects": subjects,
    }


def write_epub_metadata(file_path: str,
                         title: Optional[str] = None,
                         author: Optional[str] = None,
                         subjects: Optional[List[str]] = None,
                         tags: Optional[List[str]] = None,
                         series: Optional[str] = None,
                         series_index: Optional[str] = None,
                         series_total: Optional[int] = None):
    """Write metadata into an EPUB file, merging with existing."""
    book = epub.read_epub(file_path, {"ignore_ncx": True})

    if title:
        book.set_title(title)

    if author:
        # Clear existing authors and set new one
        book.metadata.get("http://purl.org/dc/elements/1.1/", {}).pop("creator", None)
        if "http://purl.org/dc/elements/1.1/" in book.metadata:
            book.metadata["http://purl.org/dc/elements/1.1/"] = [
                item for item in book.metadata["http://purl.org/dc/elements/1.1/"]
                if item[1] != "creator"
            ]
        book.add_author(author)

    epub.write_epub(file_path, book)
```

Note: This is a minimal first pass — subjects, tags, and series will be added in subsequent tasks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/epub_writer.py tests/test_epub_writer.py && git commit -m "feat: add EPUB writer with title and author support"
```

### Task 12: Add dc:subject (genre) merging to EPUB writer

**Files:**
- Modify: `src/booklore_enrich/epub_writer.py`
- Modify: `tests/test_epub_writer.py`

- [ ] **Step 1: Write failing tests for subject merging**

Add to `tests/test_epub_writer.py`:

```python
def test_merge_subjects(tmp_path):
    """New subjects are merged with existing ones."""
    path = _make_test_epub(tmp_path / "test.epub")
    # Add initial subject
    book = epub.read_epub(str(path), {"ignore_ncx": True})
    book.add_metadata("DC", "subject", "existing-genre")
    epub.write_epub(str(path), book)
    # Write new subjects — should merge
    write_epub_metadata(str(path), subjects=["dark-romance", "contemporary"])
    meta = read_epub_metadata(str(path))
    assert "existing-genre" in meta["subjects"]
    assert "dark-romance" in meta["subjects"]
    assert "contemporary" in meta["subjects"]


def test_subjects_deduplicated(tmp_path):
    """Duplicate subjects are not written twice."""
    path = _make_test_epub(tmp_path / "test.epub")
    book = epub.read_epub(str(path), {"ignore_ncx": True})
    book.add_metadata("DC", "subject", "romance")
    epub.write_epub(str(path), book)
    write_epub_metadata(str(path), subjects=["romance", "fantasy"])
    meta = read_epub_metadata(str(path))
    assert meta["subjects"].count("romance") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -k "subject" -v`
Expected: FAIL

- [ ] **Step 3: Add subject merging to write_epub_metadata**

In `src/booklore_enrich/epub_writer.py`, add subject handling before the `epub.write_epub` call:

```python
    if subjects:
        # Read existing subjects
        existing = {s[0] for s in book.get_metadata("DC", "subject")}
        # Clear existing
        if "http://purl.org/dc/elements/1.1/" in book.metadata:
            book.metadata["http://purl.org/dc/elements/1.1/"] = [
                item for item in book.metadata["http://purl.org/dc/elements/1.1/"]
                if not (len(item) >= 2 and isinstance(item[1], dict) and item[1].get("name") == "subject")
                and not (isinstance(item, tuple) and len(item) >= 1 and item in book.get_metadata("DC", "subject"))
            ]
        # Merge and deduplicate
        all_subjects = list(dict.fromkeys(list(existing) + subjects))
        for subj in all_subjects:
            book.add_metadata("DC", "subject", subj)
```

Note: The exact ebooklib API for clearing metadata may need adjustment during implementation — the metadata structure varies. Test and iterate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/epub_writer.py tests/test_epub_writer.py && git commit -m "feat(epub): add dc:subject merging for genres"
```

### Task 13: Add booklore:tags and series metadata to EPUB writer

**Files:**
- Modify: `src/booklore_enrich/epub_writer.py`
- Modify: `tests/test_epub_writer.py`

- [ ] **Step 1: Write failing tests for booklore:tags and series**

Add to `tests/test_epub_writer.py`:

```python
import json
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def _read_opf_xml(epub_path):
    """Extract and parse the OPF XML from an EPUB for custom metadata checks."""
    with ZipFile(str(epub_path), "r") as zf:
        # Find the OPF file
        for name in zf.namelist():
            if name.endswith(".opf"):
                return ET.fromstring(zf.read(name))
    return None


def test_write_booklore_tags(tmp_path):
    """Tropes/steam/hero types are written as booklore:tags JSON."""
    path = _make_test_epub(tmp_path / "test.epub")
    write_epub_metadata(str(path), tags=["enemies-to-lovers", "steam:4", "hero:alpha-male"])
    opf = _read_opf_xml(path)
    # Find meta elements with property="booklore:tags" anywhere in the OPF
    # (ElementTree namespace handling varies, so iterate all elements)
    meta_tags = [el for el in opf.iter() if el.get("property") == "booklore:tags"]
    assert len(meta_tags) == 1, f"Expected exactly 1 booklore:tags element, found {len(meta_tags)}"
    tags_json = json.loads(meta_tags[0].text)
    assert "enemies-to-lovers" in tags_json
    assert "steam:4" in tags_json
    assert "hero:alpha-male" in tags_json


def test_write_series_metadata(tmp_path):
    """Series name and index are written in both Calibre and EPUB3 formats."""
    path = _make_test_epub(tmp_path / "test.epub")
    write_epub_metadata(str(path), series="Hot and Hammered", series_index="1", series_total=3)
    opf = _read_opf_xml(path)
    # Check for calibre:series
    all_meta = list(opf.iter())
    calibre_series = [el for el in all_meta if el.get("name") == "calibre:series"]
    assert len(calibre_series) >= 1
    assert calibre_series[0].get("content") == "Hot and Hammered"
    calibre_index = [el for el in all_meta if el.get("name") == "calibre:series_index"]
    assert len(calibre_index) >= 1
    assert calibre_index[0].get("content") == "1"


def test_merge_booklore_tags(tmp_path):
    """New tags merge with existing booklore:tags."""
    path = _make_test_epub(tmp_path / "test.epub")
    write_epub_metadata(str(path), tags=["slow-burn"])
    write_epub_metadata(str(path), tags=["enemies-to-lovers"])
    opf = _read_opf_xml(path)
    meta_tags = [el for el in opf.iter() if el.get("property") == "booklore:tags"]
    assert len(meta_tags) >= 1
    tags_json = json.loads(meta_tags[0].text)
    assert "slow-burn" in tags_json
    assert "enemies-to-lovers" in tags_json
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -k "booklore_tags or series" -v`
Expected: FAIL

- [ ] **Step 3: Implement booklore:tags and series writing**

This requires direct OPF XML manipulation since ebooklib doesn't support custom namespaces. Add to `src/booklore_enrich/epub_writer.py`:

```python
import json
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import shutil
import tempfile


def _inject_custom_metadata(file_path: str,
                              tags: Optional[List[str]] = None,
                              series: Optional[str] = None,
                              series_index: Optional[str] = None,
                              series_total: Optional[int] = None):
    """Inject custom metadata directly into the OPF XML.

    Handles booklore:tags, calibre:series, belongs-to-collection, and booklore:series_total.
    Called after ebooklib writes the standard metadata.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        temp_epub = f"{temp_dir}/modified.epub"
        opf_path = None
        opf_content = None

        with ZipFile(file_path, "r") as zin:
            for item in zin.namelist():
                if item.endswith(".opf"):
                    opf_path = item
                    opf_content = zin.read(item)
                    break

        if not opf_path or not opf_content:
            return

        root = ET.fromstring(opf_content)
        # Find metadata element
        ns_opf = "http://www.idpf.org/2007/opf"
        metadata = root.find(f"{{{ns_opf}}}metadata")
        if metadata is None:
            metadata = root.find("metadata")
        if metadata is None:
            return

        if tags:
            # Read existing booklore:tags
            existing_tags = []
            existing_el = None
            for el in metadata:
                if el.get("property") == "booklore:tags":
                    existing_el = el
                    try:
                        existing_tags = json.loads(el.text or "[]")
                    except json.JSONDecodeError:
                        existing_tags = []
                    break
            # Merge and deduplicate
            merged = list(dict.fromkeys(existing_tags + tags))
            if existing_el is not None:
                existing_el.text = json.dumps(merged)
            else:
                tag_el = ET.SubElement(metadata, "meta")
                tag_el.set("property", "booklore:tags")
                tag_el.text = json.dumps(merged)

        if series:
            # Calibre format
            _set_or_create_meta(metadata, "calibre:series", series, by_name=True)
            if series_index:
                _set_or_create_meta(metadata, "calibre:series_index", series_index, by_name=True)
            # EPUB3 format
            _set_or_create_property(metadata, "belongs-to-collection", series)
            if series_index:
                _set_or_create_property(metadata, "group-position", series_index)

        if series_total is not None:
            _set_or_create_property(metadata, "booklore:series_total", str(series_total))

        # Write modified OPF back into EPUB
        modified_opf = ET.tostring(root, encoding="unicode", xml_declaration=True)
        with ZipFile(file_path, "r") as zin, ZipFile(temp_epub, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == opf_path:
                    zout.writestr(item, modified_opf)
                else:
                    zout.writestr(item, zin.read(item.filename))
        shutil.move(temp_epub, file_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _set_or_create_meta(metadata, name: str, content: str, by_name: bool = False):
    """Set a <meta name="..." content="..."> element, creating if needed."""
    for el in metadata:
        if el.get("name") == name:
            el.set("content", content)
            return
    el = ET.SubElement(metadata, "meta")
    el.set("name", name)
    el.set("content", content)


def _set_or_create_property(metadata, prop: str, value: str):
    """Set a <meta property="...">value</meta> element, creating if needed."""
    for el in metadata:
        if el.get("property") == prop:
            el.text = value
            return
    el = ET.SubElement(metadata, "meta")
    el.set("property", prop)
    el.text = value
```

Then update `write_epub_metadata` to call `_inject_custom_metadata` after `epub.write_epub`:

```python
    epub.write_epub(file_path, book)

    # Inject custom metadata that ebooklib can't handle
    if tags or series or series_total is not None:
        _inject_custom_metadata(file_path, tags=tags, series=series,
                                 series_index=series_index, series_total=series_total)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_epub_writer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/epub_writer.py tests/test_epub_writer.py && git commit -m "feat(epub): add booklore:tags and series metadata writing"
```

---

## Chunk 5: Embed Command

### Task 14: Create the embed command

**Files:**
- Create: `src/booklore_enrich/commands/embed.py`
- Modify: `src/booklore_enrich/cli.py`
- Create: `tests/test_embed.py`

- [ ] **Step 1: Write failing test for embed CLI registration**

Add to `tests/test_cli.py`:

```python
def test_embed_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["embed", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "--force" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_cli.py::test_embed_command_exists -v`
Expected: FAIL

- [ ] **Step 3: Create embed command skeleton**

Create `src/booklore_enrich/commands/embed.py`:

```python
# ABOUTME: Embed command — writes scraped metadata into EPUB files.
# ABOUTME: Reads from SQLite cache, merges into EPUB OPF metadata.

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

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
                    logger.info("DRY RUN: %s | subjects=%s tags=%s", file_path, subgenre_subjects, trope_tags)
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
                logger.info("EMBEDDED: %s | subjects=%s tags=%s series=%s",
                            file_path, subgenre_subjects, trope_tags, book.get("series"))
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
    logger.info("SUMMARY: embedded=%d skipped=%d errors=%d", embedded, skipped, errors)
```

Register in `src/booklore_enrich/cli.py` using lazy import (matching existing pattern — all other commands use lazy imports inside the function body):

```python
@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
@click.option("--force", is_flag=True, help="Re-embed already processed books")
def embed(directory, dry_run, force):
    """Write cached metadata into EPUB files."""
    from booklore_enrich.commands.embed import run_embed
    run_embed(directory=directory, dry_run=dry_run, force=force)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add src/booklore_enrich/commands/embed.py src/booklore_enrich/cli.py tests/test_cli.py && git commit -m "feat: add embed command for writing metadata into EPUBs"
```

### Task 15: Integration test for embed command

**Files:**
- Create: `tests/test_embed.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_embed.py`:

```python
# ABOUTME: Integration tests for the embed command.
# ABOUTME: Tests the full flow from cached data to EPUB metadata writing.

import json
import os
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ebooklib import epub

from booklore_enrich.commands.embed import run_embed
from booklore_enrich.db import Database
from booklore_enrich.epub_writer import read_epub_metadata


def _make_test_epub(path):
    """Create a minimal valid EPUB at the given path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("Original Title")
    book.set_language("en")
    book.add_author("Bailey, Tessa")
    ch = epub.EpubHtml(title="Ch", file_name="ch1.xhtml", lang="en")
    ch.content = "<html><body><p>Test</p></body></html>"
    book.add_item(ch)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    epub.write_epub(str(path), book)


def _read_opf_xml(epub_path):
    with ZipFile(str(epub_path), "r") as zf:
        for name in zf.namelist():
            if name.endswith(".opf"):
                return ET.fromstring(zf.read(name))
    return None


def test_embed_full_flow(tmp_path, monkeypatch):
    """Full integration: cache data → embed → EPUB has metadata."""
    # Create test EPUB
    epub_path = tmp_path / "books" / "Tessa Bailey" / "Hot and Hammered" / "01 - Fix Her Up.epub"
    _make_test_epub(epub_path)

    # Set up database with scraped data
    db_path = tmp_path / "cache.db"
    db = Database(db_path)
    db.upsert_book_by_path(
        file_path=str(epub_path),
        title="Fix Her Up", author="Tessa Bailey",
        series="Hot and Hammered", series_index="01",
    )
    book = db.get_book_by_path(str(epub_path))
    db.mark_scraped(book["id"], source="romance.io", source_id="abc")
    # Add tags
    t1 = db.get_or_create_tag("enemies-to-lovers", "trope", "romance.io")
    t2 = db.get_or_create_tag("contemporary", "subgenre", "romance.io")
    t3 = db.get_or_create_tag("alpha-male", "hero-type", "romance.io")
    db.add_book_tag(book["id"], t1)
    db.add_book_tag(book["id"], t2)
    db.add_book_tag(book["id"], t3)
    db.set_steam_level(book["id"], 4, "Explicit open door")

    # Monkeypatch Database to use our test db
    monkeypatch.setattr("booklore_enrich.commands.embed.Database", lambda: db)

    # Run embed
    run_embed(directory=str(tmp_path / "books"), dry_run=False, force=False)

    # Verify EPUB metadata
    meta = read_epub_metadata(str(epub_path))
    assert meta["title"] == "Fix Her Up"
    assert "Tessa Bailey" in meta["authors"]
    assert "contemporary" in meta["subjects"]

    # Verify custom metadata
    opf = _read_opf_xml(epub_path)
    meta_tags = [el for el in opf.iter() if el.get("property") == "booklore:tags"]
    assert len(meta_tags) >= 1
    tags_json = json.loads(meta_tags[0].text)
    assert "enemies-to-lovers" in tags_json
    assert "steam:4" in tags_json
    assert "hero:alpha-male" in tags_json

    # Verify series
    calibre_series = [el for el in opf.iter() if el.get("name") == "calibre:series"]
    assert len(calibre_series) >= 1
    assert calibre_series[0].get("content") == "Hot and Hammered"

    # Verify marked as embedded
    updated = db.get_book_by_path(str(epub_path))
    assert updated["embedded_at"] is not None


def test_embed_dry_run_does_not_modify(tmp_path, monkeypatch):
    """Dry run shows changes but doesn't write to EPUB."""
    epub_path = tmp_path / "books" / "Author" / "Standalone" / "Book.epub"
    _make_test_epub(epub_path)
    db = Database(tmp_path / "cache.db")
    db.upsert_book_by_path(str(epub_path), "Book", "Author")
    book = db.get_book_by_path(str(epub_path))
    db.mark_scraped(book["id"], source="romance.io", source_id="x")
    db.add_book_tag(book["id"], db.get_or_create_tag("t", "trope", "romance.io"))
    monkeypatch.setattr("booklore_enrich.commands.embed.Database", lambda: db)

    run_embed(directory=str(tmp_path / "books"), dry_run=True)

    # EPUB should not have been modified — title should still be the original
    meta = read_epub_metadata(str(epub_path))
    assert meta["title"] == "Original Title"
    # Not marked as embedded
    updated = db.get_book_by_path(str(epub_path))
    assert updated["embedded_at"] is None
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest tests/test_embed.py -v`
Expected: All PASS (these test the full integration)

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add tests/test_embed.py && git commit -m "test: add integration tests for embed command"
```

### Task 16: Update CLAUDE.md and ABOUTME comments

**Files:**
- Modify: `/Users/nervous/Dev/booklore-enrich/CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with new commands**

Add `embed` and `--from-dir` to the Commands section:

```markdown
## Commands
- `uv run booklore-enrich export` — export library as CSV
- `uv run booklore-enrich scrape` — scrape trope metadata (from BookLore API)
- `uv run booklore-enrich scrape --from-dir /path` — scrape trope metadata (from filesystem)
- `uv run booklore-enrich tag` — push metadata to BookLore
- `uv run booklore-enrich discover` — find new books by trope
- `uv run booklore-enrich embed /path` — write cached metadata into EPUB files
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nervous/Dev/booklore-enrich && git add CLAUDE.md && git commit -m "docs: update CLAUDE.md with embed and --from-dir commands"
```

- [ ] **Step 3: Run full test suite one final time**

Run: `cd /Users/nervous/Dev/booklore-enrich && uv run pytest -v`
Expected: All PASS

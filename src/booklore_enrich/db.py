# ABOUTME: SQLite database cache for scraped book metadata.
# ABOUTME: Stores books, trope tags, steam levels, and discovery results.

import hashlib
import sqlite3
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB_PATH = Path.home() / ".config" / "booklore-enrich" / "cache.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booklore_id INTEGER UNIQUE,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    isbn TEXT,
    romance_io_id TEXT,
    booknaut_id TEXT,
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT UNIQUE,
    series TEXT,
    series_index TEXT,
    series_total INTEGER,
    embedded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS book_tags (
    book_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE IF NOT EXISTS book_steam (
    book_id INTEGER PRIMARY KEY,
    level INTEGER NOT NULL,
    label TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT,
    source_url TEXT,
    genre TEXT,
    steam_level INTEGER,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dismissed BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS discovery_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    trope TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    UNIQUE(source, trope)
);

CREATE TABLE IF NOT EXISTS tag_cache (
    booklore_id INTEGER PRIMARY KEY,
    tag_hash TEXT NOT NULL,
    tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def compute_tag_hash(tags: List[str]) -> str:
    """Compute a stable hash for a list of tags, independent of input order."""
    canonical = "|".join(sorted(set(tags)))
    return hashlib.sha256(canonical.encode()).hexdigest()


class Database:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH, check_same_thread: bool = True):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate()

    def _create_tables(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def _migrate(self):
        """Add columns that may be missing from older databases."""
        existing = {row[1] for row in self.execute("PRAGMA table_info(books)").fetchall()}
        # Note: SQLite does not allow ADD COLUMN with UNIQUE constraint.
        # file_path uniqueness is enforced only on fresh databases via the schema.
        migrations = [
            ("file_path", "TEXT"),
            ("series", "TEXT"),
            ("series_index", "TEXT"),
            ("series_total", "INTEGER"),
            ("embedded_at", "TIMESTAMP"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing:
                self.execute(f"ALTER TABLE books ADD COLUMN {col_name} {col_type}")
        self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def upsert_book(self, booklore_id: int, title: str, author: str, isbn: str = None):
        self.conn.execute(
            """INSERT INTO books (booklore_id, title, author, isbn)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(booklore_id) DO UPDATE SET
                   title=excluded.title, author=excluded.author, isbn=excluded.isbn""",
            (booklore_id, title, author, isbn),
        )
        self.conn.commit()

    def get_book_by_booklore_id(self, booklore_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM books WHERE booklore_id = ?", (booklore_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_or_create_tag(self, name: str, category: str, source: str) -> int:
        row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cursor = self.conn.execute(
            "INSERT INTO tags (name, category, source) VALUES (?, ?, ?)",
            (name, category, source),
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_book_tag(self, book_id: int, tag_id: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )
        self.conn.commit()

    def get_book_tags(self, book_id: int) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT t.* FROM tags t
               JOIN book_tags bt ON bt.tag_id = t.id
               WHERE bt.book_id = ?""",
            (book_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_steam_level(self, book_id: int, level: int, label: str = None):
        self.conn.execute(
            """INSERT INTO book_steam (book_id, level, label) VALUES (?, ?, ?)
               ON CONFLICT(book_id) DO UPDATE SET level=excluded.level, label=excluded.label""",
            (book_id, level, label),
        )
        self.conn.commit()

    def get_steam_level(self, book_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM book_steam WHERE book_id = ?", (book_id,)
        ).fetchone()
        return dict(row) if row else None

    def mark_scraped(self, book_id: int, source: str, source_id: str):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        col = "romance_io_id" if source == "romance.io" else "booknaut_id"
        self.conn.execute(
            f"UPDATE books SET {col} = ?, last_scraped_at = ? WHERE id = ?",
            (source_id, now, book_id),
        )
        self.conn.commit()

    def get_unscraped_books(self, source: str) -> List[Dict[str, Any]]:
        col = "romance_io_id" if source == "romance.io" else "booknaut_id"
        rows = self.conn.execute(
            f"SELECT * FROM books WHERE {col} IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_discovery(self, title: str, author: str, source: str,
                      source_id: str = None, source_url: str = None,
                      genre: str = None, steam_level: int = None):
        self.conn.execute(
            """INSERT OR IGNORE INTO discoveries
               (title, author, source, source_id, source_url, genre, steam_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, author, source, source_id, source_url, genre, steam_level),
        )
        self.conn.commit()

    def get_discoveries(self, source: str = None, include_dismissed: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM discoveries WHERE 1=1"
        params = []
        if source:
            sql += " AND source = ?"
            params.append(source)
        if not include_dismissed:
            sql += " AND dismissed = 0"
        sql += " ORDER BY discovered_at DESC"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def dismiss_discovery(self, discovery_id: int):
        self.conn.execute("UPDATE discoveries SET dismissed = 1 WHERE id = ?", (discovery_id,))
        self.conn.commit()

    def get_tag_hash(self, booklore_id: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT tag_hash FROM tag_cache WHERE booklore_id = ?", (booklore_id,)
        ).fetchone()
        return row["tag_hash"] if row else None

    def set_tag_hash(self, booklore_id: int, tag_hash: str) -> None:
        self.conn.execute(
            """INSERT INTO tag_cache (booklore_id, tag_hash, tagged_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(booklore_id) DO UPDATE SET
                   tag_hash=excluded.tag_hash, tagged_at=excluded.tagged_at""",
            (booklore_id, tag_hash),
        )
        self.conn.commit()

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

        Returns books with their tags. Skips already-embedded books unless force=True.
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
            if not path_prefix.endswith("/"):
                path_prefix += "/"
            query += " AND b.file_path LIKE ?"
            params.append(path_prefix + "%")
        rows = self.execute(query, params).fetchall()
        results = []
        for row in rows:
            book = dict(row)
            book["tags"] = self.get_book_tags(book["id"])
            results.append(book)
        return results

    def get_enriched_books(self) -> List[Dict[str, Any]]:
        """Get all books that have been enriched with tags or steam levels."""
        books = self.conn.execute(
            """SELECT b.* FROM books b
               WHERE EXISTS (SELECT 1 FROM book_tags bt WHERE bt.book_id = b.id)
                  OR EXISTS (SELECT 1 FROM book_steam bs WHERE bs.book_id = b.id)"""
        ).fetchall()
        result = []
        for book in books:
            book_dict = dict(book)
            book_dict["tags"] = self.get_book_tags(book["id"])
            steam = self.get_steam_level(book["id"])
            book_dict["steam_level"] = steam["level"] if steam else None
            book_dict["steam_label"] = steam["label"] if steam else None
            result.append(book_dict)
        return result

    def close(self):
        self.conn.close()

# booklore-enrich Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that enriches a BookLore library with trope/heat metadata from romance.io and thebooknaut.com, and discovers new books by genre and trope.

**Architecture:** Modular CLI with four commands (export, scrape, tag, discover). BookLore API client for reading/writing library data. Playwright browser automation for scraping Cloudflare-protected sites. SQLite cache to avoid re-scraping. Config via TOML file.

**Tech Stack:** Python 3.12+, uv, click, httpx, playwright, rich, sqlite3, pytest

**Design doc:** `docs/plans/2026-02-20-booklore-enrich-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/booklore_enrich/__init__.py`
- Create: `src/booklore_enrich/cli.py`
- Create: `tests/__init__.py`
- Create: `tests/test_cli.py`
- Create: `CLAUDE.md`

**Step 1: Initialize project with uv**

```bash
cd /Users/nervous/Dev/booklore-enrich
uv init --name booklore-enrich --package --python 3.12
```

**Step 2: Configure pyproject.toml**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "booklore-enrich"
version = "0.1.0"
description = "Enrich BookLore library with metadata from romance.io and thebooknaut.com"
requires-python = ">=3.12"
dependencies = [
    "click>=8.2.0",
    "httpx>=0.28.0",
    "rich>=14.0.0",
    "tomli>=2.0.0;python_version<'3.11'",
    "tomli-w>=1.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.4.0",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.25.0",
]
scraping = [
    "playwright>=1.50.0",
]

[project.scripts]
booklore-enrich = "booklore_enrich.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/booklore_enrich"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 3: Install dependencies**

```bash
uv add click httpx rich tomli-w
uv add --dev pytest pytest-cov pytest-asyncio
```

**Step 4: Create minimal CLI entry point**

Write `src/booklore_enrich/__init__.py`:
```python
# ABOUTME: Root package for booklore-enrich CLI tool.
# ABOUTME: Enriches BookLore libraries with metadata from romance.io and thebooknaut.com.
```

Write `src/booklore_enrich/cli.py`:
```python
# ABOUTME: Click CLI entry point for booklore-enrich.
# ABOUTME: Defines the main CLI group and registers subcommands.

import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Enrich your BookLore library with metadata from romance.io and thebooknaut.com."""
    pass


@cli.command()
def export():
    """Export BookLore library as Goodreads-compatible CSV."""
    click.echo("Export not yet implemented.")


@cli.command()
def scrape():
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    click.echo("Scrape not yet implemented.")


@cli.command()
def tag():
    """Push enriched metadata as tags and shelves into BookLore."""
    click.echo("Tag not yet implemented.")


@cli.command()
def discover():
    """Discover new books by trope from romance.io and thebooknaut.com."""
    click.echo("Discover not yet implemented.")
```

**Step 5: Write CLI smoke test**

Write `tests/__init__.py` (empty file).

Write `tests/test_cli.py`:
```python
# ABOUTME: Tests for the CLI entry point and command registration.
# ABOUTME: Verifies all commands are registered and --help works.

from click.testing import CliRunner
from booklore_enrich.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Enrich your BookLore library" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_export_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0
    assert "Export BookLore library" in result.output


def test_scrape_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["scrape", "--help"])
    assert result.exit_code == 0


def test_tag_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert result.exit_code == 0


def test_discover_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["discover", "--help"])
    assert result.exit_code == 0
```

**Step 6: Run tests**

```bash
cd /Users/nervous/Dev/booklore-enrich
uv run pytest tests/test_cli.py -v
```
Expected: All 6 tests PASS.

**Step 7: Write CLAUDE.md**

Write `CLAUDE.md`:
```markdown
# booklore-enrich

## What is this?
CLI tool that enriches a BookLore digital library with metadata from romance.io (romance) and thebooknaut.com (sci-fi, fantasy). Also discovers new books by trope.

## Commands
- `uv run booklore-enrich export` — export library as CSV
- `uv run booklore-enrich scrape` — scrape trope metadata
- `uv run booklore-enrich tag` — push metadata to BookLore
- `uv run booklore-enrich discover` — find new books by trope

## Development
- Python 3.12+, managed with uv
- Tests: `uv run pytest`
- Lint: `uv run ruff check src/ tests/`

## Architecture
See `docs/plans/2026-02-20-booklore-enrich-design.md`

## Key Dependencies
- click (CLI), httpx (HTTP), playwright (scraping), rich (output), sqlite3 (cache)
```

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: scaffold booklore-enrich project with CLI skeleton"
```

---

### Task 2: Configuration Management

**Files:**
- Create: `src/booklore_enrich/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing config tests**

Write `tests/test_config.py`:
```python
# ABOUTME: Tests for configuration loading, defaults, and validation.
# ABOUTME: Covers TOML config reading, default values, and config creation.

import os
import tempfile
from pathlib import Path

from booklore_enrich.config import Config, load_config, save_config, DEFAULT_CONFIG


def test_default_config_has_required_sections():
    config = Config()
    assert config.booklore_url == "http://192.168.7.21:6060"
    assert config.booklore_username == ""
    assert config.rate_limit_seconds == 3
    assert config.headless is True


def test_load_config_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[booklore]
url = "http://10.0.0.1:9090"
username = "testuser"

[scraping]
rate_limit_seconds = 5
headless = false

[discovery]
romance_tropes = ["slow-burn"]
scifi_tropes = ["cyberpunk"]
fantasy_tropes = ["dark-fantasy"]
''')
    config = load_config(config_file)
    assert config.booklore_url == "http://10.0.0.1:9090"
    assert config.booklore_username == "testuser"
    assert config.rate_limit_seconds == 5
    assert config.headless is False
    assert config.romance_tropes == ["slow-burn"]
    assert config.scifi_tropes == ["cyberpunk"]
    assert config.fantasy_tropes == ["dark-fantasy"]


def test_load_config_missing_file_returns_defaults(tmp_path):
    config = load_config(tmp_path / "nonexistent.toml")
    assert config.booklore_url == "http://192.168.7.21:6060"


def test_save_config_creates_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config = Config(booklore_url="http://mynas:6060", booklore_username="dylan")
    save_config(config, config_file)
    assert config_file.exists()
    loaded = load_config(config_file)
    assert loaded.booklore_url == "http://mynas:6060"
    assert loaded.booklore_username == "dylan"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement config module**

Write `src/booklore_enrich/config.py`:
```python
# ABOUTME: Configuration management for booklore-enrich.
# ABOUTME: Loads/saves TOML config files with sensible defaults.

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomli_w


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "booklore-enrich"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "booklore": {
        "url": "http://192.168.7.21:6060",
        "username": "",
    },
    "scraping": {
        "rate_limit_seconds": 3,
        "max_concurrent": 1,
        "headless": True,
    },
    "discovery": {
        "romance_tropes": ["enemies-to-lovers", "slow-burn", "forced-proximity"],
        "scifi_tropes": ["space-opera", "first-contact", "cyberpunk"],
        "fantasy_tropes": ["epic-fantasy", "urban-fantasy", "dark-fantasy"],
    },
}


@dataclass
class Config:
    booklore_url: str = "http://192.168.7.21:6060"
    booklore_username: str = ""
    rate_limit_seconds: int = 3
    max_concurrent: int = 1
    headless: bool = True
    romance_tropes: List[str] = field(
        default_factory=lambda: ["enemies-to-lovers", "slow-burn", "forced-proximity"]
    )
    scifi_tropes: List[str] = field(
        default_factory=lambda: ["space-opera", "first-contact", "cyberpunk"]
    )
    fantasy_tropes: List[str] = field(
        default_factory=lambda: ["epic-fantasy", "urban-fantasy", "dark-fantasy"]
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load config from TOML file, falling back to defaults for missing values."""
    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    booklore = data.get("booklore", {})
    scraping = data.get("scraping", {})
    discovery = data.get("discovery", {})

    return Config(
        booklore_url=booklore.get("url", Config.booklore_url),
        booklore_username=booklore.get("username", Config.booklore_username),
        rate_limit_seconds=scraping.get("rate_limit_seconds", Config.rate_limit_seconds),
        max_concurrent=scraping.get("max_concurrent", Config.max_concurrent),
        headless=scraping.get("headless", Config.headless),
        romance_tropes=discovery.get("romance_tropes", Config().romance_tropes),
        scifi_tropes=discovery.get("scifi_tropes", Config().scifi_tropes),
        fantasy_tropes=discovery.get("fantasy_tropes", Config().fantasy_tropes),
    )


def save_config(config: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save config to TOML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "booklore": {
            "url": config.booklore_url,
            "username": config.booklore_username,
        },
        "scraping": {
            "rate_limit_seconds": config.rate_limit_seconds,
            "max_concurrent": config.max_concurrent,
            "headless": config.headless,
        },
        "discovery": {
            "romance_tropes": config.romance_tropes,
            "scifi_tropes": config.scifi_tropes,
            "fantasy_tropes": config.fantasy_tropes,
        },
    }
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_config.py -v
```
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/booklore_enrich/config.py tests/test_config.py
git commit -m "feat: add configuration management with TOML support"
```

---

### Task 3: SQLite Database Layer

**Files:**
- Create: `src/booklore_enrich/db.py`
- Create: `tests/test_db.py`

**Step 1: Write failing database tests**

Write `tests/test_db.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement database module**

Write `src/booklore_enrich/db.py`:
```python
# ABOUTME: SQLite database cache for scraped book metadata.
# ABOUTME: Stores books, trope tags, steam levels, and discovery results.

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
"""


class Database:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript(SCHEMA)
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
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_db.py -v
```
Expected: All 10 tests PASS.

**Step 5: Commit**

```bash
git add src/booklore_enrich/db.py tests/test_db.py
git commit -m "feat: add SQLite database cache layer"
```

---

### Task 4: BookLore API Client

**Files:**
- Create: `src/booklore_enrich/booklore_client.py`
- Create: `tests/test_booklore_client.py`

**Step 1: Write failing client tests**

Write `tests/test_booklore_client.py`:
```python
# ABOUTME: Tests for the BookLore REST API client.
# ABOUTME: Uses httpx mock transport to test without a real BookLore server.

import json
import httpx
import pytest
from booklore_enrich.booklore_client import BookLoreClient


def make_mock_transport(responses: dict):
    """Create a mock transport that returns canned responses by URL path."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            return httpx.Response(200, json=responses[path])
        return httpx.Response(404, json={"error": "not found"})
    return httpx.MockTransport(handler)


def test_login_stores_token():
    transport = make_mock_transport({
        "/api/v1/auth/login": {
            "status": 200,
            "data": {"accessToken": "test-jwt-token", "refreshToken": "test-refresh"}
        }
    })
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    assert client._access_token == "test-jwt-token"


def test_get_books():
    transport = make_mock_transport({
        "/api/v1/auth/login": {
            "status": 200,
            "data": {"accessToken": "tok", "refreshToken": "ref"}
        },
        "/api/v1/books": {
            "status": 200,
            "data": [
                {"id": 1, "title": "Book One", "authors": [{"name": "Author A"}], "isbn": "111"},
                {"id": 2, "title": "Book Two", "authors": [{"name": "Author B"}], "isbn": "222"},
            ]
        }
    })
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    books = client.get_books()
    assert len(books) == 2
    assert books[0]["title"] == "Book One"


def test_get_shelves():
    transport = make_mock_transport({
        "/api/v1/auth/login": {
            "status": 200,
            "data": {"accessToken": "tok", "refreshToken": "ref"}
        },
        "/api/v1/shelves": {
            "status": 200,
            "data": [
                {"id": 1, "name": "Currently Reading"},
                {"id": 2, "name": "Favorites"},
            ]
        }
    })
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    shelves = client.get_shelves()
    assert len(shelves) == 2


def test_auth_header_included():
    """Verify that authenticated requests include the Bearer token."""
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={
                "status": 200,
                "data": {"accessToken": "my-token", "refreshToken": "ref"}
            })
        received_headers.update(dict(request.headers))
        return httpx.Response(200, json={"status": 200, "data": []})

    transport = httpx.MockTransport(handler)
    client = BookLoreClient("http://test:6060", transport=transport)
    client.login("user", "pass")
    client.get_books()
    assert "authorization" in received_headers
    assert received_headers["authorization"] == "Bearer my-token"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_booklore_client.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement BookLore client**

Write `src/booklore_enrich/booklore_client.py`:
```python
# ABOUTME: HTTP client for the BookLore REST API.
# ABOUTME: Handles JWT authentication and provides typed access to books, shelves, and metadata.

from typing import Any, Dict, List, Optional

import httpx


class BookLoreError(Exception):
    """Raised when a BookLore API call fails."""
    pass


class BookLoreClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport = None):
        self._base_url = base_url.rstrip("/")
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        kwargs = {"base_url": self._base_url, "timeout": 30.0}
        if transport:
            kwargs["transport"] = transport
        self._client = httpx.Client(**kwargs)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self._client.request(method, path, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise BookLoreError(f"API error {response.status_code}: {response.text}")
        data = response.json()
        return data.get("data", data)

    def login(self, username: str, password: str):
        """Authenticate and store JWT tokens."""
        result = self._request("POST", "/api/v1/auth/login", json={
            "username": username,
            "password": password,
        })
        self._access_token = result["accessToken"]
        self._refresh_token = result["refreshToken"]

    def get_books(self, with_description: bool = False) -> List[Dict[str, Any]]:
        """List all books in the library."""
        params = {}
        if with_description:
            params["withDescription"] = "true"
        return self._request("GET", "/api/v1/books", params=params)

    def get_book(self, book_id: int, with_description: bool = False) -> Dict[str, Any]:
        """Get a single book by ID."""
        params = {}
        if with_description:
            params["withDescription"] = "true"
        return self._request("GET", f"/api/v1/books/{book_id}", params=params)

    def get_shelves(self) -> List[Dict[str, Any]]:
        """List all shelves."""
        return self._request("GET", "/api/v1/shelves")

    def create_shelf(self, name: str) -> Dict[str, Any]:
        """Create a new shelf."""
        return self._request("POST", "/api/v1/shelves", json={"name": name})

    def assign_books_to_shelf(self, shelf_id: int, book_ids: List[int]):
        """Assign books to a shelf."""
        return self._request("POST", "/api/v1/books/shelves", json={
            "shelfId": shelf_id,
            "bookIds": book_ids,
        })

    def update_book_metadata(self, book_id: int, metadata: Dict[str, Any],
                             merge_categories: bool = True):
        """Update a book's metadata."""
        params = {"mergeCategories": str(merge_categories).lower()}
        return self._request("PUT", f"/api/v1/books/{book_id}/metadata",
                             json=metadata, params=params)

    def get_libraries(self) -> List[Dict[str, Any]]:
        """List all libraries."""
        return self._request("GET", "/api/v1/libraries")

    def close(self):
        self._client.close()
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_booklore_client.py -v
```
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/booklore_enrich/booklore_client.py tests/test_booklore_client.py
git commit -m "feat: add BookLore API client with JWT auth"
```

---

### Task 5: Export Command

**Files:**
- Create: `src/booklore_enrich/commands/__init__.py`
- Create: `src/booklore_enrich/commands/export.py`
- Create: `tests/test_export.py`
- Modify: `src/booklore_enrich/cli.py` — wire up real export command

**Step 1: Write failing export tests**

Write `tests/test_export.py`:
```python
# ABOUTME: Tests for the export command that generates Goodreads-compatible CSV.
# ABOUTME: Verifies CSV format, field mapping, and handling of missing data.

import csv
import io
from booklore_enrich.commands.export import books_to_goodreads_csv


def test_books_to_csv_basic():
    books = [
        {
            "id": 1, "title": "Test Book", "isbn": "9781234567890",
            "authors": [{"name": "Test Author"}],
            "publisher": "Test Publisher", "publishedDate": "2024",
            "description": "A test book.",
        },
    ]
    output = books_to_goodreads_csv(books)
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["Title"] == "Test Book"
    assert rows[0]["Author"] == "Test Author"
    assert rows[0]["ISBN13"] == "9781234567890"


def test_books_to_csv_multiple_authors():
    books = [
        {
            "id": 1, "title": "Collab Book",
            "authors": [{"name": "Author A"}, {"name": "Author B"}],
        },
    ]
    output = books_to_goodreads_csv(books)
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    assert rows[0]["Author"] == "Author A"
    assert rows[0]["Additional Authors"] == "Author B"


def test_books_to_csv_missing_fields():
    books = [{"id": 1, "title": "Minimal Book", "authors": []}]
    output = books_to_goodreads_csv(books)
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    assert rows[0]["Title"] == "Minimal Book"
    assert rows[0]["Author"] == ""


def test_books_to_csv_header_matches_goodreads():
    books = [{"id": 1, "title": "X", "authors": [{"name": "Y"}]}]
    output = books_to_goodreads_csv(books)
    reader = csv.DictReader(io.StringIO(output))
    expected_fields = ["Title", "Author", "Additional Authors", "ISBN", "ISBN13",
                       "Publisher", "Year Published", "Number of Pages", "Bookshelves"]
    for field in expected_fields:
        assert field in reader.fieldnames
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_export.py -v
```
Expected: FAIL.

**Step 3: Implement export module**

Write `src/booklore_enrich/commands/__init__.py` (empty file with ABOUTME):
```python
# ABOUTME: CLI command implementations for booklore-enrich.
# ABOUTME: Each module implements one CLI command (export, scrape, tag, discover).
```

Write `src/booklore_enrich/commands/export.py`:
```python
# ABOUTME: Export command that generates a Goodreads-compatible CSV from BookLore.
# ABOUTME: Used for importing your library into romance.io and thebooknaut.com.

import csv
import io
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.progress import Progress

from booklore_enrich.booklore_client import BookLoreClient
from booklore_enrich.config import load_config

console = Console()

GOODREADS_FIELDS = [
    "Title", "Author", "Additional Authors", "ISBN", "ISBN13",
    "Publisher", "Year Published", "Number of Pages", "Bookshelves",
]


def books_to_goodreads_csv(books: List[Dict[str, Any]]) -> str:
    """Convert BookLore book list to Goodreads-compatible CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=GOODREADS_FIELDS)
    writer.writeheader()

    for book in books:
        authors = book.get("authors", [])
        primary_author = authors[0]["name"] if authors else ""
        additional = ", ".join(a["name"] for a in authors[1:]) if len(authors) > 1 else ""

        writer.writerow({
            "Title": book.get("title", ""),
            "Author": primary_author,
            "Additional Authors": additional,
            "ISBN": book.get("isbn10", book.get("isbn", "")),
            "ISBN13": book.get("isbn13", book.get("isbn", "")),
            "Publisher": book.get("publisher", ""),
            "Year Published": book.get("publishedDate", ""),
            "Number of Pages": book.get("pageCount", ""),
            "Bookshelves": "",
        })

    return output.getvalue()


def run_export(output_path: str):
    """Execute the export command."""
    config = load_config()

    if not config.booklore_username:
        console.print("[red]No BookLore username configured. Run with --username or set in config.[/red]")
        return

    password = click.prompt("BookLore password", hide_input=True)

    client = BookLoreClient(config.booklore_url)
    try:
        console.print(f"Connecting to BookLore at {config.booklore_url}...")
        client.login(config.booklore_username, password)

        console.print("Fetching books...")
        books = client.get_books(with_description=True)
        console.print(f"Found {len(books)} books.")

        csv_data = books_to_goodreads_csv(books)
        with open(output_path, "w") as f:
            f.write(csv_data)

        console.print(f"[green]Exported {len(books)} books to {output_path}[/green]")
        console.print("\nNext steps:")
        console.print("  1. Go to https://www.romance.io/import")
        console.print("  2. Upload the CSV file")
        console.print("  3. Wait for the confirmation email")
    finally:
        client.close()
```

**Step 4: Wire up export command in CLI**

Modify `src/booklore_enrich/cli.py` — replace the `export` stub:
```python
# ABOUTME: Click CLI entry point for booklore-enrich.
# ABOUTME: Defines the main CLI group and registers subcommands.

import click

from booklore_enrich.config import load_config, save_config, Config


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Enrich your BookLore library with metadata from romance.io and thebooknaut.com."""
    pass


@cli.command()
@click.option("--output", "-o", default="booklore-export.csv", help="Output CSV file path.")
@click.option("--username", "-u", help="BookLore username (overrides config).")
def export(output, username):
    """Export BookLore library as Goodreads-compatible CSV."""
    from booklore_enrich.commands.export import run_export
    if username:
        config = load_config()
        config.booklore_username = username
        save_config(config)
    run_export(output)


@cli.command()
def scrape():
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    click.echo("Scrape not yet implemented.")


@cli.command()
def tag():
    """Push enriched metadata as tags and shelves into BookLore."""
    click.echo("Tag not yet implemented.")


@cli.command()
def discover():
    """Discover new books by trope from romance.io and thebooknaut.com."""
    click.echo("Discover not yet implemented.")
```

**Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/booklore_enrich/commands/ tests/test_export.py src/booklore_enrich/cli.py
git commit -m "feat: add export command for Goodreads-compatible CSV"
```

---

### Task 6: Scraper Base (Playwright)

**Files:**
- Create: `src/booklore_enrich/scraper/__init__.py`
- Create: `src/booklore_enrich/scraper/base.py`
- Create: `tests/test_scraper_base.py`

**Note:** Playwright tests need `uv add --optional scraping playwright` and `uv run playwright install chromium`. These tests verify the scraper's HTML parsing logic using static HTML strings, not live browser sessions.

**Step 1: Install playwright dependency**

```bash
uv add --optional scraping playwright
uv run playwright install chromium
```

**Step 2: Write failing scraper base tests**

Write `tests/test_scraper_base.py`:
```python
# ABOUTME: Tests for the base scraper HTML parsing utilities.
# ABOUTME: Tests parse logic against static HTML without needing a live browser.

from booklore_enrich.scraper.base import parse_book_page, parse_search_results, slugify


def test_slugify_basic():
    assert slugify("The Great Gatsby", "F. Scott Fitzgerald") == "the-great-gatsby-f-scott-fitzgerald"


def test_slugify_special_chars():
    assert slugify("It's a Test!", "O'Brien") == "its-a-test-obrien"


def test_parse_search_results_extracts_book_links():
    html = '''
    <div class="book-list">
        <a href="/books/abc123def456789012345678/cool-book-author-name">Cool Book</a>
        <a href="/books/def456abc123789012345678/another-book-other-author">Another Book</a>
    </div>
    '''
    results = parse_search_results(html)
    assert len(results) == 2
    assert results[0]["source_id"] == "abc123def456789012345678"
    assert results[0]["slug"] == "cool-book-author-name"


def test_parse_search_results_empty_html():
    results = parse_search_results("<div>No books here</div>")
    assert results == []


def test_parse_book_page_extracts_tags():
    html = '''
    <div class="topics">
        <a href="/topics/best/enemies-to-lovers/1">enemies-to-lovers</a>
        <a href="/topics/best/slow-burn/1">slow-burn</a>
    </div>
    '''
    data = parse_book_page(html)
    assert "enemies-to-lovers" in data["tags"]
    assert "slow-burn" in data["tags"]
```

**Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_scraper_base.py -v
```
Expected: FAIL.

**Step 4: Implement scraper base**

Write `src/booklore_enrich/scraper/__init__.py`:
```python
# ABOUTME: Browser-based scraper package for romance.io and thebooknaut.com.
# ABOUTME: Uses Playwright for Cloudflare bypass and JavaScript rendering.
```

Write `src/booklore_enrich/scraper/base.py`:
```python
# ABOUTME: Shared scraping utilities and HTML parsing functions.
# ABOUTME: Provides Playwright browser management and page content extraction.

import re
import time
from typing import Any, Dict, List, Optional


def slugify(title: str, author: str) -> str:
    """Create a URL slug from title and author, matching romance.io/booknaut format."""
    text = f"{title} {author}".lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


def parse_search_results(html: str) -> List[Dict[str, str]]:
    """Extract book links from a search results or topic page."""
    # Match links like /books/{24-char-hex-id}/{slug}
    pattern = r'href="/books/([a-f0-9]{24})/([^"]+)"'
    matches = re.findall(pattern, html)
    results = []
    seen = set()
    for source_id, slug in matches:
        if source_id not in seen:
            seen.add(source_id)
            results.append({"source_id": source_id, "slug": slug})
    return results


def parse_book_page(html: str) -> Dict[str, Any]:
    """Extract metadata from a book detail page."""
    data: Dict[str, Any] = {
        "tags": [],
        "steam_level": None,
        "steam_label": None,
        "title": None,
        "author": None,
        "rating": None,
    }

    # Extract tags from topic links
    tag_pattern = r'href="/topics/(?:best|most)/([^/"]+)/\d+"'
    tag_matches = re.findall(tag_pattern, html)
    for tag_match in tag_matches:
        # Split comma-separated tropes in URL
        for tag in tag_match.split(","):
            tag = tag.strip()
            if tag and tag not in data["tags"]:
                data["tags"].append(tag)

    # Extract steam level from steam rating indicators
    steam_patterns = [
        (5, r'(?:Explicit and plentiful|steam[_-]?level[_-]?5|spice[_-]?5)'),
        (4, r'(?:Explicit open door|steam[_-]?level[_-]?4|spice[_-]?4)'),
        (3, r'(?:Open door|steam[_-]?level[_-]?3|spice[_-]?3)'),
        (2, r'(?:Behind closed doors|steam[_-]?level[_-]?2|spice[_-]?2)'),
        (1, r'(?:Glimpses and kisses|steam[_-]?level[_-]?1|spice[_-]?1)'),
    ]
    steam_labels = {
        1: "Glimpses and kisses",
        2: "Behind closed doors",
        3: "Open door",
        4: "Explicit open door",
        5: "Explicit and plentiful",
    }
    for level, pattern in steam_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            data["steam_level"] = level
            data["steam_label"] = steam_labels[level]
            break

    return data


class BrowserScraper:
    """Manages a Playwright browser session for scraping."""

    def __init__(self, headless: bool = True, rate_limit: float = 3.0):
        self.headless = headless
        self.rate_limit = rate_limit
        self._browser = None
        self._context = None
        self._page = None
        self._last_request_time = 0.0

    async def start(self):
        """Launch the browser."""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self._page = await self._context.new_page()

    async def stop(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _rate_limit_wait(self):
        """Wait to respect rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def fetch_page(self, url: str, wait_selector: str = None) -> str:
        """Navigate to a URL and return the page HTML."""
        await self._rate_limit_wait()
        await self._page.goto(url, wait_until="networkidle")
        if wait_selector:
            try:
                await self._page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass
        return await self._page.content()

    async def search_book(self, base_url: str, title: str, author: str) -> Optional[Dict[str, str]]:
        """Search for a book on romance.io/booknaut and return the best match."""
        slug = slugify(title, author)
        # Try the similar-books search first
        search_url = f"{base_url}/books/similar"
        html = await self.fetch_page(search_url)

        # Type in the search box
        try:
            await self._page.fill('input[type="text"]', f"{title} {author}")
            await self._page.keyboard.press("Enter")
            await self._page.wait_for_timeout(3000)
            html = await self._page.content()
        except Exception:
            pass

        results = parse_search_results(html)
        if results:
            return results[0]
        return None

    async def scrape_book(self, base_url: str, source_id: str, slug: str) -> Dict[str, Any]:
        """Scrape full metadata from a book page."""
        url = f"{base_url}/books/{source_id}/{slug}"
        html = await self.fetch_page(url)
        return parse_book_page(html)
```

**Step 5: Run tests**

```bash
uv run pytest tests/test_scraper_base.py -v
```
Expected: All 5 tests PASS.

**Step 6: Commit**

```bash
git add src/booklore_enrich/scraper/ tests/test_scraper_base.py
git commit -m "feat: add base scraper with HTML parsing and Playwright browser management"
```

---

### Task 7: Scrape Command

**Files:**
- Create: `src/booklore_enrich/commands/scrape.py`
- Create: `tests/test_scrape_command.py`
- Modify: `src/booklore_enrich/cli.py` — wire up scrape command

**Step 1: Write failing scrape command tests**

Write `tests/test_scrape_command.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_scrape_command.py -v
```
Expected: FAIL.

**Step 3: Implement scrape command**

Write `src/booklore_enrich/commands/scrape.py`:
```python
# ABOUTME: Scrape command that fetches trope/heat metadata from romance.io and booknaut.
# ABOUTME: Orchestrates browser scraping with rate limiting and SQLite caching.

import asyncio
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.progress import Progress

from booklore_enrich.booklore_client import BookLoreClient
from booklore_enrich.config import load_config
from booklore_enrich.db import Database

console = Console()

SOURCES = {
    "romance.io": "https://www.romance.io",
    "booknaut": "https://www.thebooknaut.com",
}


def sync_books_to_cache(db: Database, booklore_books: List[Dict[str, Any]]) -> int:
    """Sync BookLore book list into the local SQLite cache."""
    count = 0
    for book in booklore_books:
        authors = book.get("authors", [])
        author = authors[0]["name"] if authors else "Unknown"
        isbn = book.get("isbn13", book.get("isbn", book.get("isbn10")))
        db.upsert_book(
            booklore_id=book["id"],
            title=book.get("title", ""),
            author=author,
            isbn=isbn,
        )
        count += 1
    return count


async def scrape_source(db: Database, source: str, limit: int, headless: bool,
                        rate_limit: float):
    """Scrape metadata for unscraped books from a single source."""
    from booklore_enrich.scraper.base import BrowserScraper

    base_url = SOURCES[source]
    unscraped = db.get_unscraped_books(source)

    if limit:
        unscraped = unscraped[:limit]

    if not unscraped:
        console.print(f"  No unscraped books for {source}.")
        return

    console.print(f"  Scraping {len(unscraped)} books from {source}...")

    scraper = BrowserScraper(headless=headless, rate_limit=rate_limit)
    await scraper.start()

    try:
        with Progress(console=console) as progress:
            task = progress.add_task(f"[cyan]Scraping {source}...", total=len(unscraped))

            for book in unscraped:
                progress.update(task, description=f"[cyan]{book['title'][:40]}...")

                # Search for the book
                result = await scraper.search_book(base_url, book["title"], book["author"])
                if not result:
                    progress.advance(task)
                    continue

                # Scrape the book page
                metadata = await scraper.scrape_book(base_url, result["source_id"], result["slug"])

                # Store tags
                for tag_name in metadata.get("tags", []):
                    tag_id = db.get_or_create_tag(tag_name, category="trope", source=source)
                    db.add_book_tag(book["id"], tag_id)

                # Store steam level
                if metadata.get("steam_level"):
                    db.set_steam_level(book["id"], metadata["steam_level"],
                                       metadata.get("steam_label"))

                # Mark as scraped
                db.mark_scraped(book["id"], source, result["source_id"])
                progress.advance(task)

    finally:
        await scraper.stop()


def run_scrape(source: str, limit: int):
    """Execute the scrape command."""
    config = load_config()

    if not config.booklore_username:
        console.print("[red]No BookLore username configured.[/red]")
        return

    password = click.prompt("BookLore password", hide_input=True)

    client = BookLoreClient(config.booklore_url)
    db = Database()

    try:
        console.print(f"Connecting to BookLore at {config.booklore_url}...")
        client.login(config.booklore_username, password)

        console.print("Syncing book list to local cache...")
        books = client.get_books()
        synced = sync_books_to_cache(db, books)
        console.print(f"  Synced {synced} books.")

        sources = [source] if source != "all" else list(SOURCES.keys())
        for src in sources:
            console.print(f"\nScraping {src}...")
            asyncio.run(scrape_source(db, src, limit, config.headless,
                                      config.rate_limit_seconds))

        console.print("\n[green]Scraping complete.[/green]")
    finally:
        client.close()
        db.close()
```

**Step 4: Wire up scrape command in CLI**

Update the scrape stub in `src/booklore_enrich/cli.py`:

```python
@cli.command()
@click.option("--source", "-s", type=click.Choice(["romance.io", "booknaut", "all"]),
              default="all", help="Which source to scrape.")
@click.option("--limit", "-l", type=int, default=0, help="Max books to scrape per source (0=all).")
def scrape(source, limit):
    """Scrape trope/heat metadata from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.scrape import run_scrape
    run_scrape(source, limit)
```

**Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/booklore_enrich/commands/scrape.py tests/test_scrape_command.py src/booklore_enrich/cli.py
git commit -m "feat: add scrape command with Playwright browser automation"
```

---

### Task 8: Tag Command

**Files:**
- Create: `src/booklore_enrich/commands/tag.py`
- Create: `tests/test_tag.py`
- Modify: `src/booklore_enrich/cli.py` — wire up tag command

**Step 1: Write failing tag tests**

Write `tests/test_tag.py`:
```python
# ABOUTME: Tests for the tag command that pushes enrichment data to BookLore.
# ABOUTME: Verifies shelf creation logic and tag-to-shelf mapping.

from booklore_enrich.commands.tag import (
    build_shelf_plan,
    build_tag_plan,
    STEAM_SHELF_NAMES,
)
from booklore_enrich.db import Database


def _setup_enriched_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Book A", author="Author")
    db.upsert_book(booklore_id=2, title="Book B", author="Author")
    book_a = db.get_book_by_booklore_id(1)
    book_b = db.get_book_by_booklore_id(2)
    tag1 = db.get_or_create_tag("enemies-to-lovers", "trope", "romance.io")
    tag2 = db.get_or_create_tag("slow-burn", "trope", "romance.io")
    db.add_book_tag(book_a["id"], tag1)
    db.add_book_tag(book_a["id"], tag2)
    db.add_book_tag(book_b["id"], tag1)
    db.set_steam_level(book_a["id"], 4, "Explicit open door")
    db.set_steam_level(book_b["id"], 2, "Behind closed doors")
    return db


def test_build_shelf_plan(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_shelf_plan(db)
    # Should have shelves for the tropes and steam levels found
    shelf_names = {s["name"] for s in plan}
    assert "Enemies To Lovers" in shelf_names
    assert "Slow Burn" in shelf_names
    assert STEAM_SHELF_NAMES[4] in shelf_names
    assert STEAM_SHELF_NAMES[2] in shelf_names


def test_build_shelf_plan_maps_books(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_shelf_plan(db)
    etl_shelf = next(s for s in plan if s["name"] == "Enemies To Lovers")
    assert 1 in etl_shelf["booklore_ids"]
    assert 2 in etl_shelf["booklore_ids"]


def test_build_tag_plan(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_tag_plan(db)
    # Should map booklore_id -> list of tag strings
    assert 1 in plan
    assert "enemies-to-lovers" in plan[1]
    assert "slow-burn" in plan[1]
    assert 2 in plan
    assert "enemies-to-lovers" in plan[2]
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tag.py -v
```
Expected: FAIL.

**Step 3: Implement tag command**

Write `src/booklore_enrich/commands/tag.py`:
```python
# ABOUTME: Tag command that pushes enriched metadata into BookLore as shelves and tags.
# ABOUTME: Creates trope shelves, steam-level shelves, and adds category tags to books.

from collections import defaultdict
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.table import Table

from booklore_enrich.booklore_client import BookLoreClient
from booklore_enrich.config import load_config
from booklore_enrich.db import Database

console = Console()

STEAM_SHELF_NAMES = {
    1: "Spice: 1 - Glimpses & Kisses",
    2: "Spice: 2 - Behind Closed Doors",
    3: "Spice: 3 - Open Door",
    4: "Spice: 4 - Explicit Open Door",
    5: "Spice: 5 - Explicit & Plentiful",
}


def _trope_to_shelf_name(trope: str) -> str:
    """Convert a trope slug to a human-readable shelf name."""
    return trope.replace("-", " ").title()


def build_shelf_plan(db: Database) -> List[Dict[str, Any]]:
    """Build a plan of shelves to create and which books go on each."""
    enriched = db.get_enriched_books()

    # Group books by trope tag
    trope_books = defaultdict(set)
    steam_books = defaultdict(set)

    for book in enriched:
        for tag in book.get("tags", []):
            if tag.get("category") == "trope":
                shelf_name = _trope_to_shelf_name(tag["name"])
                trope_books[shelf_name].add(book["booklore_id"])

        if book.get("steam_level"):
            shelf_name = STEAM_SHELF_NAMES.get(book["steam_level"])
            if shelf_name:
                steam_books[shelf_name].add(book["booklore_id"])

    plan = []
    for name, book_ids in sorted(trope_books.items()):
        plan.append({"name": name, "booklore_ids": list(book_ids), "type": "trope"})
    for name, book_ids in sorted(steam_books.items()):
        plan.append({"name": name, "booklore_ids": list(book_ids), "type": "steam"})

    return plan


def build_tag_plan(db: Database) -> Dict[int, List[str]]:
    """Build a plan of category tags to add to each book."""
    enriched = db.get_enriched_books()
    plan = {}
    for book in enriched:
        tags = [t["name"] for t in book.get("tags", [])]
        if book.get("steam_level"):
            tags.append(f"spice-{book['steam_level']}")
        if tags:
            plan[book["booklore_id"]] = tags
    return plan


def run_tag(dry_run: bool):
    """Execute the tag command."""
    config = load_config()
    db = Database()

    shelf_plan = build_shelf_plan(db)
    tag_plan = build_tag_plan(db)

    if not shelf_plan and not tag_plan:
        console.print("[yellow]No enrichment data found. Run 'scrape' first.[/yellow]")
        return

    # Display plan
    table = Table(title="Shelf Plan")
    table.add_column("Shelf Name")
    table.add_column("Type")
    table.add_column("Books")
    for shelf in shelf_plan:
        table.add_row(shelf["name"], shelf["type"], str(len(shelf["booklore_ids"])))
    console.print(table)
    console.print(f"\nTag plan: {len(tag_plan)} books will get category tags.")

    if dry_run:
        console.print("\n[yellow]DRY RUN — no changes made.[/yellow]")
        return

    if not config.booklore_username:
        console.print("[red]No BookLore username configured.[/red]")
        return

    password = click.prompt("BookLore password", hide_input=True)
    client = BookLoreClient(config.booklore_url)

    try:
        client.login(config.booklore_username, password)

        # Get existing shelves to avoid duplicates
        existing_shelves = {s["name"]: s["id"] for s in client.get_shelves()}

        # Create shelves and assign books
        for shelf in shelf_plan:
            if shelf["name"] in existing_shelves:
                shelf_id = existing_shelves[shelf["name"]]
                console.print(f"  Shelf '{shelf['name']}' already exists.")
            else:
                result = client.create_shelf(shelf["name"])
                shelf_id = result["id"]
                console.print(f"  Created shelf '{shelf['name']}'.")

            client.assign_books_to_shelf(shelf_id, shelf["booklore_ids"])
            console.print(f"    Assigned {len(shelf['booklore_ids'])} books.")

        # Add category tags to books
        console.print("\nAdding category tags to books...")
        for booklore_id, tags in tag_plan.items():
            client.update_book_metadata(booklore_id, {
                "categories": tags,
            }, merge_categories=True)

        console.print(f"  Tagged {len(tag_plan)} books.")
        console.print("\n[green]Tagging complete.[/green]")
    finally:
        client.close()
        db.close()
```

**Step 4: Wire up tag command in CLI**

Update tag stub in `src/booklore_enrich/cli.py`:
```python
@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview changes without applying.")
def tag(dry_run):
    """Push enriched metadata as tags and shelves into BookLore."""
    from booklore_enrich.commands.tag import run_tag
    run_tag(dry_run)
```

**Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/booklore_enrich/commands/tag.py tests/test_tag.py src/booklore_enrich/cli.py
git commit -m "feat: add tag command for pushing shelves and category tags to BookLore"
```

---

### Task 9: Discover Command

**Files:**
- Create: `src/booklore_enrich/commands/discover.py`
- Create: `tests/test_discover.py`
- Modify: `src/booklore_enrich/cli.py` — wire up discover command

**Step 1: Write failing discover tests**

Write `tests/test_discover.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_discover.py -v
```
Expected: FAIL.

**Step 3: Implement discover command**

Write `src/booklore_enrich/commands/discover.py`:
```python
# ABOUTME: Discover command that finds new books by trope from romance.io and booknaut.
# ABOUTME: Checks topic pages for romance, sci-fi, and fantasy recommendations.

import asyncio
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.table import Table

from booklore_enrich.config import load_config
from booklore_enrich.db import Database
from booklore_enrich.scraper.base import BrowserScraper, parse_search_results

console = Console()

SOURCES = {
    "romance.io": "https://www.romance.io",
    "booknaut": "https://www.thebooknaut.com",
}

GENRE_SOURCE_MAP = {
    "romance": "romance.io",
    "sci-fi": "booknaut",
    "fantasy": "booknaut",
}


def build_topic_urls(source: str, tropes: List[str]) -> List[str]:
    """Build topic page URLs for a list of tropes."""
    base = SOURCES[source]
    return [f"{base}/topics/best/{trope}/1" for trope in tropes]


def filter_known_books(db: Database, candidates: List[Dict[str, Any]],
                       source: str) -> List[Dict[str, Any]]:
    """Filter out books that are already in the local database."""
    col = "romance_io_id" if source == "romance.io" else "booknaut_id"
    known_ids = set()
    rows = db.execute(f"SELECT {col} FROM books WHERE {col} IS NOT NULL").fetchall()
    for row in rows:
        known_ids.add(row[0])
    return [c for c in candidates if c.get("source_id") not in known_ids]


async def discover_from_source(db: Database, source: str, tropes: List[str],
                                headless: bool, rate_limit: float) -> List[Dict[str, Any]]:
    """Discover new books from a source by checking topic pages."""
    urls = build_topic_urls(source, tropes)
    if not urls:
        return []

    scraper = BrowserScraper(headless=headless, rate_limit=rate_limit)
    await scraper.start()

    all_candidates = []
    seen_ids = set()

    try:
        for url in urls:
            console.print(f"  Checking {url}...")
            html = await scraper.fetch_page(url)
            results = parse_search_results(html)
            for result in results:
                if result["source_id"] not in seen_ids:
                    seen_ids.add(result["source_id"])
                    result["source"] = source
                    result["source_url"] = f"{SOURCES[source]}/books/{result['source_id']}/{result['slug']}"
                    all_candidates.append(result)
    finally:
        await scraper.stop()

    return filter_known_books(db, all_candidates, source)


def run_discover(source: str, genre: str):
    """Execute the discover command."""
    config = load_config()
    db = Database()

    try:
        sources_and_tropes = []

        if source == "all" or source == "romance.io":
            if genre in ("romance", None):
                sources_and_tropes.append(("romance.io", config.romance_tropes))
        if source == "all" or source == "booknaut":
            if genre in ("sci-fi", None):
                sources_and_tropes.append(("booknaut", config.scifi_tropes))
            if genre in ("fantasy", None):
                sources_and_tropes.append(("booknaut", config.fantasy_tropes))

        if not sources_and_tropes:
            console.print("[yellow]No trope preferences configured for that source/genre.[/yellow]")
            return

        all_new = []
        for src, tropes in sources_and_tropes:
            console.print(f"\nDiscovering from {src}...")
            new_books = asyncio.run(discover_from_source(
                db, src, tropes, config.headless, config.rate_limit_seconds
            ))
            all_new.extend(new_books)

            # Store discoveries
            for book in new_books:
                db.add_discovery(
                    title=book.get("slug", "").replace("-", " ").title(),
                    author="",
                    source=src,
                    source_id=book["source_id"],
                    source_url=book.get("source_url", ""),
                    genre=genre or "unknown",
                )

        if all_new:
            table = Table(title=f"Discovered {len(all_new)} New Books")
            table.add_column("Source")
            table.add_column("Title/Slug")
            table.add_column("URL")
            for book in all_new[:25]:
                table.add_row(
                    book["source"],
                    book.get("slug", "unknown").replace("-", " ").title()[:50],
                    book.get("source_url", ""),
                )
            console.print(table)
            if len(all_new) > 25:
                console.print(f"  ... and {len(all_new) - 25} more.")
        else:
            console.print("[yellow]No new books found for your trope preferences.[/yellow]")

    finally:
        db.close()
```

**Step 4: Wire up discover command in CLI**

Update discover stub in `src/booklore_enrich/cli.py`:
```python
@cli.command()
@click.option("--source", "-s", type=click.Choice(["romance.io", "booknaut", "all"]),
              default="all", help="Which source to check.")
@click.option("--genre", "-g", type=click.Choice(["romance", "sci-fi", "fantasy"]),
              default=None, help="Filter by genre.")
def discover(source, genre):
    """Discover new books by trope from romance.io and thebooknaut.com."""
    from booklore_enrich.commands.discover import run_discover
    run_discover(source, genre)
```

**Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/booklore_enrich/commands/discover.py tests/test_discover.py src/booklore_enrich/cli.py
git commit -m "feat: add discover command for finding new books by trope"
```

---

### Task 10: Integration Test and Final Polish

**Files:**
- Modify: `src/booklore_enrich/cli.py` — final version with all commands wired
- Create: `tests/test_integration.py`
- Create: `.gitignore`

**Step 1: Write integration test**

Write `tests/test_integration.py`:
```python
# ABOUTME: Integration tests for the full booklore-enrich pipeline.
# ABOUTME: Tests the flow from DB sync through tag plan generation.

from booklore_enrich.db import Database
from booklore_enrich.commands.scrape import sync_books_to_cache
from booklore_enrich.commands.tag import build_shelf_plan, build_tag_plan


def test_full_pipeline_sync_to_tag(tmp_path):
    """Test the full flow: sync books -> add tags -> build shelf/tag plans."""
    db = Database(tmp_path / "test.db")

    # Simulate BookLore books
    booklore_books = [
        {"id": 1, "title": "Dark Romance", "authors": [{"name": "Author A"}], "isbn": "111"},
        {"id": 2, "title": "Sci-Fi Epic", "authors": [{"name": "Author B"}], "isbn": "222"},
        {"id": 3, "title": "No Tags Book", "authors": [{"name": "Author C"}]},
    ]
    sync_books_to_cache(db, booklore_books)

    # Simulate scraped data for book 1 (romance)
    book1 = db.get_book_by_booklore_id(1)
    for tag_name in ["enemies-to-lovers", "dark", "forced-proximity"]:
        tag_id = db.get_or_create_tag(tag_name, "trope", "romance.io")
        db.add_book_tag(book1["id"], tag_id)
    db.set_steam_level(book1["id"], 5, "Explicit and plentiful")
    db.mark_scraped(book1["id"], "romance.io", "abc123")

    # Simulate scraped data for book 2 (booknaut)
    book2 = db.get_book_by_booklore_id(2)
    for tag_name in ["space-opera", "first-contact"]:
        tag_id = db.get_or_create_tag(tag_name, "trope", "booknaut")
        db.add_book_tag(book2["id"], tag_id)
    db.mark_scraped(book2["id"], "booknaut", "def456")

    # Build plans
    shelf_plan = build_shelf_plan(db)
    tag_plan = build_tag_plan(db)

    # Verify shelf plan
    shelf_names = {s["name"] for s in shelf_plan}
    assert "Enemies To Lovers" in shelf_names
    assert "Dark" in shelf_names
    assert "Space Opera" in shelf_names
    assert "Spice: 5 - Explicit & Plentiful" in shelf_names

    # Verify tag plan
    assert 1 in tag_plan
    assert "enemies-to-lovers" in tag_plan[1]
    assert "spice-5" in tag_plan[1]
    assert 2 in tag_plan
    assert "space-opera" in tag_plan[2]
    # Book 3 has no tags, should not be in plan
    assert 3 not in tag_plan

    db.close()
```

**Step 2: Write .gitignore**

Write `.gitignore`:
```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
.ruff_cache/
cache.db
*.db
.env
```

**Step 3: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add tests/test_integration.py .gitignore CLAUDE.md
git commit -m "feat: add integration test and project configuration"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project scaffolding | pyproject.toml, cli.py, CLAUDE.md |
| 2 | Configuration management | config.py |
| 3 | SQLite database layer | db.py |
| 4 | BookLore API client | booklore_client.py |
| 5 | Export command | commands/export.py |
| 6 | Scraper base (Playwright) | scraper/base.py |
| 7 | Scrape command | commands/scrape.py |
| 8 | Tag command | commands/tag.py |
| 9 | Discover command | commands/discover.py |
| 10 | Integration test + polish | test_integration.py, .gitignore |

Each task follows TDD: write failing test → implement → verify pass → commit. Total: ~10 commits, each independently buildable and testable.

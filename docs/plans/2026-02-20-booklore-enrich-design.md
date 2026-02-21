# booklore-enrich Design Document

**Date:** 2026-02-20
**Status:** Approved

## Purpose

A Python CLI tool that enriches a BookLore digital library with metadata from romance.io (romance books) and thebooknaut.com (sci-fi, fantasy). Provides book discovery recommendations from both sources. Both sites are owned by the same company (Elektrolabs) and share identical URL structures.

## Goals

1. **Export** BookLore library as Goodreads-compatible CSV for romance.io/booknaut import
2. **Scrape** trope tags, steam/heat levels, and content metadata from romance.io and booknaut using browser automation
3. **Tag** books in BookLore with enriched metadata (both shelves and per-book category tags)
4. **Discover** new books matching preferred tropes — romance from romance.io, sci-fi/fantasy from booknaut

## Architecture

```
┌─────────────┐     HTTP/REST      ┌──────────────┐
│  BookLore   │◄──────────────────►│              │
│  (Synology) │  JWT auth, JSON    │  booklore-   │
│  :6060      │                    │  enrich      │
└─────────────┘                    │  (Mac)       │
                                   │              │
┌─────────────┐     Playwright     │  Commands:   │
│ romance.io  │◄──────────────────►│  - export    │
│ booknaut.com│  browser scraping  │  - scrape    │
└─────────────┘                    │  - tag       │
                                   │  - discover  │
┌─────────────┐                    │              │
│  SQLite     │◄──────────────────►│              │
│  cache.db   │  local storage     └──────────────┘
└─────────────┘
```

**Runtime:** Python 3.12+ on Mac, communicates with BookLore API over LAN.

**Key dependencies:**
- `click` — CLI framework
- `httpx` — async HTTP client for BookLore API
- `playwright` — browser automation for scraping Cloudflare-protected sites
- `rich` — terminal output formatting
- `sqlite3` — built-in, local cache

**Package management:** uv

## BookLore API Integration

BookLore exposes a REST API at `/api/v1/` with JWT authentication.

**Key endpoints used:**
- `POST /api/v1/auth/login` — authenticate, get JWT tokens
- `GET /api/v1/books?withDescription=true` — list all books with metadata
- `GET /api/v1/books/{bookId}` — get single book metadata
- `PUT /api/v1/books/{bookId}/metadata` — update book metadata (tags/categories)
- `GET /api/v1/shelves` — list shelves
- `POST /api/v1/shelves` — create shelf
- `POST /api/v1/books/shelves` — assign books to shelves

## Romance.io / Booknaut Site Structure

Both sites share identical patterns (same backend, Elektrolabs):

**URL patterns:**
- Book page: `/books/{24-char-mongo-id}/{slugified-title-author}`
- Similar books: `/books/{id}/{slug}/similar`
- Series: `/series/{id}/{slug}`
- Topic search: `/topics/best/{comma-separated-tropes}/{page-number}`
- By steam level: `/genres/romance/romance-books-by-steam/{level}`

**Available metadata per book:**
- Title, author, series info, page count, publication date
- Star rating (community average)
- Steam/heat level (5-tier: "Glimpses and kisses" through "Explicit and plentiful")
- Trope tags (enemies-to-lovers, slow burn, forced proximity, etc.)
- Subgenre tags (dark, contemporary, paranormal, historical, etc.)
- Hero/heroine type tags (alpha male, competent heroine, etc.)
- Content warnings
- Similar book recommendations (~30-50 per book)

**Access constraints:**
- No public API
- Cloudflare bot protection (403 on automated requests)
- JavaScript-rendered pages (requires real browser)
- Rate limiting required (2-3s between requests)

## Data Model (SQLite Cache)

```sql
books (
    id INTEGER PRIMARY KEY,
    booklore_id INTEGER,
    title TEXT,
    author TEXT,
    isbn TEXT,
    romance_io_id TEXT,
    booknaut_id TEXT,
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP
)

tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    category TEXT,  -- "trope", "subgenre", "content-warning", "hero-type", "heroine-type"
    source TEXT     -- "romance.io" or "booknaut"
)

book_tags (
    book_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (book_id, tag_id)
)

book_steam (
    book_id INTEGER PRIMARY KEY,
    level INTEGER,   -- 1-5
    label TEXT
)

discoveries (
    id INTEGER PRIMARY KEY,
    title TEXT,
    author TEXT,
    source TEXT,
    source_id TEXT,
    source_url TEXT,
    genre TEXT,
    steam_level INTEGER,
    discovered_at TIMESTAMP,
    dismissed BOOLEAN DEFAULT 0
)

discovery_preferences (
    id INTEGER PRIMARY KEY,
    source TEXT,
    trope TEXT,
    enabled BOOLEAN DEFAULT 1
)
```

## CLI Commands

### `booklore-enrich export`

Authenticates with BookLore API, pulls all books with metadata, writes Goodreads-compatible CSV. User manually uploads to romance.io/import for discovery account setup.

### `booklore-enrich scrape [--source romance.io|booknaut|all] [--limit 50]`

For each book in BookLore not yet cached (or stale):
1. Launches headless Playwright browser
2. Searches romance.io or booknaut by title + author
3. Scrapes tropes, steam level, tags, similar books from book page
4. Stores results in SQLite cache

Rate-limited at 2-3s between requests. Resumable — skips already-scraped books. Supports `--limit` to cap per session.

### `booklore-enrich tag [--dry-run]`

Reads enrichment data from SQLite cache:
1. Creates shelves in BookLore for popular tropes (e.g. "Enemies to Lovers", "Slow Burn")
2. Creates shelves for steam levels (e.g. "Spice: 1" through "Spice: 5")
3. Adds trope names as category tags on each book's metadata
4. Dry-run mode previews all changes without applying

### `booklore-enrich discover [--source romance.io|booknaut|all] [--genre romance|sci-fi|fantasy]`

Checks configured trope preferences:
- romance.io `/topics/` URLs for romance
- booknaut `/topics/` URLs for sci-fi and fantasy

Filters out books already in BookLore library. Displays recommendations with tropes, ratings, steam level. Supports dismissing uninteresting results.

## Configuration

Stored in `~/.config/booklore-enrich/config.toml`:

```toml
[booklore]
url = "http://192.168.7.21:6060"
username = "dylan"

[scraping]
rate_limit_seconds = 3
max_concurrent = 1
headless = true

[discovery]
romance_tropes = ["enemies-to-lovers", "slow-burn", "forced-proximity"]
scifi_tropes = ["space-opera", "first-contact", "cyberpunk"]
fantasy_tropes = ["epic-fantasy", "urban-fantasy", "dark-fantasy"]
```

Password is prompted at runtime or stored in system keyring.

## Future Considerations

- Containerize and move to Synology for scheduled runs
- Contact Elektrolabs (romance.io/booknaut) about proper API access
- Add Hardcover.app as additional metadata source (BookLore already supports it natively)
- Notification system for new discovery matches (email, Discord, etc.)

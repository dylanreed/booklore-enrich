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

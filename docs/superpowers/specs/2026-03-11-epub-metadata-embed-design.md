# EPUB Metadata Embed — Design Spec

## Summary

Add two capabilities to booklore-enrich:

1. **`scrape --from-dir`** — discover books from the filesystem instead of the BookLore API
2. **`embed` command** — write scraped metadata from the SQLite cache into EPUB files

This enables a pre-import workflow: scrape metadata for your ebook collection, embed it directly into the EPUB files, then import into BookLore with rich metadata already in place.

## Motivation

BookLore reads metadata from EPUB files on import. By writing tropes, genres, steam levels, and hero/heroine types into the EPUBs before import, BookLore picks them up automatically — no post-import enrichment needed. This also fixes author name formatting ("Last, First" → "First Last") and ensures title metadata is clean.

**BookLore metadata support (confirmed):** BookLore's EPUB import parser reads `dc:subject` elements as genres/categories and reads `<meta property="booklore:tags">` JSON arrays as tags. The `booklore:` namespace is BookLore's own custom metadata format, designed for round-trip fidelity. BookLore also supports `booklore:moods` and `booklore:series_total`, though mood data is not currently scraped by this tool.

## Approach

**Approach B** (selected): Keep scraping and embedding as separate commands. The existing `scrape` command gets a `--from-dir` flag for filesystem discovery. A new `embed` command reads cached metadata and writes it into EPUB files. Both commands feed and read from the same SQLite cache.

## Change 1: `scrape --from-dir`

### Behavior

When `scrape --from-dir /path/to/books` is used:

1. Walk the directory tree for `.epub` files
2. Parse metadata from the path using the naming convention:
   - `Author/Series/01 - Title.epub` → author, series, index, title
   - `Author/Standalone/Title.epub` → author, title (no series)
   - `Author/Title.epub` → author, title (flat, no series)
3. Upsert each book into SQLite with parsed metadata and file path
4. Hand off to normal scrape pipeline (search romance.io/booknaut by title + author)

### Database Change

Add these columns to the `books` table: `file_path TEXT UNIQUE`, `series TEXT`, `series_index TEXT`, `series_total INTEGER`. Nullable — books discovered via BookLore API won't have one. Books discovered via `--from-dir` won't have a `booklore_id`.

A new upsert path is needed for file-discovered books using `file_path` as the conflict/identity key (separate from the existing `booklore_id`-based upsert). SQLite allows multiple NULLs in UNIQUE columns, so books without a `file_path` (API-discovered) won't conflict.

Books discovered via `--from-dir` and via the BookLore API are treated as separate cache entries. No deduplication is performed — this is a pre-import tool, so the two discovery paths serve different workflows.

**Migration:** On startup, check for new columns and run `ALTER TABLE books ADD COLUMN` if missing. The cache is regenerable, so no complex migration is needed.

### BookLore Sync

When `--from-dir` is used, the BookLore API sync step is skipped entirely. No BookLore credentials are required. The book list comes from the filesystem instead.

### CLI

```
enrich scrape --from-dir /path/to/books --source romance.io --limit 50
```

All existing flags (`--source`, `--limit`, etc.) work the same way. `--from-dir` just changes how the initial book list is built.

## Change 2: `embed` Command

### CLI

```
enrich embed /path/to/books [--dry-run] [--force]
```

### Flags

- `--dry-run` — show what would change without writing to files
- `--force` — re-embed books that have already been processed

### Flow

1. Query SQLite for all books that have been scraped AND have a `file_path`
2. Verify each `file_path` exists on disk (paths are always stored as absolute). The `/path/to/books` CLI argument scopes which books to process — only books whose `file_path` starts with that prefix are included.
3. For each book with a matching EPUB file on disk:
   a. Open the EPUB, read existing OPF metadata
   b. Merge scraped metadata (details below)
   c. Save the modified EPUB in place
   d. Record `embedded_at` timestamp in cache
3. Print Rich progress bar during processing
4. Print summary at end: embedded, skipped, errors
5. Write detailed log file

### Metadata Mapping

| Scraped Data | EPUB Field | BookLore Import Target |
|---|---|---|
| Subgenres | `<dc:subject>` elements | Genres/Categories |
| Tropes | `<meta property="booklore:tags">` JSON array | Tags |
| Steam level | `<meta property="booklore:tags">` JSON array (e.g. `"steam:4"`) | Tags |
| Hero types | `<meta property="booklore:tags">` JSON array (e.g. `"hero:alpha-male"`) | Tags |
| Heroine types | `<meta property="booklore:tags">` JSON array (e.g. `"heroine:competent"`) | Tags |
| Author | `<dc:creator>` | Author |
| Title | `<dc:title>` | Title |
| Series name | `<meta name="calibre:series">` + `<meta property="belongs-to-collection">` | Series |
| Series index | `<meta name="calibre:series_index">` + `<meta property="group-position">` | Series position |
| Series total | `<meta property="booklore:series_total">` | Series total |

### Merge Behavior

- **`<dc:subject>`** — read existing subjects, add scraped subgenres, deduplicate, write all back
- **`booklore:tags`** — read existing JSON array if present, add new tags, deduplicate, write back
- **`dc:creator`** — if in "Last, First" format, flip to "First Last". Multi-author strings (e.g. "Margaret Weis, Tracy Hickman") are left as-is — only single-author reversed names are flipped
- **`dc:title`** — set from cached title data
- **Series metadata** — series name, index, and total are sourced from two places: the filesystem path (parsed during `--from-dir` discovery) and the scraped page data. Scraped data takes priority when available (more accurate). Written using both Calibre-compatible (`calibre:series`, `calibre:series_index`) and EPUB3 standard (`belongs-to-collection`, `group-position`) elements for maximum compatibility. Series total uses BookLore's custom `booklore:series_total`.

### Author Flip Logic

Simple heuristic: if the string contains exactly one comma and the part before the comma looks like a surname (no spaces or one word), flip it. This covers the 95% case for romance/sci-fi/fantasy collections. Known edge cases like "Jr., John" or "de la Cruz, Melissa" are rare enough to handle manually if they arise.

```
"Bailey, Tessa" → single comma, one-word prefix → "Tessa Bailey"
"Bujold, Lois McMaster" → single comma, one-word prefix → "Lois McMaster Bujold"
"Margaret Weis, Tracy Hickman" → single comma but multi-word prefix → leave as-is (multi-author)
"Tessa Bailey" → no comma → leave as-is (already correct)
```

### Database Change

Add `embedded_at TIMESTAMP` column to the `books` table. Set when a book's EPUB has been successfully written. Used to skip already-processed books on re-runs (unless `--force`).

Series fields (`series`, `series_index`) are populated from two sources:
1. **Filesystem path** — parsed during `--from-dir` discovery (e.g. `Author/Hot and Hammered/01 - Fix Her Up.epub` → series="Hot and Hammered", index="01")
2. **Scraped page data** — romance.io/booknaut pages include series info. Scraped values overwrite filesystem-parsed values when available (more authoritative). `series_total` is only available from scraped data.

## Prerequisite: Tag Category Differentiation

The current scraper stores all extracted tags with `category="trope"`. The `embed` command needs to route subgenres to `<dc:subject>` and tropes/hero/heroine types to `booklore:tags`. This requires enhancing `parse_book_page()` in `scraper/base.py` to differentiate tag categories.

Romance.io and booknaut page HTML contains separate sections for tropes, subgenres, hero types, and heroine types — all linked via `/topics/` URLs but distinguishable by their surrounding HTML context. The parser needs to extract the category from the page structure and pass it through to `get_or_create_tag()` with the correct `category` value (`"trope"`, `"subgenre"`, `"hero-type"`, `"heroine-type"`).

If category detection from the HTML proves unreliable, a fallback approach: maintain a known-subgenres list (contemporary, paranormal, dark, historical, etc.) and categorize by matching. Everything not in the subgenres list stays as `"trope"`.

## EPUB Manipulation

Use **`ebooklib`** for reading/writing EPUB files. It handles:

- ZIP structure and OPF discovery
- `dc:subject`, `dc:creator`, `dc:title` metadata
- EPUB2 and EPUB3 formats

The `booklore:tags` custom metadata property is not natively supported by ebooklib, so we'll handle that with raw XML manipulation on the OPF after ebooklib does the standard metadata work.

### Scope

- **EPUB files only** — AZW3, MOBI, PDF are skipped
- **In-place modification** — no backup copies (NAS snapshots provide safety net)

## Error Handling

| Scenario | Action |
|---|---|
| EPUB corrupted/unreadable | Log warning, skip, continue |
| Book not in cache (never scraped) | Skip, count in summary |
| No metadata found on romance.io/booknaut | Skip (nothing to write) |
| Multiple authors in `dc:creator` | Don't flip format, leave as-is |
| EPUB has no OPF | Log warning, skip |
| File path in cache is stale (moved/deleted) | Log warning, skip |

## Logging

Each run writes a log file to `~/.config/booklore-enrich/embed-YYYY-MM-DD-HHMMSS.log` containing:

- Every book embedded: file path + metadata written
- Every skip: file path + reason (no cache data, not epub, file missing, etc.)
- Every error: file path + exception detail
- Summary stats at end (embedded count, skipped count, error count)

The Rich console also shows a progress bar and summary during execution.

## Dependencies

New production dependency:

- `ebooklib` — EPUB read/write

## File Changes

| File | Change |
|---|---|
| `src/booklore_enrich/db.py` | Add `file_path`, `series`, `series_index`, `series_total`, `embedded_at` columns, query methods, migration logic |
| `src/booklore_enrich/commands/scrape.py` | Add `--from-dir` flag, filesystem discovery logic |
| `src/booklore_enrich/commands/embed.py` | New file — embed command implementation |
| `src/booklore_enrich/epub_writer.py` | New file — EPUB metadata read/merge/write logic |
| `src/booklore_enrich/cli.py` | Register `embed` command, add `--from-dir` option to `scrape` |
| `pyproject.toml` | Add `ebooklib` dependency |
| `tests/test_embed.py` | New file — embed command tests |
| `tests/test_epub_writer.py` | New file — EPUB writer tests |
| `tests/test_scrape_from_dir.py` | New file — filesystem discovery tests |

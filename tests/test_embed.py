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

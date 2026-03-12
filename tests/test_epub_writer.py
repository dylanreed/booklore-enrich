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

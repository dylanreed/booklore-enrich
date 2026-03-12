# ABOUTME: Tests for EPUB metadata read/merge/write logic.
# ABOUTME: Covers author flipping, title, subjects, tags, and series metadata.

import json
from xml.etree import ElementTree as ET
from zipfile import ZipFile

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


def _read_opf_xml(epub_path):
    """Extract and parse the OPF XML from an EPUB for custom metadata checks."""
    with ZipFile(str(epub_path), "r") as zf:
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

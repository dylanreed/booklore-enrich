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

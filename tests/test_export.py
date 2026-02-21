# ABOUTME: Tests for the export command that generates Goodreads-compatible CSV.
# ABOUTME: Verifies CSV format, field mapping, and handling of missing data.

import csv
import io

from booklore_enrich.commands.export import books_to_goodreads_csv


def test_books_to_csv_basic():
    books = [
        {
            "id": 1,
            "title": "Test Book",
            "isbn": "9781234567890",
            "authors": [{"name": "Test Author"}],
            "publisher": "Test Publisher",
            "publishedDate": "2024",
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
            "id": 1,
            "title": "Collab Book",
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
    expected_fields = [
        "Title",
        "Author",
        "Additional Authors",
        "ISBN",
        "ISBN13",
        "Publisher",
        "Year Published",
        "Number of Pages",
        "Bookshelves",
    ]
    for field in expected_fields:
        assert field in reader.fieldnames

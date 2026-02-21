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

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


def test_parse_book_page_categorizes_tags():
    """Tags are returned with categories, not as flat strings."""
    html = '''
    <a href="/topics/best/enemies-to-lovers/1">Enemies to Lovers</a>
    <a href="/topics/best/contemporary/1">Contemporary</a>
    <a href="/topics/best/alpha-male/1">Alpha Male</a>
    <a href="/topics/best/competent-heroine/1">Competent Heroine</a>
    '''
    result = parse_book_page(html)
    # Should still have tags list for backwards compat
    assert len(result["tags"]) > 0
    # Should also have categorized_tags
    cats = result["categorized_tags"]
    names_by_cat = {}
    for t in cats:
        names_by_cat.setdefault(t["category"], []).append(t["name"])
    assert "contemporary" in names_by_cat.get("subgenre", [])
    assert "enemies-to-lovers" in names_by_cat.get("trope", [])
    assert "alpha-male" in names_by_cat.get("hero-type", [])
    assert "competent-heroine" in names_by_cat.get("heroine-type", [])

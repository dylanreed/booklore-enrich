# ABOUTME: Integration tests for the full booklore-enrich pipeline.
# ABOUTME: Tests the flow from DB sync through tag plan generation.

from booklore_enrich.db import Database
from booklore_enrich.commands.scrape import sync_books_to_cache
from booklore_enrich.commands.tag import build_shelf_plan, build_tag_plan


def test_full_pipeline_sync_to_tag(tmp_path):
    """Test the full flow: sync books -> add tags -> build shelf/tag plans."""
    db = Database(tmp_path / "test.db")

    # Simulate BookLore books
    booklore_books = [
        {"id": 1, "title": "Dark Romance", "authors": [{"name": "Author A"}], "isbn": "111"},
        {"id": 2, "title": "Sci-Fi Epic", "authors": [{"name": "Author B"}], "isbn": "222"},
        {"id": 3, "title": "No Tags Book", "authors": [{"name": "Author C"}]},
    ]
    sync_books_to_cache(db, booklore_books)

    # Simulate scraped data for book 1 (romance)
    book1 = db.get_book_by_booklore_id(1)
    for tag_name in ["enemies-to-lovers", "dark", "forced-proximity"]:
        tag_id = db.get_or_create_tag(tag_name, "trope", "romance.io")
        db.add_book_tag(book1["id"], tag_id)
    db.set_steam_level(book1["id"], 5, "Explicit and plentiful")
    db.mark_scraped(book1["id"], "romance.io", "abc123")

    # Simulate scraped data for book 2 (booknaut)
    book2 = db.get_book_by_booklore_id(2)
    for tag_name in ["space-opera", "first-contact"]:
        tag_id = db.get_or_create_tag(tag_name, "trope", "booknaut")
        db.add_book_tag(book2["id"], tag_id)
    db.mark_scraped(book2["id"], "booknaut", "def456")

    # Build plans
    shelf_plan = build_shelf_plan(db)
    tag_plan = build_tag_plan(db)

    # Verify shelf plan
    shelf_names = {s["name"] for s in shelf_plan}
    assert "Enemies To Lovers" in shelf_names
    assert "Dark" in shelf_names
    assert "Space Opera" in shelf_names
    assert "Spice: 5 - Explicit & Plentiful" in shelf_names

    # Verify tag plan
    assert 1 in tag_plan
    assert "enemies-to-lovers" in tag_plan[1]
    assert "spice-5" in tag_plan[1]
    assert 2 in tag_plan
    assert "space-opera" in tag_plan[2]
    # Book 3 has no tags, should not be in plan
    assert 3 not in tag_plan

    db.close()

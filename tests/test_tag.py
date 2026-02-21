# ABOUTME: Tests for the tag command that pushes enrichment data to BookLore.
# ABOUTME: Verifies shelf creation logic and tag-to-shelf mapping.

from booklore_enrich.commands.tag import (
    build_shelf_plan,
    build_tag_plan,
    STEAM_SHELF_NAMES,
)
from booklore_enrich.db import Database


def _setup_enriched_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_book(booklore_id=1, title="Book A", author="Author")
    db.upsert_book(booklore_id=2, title="Book B", author="Author")
    book_a = db.get_book_by_booklore_id(1)
    book_b = db.get_book_by_booklore_id(2)
    tag1 = db.get_or_create_tag("enemies-to-lovers", "trope", "romance.io")
    tag2 = db.get_or_create_tag("slow-burn", "trope", "romance.io")
    db.add_book_tag(book_a["id"], tag1)
    db.add_book_tag(book_a["id"], tag2)
    db.add_book_tag(book_b["id"], tag1)
    db.set_steam_level(book_a["id"], 4, "Explicit open door")
    db.set_steam_level(book_b["id"], 2, "Behind closed doors")
    return db


def test_build_shelf_plan(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_shelf_plan(db)
    # Should have shelves for the tropes and steam levels found
    shelf_names = {s["name"] for s in plan}
    assert "Enemies To Lovers" in shelf_names
    assert "Slow Burn" in shelf_names
    assert STEAM_SHELF_NAMES[4] in shelf_names
    assert STEAM_SHELF_NAMES[2] in shelf_names


def test_build_shelf_plan_maps_books(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_shelf_plan(db)
    etl_shelf = next(s for s in plan if s["name"] == "Enemies To Lovers")
    assert 1 in etl_shelf["booklore_ids"]
    assert 2 in etl_shelf["booklore_ids"]


def test_build_tag_plan(tmp_path):
    db = _setup_enriched_db(tmp_path)
    plan = build_tag_plan(db)
    # Should map booklore_id -> list of tag strings
    assert 1 in plan
    assert "enemies-to-lovers" in plan[1]
    assert "slow-burn" in plan[1]
    assert 2 in plan
    assert "enemies-to-lovers" in plan[2]


def test_build_tag_plan_deduplicates_across_sources(tmp_path):
    """Tags from multiple sources should not produce duplicate entries."""
    db = Database(tmp_path / "dedup.db")
    db.upsert_book(booklore_id=10, title="Dupe Book", author="Author")
    book = db.get_book_by_booklore_id(10)
    # Same trope name from two different sources
    tag_rio = db.get_or_create_tag("enemies-to-lovers", "trope", "romance.io")
    tag_bn = db.get_or_create_tag("enemies-to-lovers", "trope", "booknaut")
    db.add_book_tag(book["id"], tag_rio)
    db.add_book_tag(book["id"], tag_bn)
    plan = build_tag_plan(db)
    # Should only have one "enemies-to-lovers", not two
    assert plan[10].count("enemies-to-lovers") == 1


def test_diff_tags_filters_existing():
    """diff_tags should remove tags the book already has in BookLore."""
    from booklore_enrich.commands.tag import diff_tags
    planned = ["enemies-to-lovers", "slow-burn", "spice-4"]
    existing = ["enemies-to-lovers", "romance"]
    result = diff_tags(planned, existing)
    assert "slow-burn" in result
    assert "spice-4" in result
    assert "enemies-to-lovers" not in result

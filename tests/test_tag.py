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

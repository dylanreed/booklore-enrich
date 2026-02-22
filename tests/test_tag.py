# ABOUTME: Tests for the tag command that pushes enrichment data to BookLore.
# ABOUTME: Verifies shelf creation, tag-to-shelf mapping, cache integration, and concurrency.

from unittest.mock import patch

from click.testing import CliRunner

from booklore_enrich.cli import cli
from booklore_enrich.commands.tag import (
    build_shelf_plan,
    build_tag_plan,
    run_tag,
    STEAM_SHELF_NAMES,
)
from booklore_enrich.db import Database, compute_tag_hash


def _setup_enriched_db(tmp_path, check_same_thread=False):
    db = Database(tmp_path / "test.db", check_same_thread=check_same_thread)
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


def test_run_tag_skip_shelves_skips_shelf_creation(tmp_path):
    """When skip_shelves=True, no shelves should be created."""
    db = _setup_enriched_db(tmp_path)
    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.get_book.return_value = {"metadata": {"categories": []}}

        run_tag(dry_run=False, skip_shelves=True, skip_tags=False)

        client.create_shelf.assert_not_called()
        client.assign_books_to_shelf.assert_not_called()
        # Tags should still run
        assert client.update_book_metadata.call_count > 0


def test_run_tag_full_run_tags_and_shelves(tmp_path):
    """Full run creates shelves and tags books."""
    db = _setup_enriched_db(tmp_path)
    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}
        client.get_book.return_value = {"metadata": {"categories": []}}

        run_tag(dry_run=False)

        assert client.create_shelf.call_count > 0
        assert client.update_book_metadata.call_count > 0


def test_run_tag_skip_tags_skips_tag_assignment(tmp_path):
    """When skip_tags=True, no tags should be assigned."""
    db = _setup_enriched_db(tmp_path)
    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}

        run_tag(dry_run=False, skip_shelves=False, skip_tags=True)

        # Shelves should still run
        assert client.create_shelf.call_count > 0
        # Tags should not run
        client.get_book.assert_not_called()
        client.update_book_metadata.assert_not_called()


def test_cached_books_skip_api_calls(tmp_path):
    """Books with matching cache hashes should skip API calls entirely."""
    db = _setup_enriched_db(tmp_path)
    # Pre-populate the tag cache for both books with the correct hashes
    tag_plan = build_tag_plan(db)
    for booklore_id, tags in tag_plan.items():
        db.set_tag_hash(booklore_id, compute_tag_hash(tags))

    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}

        run_tag(dry_run=False, skip_shelves=True, skip_tags=False)

        # No API calls should be made for cached books
        client.get_book.assert_not_called()
        client.update_book_metadata.assert_not_called()


def test_uncached_books_get_api_calls_and_cached_after(tmp_path):
    """Uncached books should go through the normal API flow and get cached after."""
    db_path = tmp_path / "test.db"
    db = _setup_enriched_db(tmp_path)
    tag_plan = build_tag_plan(db)

    # Verify no cache entries exist
    for booklore_id in tag_plan:
        assert db.get_tag_hash(booklore_id) is None

    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}
        client.get_book.return_value = {"metadata": {"categories": []}}

        run_tag(dry_run=False, skip_shelves=True, skip_tags=False)

        # API calls should have been made for uncached books
        assert client.get_book.call_count == len(tag_plan)
        assert client.update_book_metadata.call_count == len(tag_plan)

    # Re-open the db to verify cache entries (run_tag closes the db)
    db2 = Database(db_path)
    for booklore_id, tags in tag_plan.items():
        cached_hash = db2.get_tag_hash(booklore_id)
        assert cached_hash is not None
        assert cached_hash == compute_tag_hash(tags)
    db2.close()


def test_already_up_to_date_books_get_cached(tmp_path):
    """Books that are already up to date via API diff should still get cached."""
    db_path = tmp_path / "test.db"
    db = _setup_enriched_db(tmp_path)
    tag_plan = build_tag_plan(db)

    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}
        # All tags already exist in BookLore, so diff will be empty
        client.get_book.return_value = {
            "metadata": {"categories": ["enemies-to-lovers", "slow-burn", "spice-4", "spice-2"]}
        }

        run_tag(dry_run=False, skip_shelves=True, skip_tags=False)

        # No update calls needed since all tags already exist
        client.update_book_metadata.assert_not_called()

    # Re-open the db to verify cache entries (run_tag closes the db)
    db2 = Database(db_path)
    for booklore_id, tags in tag_plan.items():
        cached_hash = db2.get_tag_hash(booklore_id)
        assert cached_hash is not None
    db2.close()


def test_tag_command_has_concurrency_flag():
    """The tag CLI command should accept a --concurrency flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert result.exit_code == 0
    assert "--concurrency" in result.output or "-c" in result.output


def test_run_tag_accepts_concurrency_parameter(tmp_path):
    """run_tag should accept and use the concurrency parameter."""
    db = _setup_enriched_db(tmp_path)
    with patch("booklore_enrich.commands.tag.Database", return_value=db), \
         patch("booklore_enrich.commands.tag.load_config") as mock_config, \
         patch("booklore_enrich.commands.tag.get_password", return_value="pass"), \
         patch("booklore_enrich.commands.tag.BookLoreClient") as MockClient:
        mock_config.return_value.booklore_url = "http://localhost"
        mock_config.return_value.booklore_username = "user"
        client = MockClient.return_value
        client.get_shelves.return_value = []
        client.create_shelf.return_value = {"id": 99}
        client.get_book.return_value = {"metadata": {"categories": []}}

        # Should not raise an error when concurrency is passed
        run_tag(dry_run=False, skip_shelves=True, skip_tags=False, concurrency=2)

        # Books should still get tagged
        assert client.update_book_metadata.call_count > 0


def test_cli_passes_concurrency_to_run_tag(tmp_path):
    """The CLI should pass the --concurrency value through to run_tag."""
    with patch("booklore_enrich.commands.tag.run_tag") as mock_run_tag:
        runner = CliRunner()
        result = runner.invoke(cli, ["tag", "--dry-run", "--concurrency", "8"])
        assert result.exit_code == 0
        mock_run_tag.assert_called_once_with(
            True,
            skip_shelves=False,
            skip_tags=False,
            concurrency=8,
        )

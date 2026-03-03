# Tag Command Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--skip-shelves` / `--skip-tags` flags and rich progress bars to the `tag` command.

**Architecture:** Two contained changes to `cli.py` (flags) and `commands/tag.py` (flags + progress bars). The `run_tag` function gains two boolean params and wraps its two loops with `rich.progress.Progress` context managers.

**Tech Stack:** Python, Click (CLI), Rich (progress bars)

---

### Task 1: Add skip flags to CLI and run_tag signature

**Files:**
- Modify: `src/booklore_enrich/cli.py:45-50`
- Modify: `src/booklore_enrich/commands/tag.py:86`
- Test: `tests/test_cli.py`

**Step 1: Write failing tests for the new flags**

Add to `tests/test_cli.py`:

```python
def test_tag_command_has_skip_shelves_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert "--skip-shelves" in result.output


def test_tag_command_has_skip_tags_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["tag", "--help"])
    assert "--skip-tags" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_tag_command_has_skip_shelves_flag tests/test_cli.py::test_tag_command_has_skip_tags_flag -v`
Expected: FAIL — flags don't exist yet

**Step 3: Add the flags to cli.py**

In `src/booklore_enrich/cli.py`, replace the tag command definition:

```python
@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview changes without applying.")
@click.option("--skip-shelves", is_flag=True, help="Skip shelf creation, only add tags.")
@click.option("--skip-tags", is_flag=True, help="Skip tag assignment, only create shelves.")
def tag(dry_run, skip_shelves, skip_tags):
    """Push enriched metadata as tags and shelves into BookLore."""
    from booklore_enrich.commands.tag import run_tag
    run_tag(dry_run, skip_shelves=skip_shelves, skip_tags=skip_tags)
```

Update `run_tag` signature in `src/booklore_enrich/commands/tag.py`:

```python
def run_tag(dry_run: bool, skip_shelves: bool = False, skip_tags: bool = False):
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/booklore_enrich/cli.py src/booklore_enrich/commands/tag.py tests/test_cli.py
git commit -m "feat: add --skip-shelves and --skip-tags flags to tag command"
```

---

### Task 2: Implement skip logic in run_tag

**Files:**
- Modify: `src/booklore_enrich/commands/tag.py:86-164`
- Test: `tests/test_tag.py`

**Step 1: Write failing tests for skip behavior**

Add to `tests/test_tag.py`. These test that `run_tag` respects the skip flags by mocking the BookLore client. We need to verify:
- `--skip-shelves` skips the shelf loop but runs tags
- `--skip-tags` skips the tag loop but runs shelves

```python
from unittest.mock import patch, MagicMock


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

        from booklore_enrich.commands.tag import run_tag
        run_tag(dry_run=False, skip_shelves=True, skip_tags=False)

        client.create_shelf.assert_not_called()
        client.assign_books_to_shelf.assert_not_called()
        # Tags should still run
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

        from booklore_enrich.commands.tag import run_tag
        run_tag(dry_run=False, skip_shelves=False, skip_tags=True)

        # Shelves should still run
        assert client.create_shelf.call_count > 0
        # Tags should not run
        client.get_book.assert_not_called()
        client.update_book_metadata.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tag.py::test_run_tag_skip_shelves_skips_shelf_creation tests/test_tag.py::test_run_tag_skip_tags_skips_tag_assignment -v`
Expected: FAIL — skip logic not implemented yet

**Step 3: Implement skip guards in run_tag**

In `src/booklore_enrich/commands/tag.py`, modify `run_tag`:

1. Change early exit check to respect skip flags:
```python
    if not shelf_plan and not tag_plan:
        console.print("[yellow]No enrichment data found. Run 'scrape' first.[/yellow]")
        return
```
becomes:
```python
    effective_shelf_plan = shelf_plan if not skip_shelves else []
    effective_tag_plan = tag_plan if not skip_tags else {}

    if not effective_shelf_plan and not effective_tag_plan:
        console.print("[yellow]Nothing to do. Check flags or run 'scrape' first.[/yellow]")
        return
```

2. Guard the shelf loop (around line 126):
```python
        if not skip_shelves:
            # existing shelf creation code, indented one level
```

3. Guard the tag loop (around line 138):
```python
        if not skip_tags:
            # existing tag assignment code, indented one level
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tag.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/booklore_enrich/commands/tag.py tests/test_tag.py
git commit -m "feat: implement skip-shelves and skip-tags logic in run_tag"
```

---

### Task 3: Add progress bars to shelf and tag loops

**Files:**
- Modify: `src/booklore_enrich/commands/tag.py`
- Test: `tests/test_tag.py` (verify progress doesn't break behavior)

**Step 1: Write a test that verifies tagging still works end-to-end with progress**

This is a regression test — the progress bar shouldn't change behavior. Add to `tests/test_tag.py`:

```python
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

        from booklore_enrich.commands.tag import run_tag
        run_tag(dry_run=False)

        assert client.create_shelf.call_count > 0
        assert client.update_book_metadata.call_count > 0
```

**Step 2: Run the test to verify it passes (baseline)**

Run: `uv run pytest tests/test_tag.py::test_run_tag_full_run_tags_and_shelves -v`
Expected: PASS (this is a baseline before adding progress bars)

**Step 3: Add progress bars**

In `src/booklore_enrich/commands/tag.py`:

1. Add import:
```python
from rich.progress import Progress
```

2. Wrap the shelf creation loop:
```python
        if not skip_shelves:
            with Progress() as progress:
                task = progress.add_task("Creating shelves...", total=len(shelf_plan))
                for shelf in shelf_plan:
                    # existing shelf logic
                    progress.advance(task)
```

3. Wrap the tag assignment loop:
```python
        if not skip_tags:
            console.print("\nAdding category tags to books...")
            tagged = 0
            skipped = 0
            with Progress() as progress:
                task = progress.add_task("Tagging books...", total=len(tag_plan))
                for booklore_id, tags in tag_plan.items():
                    # existing tag logic
                    progress.advance(task)

            console.print(f"  Tagged {tagged} books, {skipped} already up to date.")
```

**Step 4: Run all tests to verify nothing broke**

Run: `uv run pytest tests/test_tag.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/booklore_enrich/commands/tag.py
git commit -m "feat: add rich progress bars to shelf and tag loops"
```

---

### Task 4: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 2: Run linter**

Run: `uv run ruff check src/ tests/`
Expected: No errors

**Step 3: Manual smoke test with dry-run**

Run: `uv run booklore-enrich tag --help`
Verify: Output shows `--skip-shelves`, `--skip-tags`, and `--dry-run` flags

**Step 4: Final commit if any fixes needed**

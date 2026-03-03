# Tag Command Improvements Design

## Overview

Two improvements to the `tag` command:
1. Skip flags to run shelves-only or tags-only
2. Rich progress bars for visibility during long operations

## Feature 1: Skip Flags

Add `--skip-shelves` and `--skip-tags` opt-out flags to `booklore-enrich tag`.

- Default behavior unchanged (both shelves and tags run)
- `--skip-shelves` skips shelf creation/assignment, runs tags only
- `--skip-tags` skips category tagging loop, runs shelves only
- Both flags work with `--dry-run`

### CLI changes (cli.py)
- Add two `click.option` is_flag params
- Pass through to `run_tag(dry_run, skip_shelves, skip_tags)`

### Tag command changes (commands/tag.py)
- `run_tag` signature gains `skip_shelves: bool = False, skip_tags: bool = False`
- Guard shelf loop with `if not skip_shelves`
- Guard tag loop with `if not skip_tags`
- Adjust early-exit "no data" check to only check relevant plans

## Feature 2: Progress Bars

Use `rich.progress.Progress` around both long-running loops.

### Shelf creation loop
- Progress bar showing shelf creation: `Creating shelves... X/Y`

### Tag assignment loop
- Progress bar showing book tagging: `Tagging books... X/Y`
- Print summary (tagged/skipped) after completion, same as current behavior

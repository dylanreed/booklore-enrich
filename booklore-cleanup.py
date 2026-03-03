# ABOUTME: Cleans up duplicate books in a BookLore library based on a dedup report.
# ABOUTME: Supports dry-run mode to preview changes before committing them.

"""
BookLore Library Cleanup
Phase 1: Remove exact content duplicates (keep best-organized copy)
Phase 2: Merge similar author folders into canonical "First Last" names
Requires the dedup-report.json from booklore-dedup.py.

Usage:
    python3 booklore-cleanup.py --dry-run          # Preview changes
    python3 booklore-cleanup.py --execute           # Actually do it
    python3 booklore-cleanup.py --execute --phase 1 # Only phase 1
    python3 booklore-cleanup.py --execute --phase 2 # Only phase 2
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

BOOKS_DIR = '/volume1/media/books'
REPORT_PATH = '/volume1/media/dedup-report.json'
TRASH_DIR = '/volume1/media/books-trash'


def score_path(filepath: str, books_dir: str) -> Tuple[int, str]:
    """
    Score a file path for "keep quality". Higher score = better organized.
    Prefers: First Last author folders > Last, First > scene-release style
    """
    rel = os.path.relpath(filepath, books_dir)
    parts = rel.split(os.sep)
    top_folder = parts[0] if parts else ''

    score = 0

    # Prefer paths with a clean author folder structure (subfolder per book)
    if len(parts) >= 3:
        score += 10

    # Penalize scene-release style folders (dots in folder name)
    if re.search(r'\.\d{4}\.', top_folder) or re.search(r'eBook-\w+', top_folder):
        score -= 20

    # Penalize "Last, First" format (we want "First Last")
    if ',' in top_folder:
        score -= 5

    # Penalize folders with format tags like (epub), (retail), (mobi)
    if re.search(r'\((?:epub|retail|mobi|azw3|pdf|cbz)\)', top_folder, re.IGNORECASE):
        score -= 10

    # Penalize folders with edition/source tags like (ebook by Undead), (v1.0)
    if re.search(r'\((?:ebook|v\d)', top_folder, re.IGNORECASE):
        score -= 10

    # Prefer "First Last" format (no comma, starts with capital, has space)
    if ',' not in top_folder and re.match(r'^[A-Z][a-z]+ [A-Z]', top_folder):
        score += 15

    # Prefer folders that look like just an author name (short, no book info)
    if len(top_folder) < 30 and not re.search(r'\[|\(|\.epub|\.pdf', top_folder):
        score += 5

    return (score, filepath)


def normalize_to_first_last(name: str) -> str:
    """Convert 'Last, First' to 'First Last' and clean up various formats."""
    name = name.strip()

    # Strip trailing (1), (2) etc
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)

    # Strip scene-release suffixes
    name = re.sub(r'\s*\((?:ebook|epub|retail|pdf|cbz|mobi).*?\)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*\(ebook by.*?\)\s*$', '', name, flags=re.IGNORECASE)

    # Strip leading tags like [sci-fi]
    name = re.sub(r'^\[.*?\]\s*\.?', '', name)

    # If scene-release dotted format (Author.Name.-.Book.Title...), extract author
    scene_match = re.match(
        r'^([A-Z][a-z]+(?:\.[A-Z]\.?)?(?:\.[A-Z][a-z]+)*)\.[-.]',
        name
    )
    if scene_match and '.' in scene_match.group(1):
        name = scene_match.group(1).replace('.', ' ')

    # Replace dots with spaces
    name = name.replace('.', ' ')

    # If "Author - Book Title" or "Author - [Series] - Title", extract author
    # Require space-dash-space to avoid splitting hyphenated names like "Dembski-Bowden"
    author_match = re.match(r'^(.+?)\s+-\s+(?:\[.*?\]\s*-\s*)?(?:The |A |An )?[A-Z]', name)
    if author_match:
        candidate = author_match.group(1).strip()
        if len(candidate) < 40 and not re.search(r'\d{4}', candidate):
            name = candidate

    # Handle "Last, First" -> "First Last"
    # Only flip if both parts look like human name components (no numbers, not too long)
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        if (len(parts) == 2 and parts[1]
                and not re.search(r'\d', parts[0])
                and not re.search(r'\d', parts[1])
                and len(parts[0]) < 30
                and len(parts[1]) < 30):
            name = f"{parts[1]} {parts[0]}"

    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def pick_canonical_folder(group: List[str], books_dir: str) -> str:
    """
    From a group of similar author folder names, pick the best canonical name.
    Prefers clean "First Last" format with the most books.
    """
    candidates = []
    for folder in group:
        full_path = os.path.join(books_dir, folder)
        # Count files
        file_count = 0
        for root, dirs, files in os.walk(full_path):
            dirs[:] = [d for d in dirs if d != '@eaDir' and d != '#recycle']
            file_count += len(files)

        # Score the folder name
        score = 0
        # Prefer "First Last" (no comma)
        if ',' not in folder and re.match(r'^[A-Z][a-z]+ [A-Z]', folder):
            score += 20
        # Penalize "Last, First" (but only if it looks like a name, not a franchise)
        if ',' in folder and not re.search(r'\d', folder):
            score -= 5
        # Penalize folders with extra junk
        if re.search(r'\(|\[|\.epub|\.pdf|ebook|retail', folder, re.IGNORECASE):
            score -= 15
        # Penalize dotted names
        if '..' in folder or re.search(r'\.\d{4}\.', folder):
            score -= 15
        # Prefer folders with more content
        score += file_count

        candidates.append((score, folder))

    candidates.sort(key=lambda x: (-x[0], x[1]))

    best_name = candidates[0][1]

    # If the best folder is still "Last, First", convert it
    normalized = normalize_to_first_last(best_name)
    if normalized != best_name and normalized:
        return normalized

    return best_name


def phase1_cleanup(report: dict, books_dir: str, dry_run: bool) -> Tuple[int, int]:
    """Remove exact content duplicates, keeping the best-organized copy."""
    content_dupes = report.get('content_duplicates', {})
    if not content_dupes:
        print("  No content duplicates to clean up.")
        return 0, 0

    deleted = 0
    freed_bytes = 0

    for filehash, paths in content_dupes.items():
        # Filter to paths that still exist
        existing = [p for p in paths if os.path.exists(p)]
        if len(existing) <= 1:
            continue

        # Score each path and sort (highest score = keep)
        scored = [score_path(p, books_dir) for p in existing]
        scored.sort(key=lambda x: (-x[0], x[1]))

        keep = scored[0][1]
        remove = [p for _, p in scored[1:]]

        for filepath in remove:
            size = os.path.getsize(filepath)
            rel_keep = os.path.relpath(keep, books_dir)
            rel_remove = os.path.relpath(filepath, books_dir)

            if dry_run:
                print(f"  DELETE: {rel_remove}")
                print(f"    KEEP: {rel_keep}")
            else:
                try:
                    os.remove(filepath)
                    print(f"  Deleted: {rel_remove}")
                except OSError as e:
                    print(f"  ERROR deleting {rel_remove}: {e}")
                    continue

            deleted += 1
            freed_bytes += size

    return deleted, freed_bytes


def is_franchise_folder(name: str) -> bool:
    """Check if a folder is a franchise/series prefix, not an author folder."""
    franchise_prefixes = [
        'warhammer', 'marvel', 'star wars', 'star trek', 'doctor who',
        'dungeons', 'forgotten realms', 'dragonlance', 'pathfinder',
    ]
    lower = name.lower()
    return any(lower.startswith(p) for p in franchise_prefixes)


def is_valid_author_group(group: List[str]) -> bool:
    """
    Check if a group of folders actually represents the same author,
    not just folders that happen to normalize similarly.
    Filters out franchise-prefixed folders and groups where folders
    contain different authors' books.
    """
    # If ALL folders start with a franchise prefix, skip the group
    if all(is_franchise_folder(f) for f in group):
        return False

    # If some are franchise and some aren't, still skip (they're not the same thing)
    if any(is_franchise_folder(f) for f in group):
        return False

    return True


def phase2_merge(report: dict, books_dir: str, dry_run: bool) -> int:
    """Merge similar author folders into canonical names."""
    author_groups = report.get('author_folder_groups', [])
    if not author_groups:
        print("  No author folder groups to merge.")
        return 0

    merged = 0
    skipped = 0

    for group in author_groups:
        # Filter to folders that still exist
        existing = [f for f in group if os.path.isdir(os.path.join(books_dir, f))]
        if len(existing) <= 1:
            continue

        # Skip groups that aren't real author duplicates
        if not is_valid_author_group(existing):
            skipped += 1
            continue

        canonical = pick_canonical_folder(existing, books_dir)
        canonical_path = os.path.join(books_dir, canonical)

        # Check which folders need to merge into the canonical
        to_merge = [f for f in existing if f != canonical]

        # If canonical folder doesn't exist yet (name was normalized), we need
        # to rename the best existing folder first
        if not os.path.exists(canonical_path):
            # Find the folder with the most files to use as base
            best_existing = max(
                existing,
                key=lambda f: sum(1 for _, _, files in os.walk(os.path.join(books_dir, f))
                                  for _ in files)
            )
            if dry_run:
                print(f"  RENAME: \"{best_existing}\" -> \"{canonical}\"")
            else:
                try:
                    os.rename(
                        os.path.join(books_dir, best_existing),
                        canonical_path
                    )
                    print(f"  Renamed: \"{best_existing}\" -> \"{canonical}\"")
                except OSError as e:
                    print(f"  ERROR renaming \"{best_existing}\": {e}")
                    continue
            to_merge = [f for f in to_merge if f != best_existing]

        if not to_merge:
            merged += 1
            continue

        for folder in to_merge:
            folder_path = os.path.join(books_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            if dry_run:
                print(f"  MERGE: \"{folder}\" -> \"{canonical}\"")
                # List what would move
                for root, dirs, files in os.walk(folder_path):
                    dirs[:] = [d for d in dirs if d != '@eaDir' and d != '#recycle']
                    for f in files:
                        src = os.path.join(root, f)
                        rel = os.path.relpath(src, folder_path)
                        print(f"    MOVE: {rel}")
            else:
                # Move all contents into canonical folder
                for item in os.listdir(folder_path):
                    if item in ('@eaDir', '#recycle', '.DS_Store'):
                        continue
                    src = os.path.join(folder_path, item)
                    dst = os.path.join(canonical_path, item)

                    # Handle name collision
                    if os.path.exists(dst):
                        base, ext = os.path.splitext(item) if os.path.isfile(dst) else (item, '')
                        dst = os.path.join(canonical_path, f"{base}_merged{ext}")

                    try:
                        shutil.move(src, dst)
                    except OSError as e:
                        print(f"  ERROR moving {item}: {e}")

                # Remove the now-empty folder
                try:
                    shutil.rmtree(folder_path)
                    print(f"  Merged: \"{folder}\" -> \"{canonical}\"")
                except OSError as e:
                    print(f"  ERROR removing empty folder \"{folder}\": {e}")

        merged += 1

    return merged


def cleanup_empty_dirs(books_dir: str, dry_run: bool) -> int:
    """Remove empty directories left behind after cleanup."""
    removed = 0
    for root, dirs, files in os.walk(books_dir, topdown=False):
        dirs[:] = [d for d in dirs if d != '@eaDir' and d != '#recycle']
        for d in dirs:
            dirpath = os.path.join(root, d)
            if d in ('@eaDir', '#recycle'):
                continue
            try:
                contents = [x for x in os.listdir(dirpath)
                            if x not in ('@eaDir', '#recycle', '.DS_Store',
                                         'metadata.opf', 'cover.jpg')]
                if not contents:
                    if dry_run:
                        rel = os.path.relpath(dirpath, books_dir)
                        print(f"  REMOVE EMPTY: {rel}")
                    else:
                        shutil.rmtree(dirpath)
                        rel = os.path.relpath(dirpath, books_dir)
                        print(f"  Removed empty: {rel}")
                    removed += 1
            except OSError:
                pass
    return removed


def human_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main():
    import argparse
    parser = argparse.ArgumentParser(description='BookLore Library Cleanup')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    parser.add_argument('--execute', action='store_true', help='Actually perform cleanup')
    parser.add_argument('--phase', type=int, choices=[1, 2], help='Run only this phase')
    parser.add_argument('--books-dir', default=BOOKS_DIR, help='Path to books directory')
    parser.add_argument('--report', default=REPORT_PATH, help='Path to dedup-report.json')
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Error: Must specify either --dry-run or --execute")
        sys.exit(1)

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "EXECUTING"

    print(f"BookLore Library Cleanup [{mode}]")
    print(f"{'=' * 60}")

    # Load report
    if not os.path.exists(args.report):
        print(f"Error: Report not found at {args.report}")
        print("Run booklore-dedup.py first to generate the report.")
        sys.exit(1)

    with open(args.report) as f:
        report = json.load(f)

    # Phase 1: Content duplicates
    if args.phase is None or args.phase == 1:
        print(f"\n--- PHASE 1: Removing exact content duplicates ---")
        deleted, freed = phase1_cleanup(report, args.books_dir, dry_run)
        print(f"\n  Phase 1 result: {deleted} files {'would be ' if dry_run else ''}deleted, "
              f"{human_size(freed)} {'would be ' if dry_run else ''}freed")

    # Phase 2: Merge author folders
    if args.phase is None or args.phase == 2:
        print(f"\n--- PHASE 2: Merging similar author folders ---")
        merged = phase2_merge(report, args.books_dir, dry_run)
        print(f"\n  Phase 2 result: {merged} folder groups {'would be ' if dry_run else ''}merged")

    # Cleanup empty dirs
    print(f"\n--- Cleaning up empty directories ---")
    removed = cleanup_empty_dirs(args.books_dir, dry_run)
    print(f"\n  {removed} empty directories {'would be ' if dry_run else ''}removed")

    print(f"\n{'=' * 60}")
    if dry_run:
        print("DRY RUN COMPLETE. No files were modified.")
        print("Run with --execute to apply these changes.")
    else:
        print("CLEANUP COMPLETE. Rescan your library in BookLore.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

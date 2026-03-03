# ABOUTME: Scans a book library directory for duplicate files and similar author folders.
# ABOUTME: Produces a report without modifying any files - review before taking action.

"""
BookLore Library Dedup Analyzer
Finds exact content duplicates and similar author folder names.
Python 3.8 compatible. Report-only - does not delete anything.
"""

import hashlib
import os
import re
import sys
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

BOOK_EXTENSIONS = {'.epub', '.pdf', '.cbz', '.mobi', '.azw3', '.azw', '.djvu'}
BOOKS_DIR = '/volume1/media/books'


def md5_file(filepath: str, chunk_size: int = 8192) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_book_file(filepath: str) -> bool:
    """Check if a file is a book based on extension."""
    return Path(filepath).suffix.lower() in BOOK_EXTENSIONS


def normalize_author_name(dirname: str) -> str:
    """
    Normalize an author folder name for comparison.
    Handles: dots, "Last, First", extra whitespace, case, scene-release format.
    """
    name = dirname.strip()

    # Strip scene-release style suffixes like "(ebook by Undead)", "(epub)", "(retail)"
    name = re.sub(r'\s*\((?:ebook|epub|retail|pdf|cbz|mobi).*?\)\s*', '', name, flags=re.IGNORECASE)

    # Strip leading scene-release tags like [sci-fi]
    name = re.sub(r'^\[.*?\]\s*\.?', '', name)

    # If it looks like a scene-release folder (Author.Name.-.Book.Title.Year.*)
    # extract just the author part
    scene_match = re.match(
        r'^([A-Z][a-z]+(?:\.[A-Z]\.?)?(?:\.[A-Z][a-z]+)*)\.[-.]',
        name
    )
    if scene_match and '.' in scene_match.group(1):
        name = scene_match.group(1)

    # If it looks like "Author - [Series] - Title" or "Author - Title", take just author
    book_in_folder = re.match(r'^(.+?)\s*-\s*(?:\[.*?\]\s*-\s*)?(?:The |A |An )?[A-Z].*(?:\(.*?\))?$', name)
    if book_in_folder:
        candidate = book_in_folder.group(1).strip()
        # Only use it if it looks like a name (not too long, no year patterns)
        if len(candidate) < 40 and not re.search(r'\d{4}', candidate):
            name = candidate

    # Replace dots with spaces (for scene-release names like "Alan.Bradley")
    name = name.replace('.', ' ')

    # Handle "Last, First" -> "First Last"
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        if len(parts) == 2 and parts[1]:
            name = f"{parts[1]} {parts[0]}"

    # Strip trailing (1), (2) etc
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)

    # Collapse whitespace and lowercase
    name = re.sub(r'\s+', ' ', name).strip().lower()

    return name


def find_content_duplicates(books_dir: str) -> Dict[str, List[str]]:
    """
    Find files with identical content by hashing.
    Returns dict of hash -> [list of file paths].
    """
    print("Phase 1: Scanning for content-identical duplicates...")
    print("  Indexing files by size first (fast pre-filter)...")

    # Pre-filter: group files by size (identical files must have same size)
    size_groups = defaultdict(list)
    file_count = 0

    for root, dirs, files in os.walk(books_dir):
        # Skip Synology metadata dirs
        dirs[:] = [d for d in dirs if d != '@eaDir' and d != '#recycle']
        for f in files:
            filepath = os.path.join(root, f)
            if is_book_file(filepath):
                try:
                    size = os.path.getsize(filepath)
                    size_groups[size].append(filepath)
                    file_count += 1
                except OSError:
                    pass

    print(f"  Found {file_count} book files.")

    # Only hash files that share a size with at least one other file
    candidates = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    hash_count = sum(len(paths) for paths in candidates.values())
    print(f"  {hash_count} files share sizes with other files - hashing these...")

    hash_groups = defaultdict(list)
    hashed = 0
    for size, paths in candidates.items():
        for filepath in paths:
            try:
                filehash = md5_file(filepath)
                hash_groups[filehash].append(filepath)
                hashed += 1
                if hashed % 500 == 0:
                    print(f"    Hashed {hashed}/{hash_count}...")
            except OSError:
                pass

    # Filter to only groups with actual duplicates
    duplicates = {h: paths for h, paths in hash_groups.items() if len(paths) > 1}
    return duplicates


def find_author_folder_duplicates(books_dir: str) -> List[List[str]]:
    """
    Find author folders that appear to be duplicates based on normalized names.
    Returns list of groups of folder names that normalize to the same thing.
    """
    print("\nPhase 2: Scanning for duplicate author folders...")

    normalized = defaultdict(list)
    entries = os.listdir(books_dir)

    for entry in sorted(entries):
        if entry.startswith('@') or entry.startswith('#'):
            continue
        full_path = os.path.join(books_dir, entry)
        if not os.path.isdir(full_path):
            continue

        norm = normalize_author_name(entry)
        if norm:
            normalized[norm].append(entry)

    # Filter to groups with multiple folders
    dupes = [folders for norm, folders in sorted(normalized.items()) if len(folders) > 1]
    return dupes


def count_files_in_dir(dirpath: str) -> Tuple[int, int]:
    """Count book files and total size in a directory tree."""
    count = 0
    total_size = 0
    for root, dirs, files in os.walk(dirpath):
        dirs[:] = [d for d in dirs if d != '@eaDir' and d != '#recycle']
        for f in files:
            filepath = os.path.join(root, f)
            if is_book_file(filepath):
                count += 1
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass
    return count, total_size


def human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def generate_report(books_dir: str):
    """Generate the full dedup report."""
    print(f"BookLore Dedup Analyzer")
    print(f"{'=' * 60}")
    print(f"Scanning: {books_dir}\n")

    # Phase 1: Content duplicates
    content_dupes = find_content_duplicates(books_dir)

    # Phase 2: Author folder duplicates
    author_dupes = find_author_folder_duplicates(books_dir)

    # Generate report
    print(f"\n{'=' * 60}")
    print(f"DEDUP REPORT")
    print(f"{'=' * 60}")

    # Content duplicates report
    print(f"\n--- PHASE 1: EXACT CONTENT DUPLICATES ---")
    if content_dupes:
        total_waste = 0
        dupe_count = 0
        print(f"Found {len(content_dupes)} groups of identical files:\n")
        for i, (filehash, paths) in enumerate(sorted(content_dupes.items()), 1):
            size = os.path.getsize(paths[0])
            waste = size * (len(paths) - 1)
            total_waste += waste
            dupe_count += len(paths) - 1
            print(f"  Group {i} ({human_size(size)} each, {len(paths)} copies):")
            for p in sorted(paths):
                rel = os.path.relpath(p, books_dir)
                print(f"    {rel}")
            print()

        print(f"  SUMMARY: {dupe_count} duplicate files wasting {human_size(total_waste)}")
    else:
        print("  No exact content duplicates found.")

    # Author folder duplicates report
    print(f"\n--- PHASE 2: SIMILAR AUTHOR FOLDERS ---")
    if author_dupes:
        print(f"Found {len(author_dupes)} groups of similar folder names:\n")
        for i, group in enumerate(author_dupes, 1):
            print(f"  Group {i}:")
            for folder in sorted(group):
                full_path = os.path.join(books_dir, folder)
                count, size = count_files_in_dir(full_path)
                print(f"    \"{folder}\" ({count} files, {human_size(size)})")
            print()
    else:
        print("  No similar author folders found.")

    # Save machine-readable results
    results = {
        'content_duplicates': {h: paths for h, paths in content_dupes.items()},
        'author_folder_groups': author_dupes,
    }
    report_path = os.path.join(os.path.dirname(books_dir), 'dedup-report.json')
    try:
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nMachine-readable report saved to: {report_path}")
    except OSError as e:
        print(f"\nCould not save JSON report: {e}")

    print(f"\n{'=' * 60}")
    print("NO FILES WERE MODIFIED. Review the report above before taking action.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else BOOKS_DIR
    if not os.path.isdir(target):
        print(f"Error: {target} is not a directory")
        sys.exit(1)
    generate_report(target)

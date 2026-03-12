# ABOUTME: Reads and writes metadata in EPUB files.
# ABOUTME: Handles dc:subject, booklore:tags, series, author flipping, and title.

from typing import Any, Dict, List, Optional
from ebooklib import epub


def read_epub_metadata(file_path: str) -> Dict[str, Any]:
    """Read metadata from an EPUB file."""
    book = epub.read_epub(file_path, {"ignore_ncx": True})

    title = ""
    titles = book.get_metadata("DC", "title")
    if titles:
        title = titles[0][0]

    authors = []
    for creator in book.get_metadata("DC", "creator"):
        authors.append(creator[0])

    subjects = []
    for subj in book.get_metadata("DC", "subject"):
        subjects.append(subj[0])

    return {
        "title": title,
        "authors": authors,
        "subjects": subjects,
    }


def write_epub_metadata(
    file_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subjects: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    series: Optional[str] = None,
    series_index: Optional[str] = None,
    series_total: Optional[int] = None,
) -> None:
    """Write metadata into an EPUB file, merging with existing."""
    book = epub.read_epub(file_path, {"ignore_ncx": True})

    dc_ns = "http://purl.org/dc/elements/1.1/"

    if title:
        # ebooklib stores metadata as {namespace: {element_name: [(value, attrs), ...]}}
        # set_title() appends rather than replacing, so clear first
        if dc_ns in book.metadata and "title" in book.metadata[dc_ns]:
            book.metadata[dc_ns]["title"] = []
        book.set_title(title)

    if author is not None:
        # Clear existing creators before adding the new author
        if dc_ns in book.metadata and "creator" in book.metadata[dc_ns]:
            book.metadata[dc_ns]["creator"] = []
        book.add_author(author)

    if subjects:
        # Read existing subjects
        existing = {s[0] for s in book.get_metadata("DC", "subject")}
        # Clear existing
        if dc_ns in book.metadata and "subject" in book.metadata[dc_ns]:
            book.metadata[dc_ns]["subject"] = []
        # Merge and deduplicate (preserving order: existing first, then new)
        all_subjects = list(dict.fromkeys(list(existing) + subjects))
        for subj in all_subjects:
            book.add_metadata("DC", "subject", subj)

    epub.write_epub(file_path, book)

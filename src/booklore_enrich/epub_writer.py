# ABOUTME: Reads and writes metadata in EPUB files.
# ABOUTME: Handles dc:subject, booklore:tags, series, author flipping, and title.

import json
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

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
        existing = [s[0] for s in book.get_metadata("DC", "subject")]
        # Clear existing
        if dc_ns in book.metadata and "subject" in book.metadata[dc_ns]:
            book.metadata[dc_ns]["subject"] = []
        # Merge and deduplicate (preserving order: existing first, then new)
        all_subjects = list(dict.fromkeys(list(existing) + subjects))
        for subj in all_subjects:
            book.add_metadata("DC", "subject", subj)

    epub.write_epub(file_path, book)

    # Inject custom metadata that ebooklib can't handle (custom namespaces)
    if tags or series or series_total is not None:
        _inject_custom_metadata(
            file_path,
            tags=tags,
            series=series,
            series_index=series_index,
            series_total=series_total,
        )


def _inject_custom_metadata(
    file_path: str,
    tags: Optional[List[str]] = None,
    series: Optional[str] = None,
    series_index: Optional[str] = None,
    series_total: Optional[int] = None,
) -> None:
    """Inject custom metadata directly into the OPF XML.

    Handles booklore:tags, calibre:series, belongs-to-collection, and
    booklore:series_total. Called after ebooklib writes standard metadata.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        temp_epub = f"{temp_dir}/modified.epub"
        opf_path = None
        opf_content = None

        with ZipFile(file_path, "r") as zin:
            for item in zin.namelist():
                if item.endswith(".opf"):
                    opf_path = item
                    opf_content = zin.read(item)
                    break

        if not opf_path or not opf_content:
            return

        root = ET.fromstring(opf_content)
        # Find the metadata element (may have OPF namespace prefix)
        ns_opf = "http://www.idpf.org/2007/opf"
        metadata = root.find(f"{{{ns_opf}}}metadata")
        if metadata is None:
            metadata = root.find("metadata")
        if metadata is None:
            return

        if tags:
            _inject_booklore_tags(metadata, tags)

        if series:
            _set_or_create_meta(metadata, "calibre:series", series)
            if series_index:
                _set_or_create_meta(metadata, "calibre:series_index", series_index)
            _set_or_create_property(metadata, "belongs-to-collection", series)
            if series_index:
                _set_or_create_property(metadata, "group-position", series_index)

        if series_total is not None:
            _set_or_create_property(metadata, "booklore:series_total", str(series_total))

        # Write modified OPF back into the EPUB
        modified_opf = ET.tostring(root, encoding="unicode", xml_declaration=True)
        with ZipFile(file_path, "r") as zin, ZipFile(temp_epub, "w", ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == opf_path:
                    zout.writestr(item, modified_opf)
                else:
                    zout.writestr(item, zin.read(item.filename))
        shutil.move(temp_epub, file_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _inject_booklore_tags(metadata: ET.Element, tags: List[str]) -> None:
    """Add or merge booklore:tags JSON into the metadata element."""
    existing_tags: List[str] = []
    existing_el = None
    for el in metadata:
        if el.get("property") == "booklore:tags":
            existing_el = el
            try:
                existing_tags = json.loads(el.text or "[]")
            except json.JSONDecodeError:
                existing_tags = []
            break
    merged = list(dict.fromkeys(existing_tags + tags))
    if existing_el is not None:
        existing_el.text = json.dumps(merged)
    else:
        tag_el = ET.SubElement(metadata, "meta")
        tag_el.set("property", "booklore:tags")
        tag_el.text = json.dumps(merged)


def _set_or_create_meta(metadata: ET.Element, name: str, content: str) -> None:
    """Set a <meta name="..." content="..."/> element, creating if needed."""
    for el in metadata:
        if el.get("name") == name:
            el.set("content", content)
            return
    el = ET.SubElement(metadata, "meta")
    el.set("name", name)
    el.set("content", content)


def _set_or_create_property(metadata: ET.Element, prop: str, value: str) -> None:
    """Set a <meta property="...">value</meta> element, creating if needed."""
    for el in metadata:
        if el.get("property") == prop:
            el.text = value
            return
    el = ET.SubElement(metadata, "meta")
    el.set("property", prop)
    el.text = value

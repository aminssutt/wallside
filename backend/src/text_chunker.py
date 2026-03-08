"""
Smart text chunking: section-aware splitting with junk filtering.
"""
from __future__ import annotations

import re
from typing import List

from langchain_core.documents import Document

# Patterns that identify section headings in vehicle manuals
_HEADING_PATTERNS = re.compile(
    r"^(?:"
    r"\d+[\.\-]\d*\s+\S"                  # "1.2 Title" or "3-1 Title"
    r"|[A-Z][A-Z\s]{4,}$"                 # ALL CAPS LINE (5+ chars)
    r"|(?:CHAPITRE|CHAPTER|SECTION|PARTIE|PART)\s"
    r"|#{1,3}\s"                           # Markdown headings
    r")",
    re.MULTILINE,
)

# Pages to skip entirely
_JUNK_PAGE_PATTERNS = re.compile(
    r"(?i)"
    r"(?:table\s+(?:des\s+)?mati[eè]res|table\s+of\s+contents)"
    r"|(?:^index$)"
    r"|(?:tous\s+droits\s+r[eé]serv[eé]s|all\s+rights\s+reserved)"
    r"|(?:copyright\s*©)"
    r"|(?:^page\s+\d+\s*$)"
)

MIN_PAGE_CHARS = 60          # skip pages with less meaningful text
MIN_CHUNK_CHARS = 80         # drop tiny chunks after splitting
MAX_HEADER_ONLY_RATIO = 0.6  # skip chunks that are mostly whitespace/punctuation


def is_junk_page(text: str) -> bool:
    """Return True if the page is likely a TOC, index, copyright, or blank."""
    stripped = text.strip()
    if len(stripped) < MIN_PAGE_CHARS:
        return True
    # If the whole page matches a junk pattern
    if _JUNK_PAGE_PATTERNS.search(stripped[:500]):
        # Only if the page is short or dominated by the pattern
        if len(stripped) < 400:
            return True
    return False


def _find_section_breaks(text: str) -> List[int]:
    """Return character offsets where section headings start."""
    breaks = []
    for m in _HEADING_PATTERNS.finditer(text):
        breaks.append(m.start())
    return breaks


def split_documents(
    documents: List[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Document]:
    """
    Section-aware chunker with junk filtering and precise page tracking.
    1. Merge consecutive pages into one text per PDF, tracking page offsets.
    2. Detect section headings and split at boundaries.
    3. If a section is bigger than chunk_size, sub-split with overlap.
    4. Map each chunk back to exact source pages via character offsets.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    # Group pages by source file
    file_groups: dict[str, list[Document]] = {}
    for doc in documents:
        key = doc.metadata.get("source_file", "unknown")
        file_groups.setdefault(key, []).append(doc)

    chunks: List[Document] = []

    for source_file, docs in file_groups.items():
        docs.sort(key=lambda d: d.metadata.get("page", 0))

        # Merge text while recording (start_offset, end_offset, page_num)
        merged_text = ""
        page_spans: List[tuple] = []  # (char_start, char_end, page_number)

        for doc in docs:
            text = (doc.page_content or "").strip()
            if not text or is_junk_page(text):
                continue
            page_num = doc.metadata.get("page", 0)
            start = len(merged_text)
            merged_text += text + "\n\n"
            end = len(merged_text)
            page_spans.append((start, end, page_num))

        if not merged_text.strip():
            continue

        # Find section boundaries
        breaks = _find_section_breaks(merged_text)
        if not breaks or breaks[0] != 0:
            breaks.insert(0, 0)
        breaks.append(len(merged_text))

        # Extract sections with their char ranges
        sections: List[tuple] = []  # (text, start_offset, end_offset)
        for i in range(len(breaks) - 1):
            sec_start = breaks[i]
            sec_end = breaks[i + 1]
            section_text = merged_text[sec_start:sec_end].strip()
            if section_text:
                sections.append((section_text, sec_start, sec_end))

        # Sub-split and map pages
        chunk_index = 0
        for section_text, sec_start, sec_end in sections:
            sub_chunks = _subsplit(section_text, chunk_size, chunk_overlap)
            # Track offset within the section
            offset_in_section = 0
            for sc in sub_chunks:
                if len(sc) < MIN_CHUNK_CHARS:
                    offset_in_section += len(sc)
                    continue

                # Find where this sub-chunk sits in the merged text
                sc_pos = section_text.find(sc, offset_in_section)
                if sc_pos < 0:
                    sc_pos = offset_in_section
                chunk_start = sec_start + sc_pos
                chunk_end = chunk_start + len(sc)
                offset_in_section = sc_pos + len(sc)

                # Determine which pages this chunk spans
                chunk_pages = _pages_for_range(chunk_start, chunk_end, page_spans)

                metadata = {
                    "source_file": source_file,
                    "page": _format_pages(chunk_pages),
                    "chunk_index": chunk_index,
                }
                chunks.append(Document(page_content=sc, metadata=metadata))
                chunk_index += 1

    return chunks


def _pages_for_range(
    start: int, end: int, page_spans: List[tuple]
) -> List[int]:
    """Return sorted unique page numbers that overlap with [start, end)."""
    pages = []
    for ps_start, ps_end, page_num in page_spans:
        # Check overlap: chunk [start, end) vs page [ps_start, ps_end)
        if ps_start < end and ps_end > start:
            pages.append(page_num)
    return sorted(set(pages)) if pages else []


def _format_pages(pages: List[int]) -> str:
    """Format page list into compact string: '12' or '12-14' or '12, 15, 18'."""
    if not pages:
        return "?"
    if len(pages) == 1:
        return str(pages[0])
    # Check if consecutive
    if pages[-1] - pages[0] == len(pages) - 1:
        return f"{pages[0]}-{pages[-1]}"
    return ", ".join(str(p) for p in pages)


def _subsplit(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping pieces, preferring paragraph/sentence breaks."""
    if len(text) <= chunk_size:
        return [text]

    pieces: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at paragraph, then sentence, then word boundary
        if end < text_len:
            # Look back from `end` for a good break point
            candidate = text[start:end]
            for sep in ["\n\n", "\n", ". ", "! ", "? ", ", ", " "]:
                last_sep = candidate.rfind(sep)
                if last_sep > chunk_size // 3:  # at least 1/3 into the chunk
                    end = start + last_sep + len(sep)
                    break

        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)

        if end >= text_len:
            break
        start = max(end - overlap, start + 1)

    return pieces


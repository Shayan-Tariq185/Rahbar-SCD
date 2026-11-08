"""Stage 2: Clean. Remove artefacts without destroying structure.

Rules (also written in docs/PIPELINE.md):
  1. normalise whitespace: tabs and runs of spaces become one space, 3+ blank lines become 1;
  2. join words hyphenated across a line break ("exami-\\nnation" -> "examination");
  3. drop page-number lines ("12", "Page 12", "12 of 58");
  4. drop header/footer lines: a line among the first or last three lines of a page that
     repeats (digits ignored) on more than half the pages.
Deliberately NOT stripped: numbered clause headings such as "1.21" or "5.4 Academic Warning".
They start with digits like a page number does, but citations and chunk boundaries depend on
them, so rule 3 only removes lines that are digits and nothing else, and rule 4 never touches
a line that starts with a clause number.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import Document, Page

PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?\s*$", re.IGNORECASE)
CLAUSE_START = re.compile(r"^\s*\d{1,3}(?:\.\d{1,3})*\.?\s+\S")
HYPHEN_BREAK = re.compile(r"([A-Za-z]{3,})-\n([a-z])")
EDGE_LINES = 3
MAX_HEADER_CHARS = 80      # real headers and footers are short; long lines are body text


def _shape(line: str) -> str:
    """A line with digits masked, so 'Page 3' and 'Page 4' compare equal."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip().lower()))


def _normalise(text: str) -> str:
    text = text.replace(" ", " ").replace("\r", "")
    text = HYPHEN_BREAK.sub(r"\1\2", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(lines)


def _edges(lines: list[str]) -> list[int]:
    """Indexes of the first and last EDGE_LINES non-empty lines."""
    idx = [i for i, ln in enumerate(lines) if ln.strip()]
    return idx[:EDGE_LINES] + idx[-EDGE_LINES:]


def clean(doc: Document) -> Document:
    """Strip headers and footers that repeat on most pages; keep headings and section
    boundaries, because chunking and citations depend on them."""
    texts = [_normalise(p.text).split("\n") for p in doc.pages]

    repeated: set[str] = set()
    if len(doc.pages) >= 3:
        counts: Counter[str] = Counter()
        for lines in texts:
            seen = {_shape(lines[i]) for i in _edges(lines)
                    if len(lines[i]) <= MAX_HEADER_CHARS and not CLAUSE_START.match(lines[i])}
            counts.update(s for s in seen if s)
        repeated = {s for s, n in counts.items() if n > len(doc.pages) / 2}

    pages: list[Page] = []
    for page, lines in zip(doc.pages, texts, strict=True):
        edge = set(_edges(lines))
        kept = []
        for i, line in enumerate(lines):
            if line and PAGE_NUMBER.match(line):
                continue
            if i in edge and line and len(line) <= MAX_HEADER_CHARS and _shape(line) in repeated and not CLAUSE_START.match(line):
                continue
            kept.append(line)
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
        pages.append(Page(page.source, page.page, text, page.ocr))
    return Document(doc.source, doc.doc_version, doc.superseded, pages)

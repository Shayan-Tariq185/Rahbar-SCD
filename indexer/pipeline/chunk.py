"""Stage 3: Chunk. Structure-aware, with overlap.

Unit: a "token" here is a whitespace-separated word. CHUNK_SIZE and CHUNK_OVERLAP are
counted in words, so the default 400/50 means at most 400 words per chunk, sharing up to
50 words with the previous chunk when a section is too long for one chunk.

How a document is split:
  1. Sections. A new block starts at a heading (Markdown '#', ALL-CAPS line, short numbered
     line such as "5.4 Academic Warning") and at every numbered clause ("1.21 Students ...").
     Clauses are their own blocks, so a citation can point at clause 1.21 and not at a page.
  2. A block that fits in `size` words is ONE chunk. This keeps a definition whole.
  3. A longer block is split on paragraphs, then sentences, packed up to `size` words,
     and each next chunk starts with the last `overlap` words of the previous one.
  4. Table rows are never cut: a row is one line ("Header: value | Header: value").
Every chunk carries its section label, first page, doc_version and superseded flag. Ids are
"<source>-<4-digit position>", so the same document in the same state gives the same ids.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Chunk, Document

CLAUSE = re.compile(r"^(\d{1,3}(?:\.\d{1,3})*)(\.?)\s+(\S.*)$")
MD_HEADING = re.compile(r"^#{1,6}\s+(\S.*?)\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
STOP_WORDS = {"in", "of", "the", "and", "to", "a", "for", "by", "or", "with", "on", "at",
              "is", "are", "be", "as", "an", "from", "that", "if", "shall", "will"}
MIN_CHUNK_WORDS = 3
LABEL_WORDS = 6


@dataclass
class _Block:
    section: str
    page: int
    lines: list[tuple[int, str]] = field(default_factory=list)
    has_body: bool = False


def _words(text: str) -> int:
    return len(text.split())


def _clause(line: str) -> re.Match[str] | None:
    m = CLAUSE.match(line)
    if m and ("." in m.group(1) or m.group(2) == "."):
        return m
    return None


def _heading_text(line: str) -> str | None:
    """The heading text when this line is a heading, else None."""
    stripped = line.strip()
    md = MD_HEADING.match(stripped)
    if md:
        return md.group(1)
    if _clause(stripped):
        last = stripped.split()[-1].lower().strip(".,;:")
        if len(stripped) <= 60 and stripped[-1] not in ".,;:" and last not in STOP_WORDS:
            return stripped
        return None
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    if len(stripped) >= 6 and len(letters) >= 4 and stripped.upper() == stripped \
            and len(stripped) <= 80 and ":" not in stripped:
        return stripped
    return None


def _label(match: re.Match[str]) -> str:
    number = match.group(1) + (match.group(2) or "")
    rest = " ".join(match.group(3).split()[:LABEL_WORDS]).rstrip(" ,;:.-")
    return f"{number} {rest}".strip()


def _blocks(doc: Document) -> list[tuple[_Block, str | None]]:
    """Split the document into blocks; each comes with the heading it sits under."""
    out: list[tuple[_Block, str | None]] = []
    block: _Block | None = None
    heading: str | None = None
    block_heading: str | None = None

    def start(section: str, page: int, line: str, body: bool) -> None:
        nonlocal block, block_heading
        carry: list[tuple[int, str]] = []
        if block is not None:
            if block.has_body:
                out.append((block, block_heading))
            else:                       # a heading with nothing under it joins the next block
                carry = [(p, ln) for p, ln in block.lines if ln.strip()]
        head = [item for p, ln in carry for item in ((p, ln), (p, ""))]   # one paragraph each
        block = _Block(section, page, [*head, (page, line)], has_body=body)
        block_heading = heading

    for page in doc.pages:
        for raw in page.text.split("\n"):
            line = raw.strip()
            if not line:
                if block is not None:
                    block.lines.append((page.page, ""))
                continue
            title = _heading_text(line)
            if title is not None:
                heading = title
                start(title, page.page, title, body=False)
                continue
            match = _clause(line)
            if match:
                start(_label(match), page.page, line, body=True)
                continue
            if block is None:
                start(heading or "Introduction", page.page, line, body=True)
            else:
                block.lines.append((page.page, line))
                block.has_body = True
    if block is not None and block.has_body:
        out.append((block, block_heading))
    return out


def _paragraphs(lines: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    paragraphs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for page, line in lines:
        if line.strip():
            current.append((page, line))
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _units(lines: list[tuple[int, str]], size: int) -> list[tuple[int, str]]:
    """(page, text) pieces, each at most `size` words, in reading order."""
    units: list[tuple[int, str]] = []
    for para in _paragraphs(lines):
        page = para[0][0]
        is_table = any(" | " in ln for _, ln in para)
        text = "\n".join(ln for _, ln in para) if is_table else " ".join(ln for _, ln in para)
        if _words(text) <= size:
            units.append((page, text))
            continue
        pieces = text.split("\n") if is_table else SENTENCE_END.split(text)
        for piece in pieces:
            words = piece.split()
            for i in range(0, len(words), size):          # a single huge sentence: hard cut
                units.append((page, " ".join(words[i:i + size])))
    return units


def _overlap_tail(units: list[tuple[int, str]], keep: int) -> list[tuple[int, str]]:
    """The trailing whole units (sentences or table rows) worth at most `keep` words. When
    even the last unit is too long, a prose unit is cut to its last `keep` words; a table
    row is never cut."""
    if keep <= 0 or not units:
        return []
    tail: list[tuple[int, str]] = []
    total = 0
    for page, text in reversed(units):
        w = _words(text)
        if total + w > keep:
            break
        tail.insert(0, (page, text))
        total += w
    if not tail:
        page, text = units[-1]
        if " | " not in text:
            tail = [(page, " ".join(text.split()[-keep:]))]
    return tail


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under
    `size` words, with `overlap` words shared between neighbours. Every chunk keeps
    the section heading it sits under, its page, doc_version and superseded."""
    if size < 1:
        raise ValueError("size must be at least 1")
    overlap = max(0, min(overlap, size // 2))
    chunks: list[Chunk] = []

    def emit(section: str, page: int, text: str) -> None:
        if _words(text) >= MIN_CHUNK_WORDS:
            chunks.append(Chunk(
                id=f"{doc.source}-{len(chunks):04d}", text=text, source=doc.source,
                section=section, page=page, doc_version=doc.doc_version,
                superseded=doc.superseded,
            ))

    for block, heading in _blocks(doc):
        lines = block.lines
        first = lines[0][1].strip() if lines else ""
        prefix = ""
        if heading and heading != first and not any(ln.strip() == heading for _, ln in lines):
            prefix = heading + "\n"
        budget = max(1, size - _words(prefix))
        units = _units(lines, budget)
        if not units:
            continue
        if sum(_words(t) for _, t in units) <= budget:
            emit(block.section, block.page, prefix + "\n".join(t for _, t in units))
            continue
        current: list[tuple[int, str]] = []
        used, fresh = 0, False
        for page, text in units:
            w = _words(text)
            if fresh and used + w > budget:
                emit(block.section, current[0][0], prefix + "\n".join(t for _, t in current))
                current = _overlap_tail(current, min(overlap, max(0, budget - w)))
                used, fresh = sum(_words(t) for _, t in current), False
            current.append((page, text))
            used += w
            fresh = True
        if fresh:
            emit(block.section, current[0][0], prefix + "\n".join(t for _, t in current))
    return chunks

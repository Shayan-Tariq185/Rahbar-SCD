"""Stage 1: Extract. PDF (or HTML, Markdown, text) to text, page by page.

What this stage does, in order, for a PDF page:
  1. find real tables with pdfplumber and render each row as "Header: value | Header: value"
     (so a row still carries its column names after chunking);
  2. read the remaining text, splitting two-column pages into left then right column
     (otherwise the two columns are interleaved line by line);
  3. if the page has (almost) no text layer, OCR it and mark the page ocr=True.

Known limits: tables are appended after the page's running text (their position on the page
is lost), and OCR quality depends on the scan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .models import Document, Page

# A page with fewer visible characters than this is treated as image-only. The 2023 rules
# have a stray word or two per page on otherwise scanned pages, so the bar is per page.
MIN_TEXT_CHARS = 40
OCR_DPI = 200
# A "table" needs at least this many rows and columns, so ruled boxes are not mistaken for one.
MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page, OCR-ing pages that have no text layer."""
    file = Path(path)
    suffix = file.suffix.lower()
    name = file.name
    if suffix == ".pdf":
        pages = _cached_pdf(file)
    elif suffix == ".md":
        pages = [Page(name, 1, _markdown_text(file.read_text(encoding="utf-8")))]
    elif suffix in {".html", ".htm"}:
        pages = [Page(name, 1, _html_text(file.read_text(encoding="utf-8", errors="replace")))]
    elif suffix == ".txt":
        pages = [Page(name, 1, file.read_text(encoding="utf-8", errors="replace"))]
    else:
        raise ValueError(f"cannot extract {name}: unsupported file type {suffix!r}")
    return Document(source=name, doc_version=doc_version, superseded=superseded, pages=pages)


# --------------------------------------------------------------------------- tables


def render_table(rows: list[list[str | None]]) -> list[str]:
    """One text line per data row: 'Header: value | Header: value'. The first row is the header."""
    cleaned = [[_cell(c) for c in row] for row in rows]
    cleaned = [r for r in cleaned if any(r)]
    if len(cleaned) < 2:
        return [" | ".join(c for c in r if c) for r in cleaned]
    header = cleaned[0]
    lines = []
    for row in cleaned[1:]:
        parts = []
        for i, value in enumerate(row):
            if not value:
                continue
            label = header[i] if i < len(header) and header[i] else ""
            parts.append(f"{label}: {value}" if label else value)
        if parts:
            lines.append(" | ".join(parts))
    return lines


def _cell(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


# --------------------------------------------------------------------------- markdown / html


def _markdown_text(text: str) -> str:
    """Drop the front matter block and turn pipe tables into row lines."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None)
        if end is not None:
            lines = lines[end + 1:]
    out: list[str] = []
    table: list[list[str | None]] = []

    def flush() -> None:
        nonlocal table
        if table:
            out.append("")
            out.extend(render_table(table))
            out.append("")
            table = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue                       # the | --- | --- | separator row
            table.append(list(cells))
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out).strip()


class _TextHTML(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}
    SKIP = {"script", "style", "nav", "footer", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag in {"td", "th"}:
            self.parts.append(" | ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _html_text(html: str) -> str:
    parser = _TextHTML()
    parser.feed(html)
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --------------------------------------------------------------------------- pdf


def _cached_pdf(path: Path) -> list[Page]:
    """Optional on-disk cache (set EXTRACT_CACHE_DIR) so OCR runs once while you tune chunking.
    Off by default: the Job always extracts from the baked-in file."""
    cache_dir = os.environ.get("EXTRACT_CACHE_DIR")
    if not cache_dir:
        return _extract_pdf(path)
    stat = path.stat()
    key = hashlib.sha1(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}".encode()).hexdigest()[:16]
    cached = Path(cache_dir) / f"{path.stem}-{key}.json"
    if cached.exists():
        return [Page(**p) for p in json.loads(cached.read_text(encoding="utf-8"))]
    pages = _extract_pdf(path)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps([p.__dict__ for p in pages]), encoding="utf-8")
    return pages


def _extract_pdf(path: Path) -> list[Page]:
    import pdfplumber

    pages: list[Page] = []
    with pdfplumber.open(str(path)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = _page_text(page)
            if len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
                pages.append(Page(path.name, number, ocr_page(str(path), number), ocr=True))
            else:
                pages.append(Page(path.name, number, text))
    return pages


def ocr_page(path: str, number: int) -> str:
    """OCR one page (1-based). Needs tesseract-ocr and poppler-utils on the machine."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(path, dpi=OCR_DPI, first_page=number, last_page=number)
    return str(pytesseract.image_to_string(images[0], lang="eng")).strip()


def _inside(obj: dict[str, Any], boxes: list[tuple[float, float, float, float]]) -> bool:
    try:
        cx = (obj["x0"] + obj["x1"]) / 2
        cy = (obj["top"] + obj["bottom"]) / 2
    except KeyError:
        return False
    return any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in boxes)


def _page_text(page: Any) -> str:
    boxes: list[tuple[float, float, float, float]] = []
    table_lines: list[str] = []
    try:
        for table in page.find_tables():
            rows = table.extract()
            cols = max((len(r) for r in rows), default=0)
            if len(rows) >= MIN_TABLE_ROWS and cols >= MIN_TABLE_COLS:
                boxes.append(tuple(table.bbox))
                table_lines.extend(render_table(rows))
    except Exception:  # a malformed table must not lose the page's running text
        boxes, table_lines = [], []
    body = page.filter(lambda o: not _inside(o, boxes)) if boxes else page
    text = _column_text(body)
    if table_lines:
        text = f"{text}\n\n" + "\n".join(table_lines) if text else "\n".join(table_lines)
    return text


def _column_text(page: Any) -> str:
    """Text of the page; a two-column page is read left column, then right column."""
    try:
        words = page.extract_words()
        width, height = float(page.width), float(page.height)
        mid = width / 2
        if len(words) > 80:
            crossing = sum(1 for w in words if w["x0"] < mid - 2 and w["x1"] > mid + 2)
            left = sum(1 for w in words if w["x1"] <= mid + 2)
            right = sum(1 for w in words if w["x0"] >= mid - 2)
            if crossing / len(words) < 0.03 and min(left, right) / len(words) > 0.3:
                left_text = page.crop((0, 0, mid, height)).extract_text() or ""
                right_text = page.crop((mid, 0, width, height)).extract_text() or ""
                return f"{left_text}\n{right_text}".strip()
    except Exception:  # fall back to plain reading order
        pass
    return str(page.extract_text() or "").strip()

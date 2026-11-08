"""Measure the pipeline without touching Chroma or a model. For docs/PIPELINE.md.

    python -m pipeline.stats                         # per-document table, OCR'd pages, amplification
    python -m pipeline.stats --size 200 --overlap 20
    python -m pipeline.stats --table SOURCE PAGE     # raw text vs rows for one page (before/after)
    python -m pipeline.stats --chunks SOURCE 5       # print the first 5 chunks of a document

Set EXTRACT_CACHE_DIR=/tmp/rahbar-extract to OCR each scanned PDF only once.
Storage amplification = words stored in chunks / words in the cleaned documents; it is above 1
because of overlap and because each chunk repeats its heading.
"""

from __future__ import annotations

import argparse
import time

from .chunk import chunk
from .clean import clean
from .config import get_settings
from .extract import extract
from .run import discover


def _words(text: str) -> int:
    return len(text.split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline statistics (no Chroma, no model).")
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--size", type=int, default=None)
    parser.add_argument("--overlap", type=int, default=None)
    parser.add_argument("--table", nargs=2, metavar=("SOURCE", "PAGE"))
    parser.add_argument("--chunks", nargs=2, metavar=("SOURCE", "N"))
    args = parser.parse_args()
    settings = get_settings()
    corpus = args.corpus or settings.corpus_dir
    size = args.size or settings.chunk_size
    overlap = settings.chunk_overlap if args.overlap is None else args.overlap
    found = discover(corpus)

    if args.table:
        source, page_no = args.table[0], int(args.table[1])
        path = next(p for p, _, _ in found if p.name == source)
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            page = pdf.pages[page_no - 1]
            print("=== BEFORE: pdfplumber extract_text() (what a naive extractor returns)\n")
            print(page.extract_text())
        print("\n=== AFTER: this pipeline's extract() + clean() for the same page\n")
        doc = clean(extract(str(path), "x", False))
        print(doc.pages[page_no - 1].text)
        return 0

    print(f"corpus={corpus} size={size} overlap={overlap} (words)\n")
    header = f"{'document':<58}{'pages':>6}{'ocr':>5}{'words':>9}{'chunks':>8}{'stored':>9}{'amp':>6}"
    print(header)
    total_words = total_stored = total_chunks = 0
    ocr_docs: list[str] = []
    for path, version, old in found:
        started = time.perf_counter()
        doc = clean(extract(str(path), version, old))
        pieces = chunk(doc, size, overlap)
        words = sum(_words(p.text) for p in doc.pages)
        stored = sum(_words(c.text) for c in pieces)
        ocr_pages = sum(1 for p in doc.pages if p.ocr)
        if ocr_pages:
            ocr_docs.append(f"{path.name} ({ocr_pages}/{len(doc.pages)} pages)")
        print(f"{path.name:<58}{len(doc.pages):>6}{ocr_pages:>5}{words:>9}{len(pieces):>8}"
              f"{stored:>9}{stored / max(words, 1):>6.2f}   [{time.perf_counter() - started:.0f}s]")
        total_words += words
        total_stored += stored
        total_chunks += len(pieces)
        if args.chunks and path.name == args.chunks[0]:
            for c in pieces[: int(args.chunks[1])]:
                print(f"\n--- {c.id} | section={c.section!r} page={c.page}\n{c.text}")
    print(f"\nTOTAL chunks={total_chunks} words={total_words} stored={total_stored} "
          f"amplification={total_stored / max(total_words, 1):.2f}")
    print("OCR'd documents:", "; ".join(ocr_docs) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

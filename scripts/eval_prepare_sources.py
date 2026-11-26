#!/usr/bin/env python3
"""Fetch checksum-pinned A02 sources without rewriting the corpus manifest."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from eval_bootstrap import ROOT

from ragops.evalsuite.io import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "corpus/raw")
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    parser.add_argument("--all", action="store_true", help="fetch all six sources, including scans")
    parser.add_argument("--render-review", action="store_true", help="render selected source pages for local evidence QA")
    args = parser.parse_args()
    import httpx
    import pdfplumber

    manifest = (ROOT / "corpus/MANIFEST.md").read_text(encoding="utf-8")
    pattern = re.compile(r"\| ([^|]+) \| ([^|]+) \| (yes|no) \| `([^`]+)` \| [\d,]+ \| `([0-9a-f]{64})` \| <([^>]+)>")
    documents = []
    args.out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=90,
                      headers={"User-Agent": "RAHBAR-M2-source-review/1.0"}) as client:
        for title, version, old, filename, expected, url in pattern.findall(manifest):
            if not args.all and filename not in {"academic-rules-handbook-jun-2026.pdf",
                                                 "student-handbook-jun-2026.pdf"}:
                continue
            path = args.out / filename
            if not path.exists():
                # Some official links use HTTP; HTTPS is attempted before the listed URL.
                actual_url = url.replace("http://", "https://", 1)
                response = client.get(actual_url)
                response.raise_for_status()
                data = response.content
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(f"{filename}: upstream bytes differ from the committed A02 checksum")
                path.write_bytes(data)
                time.sleep(2)
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"{filename}: cached source checksum mismatch")
            with pdfplumber.open(path) as pdf:
                # Discard text outside the visible page instead of indexing hidden overflow.
                pages = [page.crop(page.bbox).extract_text() or "" for page in pdf.pages]
            text_path = path.with_suffix(".pages.json")
            write_json(text_path, {"source": filename, "sha256": expected,
                                   "pages": [{"page": i, "text": text} for i, text in enumerate(pages, 1)]})
            documents.append({"doc_id": Path(filename).stem, "doc_version": version.strip(),
                              "source": filename, "title": title.strip(), "url": url,
                              "pages": len(pages), "superseded": old == "yes",
                              "verified_sha256": expected, "page_convention": "physical_one_based",
                              "identity_status": "filename-stem mapping; confirm against M1 ingestion inventory"})
            if args.render_review:
                import pypdfium2

                review_dir = ROOT / "tmp/source-review"
                review_dir.mkdir(parents=True, exist_ok=True)
                selected = [8, 10, 11, 12, 24, 25] if filename.startswith("academic") else [33]
                pdf_bitmap = pypdfium2.PdfDocument(path)
                for number in selected:
                    pdf_bitmap[number - 1].render(scale=1.5).to_pil().save(
                        review_dir / f"{path.stem}-page-{number}.png")
            print(f"verified {filename}: {len(pages)} pages, sha256={expected}")
    if not documents:
        raise ValueError("no manifest source entries matched")
    write_json(args.inventory, {"schema_version": "1.0", "documents": documents})
    print(f"inventory: {args.inventory}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"source preparation error: {exc}", file=sys.stderr)
        raise SystemExit(2)

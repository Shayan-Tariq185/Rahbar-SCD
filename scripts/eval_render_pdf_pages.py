#!/usr/bin/env python3
"""Render an already exported document PDF for internal layout QA."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    import pypdfium2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    document = pypdfium2.PdfDocument(args.input)
    for index, page in enumerate(document):
        page.render(scale=1.5).to_pil().save(args.out / f"page-{index + 1}.png")
    print(f"Rendered {len(document)} pages for visual QA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

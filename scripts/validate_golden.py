#!/usr/bin/env python3
"""Validate golden provenance, physical pages and optional live/pair datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT

from ragops.evalsuite.datasets import validate_golden, validate_live, validate_pairs
from ragops.evalsuite.io import read_json, read_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    parser.add_argument("--live", type=Path)
    parser.add_argument("--pairs", type=Path)
    parser.add_argument("--draft", action="store_true", help="inspect drafts; never authorizes measured runs")
    args = parser.parse_args()
    counts = validate_golden(read_jsonl(args.golden), read_json(args.inventory),
                             require_humans=not args.draft)
    if args.live:
        validate_live(read_jsonl(args.live))
    if args.pairs:
        validate_pairs(read_jsonl(args.pairs))
    print(("DRAFT ONLY " if args.draft else "VALID ") + str(counts))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"invalid golden input: {exc}", file=sys.stderr)
        raise SystemExit(2)

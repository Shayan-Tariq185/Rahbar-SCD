#!/usr/bin/env python3
"""Merge actual handwritten entries only after schema and source validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT

from ragops.evalsuite.datasets import validate_golden
from ragops.evalsuite.io import read_json, read_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    args = parser.parse_args()
    entries = read_jsonl(args.entries)
    if any(row.get("origin") != "human" for row in entries):
        raise ValueError("handwritten merge accepts only human-origin entries")
    inventory = read_json(args.inventory)
    validate_golden(entries, inventory, require_humans=False)
    if any(not row["author"].strip() or row["author"].casefold().startswith(("student ", "member ")) for row in entries):
        raise ValueError("fill actual author identities before merging")
    merged = read_jsonl(args.golden) + entries
    validate_golden(merged, inventory, require_humans=False)
    write_jsonl(args.golden, merged)
    print(f"Merged {len(entries)} human entries. Run the full validator before freezing golden v1.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"human merge error: {exc}", file=sys.stderr)
        raise SystemExit(2)

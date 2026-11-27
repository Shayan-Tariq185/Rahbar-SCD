#!/usr/bin/env python3
"""Validate and freeze a golden version without overwriting any existing snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from eval_bootstrap import ROOT

from ragops.evalsuite.datasets import load_golden
from ragops.evalsuite.io import digest, git_sha, read_json, timestamp, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    args = parser.parse_args()
    load_golden(args.golden, read_json(args.inventory))
    if args.out.exists():
        raise ValueError("frozen golden already exists; refusing to overwrite")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as stream:
        stream.write(args.golden.read_bytes())
    write_json(args.out.with_suffix(".manifest.json"),
               {"golden_sha256": digest(args.out), "inventory_sha256": digest(args.inventory),
                "frozen_at": timestamp(), "git_sha": git_sha()})
    print(f"Frozen {args.out}: {digest(args.out)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"freeze error: {exc}")
        raise SystemExit(2)

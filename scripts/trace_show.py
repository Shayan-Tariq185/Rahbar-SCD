#!/usr/bin/env python3
"""Reconstruct exact retrieved evidence and prompt for a query by trace_id (D2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragops.trace import find_trace, format_trace_reconstruction  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and reconstruct a query trace by trace_id.")
    parser.add_argument("trace_id", help="Trace ID to inspect")
    parser.add_argument("--traces-dir", type=Path, default=Path("traces"), help="Directory of *.jsonl traces")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print full trace JSON")
    args = parser.parse_args(argv)

    trace = find_trace(args.trace_id, args.traces_dir)
    if trace is None:
        print(f"ERROR: trace_id {args.trace_id!r} not found in {args.traces_dir}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(trace, indent=2))
    else:
        print(format_trace_reconstruction(trace))
    return 0


if __name__ == "__main__":
    sys.exit(main())

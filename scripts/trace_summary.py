#!/usr/bin/env python3
"""Summarize query traces over a time window (D3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragops.trace import load_traces, summarize_traces  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize query traces (similarity, rates, p95, injections).")
    parser.add_argument("--traces-dir", type=Path, default=Path("traces"), help="Directory of *.jsonl traces")
    parser.add_argument("--since", default="24h", help="Time window (e.g. 1h, 24h, 30m, all)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON only")
    args = parser.parse_args(argv)

    try:
        traces = load_traces(args.traces_dir, since=args.since)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summary = summarize_traces(traces)
    summary["traces_dir"] = str(args.traces_dir)
    summary["since"] = args.since

    if args.as_json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"=== Trace Summary (dir={args.traces_dir}, since={args.since}) ===")
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

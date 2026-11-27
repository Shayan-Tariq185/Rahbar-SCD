#!/usr/bin/env python3
"""Collect genuine human faithfulness labels from exact real answers and contexts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

from ragops.evalsuite.clients import decode_query
from ragops.evalsuite.io import digest, read_json, read_jsonl, timestamp, write_jsonl
from ragops.evalsuite.runner import evidence_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--limit", type=int, default=4)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise ValueError("faithfulness labeling requires a human in an interactive terminal")
    if not args.reviewer.strip() or args.reviewer.casefold().startswith(("student ", "member ")):
        raise ValueError("use your actual reviewer identity")
    suite = read_json(args.results)
    if suite["identity"]["provenance"] != "real" or suite["errors"]:
        raise ValueError("labels must reference a real error-free suite")
    labels = read_jsonl(args.out) if args.out.exists() else []
    seen = {label["evidence_sha256"] for label in labels}
    count = 0
    for row in suite["runs"][0]["queries"]:
        evidence = decode_query(row["evidence"])
        key = evidence_hash(evidence)
        if not evidence.answered_from_context or key in seen:
            continue
        print(f"\nQuery {row['golden_id']}; trace {evidence.trace_id}\nANSWER:\n{evidence.answer}")
        for passage in evidence.retrieval.passages:
            print(f"\nCONTEXT {passage.doc_id} {passage.doc_version}, physical page {passage.page}:\n{passage.text}")
        decision = input("Are all material factual claims supported? [yes/no/skip/quit]: ").strip().lower()
        if decision == "quit":
            break
        if decision == "skip":
            continue
        if decision not in {"yes", "no"}:
            raise ValueError("invalid human label")
        notes = input("Explain the support or unsupported claim: ").strip()
        if not notes:
            raise ValueError("actual human review notes are required")
        labels.append({"golden_id": row["golden_id"], "evidence": row["evidence"],
                       "evidence_sha256": key, "source_suite_sha256": digest(args.results),
                       "reviewer": args.reviewer, "reviewed_at": timestamp(),
                       "supported": decision == "yes", "notes": notes})
        write_jsonl(args.out, labels)
        seen.add(key)
        count += 1
        if count >= args.limit:
            break
    print(f"Saved {count} genuine human labels.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"labeling error: {exc}", file=sys.stderr)
        raise SystemExit(2)

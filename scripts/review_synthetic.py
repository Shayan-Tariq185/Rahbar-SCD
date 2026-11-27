#!/usr/bin/env python3
"""Interactive human review with original source-page text; never auto-accepts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT

from ragops.evalsuite.io import digest, read_json, read_jsonl, timestamp, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    parser.add_argument("--source-dir", type=Path, default=ROOT / "corpus/raw")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise ValueError("human review requires an interactive terminal; piped/generated decisions are rejected")
    if args.reviewer.strip().casefold() in {"student 1", "student 2", "member 1", "member 2", ""}:
        raise ValueError("use your actual name for review provenance")
    if args.limit < 1:
        raise ValueError("limit must be positive")
    rows = read_jsonl(args.golden)
    inventory = {(d["doc_id"], d["doc_version"]): d for d in read_json(args.inventory)["documents"]}
    before_hash = digest(args.golden)
    reviewed = 0
    for row in rows:
        if row["origin"] != "synthetic" or any(r["reviewer"] == args.reviewer for r in row["reviews"]):
            continue
        print(f"\n{row['id']}: {row['question']}\nExpected: {row['expected_behavior']}; hard={row['hard']}")
        for relevant in row["relevant"]:
            doc = inventory[(relevant["doc_id"], relevant["doc_version"])]
            source = args.source_dir / doc["source"]
            if digest(source) != doc["verified_sha256"]:
                raise ValueError("review source bytes differ from inventory")
            pages = read_json(source.with_suffix(".pages.json"))["pages"]
            print(f"SOURCE {doc['source']}, physical page {relevant['page']}, section {relevant.get('section')}")
            print(pages[relevant["page"] - 1]["text"])
        if not row["relevant"]:
            print("Unanswerable: check the documented corpus scope; absence needs human judgment.")
        decision = input("Your decision [accept/reject/skip/quit]: ").strip().lower()
        if decision == "quit":
            break
        if decision == "skip":
            continue
        if decision not in {"accept", "reject"}:
            raise ValueError("invalid decision; nothing saved for this question")
        notes = input("Explain your source/page/answerability review: ").strip()
        if not notes:
            raise ValueError("review notes are required")
        row["reviews"].append({"reviewer": args.reviewer, "reviewed_at": timestamp(),
                               "decision": decision, "notes": notes})
        if digest(args.golden) != before_hash:
            raise ValueError("golden file changed during review; refusing to overwrite")
        write_jsonl(args.golden, rows)
        before_hash = digest(args.golden)
        reviewed += 1
        if reviewed >= args.limit:
            break
    print(f"Saved {reviewed} actual human review decisions.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"review error: {exc}", file=sys.stderr)
        raise SystemExit(2)

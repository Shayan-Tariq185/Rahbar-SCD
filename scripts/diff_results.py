#!/usr/bin/env python3
"""Compare fixed-golden suite metrics and per-query retrieval/answer changes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

from ragops.evalsuite.io import digest, read_json, run_id, write_json
from ragops.evalsuite.metrics import differences
from ragops.gate import measured_suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--kind", choices=["drift", "experiment"], default="drift")
    parser.add_argument("--verification", type=Path)
    args = parser.parse_args()
    before, after = read_json(args.baseline), read_json(args.candidate)
    measured_suite(before)
    measured_suite(after)
    for key in ("golden_sha256", "pairs_sha256", "judge", "provider", "seeds"):
        if before[key] != after[key]:
            raise ValueError(f"fixed-test comparison cannot change {key}")
    if args.kind == "drift" and before["config"] != after["config"]:
        raise ValueError("data drift comparison must hold pipeline/evaluation configuration fixed")
    if args.kind == "experiment" and before["identity"]["corpus_sha256"] != after["identity"]["corpus_sha256"]:
        raise ValueError("one-variable experiment cannot compare different corpora")
    query_changes = []
    for repeat_index, (old_run, new_run) in enumerate(zip(before["runs"], after["runs"], strict=True), 1):
        new_rows = {row["golden_id"]: row for row in new_run["queries"]}
        for row in old_run["queries"]:
            old = row["evidence"]
            new = new_rows[row["golden_id"]]["evidence"]
            fields = {}
            for key in ("answer", "answered_from_context", "citations"):
                if old[key] != new[key]:
                    fields[key] = {"before": old[key], "after": new[key]}
            if old["retrieval"]["passages"] != new["retrieval"]["passages"]:
                fields["retrieval"] = {"before": old["retrieval"]["passages"], "after": new["retrieval"]["passages"]}
            if fields:
                query_changes.append({"repeat": repeat_index, "golden_id": row["golden_id"],
                                      "before_trace": old["trace_id"], "after_trace": new["trace_id"],
                                      "changes": fields})
    result = {"kind": args.kind, "baseline_sha256": digest(args.baseline),
              "candidate_sha256": digest(args.candidate), "golden_sha256": before["golden_sha256"],
              "repeat_deltas": [differences(old, new) for old, new in zip(before["runs"], after["runs"], strict=True)],
              "query_changes": query_changes,
              "verification": read_json(args.verification) if args.verification else None}
    args.out.mkdir(parents=True, exist_ok=True)
    stem = run_id("comparison")
    write_json(args.out / (stem + ".json"), result)
    lines = [f"# {args.kind.title()} comparison", "", f"Changed per-query records: {len(query_changes)}.",
             "The JSON contains every metric delta and exact before/after ranks, versions, answers and citations.",
             "A data-drift comparison is not a release gate; explain measured changes using the linked verification inventory."]
    (args.out / (stem + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(args.out / (stem + ".json"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"comparison error: {exc}", file=sys.stderr)
        raise SystemExit(2)

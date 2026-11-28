#!/usr/bin/env python3
"""Draft six gap questions only after the fixed-golden drift and pre-expansion evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

from ragops.evalsuite.io import digest, read_json, read_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-v1", required=True, type=Path)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--drift-comparison", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    before = read_json(args.before)
    drift = read_json(args.drift_comparison)
    if before.get("mode") != "complete" or before.get("provenance") != "real":
        raise ValueError("save real pre-expansion coverage first")
    if before["golden_sha256"] != digest(args.golden_v1) or drift.get("kind") != "drift":
        raise ValueError("fixed golden v1 drift/coverage identity mismatch")
    if drift["golden_sha256"] != before["golden_sha256"]:
        raise ValueError("finish A versus A+B with the same golden v1 before expansion")
    if not any(group["topic"] == "campus IT account recovery" for group in before["topic_groups"]):
        raise ValueError("observed gaps differ; draft questions from the actual uncovered topics instead")
    if args.out.exists():
        raise ValueError("refusing to overwrite golden v2 or its human reviews")
    questions = [
        "What documented steps recover a forgotten campus mailbox password?",
        "How can a student regain wireless access after an account lockout?",
        "What is the approved process for enrolling a replacement device in campus Wi-Fi?",
        "How is access recovered when the second authentication factor is unavailable?",
        "What should a student do after university email credentials are stolen?",
        "Which documented support process handles a deactivated learning-platform login?",
    ]
    added = [{"schema_version": "1.0", "id": f"gap-{i:02d}", "question": question,
              "origin": "synthetic", "author": "Codex", "answerable": False, "hard": False,
              "expected_behavior": "abstain", "relevant": [], "reviews": [], "batches": ["A", "AB"],
              "notes": f"Gap draft from real coverage {digest(args.before)}; corpus IT procedure absent; human topic/scope review pending."}
             for i, question in enumerate(questions, 1)]
    added.append({"schema_version": "1.0", "id": "gap-credit-01",
                  "question": "What do the two numbers in a 3+1 course credit notation represent?",
                  "origin": "synthetic", "author": "Codex", "answerable": True, "hard": False,
                  "expected_behavior": "answer",
                  "relevant": [{"doc_id": "academic-rules-handbook-jun-2026", "doc_version": "2026-06",
                                "page": 8, "section": "1.12"}], "reviews": [], "batches": ["A"],
                  "notes": "AI source-checked against physical PDF p8, rule 1.12: three theory credits plus one lab credit, four total. User confirmed this test gap. Valid for the A-based production/experiment snapshot; the synthetic B policy supersedes this document in AB. No additional human question review is claimed."})
    write_jsonl(args.out, read_jsonl(args.golden_v1) + added)
    print(f"Drafted seven synthetic gap questions into {args.out}; preserve v1. Six IT recovery questions expect abstention; one source-checked credit question expects an answer on the A-based snapshot.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"expansion error: {exc}")
        raise SystemExit(2)

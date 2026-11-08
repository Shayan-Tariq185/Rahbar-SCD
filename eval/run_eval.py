#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails. CI relies on that exit code.

Given: talking to the API, reading the golden set, writing results.json, and the exit
code. The evaluation functions below calculate recall, citation validity, summaries,
and the CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4. Change these only with a reason written in docs/PIPELINE.md.
MAX_RECALL5_DROP = 0.05        # recall@5 may fall at most 5 points below the baseline
MIN_CITATION_VALIDITY = 0.95   # at least 95% of citations must match retrieved passages
REQUIRED_ABSTENTION = 1.0      # every must-abstain question must be declined


def load_golden(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    return questions


def ask(client: httpx.Client, api: str, question: str) -> dict:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py)."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    return response.json()


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Return None when the question has no relevant passages (must-abstain questions)."""
    if not relevant:
        return None

    def matches(expected: dict, actual: dict) -> bool:
        if expected.get("source") != actual.get("source"):
            return False
        expected_section = str(expected.get("section", "")).strip()
        actual_section = str(actual.get("section", "")).strip()
        return actual_section == expected_section or actual_section.startswith(
            expected_section + " "
        )

    top = retrieved[:k]
    found = sum(any(matches(expected, actual) for actual in top) for expected in relevant)
    return found / len(relevant)


def citation_validity(response: dict) -> float | None:
    """Fraction of the response's citations that match a passage in response['retrieved'].
    Return None when there are no citations."""
    citations = response.get("citations") or []
    if not citations:
        return None
    retrieved = response.get("retrieved") or []
    valid = {
        (item.get("source"), item.get("section"), item.get("page"))
        for item in retrieved
    }
    matched = sum(
        (citation.get("source"), citation.get("section"), citation.get("page")) in valid
        for citation in citations
    )
    return matched / len(citations)


def summarise(rows: list[dict]) -> dict:
    """Overall recall@3, recall@5, citation validity and abstention correctness, plus
    recall@5 broken down by question type. This dict becomes results.json."""
    def average(values: list[float | None]) -> float | None:
        present = [value for value in values if value is not None]
        return sum(present) / len(present) if present else None

    for row in rows:
        response = row.get("response") or {}
        retrieved = response.get("retrieved") or []
        row["recall_at_3"] = recall_at_k(row["relevant"], retrieved, 3)
        row["recall_at_5"] = recall_at_k(row["relevant"], retrieved, 5)
        row["citation_validity"] = citation_validity(response)
        row["abstention_correct"] = (
            response.get("answered_from_context") is False
            if row.get("must_abstain")
            else None
        )

    by_type: dict[str, dict[str, float | None]] = {}
    for row in rows:
        question_type = str(row.get("type", "ordinary"))
        group = by_type.setdefault(question_type, {"recall_at_5": None})
        values = [
            item["recall_at_5"]
            for item in rows
            if item.get("type", "ordinary") == question_type
        ]
        group["recall_at_5"] = average(values)

    abstentions = [row["abstention_correct"] for row in rows if row["must_abstain"]]
    abstention_rate = (
        sum(bool(value) for value in abstentions) / len(abstentions)
        if abstentions
        else None
    )
    return {
        "recall_at_3": average([row["recall_at_3"] for row in rows]),
        "recall_at_5": average([row["recall_at_5"] for row in rows]),
        "citation_validity": average([row["citation_validity"] for row in rows]),
        "abstention_correctness": abstention_rate,
        "by_type": by_type,
    }


def gate(results: dict, baseline: dict | None) -> list[str]:
    """Return one message per failed gate (section 5.4); an empty list means pass."""
    failures: list[str] = []
    recall5 = results.get("recall_at_5")
    if recall5 is None:
        failures.append("recall@5 is unavailable")
    if baseline is not None:
        baseline_recall = baseline.get("recall_at_5")
        if baseline_recall is not None and recall5 is not None:
            if recall5 < baseline_recall - MAX_RECALL5_DROP:
                failures.append(
                    f"recall@5 dropped from {baseline_recall:.3f} to {recall5:.3f}"
                )

    citation = results.get("citation_validity")
    if citation is None or citation < MIN_CITATION_VALIDITY:
        failures.append(
            f"citation validity {citation!r} is below {MIN_CITATION_VALIDITY:.2f}"
        )

    abstention = results.get("abstention_correctness")
    if abstention is None or abstention < REQUIRED_ABSTENTION:
        failures.append(
            f"must-abstain correctness {abstention!r} is below "
            f"{REQUIRED_ABSTENTION:.2f}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--golden", type=Path, default=HERE / "golden.yaml")
    parser.add_argument("--baseline", type=Path, default=HERE / "baseline.json")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write these results as the new baseline")
    args = parser.parse_args()

    questions = load_golden(args.golden)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        for q in questions:
            started = time.perf_counter()
            response = ask(client, args.api, q["question"])
            rows.append({
                "id": q["id"], "type": q.get("type", "ordinary"),
                "must_abstain": bool(q.get("must_abstain", False)),
                "relevant": q.get("relevant") or [],
                "expect": q.get("expect"),
                "response": response,
                "seconds": round(time.perf_counter() - started, 2),
            })
            print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")

    try:
        results = summarise(rows)
        baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
        failures = gate(results, baseline)
    except NotImplementedError as exc:
        print(f"\nnot implemented yet: {exc}")
        return 2

    results["golden"] = str(args.golden)
    results["questions"] = len(rows)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    if args.update_baseline:
        args.baseline.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"baseline updated: {args.baseline}")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

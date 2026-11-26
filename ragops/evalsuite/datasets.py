"""Golden provenance, source inventory and simulated-query validation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_jsonl, schema_check


def validate_golden(rows: list[dict[str, Any]], inventory: dict[str, Any], *,
                    require_humans: bool = True) -> dict[str, int]:
    ids: set[str] = set()
    questions: set[str] = set()
    authors: Counter[str] = Counter()
    reviewers: dict[str, set[str]] = {}
    counts = {"total": len(rows), "answerable": 0, "unanswerable": 0, "hard": 0,
              "human": 0, "reviewed_synthetic": 0}
    documents = {(d["doc_id"], d["doc_version"]): d for d in inventory["documents"]}
    for row in rows:
        schema_check("golden", row)
        if row["id"] in ids:
            raise ValueError(f"duplicate golden ID: {row['id']}")
        normalized = " ".join(row["question"].casefold().split())
        if normalized in questions:
            raise ValueError(f"duplicate golden question: {row['id']}")
        ids.add(row["id"])
        questions.add(normalized)
        counts["answerable" if row["answerable"] else "unanswerable"] += 1
        counts["hard"] += int(row["hard"])
        for relevant in row["relevant"]:
            if not relevant.get("doc_version"):
                raise ValueError(f"{row['id']}: ground truth requires an explicit document version")
            key = (relevant["doc_id"], relevant["doc_version"])
            if key not in documents:
                raise ValueError(f"{row['id']}: document/version absent from source inventory: {key}")
            doc = documents[key]
            if relevant["page"] > doc["pages"]:
                raise ValueError(f"{row['id']}: physical page outside document")
            if not doc.get("verified_sha256"):
                raise ValueError(f"{row['id']}: source bytes not verified")
        if row["origin"] == "human":
            author = row["author"].strip()
            if author.casefold() in {"student 1", "student 2", "member 1", "member 2", "todo"}:
                raise ValueError(f"{row['id']}: human author must be an actual identity")
            authors[author] += 1
            counts["human"] += 1
        else:
            if any(review["decision"] == "reject" for review in row["reviews"]):
                raise ValueError(f"{row['id']}: resolve rejected synthetic question before evaluation")
            accepted = [review for review in row["reviews"] if review["decision"] == "accept"]
            if accepted:
                counts["reviewed_synthetic"] += 1
            for review in accepted:
                if review["reviewer"].strip().casefold() in {"student 1", "student 2", "member 1", "member 2", "todo"}:
                    raise ValueError(f"{row['id']}: reviewer must be an actual identity")
                reviewers.setdefault(review["reviewer"], set()).add(row["id"])
    if require_humans:
        for name, minimum in (("total", 25), ("answerable", 15), ("unanswerable", 5),
                              ("hard", 5), ("human", 8), ("reviewed_synthetic", 8)):
            if counts[name] < minimum:
                raise ValueError(f"golden {name}: {counts[name]}, requires >= {minimum}")
        if len([author for author, count in authors.items() if count >= 4]) < 2:
            raise ValueError("each of two actual members must write at least four questions")
        if len([name for name, reviewed in reviewers.items() if len(reviewed) >= 4]) < 2:
            raise ValueError("each of two actual members must accept at least four synthetic reviews")
    return counts


def validate_live(rows: list[dict[str, Any]]) -> None:
    if len(rows) < 40:
        raise ValueError("live simulation requires at least 40 queries")
    ids = [row.get("id") for row in rows]
    questions = [" ".join(str(row.get("query", "")).casefold().split()) for row in rows]
    if len(set(ids)) != len(ids) or len(set(questions)) != len(questions):
        raise ValueError("live IDs and query texts must be unique")
    for row in rows:
        if not row.get("id") or not str(row.get("query", "")).strip() or not row.get("topic"):
            raise ValueError("live rows require id, query and topic")
        if row.get("provenance") != "simulated" or row.get("origin") not in {"synthetic", "human"}:
            raise ValueError("live queries must explicitly identify simulated provenance and origin")
    if sum(row.get("uncovered_topic") is True for row in rows) < 12:
        raise ValueError("live simulation requires at least 12 uncovered-topic queries")


def validate_pairs(rows: list[dict[str, Any]]) -> None:
    if len({row.get("id") for row in rows}) != len(rows):
        raise ValueError("embedding pair IDs must be unique")
    for label in ("paraphrase", "unrelated"):
        if sum(row.get("label") == label for row in rows) < 15:
            raise ValueError(f"requires >=15 {label} pairs")
    for row in rows:
        if row.get("label") not in {"paraphrase", "unrelated"}:
            raise ValueError("unknown pair label")
        if not str(row.get("a", "")).strip() or not str(row.get("b", "")).strip():
            raise ValueError("embedding pair text must be nonempty")


def load_golden(path: Path, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    validate_golden(rows, inventory)
    return rows

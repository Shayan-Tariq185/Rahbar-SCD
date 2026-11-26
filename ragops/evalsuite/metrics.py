"""Hand-computable retrieval metrics, cosine and latency statistics."""

from __future__ import annotations

import math
import random
import re
from statistics import mean
from typing import Any

from .contracts import RankedPassage
from .io import finite


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("cosine requires equal nonempty dimensions")
    if any(not math.isfinite(value) for value in (*left, *right)):
        raise ValueError("non-finite embedding coordinate")
    denominator = math.sqrt(sum(v * v for v in left) * sum(v * v for v in right))
    if denominator == 0:
        raise ValueError("zero embedding vector")
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        raise ValueError("percentile of an empty sample")
    finite(percentile_value, minimum=0, maximum=100)
    ordered = sorted(finite(value, minimum=0) for value in values)
    position = (len(ordered) - 1) * percentile_value / 100
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def metric(values: list[float], unit: str, *, na_reason: str = "no eligible samples") -> dict[str, Any]:
    return {"value": mean(values) if values else None, "unit": unit, "samples": len(values),
            "na_reason": None if values else na_reason}


def retrieval_metrics(relevant: list[dict[str, Any]], passages: tuple[RankedPassage, ...]) -> dict[str, float] | None:
    if not relevant:
        return None
    canonical = list(dict.fromkeys((r["doc_id"], r.get("doc_version"), r["page"],
                                   r.get("section"), r.get("chunk_id")) for r in relevant))

    def matches(target: tuple[Any, ...], passage: RankedPassage) -> bool:
        doc, version, page, section, chunk = target
        if (doc, page) != (passage.doc_id, passage.page):
            return False
        if version is not None and version != passage.doc_version:
            return False
        if chunk is not None:
            return bool(chunk == passage.chunk_id)
        # Golden sections may be clause numbers, but never prefix-match 1.2 with 1.20.
        return bool(section == passage.section or passage.section.startswith(str(section) + " "))

    seen: set[int] = set()
    hits = []
    for passage in passages:
        hit = next((index for index, target in enumerate(canonical)
                    if index not in seen and matches(target, passage)), None)
        hits.append(int(hit is not None))
        if hit is not None:
            seen.add(hit)
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(len(canonical), 5)))
    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits[:5]))
    first = next((rank for rank, hit in enumerate(hits, 1) if hit), None)
    return {"recall_at_3": sum(hits[:3]) / len(canonical),
            "recall_at_5": sum(hits[:5]) / len(canonical),
            "mrr": 1 / first if first is not None else 0.0, "ndcg_at_5": dcg / ideal}


def typo(question: str, seed: int) -> str:
    candidates = list(re.finditer(r"[A-Za-z]{4,}", question))
    if not candidates:
        raise ValueError("query has no eligible word for deterministic typo perturbation")
    rng = random.Random(seed)
    word = rng.choice(candidates)
    position = rng.randrange(word.start() + 1, word.end() - 1)
    return question[:position] + question[position + 1:]


def differences(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in sorted(set(first) | set(second)):
        a, b = first.get(key), second.get(key)
        if isinstance(a, dict) and "value" in a and isinstance(b, dict) and "value" in b:
            left, right = a["value"], b["value"]
            result[key] = {"run1": left, "run2": right,
                           "delta": right - left if left is not None and right is not None else None,
                           "absolute_variation": abs(right - left) if left is not None and right is not None else None,
                           "unit": a["unit"]}
        elif isinstance(a, dict) and isinstance(b, dict):
            result[key] = differences(a, b)
    return result

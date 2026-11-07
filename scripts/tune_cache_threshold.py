#!/usr/bin/env python3
"""Semantic Cache Threshold Tuning Tool (Track A).

Evaluates cosine similarity across paraphrase pairs and near-miss pairs to determine
the optimal CACHE_THRESHOLD for RAHBAR's Redis semantic cache.

Usage:
    python scripts/tune_cache_threshold.py [--data eval/fixtures/cache_tuning_pairs.json]
                                           [--thresholds 0.80,0.88,0.93]
                                           [--use-real]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

# Ensure repository root and api/ are on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _fallback_hash_vector(text: str, dim: int = 768) -> list[float]:
    """Deterministic normalized hash vector used when Track B embedder is unavailable."""
    values: list[float] = []
    seed = text.encode("utf-8")
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        values.extend((b - 127.5) / 127.5 for b in seed)
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def get_embedder() -> tuple[Any, str]:
    """Resolve embedding function: app.embedding.embed_query or fallback hash embedder."""
    try:
        from app.embedding import embed_query  # type: ignore

        # Probe to see if it returns a non-empty vector
        sample = embed_query("test probe")
        if sample and isinstance(sample, list) and len(sample) > 0:
            return embed_query, "app.embedding.embed_query (Track B active)"
    except Exception:
        pass

    return _fallback_hash_vector, "fallback hashing-768 (Track B not yet merged or Ollama offline)"


def cosine_sim(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def evaluate_thresholds(
    paraphrases: list[dict[str, str]],
    near_misses: list[dict[str, str]],
    embed_fn: Any,
    thresholds: list[float],
) -> None:
    print("\n" + "=" * 80)
    print("PAIR-BY-PAIR SIMILARITY SCORES")
    print("=" * 80)

    para_scores: list[tuple[dict[str, str], float]] = []
    print("\n[PARAPHRASE PAIRS - Should hit cache (similarity >= threshold)]")
    for idx, item in enumerate(paraphrases, 1):
        v1 = embed_fn(item["q1"])
        v2 = embed_fn(item["q2"])
        sim = cosine_sim(v1, v2)
        para_scores.append((item, sim))
        print(f"  P{idx:02d} [{sim:.4f}] Q1: {item['q1'][:45]}... | Q2: {item['q2'][:45]}...")

    near_scores: list[tuple[dict[str, str], float]] = []
    print("\n[NEAR-MISS PAIRS - Must NOT hit cache (similarity < threshold)]")
    for idx, item in enumerate(near_misses, 1):
        v1 = embed_fn(item["q1"])
        v2 = embed_fn(item["q2"])
        sim = cosine_sim(v1, v2)
        near_scores.append((item, sim))
        print(f"  NM{idx:02d} [{sim:.4f}] Q1: {item['q1'][:45]}... | Q2: {item['q2'][:45]}...")

    print("\n" + "=" * 80)
    print("THRESHOLD BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"{'Threshold':<12} | {'Paraphrase Hits':<18} | {'Hit Rate (Recall)':<20} | "
          f"{'False Hits':<12} | {'False Hit Rate':<16} | {'Recommendation'}")
    print("-" * 95)

    n_para = len(paraphrases)
    n_near = len(near_misses)

    for thresh in sorted(thresholds):
        hits = sum(1 for _, s in para_scores if s >= thresh)
        false_hits = sum(1 for _, s in near_scores if s >= thresh)
        hit_rate = (hits / n_para * 100.0) if n_para else 0.0
        false_hit_rate = (false_hits / n_near * 100.0) if n_near else 0.0

        if false_hits > 0:
            verdict = "UNSAFE (serves wrong answer!)"
        elif hit_rate >= 80.0:
            verdict = "EXCELLENT (high hit rate, 0 false hits)"
        else:
            verdict = "SAFE (conservative, lower cache hit rate)"

        print(f"{thresh:<12.2f} | {hits}/{n_para:<16} | {hit_rate:>6.1f}%{'':<13} | "
              f"{false_hits}/{n_near:<10} | {false_hit_rate:>6.1f}%{'':<9} | {verdict}")

    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tune CACHE_THRESHOLD for semantic caching.")
    parser.add_argument(
        "--data",
        default="eval/fixtures/cache_tuning_pairs.json",
        help="Path to pair dataset JSON file.",
    )
    parser.add_argument(
        "--thresholds",
        default="0.80,0.88,0.93",
        help="Comma-separated list of similarity thresholds to test.",
    )
    parser.add_argument(
        "--use-real",
        action="store_true",
        help="Evaluate on 'real_corpus' pairs instead of 'fixtures'.",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        print(f"Error: Dataset file not found at {data_path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error reading JSON from {data_path}: {exc}", file=sys.stderr)
        return 1

    section_key = "real_corpus" if args.use_real else "fixtures"
    dataset = payload.get(section_key, {})
    paraphrases = dataset.get("paraphrases", [])
    near_misses = dataset.get("near_misses", [])

    if not paraphrases or not near_misses:
        print(f"Error: Section '{section_key}' does not contain both paraphrases and near_misses.",
              file=sys.stderr)
        return 1

    thresholds = [float(t.strip()) for t in args.thresholds.split(",") if t.strip()]

    embed_fn, embed_label = get_embedder()
    print("\n" + "=" * 80)
    print(f"RAHBAR Semantic Cache Threshold Tuning Tool")
    print(f"Dataset : {data_path} (section: {section_key})")
    print(f"Embedder: {embed_label}")
    print(f"Counts  : {len(paraphrases)} paraphrases, {len(near_misses)} near-misses")
    print(f"Testing : {thresholds}")
    print("=" * 80)

    evaluate_thresholds(paraphrases, near_misses, embed_fn, thresholds)
    return 0


if __name__ == "__main__":
    sys.exit(main())


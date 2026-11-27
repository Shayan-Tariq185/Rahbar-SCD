"""Nearest-golden semantic coverage with separate cosine cutoff and coverage floor."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .evalsuite.clients import OllamaEmbeddingClient
from .evalsuite.contracts import EmbeddingClient, EmbeddingIdentity, EvaluationError
from .evalsuite.datasets import load_golden, validate_live
from .evalsuite.io import ROOT, digest, finite, read_config, read_json, read_jsonl, run_id, schema_check, timestamp, write_json
from .evalsuite.metrics import cosine


def measure(golden: list[dict[str, Any]], live: list[dict[str, Any]], embedder: EmbeddingClient, *,
            cutoff: float, floor: float, reviewers: dict[str, str] | None = None) -> dict[str, Any]:
    cutoff = finite(cutoff, minimum=-1, maximum=1)
    floor = finite(floor, minimum=0, maximum=1)
    texts = tuple([row["question"] for row in golden] + [row["query"] for row in live])
    vectors: list[tuple[float, ...]] = []
    identity = None
    provenance = None
    for start in range(0, len(texts), 16):
        batch = embedder.embed(texts[start:start + 16], task="query", fresh=True)
        if batch.cache_hit or len(batch.vectors) != len(texts[start:start + 16]):
            raise EvaluationError("coverage embedding batch is cached or incomplete")
        if identity is not None and (identity != batch.identity or provenance != batch.provenance):
            raise EvaluationError("coverage embedding identity changed")
        identity, provenance = batch.identity, batch.provenance
        vectors.extend(batch.vectors)
    if identity is None or not golden or not live:
        raise ValueError("coverage requires nonempty golden and live datasets")
    golden_vectors = vectors[:len(golden)]
    query_rows = []
    groups: dict[str, list[str]] = {}
    for row, vector in zip(live, vectors[len(golden):], strict=True):
        scores = [cosine(vector, reference) for reference in golden_vectors]
        best = max(range(len(scores)), key=lambda index: scores[index])
        covered = scores[best] >= cutoff
        query_rows.append({"id": row["id"], "query": row["query"],
                           "nearest_golden_id": golden[best]["id"], "similarity": scores[best],
                           "covered": covered, "topic": row["topic"]})
        if not covered:
            groups.setdefault(row["topic"], []).append(row["id"])
    coverage = sum(row["covered"] for row in query_rows) / len(query_rows)
    passed = coverage >= floor
    histogram = [{"low": low, "high": high,
                  "count": sum(low <= row["similarity"] < high or (high == 1 and row["similarity"] == 1)
                               for row in query_rows)}
                 for low, high in ((-1, 0), (0, .25), (.25, .5), (.5, .65), (.65, .75), (.75, .85), (.85, 1))]
    return {"schema_version": "1.0", "artifact_type": "coverage_report", "timestamp": timestamp(),
            "provenance": provenance, "embedding": asdict(identity), "similarity_cutoff": cutoff,
            "coverage_floor": floor, "coverage": coverage, "decision": "pass" if passed else "fail",
            "exit_code": 0 if passed else 1, "queries": query_rows,
            "topic_groups": [{"topic": topic, "query_ids": ids,
                              "human_confirmed_by": (reviewers or {}).get(topic)} for topic, ids in sorted(groups.items())],
            "similarity_distribution": histogram, "errors": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--live", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    parser.add_argument("--calibration-only", action="store_true", help="inspect distribution; no coverage policy decision")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    identifier = run_id("coverage")
    try:
        golden = load_golden(args.golden, read_json(args.inventory))
        live = read_jsonl(args.live)
        validate_live(live)
        config = read_config(args.config)
        input_hashes = {"golden": digest(args.golden), "live": digest(args.live), "config": digest(args.config)}
        if not args.calibration_only and not config.get("frozen"):
            raise ValueError("justify and freeze cutoff/floor before final coverage measurements")
        if not args.calibration_only and config.get("live_sha256") != digest(args.live):
            raise ValueError("coverage live set differs from the frozen policy")
        model = config["embedding"]
        if not model.get("digest"):
            raise ValueError("coverage configuration must pin the real resolved embedding digest")
        expected = EmbeddingIdentity(model["model"], model["digest"], model["dimension"])
        embedder = OllamaEmbeddingClient(config["embedding_url"], expected.model, expected=expected)
        embedder.verify_identity()
        result = measure(golden, live, embedder, cutoff=config["similarity_cutoff"],
                          floor=config["coverage_floor"], reviewers=config.get("topic_reviewers"))
        embedder.verify_identity()
        for name, path in (("golden", args.golden), ("live", args.live), ("config", args.config)):
            if digest(path) != input_hashes[name]:
                raise ValueError(f"{name} input changed during coverage measurement")
        result.update({"run_id": identifier, "golden_sha256": digest(args.golden),
                       "live_sha256": digest(args.live), "config_sha256": digest(args.config),
                       "mode": "calibration" if args.calibration_only else "complete",
                       "rationale": config["rationale"]})
        schema_check("coverage_report", result)
        write_json(args.out / (identifier + ".json"), result)
        lines = ["# Query coverage", "", f"Mode: {result['mode']}",
                 f"Coverage: {result['coverage']:.2%}; floor: {result['coverage_floor']:.2%}; cosine cutoff: {result['similarity_cutoff']}",
                 "", "| Uncovered topic | Query IDs | Human confirmation |", "| --- | --- | --- |"]
        lines += [f"| {group['topic']} | {', '.join(group['query_ids'])} | {group['human_confirmed_by'] or 'pending'} |"
                  for group in result["topic_groups"]]
        lines += ["", "Semantic test-question coverage does not establish corpus answerability."]
        (args.out / (identifier + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        print(f"coverage_json={args.out / (identifier + '.json')}")
        return 0 if args.calibration_only else int(result["exit_code"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        write_json(args.out / (identifier + ".error.json"),
                   {"artifact_type": "coverage_error", "run_id": identifier, "errors": [str(exc)]})
        print(f"coverage input/runtime error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

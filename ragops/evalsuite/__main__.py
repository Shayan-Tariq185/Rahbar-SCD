"""Run all three evaluation levels against an integrated real target."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from .clients import HttpApiClient, OllamaEmbeddingClient, OllamaJudge
from .datasets import load_golden, validate_pairs
from .io import ROOT, digest, git_sha, read_json, read_jsonl, run_id, schema_check, timestamp, write_json
from .runner import run_suite


def save_summary(path: Path, result: dict[str, Any]) -> None:
    lines = ["# Three level evaluation", "", f"Run: {result['run_id']}",
             f"Mode: {result['mode']}; collection: {result['identity']['collection']}; revision: {result['identity']['revision']}",
             "", "| Level | Metric | Run 1 | Run 2 | Difference | Unit |",
             "| --- | --- | ---: | ---: | ---: | --- |"]
    for level in ("module", "component", "noisy_component", "e2e"):
        for name, record in result["runs"][0][level].items():
            a, b = record["value"], result["runs"][1][level][name]["value"]
            delta = b - a if a is not None and b is not None else None
            formatted = ["NA" if value is None else f"{value:.6g}" for value in (a, b, delta)]
            lines.append(f"| {level} | {name} | {' | '.join(formatted)} | {record['unit']} |")
    lines += ["", "Noise deltas are noisy minus clean; repeat differences are run 2 minus run 1.",
              "MRR uses all returned ranks. Recall@3/@5 and nDCG@5 use at most those ranks;",
              "a serving top-k below five can return fewer than five passages.",
              "Faithfulness excludes abstentions. Citation validity excludes uncited abstentions.",
              "Latency measures client-observed ask calls, excluding offline judge time.",
              f"Human validation: {result['human_validation']}",
              "Fixed client/noise seeds do not imply deterministic provider inference."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-api", required=True)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config/corpus-inventory.json")
    parser.add_argument("--golden-version", default="v1")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--embedding-url", default=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"))
    parser.add_argument("--judge-url")
    parser.add_argument("--judge-model", default="llama3.2:3b")
    parser.add_argument("--human-labels", type=Path)
    parser.add_argument("--collect-labels", action="store_true", help="preliminary capture; cannot be a baseline or release result")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    identifier = run_id("suite")
    try:
        golden = load_golden(args.golden, read_json(args.inventory))
        pairs = read_jsonl(args.pairs)
        validate_pairs(pairs)
        labels = read_jsonl(args.human_labels) if args.human_labels else []
        if not labels and not args.collect_labels:
            raise ValueError("supply >=8 human faithfulness labels, or use explicit preliminary --collect-labels")
        api = HttpApiClient(args.target_api)
        identity = api.identity()
        embedding = OllamaEmbeddingClient(args.embedding_url, identity.embedding.model,
                                          expected=identity.embedding)
        embedding.verify_identity()
        judge = OllamaJudge(args.judge_url or args.embedding_url, args.judge_model)
        judge_info = judge.identity()
        metadata = {
            "run_id": identifier, "git_sha": git_sha(), "golden_sha256": digest(args.golden),
            "golden_version": args.golden_version, "pairs_sha256": digest(args.pairs),
            "provider": api.metadata["provider"],
            "judge": {"method": "ollama_llm", "rubric_sha256": judge_info["rubric_sha256"],
                      "identity": judge_info,
                      "human_labels_sha256": digest(args.human_labels) if args.human_labels else None},
            "input_hashes": {"golden": digest(args.golden), "pairs": digest(args.pairs),
                             "inventory": digest(args.inventory)},
        }
        result = run_suite(api, embedding, judge, golden=golden, pairs=pairs, metadata=metadata,
                            labels=labels, repeat=args.repeat, seed=args.seed)
        embedding.verify_identity()
        judge.verify_identity()
        for name, path in (("golden", args.golden), ("pairs", args.pairs), ("inventory", args.inventory)):
            if digest(path) != metadata["input_hashes"][name]:
                raise ValueError(f"{name} input changed during the suite; discard this run")
        if args.human_labels and digest(args.human_labels) != metadata["judge"]["human_labels_sha256"]:
            raise ValueError("human labels changed during the suite; discard this run")
        result["mode"] = "label_collection" if args.collect_labels else "complete"
        result["seed_support"] = {"provider": api.metadata.get("seed_support", False),
                                  "python": True, "noise": True}
        schema_check("suite_result", result)
        if not args.collect_labels and not result["human_validation"]["faithfulness_complete"]:
            raise ValueError("requires >=8 unique actual human labels, at least four from each member")
        result_path = args.out / (identifier + ".json")
        write_json(result_path, result)
        save_summary(args.out / (identifier + ".md"), result)
        print((args.out / (identifier + ".md")).read_text(encoding="utf-8"))
        print(f"suite_json={result_path}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        write_json(args.out / (identifier + ".error.json"),
                   {"schema_version": "1.0", "artifact_type": "suite_error", "run_id": identifier,
                    "timestamp": timestamp(), "errors": [str(exc)], "metrics": None})
        print(f"suite input/runtime error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""One complete measured suite, repeated with fixed seeds and cold answer caches."""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict
from statistics import mean
from typing import Any

from .contracts import ApiClient, EmbeddingClient, EvaluationError, Judge, QueryEvidence
from .io import object_hash, timestamp
from .metrics import cosine, differences, metric, percentile, retrieval_metrics, typo


def evidence_hash(evidence: QueryEvidence) -> str:
    return object_hash({"answer": evidence.answer,
                        "context": [asdict(passage) for passage in evidence.retrieval.passages]})


def _embedding(embedding: EmbeddingClient, texts: tuple[str, ...], *, task: str,
               expected: dict[str, Any]) -> Any:
    from typing import cast
    from .contracts import EmbeddingTask

    result = embedding.embed(texts, task=cast(EmbeddingTask, task), fresh=True)
    if result.cache_hit or len(result.vectors) != len(texts):
        raise EvaluationError("embedding measurement returned cached or incomplete vectors")
    if result.identity.digest != expected["digest"] or result.identity.dimension != expected["dimension"]:
        raise EvaluationError("measured embeddings differ from deployed model/dimension")
    return result


def module_metrics(embedding: EmbeddingClient, pairs: list[dict[str, Any]],
                   chunk_texts: tuple[str, ...], identity: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not chunk_texts:
        raise EvaluationError("no real retrieved chunks available to measure embedding time per chunk")
    similarities: dict[str, list[float]] = {"paraphrase": [], "unrelated": []}
    pair_records = []
    # Bound batches as the production indexer does, instead of one enormous request.
    for start in range(0, len(pairs), 8):
        batch = pairs[start:start + 8]
        texts = tuple(text for row in batch for text in (row["a"], row["b"]))
        result = _embedding(embedding, texts, task="query", expected=identity)
        for offset, row in enumerate(batch):
            left, right = result.vectors[offset * 2:offset * 2 + 2]
            score = cosine(left, right)
            similarities[row["label"]].append(score)
            pair_records.append({"id": row["id"], "label": row["label"], "cosine": score,
                                 "left_vector_sha256": object_hash(left),
                                 "right_vector_sha256": object_hash(right)})
    chunk_batch = _embedding(embedding, chunk_texts, task="document", expected=identity)
    first = _embedding(embedding, (chunk_texts[0],), task="document", expected=identity)
    second = _embedding(embedding, (chunk_texts[0],), task="document", expected=identity)
    largest = max(abs(a - b) for a, b in zip(first.vectors[0], second.vectors[0], strict=True))
    values = {"paraphrase_cosine_mean": metric(similarities["paraphrase"], "cosine"),
              "unrelated_cosine_mean": metric(similarities["unrelated"], "cosine"),
              "cosine_gap": metric([mean(similarities["paraphrase"]) - mean(similarities["unrelated"])],
                                     "cosine_difference"),
              "embedding_ms_per_chunk": metric([chunk_batch.latency_ms / len(chunk_texts)], "ms"),
              "identical_text_max_difference": metric([largest], "coordinate_difference")}
    return values, {"pairs": pair_records, "timed_chunks": len(chunk_texts),
                    "chunk_batch_ms": chunk_batch.latency_ms,
                    "determinism_first": first.vectors[0], "determinism_second": second.vectors[0],
                    "identity": asdict(first.identity), "fresh_requests": True}


def calibration(judge: Judge, labels: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    from .clients import decode_query

    people: dict[str, int] = {}
    seen: set[str] = set()
    rows = []
    confusion = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    for label in labels:
        reviewer = str(label.get("reviewer", "")).strip()
        if not reviewer or reviewer.casefold().startswith(("student ", "member ")):
            raise ValueError("faithfulness labels need actual reviewer identities")
        if type(label.get("supported")) is not bool or not label.get("reviewed_at") or not label.get("notes"):
            raise ValueError("faithfulness label needs human decision, date and notes")
        evidence = decode_query(label["evidence"])
        if evidence.retrieval.identity.provenance != "real" or not evidence.answered_from_context:
            raise ValueError("human faithfulness labels must reference real answered query evidence")
        key = evidence_hash(evidence)
        if key != label.get("evidence_sha256") or key in seen:
            raise ValueError("label evidence hash mismatch or duplicate labelled answer")
        seen.add(key)
        people[reviewer] = people.get(reviewer, 0) + 1
        prediction = judge.assess(evidence, seed=seed)
        if prediction.provenance != "real":
            raise EvaluationError("synthetic judge cannot calibrate real human labels")
        human, predicted = label["supported"], prediction.supported
        category = ("true_positive" if human else "false_positive") if predicted else (
            "false_negative" if human else "true_negative")
        confusion[category] += 1
        rows.append({"trace_id": evidence.trace_id, "evidence_sha256": key,
                     "reviewer": reviewer, "human": human, "judge": predicted, "agree": human == predicted,
                     "judge_explanation": prediction.explanation})
    complete = len(rows) >= 8 and len([person for person, count in people.items() if count >= 4]) >= 2
    return {"complete": complete, "agreement": metric([float(row["agree"]) for row in rows], "fraction"),
            "rows": rows, "confusion": confusion, "reviewer_counts": people}


def run_suite(api: ApiClient, embedding: EmbeddingClient, judge: Judge, *,
              golden: list[dict[str, Any]], pairs: list[dict[str, Any]],
              metadata: dict[str, Any], labels: list[dict[str, Any]], repeat: int = 2,
              seed: int = 42, golden_validated: bool = True) -> dict[str, Any]:
    if repeat < 2:
        raise ValueError("repeat the whole suite at least twice")
    identity = api.identity()
    identity_dict = asdict(identity)
    top_k = json.loads(identity.config_json).get("top_k")
    if type(top_k) is not int or top_k < 1:
        raise EvaluationError("runtime identity is missing effective top_k")
    if identity.provenance == "real":
        calibration_result = calibration(judge, labels, seed)
    else:
        calibration_result = {"complete": False, "agreement": metric([], "fraction"),
                              "rows": [], "confusion": {}, "reviewer_counts": {}}
    runs = []
    trace_ids: set[str] = set()
    for repeat_index in range(1, repeat + 1):
        random.seed(seed)
        component_rows: list[dict[str, float]] = []
        noisy_rows: list[dict[str, float]] = []
        query_rows = []
        perturbations = []
        faithful: list[float] = []
        citations: list[float] = []
        abstention: list[float] = []
        latencies: list[float] = []
        chunk_texts: dict[str, str] = {}
        group_rows: dict[str, list[dict[str, float]]] = {"hard": [], "ordinary": [], "version_sensitive": []}
        for index, row in enumerate(golden):
            question = row["question"]
            retrieved = api.retrieve(question, k=top_k, seed=seed)
            if retrieved.identity != identity:
                raise EvaluationError("collection/config identity changed during retrieval evaluation")
            for passage in retrieved.passages:
                chunk_texts.setdefault(passage.chunk_id, passage.text)
            scores = retrieval_metrics(row["relevant"], retrieved.passages)
            if scores is not None:
                component_rows.append(scores)
                group_rows["hard" if row["hard"] else "ordinary"].append(scores)
                if row.get("version_sensitive"):
                    group_rows["version_sensitive"].append(scores)
            perturbed = typo(question, seed + index)
            noisy = api.retrieve(perturbed, k=top_k, seed=seed)
            if noisy.identity != identity:
                raise EvaluationError("runtime identity changed during noise evaluation")
            noisy_scores = retrieval_metrics(row["relevant"], noisy.passages)
            if noisy_scores is not None:
                noisy_rows.append(noisy_scores)
            perturbations.append({"golden_id": row["id"], "original": question,
                                  "perturbed": perturbed, "changed": perturbed != question,
                                  "retrieved": [asdict(p) for p in noisy.passages]})
            started = time.perf_counter()
            evidence = api.ask(question, use_cache=False, seed=seed)
            elapsed = (time.perf_counter() - started) * 1000
            if evidence.retrieval.identity != identity or evidence.errors or evidence.cache_hit:
                raise EvaluationError("query has changed identity, pipeline errors or an answer-cache hit")
            if evidence.trace_id in trace_ids:
                raise EvaluationError("runtime reused a trace ID across distinct evaluation calls")
            trace_ids.add(evidence.trace_id)
            if evidence.answered_from_context:
                assessment = judge.assess(evidence, seed=seed)
                if assessment.provenance != identity.provenance:
                    raise EvaluationError("judge provenance differs from runtime provenance")
                faithful.append(float(assessment.supported))
            else:
                assessment = None
            valid_refs = {(p.source, p.section, p.page) for p in evidence.retrieval.passages}
            citation_score = None
            if evidence.citations:
                citation_score = sum((c.source, c.section, c.page) in valid_refs for c in evidence.citations) / len(evidence.citations)
            elif evidence.answered_from_context:
                citation_score = 0.0
            if citation_score is not None:
                citations.append(citation_score)
            if not row["answerable"]:
                abstention.append(float(not evidence.answered_from_context))
            latencies.append(elapsed)
            per_query = {"citation_validity": metric([] if citation_score is None else [citation_score], "fraction"),
                         "faithfulness": metric([] if assessment is None else [float(assessment.supported)], "fraction"),
                         "latency_ms": metric([elapsed], "ms")}
            query_rows.append({"golden_id": row["id"], "evidence": asdict(evidence),
                               "metrics": per_query, "judge": asdict(assessment) if assessment else None,
                               "component_retrieval": asdict(retrieved)})
        module, module_evidence = module_metrics(embedding, pairs, tuple(list(chunk_texts.values())[:16]),
                                                 asdict(identity.embedding))
        component = {key: metric([row[key] for row in component_rows], "fraction")
                     for key in ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")}
        noisy_component = {key: metric([row[key] for row in noisy_rows], "fraction") for key in component}
        e2e = {"faithfulness": metric(faithful, "fraction", na_reason="no non-abstaining answers"),
               "citation_validity": metric(citations, "fraction"),
               "abstention_correctness": metric(abstention, "fraction"),
               "latency_p50_ms": metric([percentile(latencies, 50)], "ms"),
               "latency_p95_ms": metric([percentile(latencies, 95)], "ms"),
               "judge_human_agreement": calibration_result["agreement"]}
        runs.append({"repeat": repeat_index, "module": module, "module_evidence": module_evidence,
                     "component": component, "noisy_component": noisy_component,
                     "noise_deltas": differences(component, noisy_component), "e2e": e2e,
                     "queries": query_rows, "perturbations": perturbations,
                     "by_group": {group: {key: metric([row[key] for row in group_values], "fraction")
                                          for key in component} for group, group_values in group_rows.items()}})
        if api.identity() != identity:
            raise EvaluationError("runtime changed before the repeat completed")
    result = {**metadata, "schema_version": "1.0", "artifact_type": "suite_result",
              "timestamp": timestamp(), "identity": identity_dict,
              "config": {"top_k": top_k, "noise": "one seeded character deletion in eligible word",
                         "retrieval_depth_policy": "effective serving top_k", "percentile": "linear interpolation"},
              "seeds": {"python": seed, "noise": seed, "provider_requested": seed},
              "cache_policy": "cold", "runs": runs, "differences": differences(runs[0], runs[1]),
              "errors": [], "human_validation": {"golden_complete": golden_validated,
                                                   "faithfulness_complete": calibration_result["complete"]},
              "judge_calibration": calibration_result}
    return result

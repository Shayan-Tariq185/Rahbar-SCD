"""Fail-closed release comparisons for the chosen one-variable top-k experiment."""

from __future__ import annotations

import json
from typing import Any

from .evalsuite.io import finite, object_hash, schema_check, timestamp


def measured_suite(value: dict[str, Any]) -> None:
    schema_check("suite_result", value)
    if value["identity"]["provenance"] != "real" or value.get("test_only"):
        raise ValueError("synthetic fixture results cannot authorize release")
    if value.get("mode") != "complete":
        raise ValueError("preliminary label-collection results cannot authorize release")
    if value["errors"] or len(value["runs"]) < 2:
        raise ValueError("suite has errors or fewer than two complete repeats")
    if value["cache_policy"] != "cold":
        raise ValueError("release comparison requires cold generated-answer caches")
    if not value.get("human_validation", {}).get("golden_complete"):
        raise ValueError("golden human provenance validation is missing")
    if not value.get("human_validation", {}).get("faithfulness_complete"):
        raise ValueError("faithfulness human labels/agreement are incomplete")
    for run in value["runs"]:
        for query in run["queries"]:
            evidence = query["evidence"]
            if evidence["errors"] or evidence["cache_hit"]:
                raise ValueError("suite contains pipeline errors or answer-cache hits")
            if evidence["retrieval"]["identity"] != value["identity"]:
                raise ValueError("per-query runtime identity differs from suite identity")


def _metric(suite: dict[str, Any], level: str, name: str, *, worst: str) -> float:
    values = []
    for run in suite["runs"]:
        record = run[level][name]
        unit = "ms" if name.endswith("_ms") else "fraction"
        if record["unit"] != unit or record["samples"] < 1 or record["na_reason"] is not None:
            raise ValueError(f"invalid or unavailable required metric {level}.{name}")
        values.append(finite(record["value"], minimum=0, maximum=1 if unit == "fraction" else None))
    return min(values) if worst == "min" else max(values)


def metric_checks(baseline: dict[str, Any], candidate: dict[str, Any],
                  policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure threshold math; this function alone never authorizes a release."""
    drop = finite(policy["max_recall5_drop"], minimum=0, maximum=1)
    checks = []
    for level, name, direction, limit in (
        ("component", "recall_at_5", "min", _metric(baseline, "component", "recall_at_5", worst="min") - drop),
        ("e2e", "faithfulness", "min", finite(policy["min_faithfulness"], minimum=0, maximum=1)),
        ("e2e", "citation_validity", "min", finite(policy["min_citation_validity"], minimum=0, maximum=1)),
        ("e2e", "latency_p95_ms", "max", finite(policy["max_p95_latency_ms"], minimum=0)),
        ("e2e", "abstention_correctness", "min", max(
            finite(policy["min_abstention_correctness"], minimum=0, maximum=1),
            _metric(baseline, "e2e", "abstention_correctness", worst="min"))),
    ):
        base = _metric(baseline, level, name, worst=direction)
        value = _metric(candidate, level, name, worst=direction)
        passed = value >= limit if direction == "min" else value <= limit
        checks.append({"metric": f"{level}.{name}", "baseline": base, "candidate": value,
                       "threshold": limit, "passed": passed,
                       "reason": f"{value:.6g} {'>=' if direction == 'min' else '<='} {limit:.6g}"})
    return checks


def decide(baseline: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any], *,
           baseline_hash: str, candidate_hash: str, policy_hash: str,
           current_identity: dict[str, Any]) -> dict[str, Any]:
    measured_suite(baseline)
    measured_suite(candidate)
    if policy.get("schema_version") != "1.0" or policy.get("declared_change") != "top_k":
        raise ValueError("this experiment supports exactly one declared change: top_k")
    if policy.get("policy_mode") not in {"release", "demo"}:
        raise ValueError("unknown gate policy mode")
    if not policy.get("frozen") or policy.get("baseline_sha256") != baseline_hash:
        raise ValueError("freeze a justified policy against this measured baseline before evaluating candidates")
    if not str(policy.get("rationale", "")).strip():
        raise ValueError("gate rationale is required")
    if current_identity != candidate["identity"]:
        raise ValueError("candidate collection/config revision is stale or differs from the running target")
    for key in ("golden_sha256", "golden_version", "pairs_sha256", "seeds", "provider", "judge", "git_sha"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"incompatible comparison: {key} changed")
    before = baseline["identity"]
    after = candidate["identity"]
    for key in ("embedding", "corpus_sha256", "api_image"):
        if before[key] != after[key]:
            raise ValueError(f"incompatible runtime identity: {key} changed")
    if not before.get("vector_sha256") or before["vector_sha256"] != after.get("vector_sha256"):
        raise ValueError("matching vector snapshot fingerprints are required for a top-k-only experiment")
    configs = [json.loads(identity["config_json"]) for identity in (before, after)]
    top_ks = [config.pop("top_k", None) for config in configs]
    if any(type(value) is not int or value < 1 for value in top_ks):
        raise ValueError("effective top_k must be a positive integer")
    if configs[0] != configs[1]:
        raise ValueError("more than one effective pipeline setting changed")
    suite_configs = [dict(value["config"]) for value in (baseline, candidate)]
    for config in suite_configs:
        config.pop("top_k", None)
    if suite_configs[0] != suite_configs[1]:
        raise ValueError("evaluation configuration changed")
    checks = metric_checks(baseline, candidate, policy)
    passed = all(check["passed"] for check in checks)
    changed = top_ks[0] != top_ks[1]
    result = {
        "schema_version": "1.0", "artifact_type": "gate_decision", "timestamp": timestamp(),
        "decision": "pass" if passed else "fail", "exit_code": 0 if passed else 1,
        "release_authorized": passed and changed and policy["policy_mode"] == "release",
        "policy_mode": policy["policy_mode"], "baseline_sha256": baseline_hash,
        "candidate_sha256": candidate_hash, "policy_sha256": policy_hash,
        "baseline_identity": before, "candidate_identity": after,
        "golden_sha256": candidate["golden_sha256"],
        "declared_change": {"parameter": "top_k", "baseline": top_ks[0], "candidate": top_ks[1]},
        "checks": checks, "errors": [],
        "smoke_comparison": not changed, "decision_identity_sha256": object_hash(after),
    }
    return result


if __name__ == "__main__":
    from .evalsuite.gate_cli import entrypoint

    raise SystemExit(entrypoint())

"""Run under pytest with eval/requirements-dev.txt installed; no network calls."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from fakes import fixture_query
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[3] / "config/schemas/h0.schema.json")
    .read_text(encoding="utf-8")
)


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]},
        format_checker=FormatChecker(),
    )


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_adapter_serialization_matches_wire_schema() -> None:
    value = json.loads(json.dumps(asdict(fixture_query()), allow_nan=False))
    validator("query_evidence").validate(value)


def test_golden_checks_answerability_and_provenance_fields() -> None:
    question = {
        "schema_version": "1.0", "id": "test-only", "question": "What is required?",
        "origin": "synthetic", "author": "test generator", "answerable": True,
        "hard": True, "expected_behavior": "answer",
        "relevant": [{"doc_id": "self-made", "page": 1, "section": "1"}],
        "reviews": [], "batches": ["A"], "notes": "test-only, never evidence",
    }
    checker = validator("golden")
    checker.validate(question)
    for patch in ({"relevant": []}, {"origin": "AI-but-human"}, {"author": ""},
                  {"expected_behavior": "abstain"}, {"question": "  "}):
        assert not checker.is_valid({**question, **patch})
    abstain = {**question, "answerable": False, "expected_behavior": "abstain", "relevant": []}
    checker.validate(abstain)


@pytest.mark.parametrize("value,unit", [(1.1, "fraction"), (-1, "ms"), (2, "cosine")])
def test_metric_units_have_bounds(value: float, unit: str) -> None:
    assert not validator("metric").is_valid(
        {"value": value, "unit": unit, "samples": 1, "na_reason": None}
    )


def test_na_metric_has_explicit_reason_and_empty_samples() -> None:
    validator("metric").validate(
        {"value": None, "unit": "fraction", "samples": 0, "na_reason": "no answered queries"}
    )
    assert not validator("metric").is_valid(
        {"value": None, "unit": "fraction", "samples": 0, "na_reason": None}
    )


def test_demo_policy_can_never_authorize_release() -> None:
    identity = asdict(fixture_query().retrieval.identity)
    decision = {
        "schema_version": "1.0", "artifact_type": "gate_decision",
        "timestamp": "2026-11-25T00:00:00Z", "decision": "pass", "exit_code": 0,
        "release_authorized": False, "policy_mode": "demo",
        "baseline_sha256": "a" * 64, "candidate_sha256": "b" * 64,
        "policy_sha256": "c" * 64, "golden_sha256": "d" * 64,
        "baseline_identity": identity, "candidate_identity": identity,
        "declared_change": {"parameter": "top_k", "baseline": 5, "candidate": 1},
        "checks": [], "errors": [],
    }
    checker = validator("gate_decision")
    checker.validate(decision)
    assert not checker.is_valid({**decision, "release_authorized": True})
    assert not checker.is_valid({**decision, "exit_code": 1})
    assert not checker.is_valid({**decision, "decision": "fail", "release_authorized": True})
    assert not checker.is_valid({**decision, "policy_mode": "release", "release_authorized": True})

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from fakes import FakeApiClient, FakeEmbeddingClient, FakeJudge, fixture_query

from ragops.coverage import measure
from ragops.evalsuite.contracts import EvaluationError
from ragops.evalsuite.datasets import validate_golden, validate_live, validate_pairs
from ragops.evalsuite.io import loads, read_config, schema_check
from ragops.evalsuite.metrics import cosine, percentile, retrieval_metrics, typo
from ragops.evalsuite.runner import run_suite
from ragops.gate import decide, measured_suite, metric_checks


def test_retrieval_metrics_deduplicate_relevant_keys_and_returned_page_section() -> None:
    p = fixture_query().retrieval.passages[0]
    relevant = [{"doc_id": p.doc_id, "doc_version": p.doc_version, "page": 1, "section": "1"}]
    passages = (p, replace(p, rank=2, chunk_id="duplicate-page"))
    metrics = retrieval_metrics(relevant + relevant, passages)
    assert metrics == {"recall_at_3": 1, "recall_at_5": 1, "mrr": 1, "ndcg_at_5": 1}
    assert retrieval_metrics([], passages) is None


def test_ranked_metrics_hand_computed_missing_version_and_section_boundary() -> None:
    p = fixture_query().retrieval.passages[0]
    relevant = [{"doc_id": p.doc_id, "doc_version": "v1", "page": 1, "section": "1"},
                {"doc_id": "second", "doc_version": "v1", "page": 2, "section": "2"}]
    passages = (replace(p, doc_version="old"), replace(p, rank=2, chunk_id="good"),
                replace(p, rank=3, chunk_id="not-a-prefix", section="1.20"))
    result = retrieval_metrics(relevant, passages)
    assert result is not None
    assert result["recall_at_5"] == .5
    assert result["mrr"] == .5
    assert 0 < result["ndcg_at_5"] < .5


def test_mrr_considers_available_ranks_beyond_five_but_recall5_does_not() -> None:
    p = fixture_query().retrieval.passages[0]
    passages = tuple(replace(p, rank=i, chunk_id=str(i), doc_id="noise" if i < 6 else p.doc_id)
                     for i in range(1, 7))
    result = retrieval_metrics([{"doc_id": p.doc_id, "page": 1, "section": "1"}], passages)
    assert result is not None
    assert result["mrr"] == pytest.approx(1 / 6)
    assert result["recall_at_5"] == 0
    assert result["ndcg_at_5"] == 0


def test_page_ground_truth_matches_exact_document_version_page_without_invented_section() -> None:
    passage = fixture_query().retrieval.passages[0]
    relevant = [{"doc_id": passage.doc_id, "doc_version": passage.doc_version, "page": passage.page}]
    schema_check("relevant", relevant[0])
    assert retrieval_metrics(relevant, (passage,))["recall_at_5"] == 1
    for wrong in (replace(passage, page=passage.page + 1), replace(passage, doc_version="other"),
                  replace(passage, doc_id="other")):
        assert retrieval_metrics(relevant, (wrong,))["recall_at_5"] == 0
    # An explicitly annotated section still requires that section, even on the right page.
    assert retrieval_metrics([{**relevant[0], "section": "missing-clause"}], (passage,))["recall_at_5"] == 0


def test_cosine_and_linear_percentile_are_explicit() -> None:
    assert cosine((1., 0.), (0., 1.)) == 0
    assert cosine((1., 0.), (-1., 0.)) == -1
    assert percentile([10, 20, 30, 40], 95) == pytest.approx(38.5)
    with pytest.raises(ValueError):
        cosine((0., 0.), (1., 0.))
    with pytest.raises(ValueError):
        percentile([], 95)


def test_seeded_typos_change_text_without_changing_ground_truth() -> None:
    question = "What attendance requirement applies?"
    assert typo(question, 42) == typo(question, 42)
    assert typo(question, 42) != question
    with pytest.raises(ValueError):
        typo("A B?", 42)


def test_strict_json_and_yaml_reject_nan_and_duplicate_keys(tmp_path: Path) -> None:
    for text in ('{"x":NaN}', '{"x":1,"x":2}'):
        with pytest.raises(ValueError):
            loads(text)
    config = tmp_path / "policy.yaml"
    config.write_text("limit: 1\nlimit: 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_config(config)


def test_missing_human_work_never_passes_final_golden_validation() -> None:
    row = {"schema_version": "1.0", "id": "draft", "question": "What is required?",
           "origin": "synthetic", "author": "test generator", "answerable": True, "hard": False,
           "expected_behavior": "answer", "relevant": [{"doc_id": "d", "doc_version": "v1", "page": 1, "section": "1"}],
           "reviews": [], "batches": ["A"], "notes": "test-only"}
    inventory = {"documents": [{"doc_id": "d", "doc_version": "v1", "pages": 1, "verified_sha256": "a" * 64}]}
    assert validate_golden([row], inventory, require_humans=False)["human"] == 0
    with pytest.raises(ValueError, match="requires"):
        validate_golden([row], inventory)
    with pytest.raises(ValueError, match="outside"):
        bad = deepcopy(row)
        bad["relevant"][0]["page"] = 2
        validate_golden([bad], inventory, require_humans=False)


def test_coverage_cutoff_and_floor_are_separate_and_equality_is_covered() -> None:
    client = FakeEmbeddingClient({"golden": (1., 0.), "near": (1., 0.), "far": (0., 1.)})
    golden = [{"id": "g", "question": "golden"}]
    live = [{"id": "a", "query": "near", "topic": "known"}, {"id": "b", "query": "far", "topic": "gap"}]
    before = measure(golden, live, client, cutoff=1, floor=.85)
    assert before["coverage"] == .5 and before["exit_code"] == 1
    assert before["topic_groups"][0]["query_ids"] == ["b"]
    after = measure(golden + [{"id": "new", "question": "far"}], live, client, cutoff=1, floor=.85)
    assert after["coverage"] == 1 and after["exit_code"] == 0
    assert before["provenance"] == "synthetic_fixture"


def fixture_suite() -> dict:
    class Api(FakeApiClient):
        def ask(self, question: str, *, use_cache: bool, seed: int):
            result = super().ask(question, use_cache=use_cache, seed=seed)
            if question.startswith("unknown"):
                return replace(result, answered_from_context=False, citations=(), prompt_json=None,
                               generation_skipped_reason="outside fixture", answer="Fixture abstention")
            return result

    p = fixture_query().retrieval.passages[0]
    client = FakeEmbeddingClient({"same": (1., 0.), "para": (1., 0.), "other": (0., 1.), p.text: (1., 0.)})
    golden = [{"id": "a", "question": "known attendance question", "answerable": True, "hard": True,
               "relevant": [{"doc_id": p.doc_id, "doc_version": p.doc_version, "page": 1, "section": "1"}]},
              {"id": "b", "question": "unknown topic question", "answerable": False, "hard": False, "relevant": []}]
    pairs = [{"id": f"p{i}", "a": "same", "b": "para", "label": "paraphrase"} for i in range(15)]
    pairs += [{"id": f"u{i}", "a": "same", "b": "other", "label": "unrelated"} for i in range(15)]
    validate_pairs(pairs)
    result = run_suite(Api(), client, FakeJudge(), golden=golden, pairs=pairs, labels=[],
                        golden_validated=False, metadata={"run_id": "test-only", "git_sha": "a" * 40,
                        "golden_sha256": "b" * 64, "golden_version": "fixture", "pairs_sha256": "c" * 64,
                        "provider": {"name": "fixture", "model": "fixture", "version": "1", "parameters": {}},
                        "judge": {"method": "fixture", "rubric_sha256": "d" * 64, "identity": {}, "human_labels_sha256": None},
                        "input_hashes": {"fixture": "e" * 64}})
    result["mode"] = "label_collection"
    return result


def test_whole_suite_repeats_and_preserves_test_only_provenance() -> None:
    result = fixture_suite()
    schema_check("suite_result", result)
    assert len(result["runs"]) == 2
    assert result["runs"][0]["module"]["cosine_gap"]["value"] == 1
    assert result["runs"][0]["e2e"]["faithfulness"]["samples"] == 1
    assert result["runs"][0]["e2e"]["abstention_correctness"]["value"] == 1
    assert result["differences"]["component"]["recall_at_5"]["delta"] == 0
    with pytest.raises(ValueError, match="synthetic fixture"):
        measured_suite(result)


def test_gate_binds_policy_live_identity_vector_snapshot_and_single_change() -> None:
    # Ephemeral mock envelopes exercise gate admission only. They are never saved as results.
    import json

    baseline = fixture_suite()
    baseline["mode"] = "complete"
    baseline["human_validation"] = {"golden_complete": True, "faithfulness_complete": True}
    baseline["identity"]["provenance"] = "real"
    baseline["identity"]["vector_sha256"] = "f" * 64
    baseline["identity"]["config_json"] = json.dumps({"top_k": 5, "prompt": "same"})
    for run in baseline["runs"]:
        for query in run["queries"]:
            query["evidence"]["retrieval"]["identity"] = deepcopy(baseline["identity"])
    candidate = deepcopy(baseline)
    candidate["identity"]["collection"] = "test-only-candidate"
    candidate["identity"]["config_json"] = json.dumps({"top_k": 3, "prompt": "same"})
    candidate["config"]["top_k"] = 3
    for run in candidate["runs"]:
        for query in run["queries"]:
            query["evidence"]["retrieval"]["identity"] = deepcopy(candidate["identity"])
    policy = {"schema_version": "1.0", "declared_change": "top_k", "policy_mode": "release",
              "frozen": True, "baseline_sha256": "a" * 64, "rationale": "Test-only policy",
              "max_recall5_drop": .02, "min_faithfulness": .9, "min_citation_validity": .95,
              "max_p95_latency_ms": 100000, "min_abstention_correctness": 1}
    kwargs = {"baseline_hash": "a" * 64, "candidate_hash": "b" * 64, "policy_hash": "c" * 64,
              "current_identity": deepcopy(candidate["identity"])}
    decision = decide(baseline, candidate, policy, **kwargs)
    schema_check("gate_decision", decision)
    assert decision["release_authorized"]
    assert not decide(baseline, candidate, {**policy, "policy_mode": "demo"}, **kwargs)["release_authorized"]
    for altered in ({**kwargs, "current_identity": baseline["identity"]},
                    {**kwargs, "baseline_hash": "d" * 64}):
        with pytest.raises(ValueError):
            decide(baseline, candidate, policy, **altered)
    candidate["identity"]["vector_sha256"] = "e" * 64
    for run in candidate["runs"]:
        for query in run["queries"]:
            query["evidence"]["retrieval"]["identity"] = deepcopy(candidate["identity"])
    kwargs["current_identity"] = deepcopy(candidate["identity"])
    with pytest.raises(ValueError, match="vector snapshot"):
        decide(baseline, candidate, policy, **kwargs)


def test_gate_threshold_math_uses_percentage_points_and_zero_latency_is_valid() -> None:
    baseline = fixture_suite()
    candidate = deepcopy(baseline)
    for run in baseline["runs"]:
        run["component"]["recall_at_5"]["value"] = .8
    for run in candidate["runs"]:
        run["component"]["recall_at_5"]["value"] = .78
    policy = {"max_recall5_drop": .02, "min_faithfulness": .9, "min_citation_validity": .95,
              "max_p95_latency_ms": 100000, "min_abstention_correctness": 1}
    assert all(row["passed"] for row in metric_checks(baseline, candidate, policy))
    policy["max_p95_latency_ms"] = 0
    checks = metric_checks(baseline, candidate, policy)
    assert not next(row for row in checks if row["metric"] == "e2e.latency_p95_ms")["passed"]
    candidate["runs"][0]["component"]["recall_at_5"]["value"] = .779
    assert not metric_checks(baseline, candidate, policy)[0]["passed"]


def test_gate_rejects_missing_nan_units_and_empty_samples() -> None:
    baseline = fixture_suite()
    policy = {"max_recall5_drop": .02, "min_faithfulness": .9, "min_citation_validity": .95,
              "max_p95_latency_ms": 100, "min_abstention_correctness": 1}
    for patch in ({"value": float("nan")}, {"value": None}, {"unit": "seconds"}, {"samples": 0}):
        candidate = deepcopy(baseline)
        candidate["runs"][0]["e2e"]["faithfulness"].update(patch)
        with pytest.raises(ValueError):
            metric_checks(baseline, candidate, policy)


def test_live_validation_rejects_missing_uncovered_population() -> None:
    live = [{"id": f"q{i}", "query": f"query {i}", "topic": "known", "origin": "synthetic",
             "provenance": "simulated", "uncovered_topic": False} for i in range(40)]
    with pytest.raises(ValueError, match="uncovered"):
        validate_live(live)


def test_outage_stays_an_error_instead_of_a_successful_abstention() -> None:
    with pytest.raises(EvaluationError):
        FakeApiClient(fail=True).ask("attendance question", use_cache=False, seed=42)

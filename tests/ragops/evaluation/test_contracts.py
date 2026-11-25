"""Contract invariants with no API, model, ingestion package or third-party imports."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from fakes import FakeApiClient, FakeEmbeddingClient, FakeJudge, fixture_query

from ragops.evalsuite.contracts import (
    ApiClient,
    EmbeddingBatch,
    EmbeddingClient,
    EmbeddingIdentity,
    EvaluationError,
    Judge,
    require_measured_query,
)


class ContractTests(unittest.TestCase):
    def test_clients_satisfy_typed_interfaces_without_runtime_dependencies(self) -> None:
        api: ApiClient = FakeApiClient()
        embedder: EmbeddingClient = FakeEmbeddingClient({"same": (1.0, 0.0)})
        judge: Judge = FakeJudge()
        evidence = api.ask("same", use_cache=False, seed=7)
        self.assertEqual(api.identity().provenance, "synthetic_fixture")
        self.assertEqual(judge.assess(evidence, seed=7).provenance, "synthetic_fixture")
        first = embedder.embed(("same",), task="document", fresh=True)
        second = embedder.embed(("same",), task="document", fresh=True)
        self.assertEqual(first.vectors, second.vectors)
        self.assertFalse(second.cache_hit)

    def test_fixture_evidence_is_rejected_from_measurement(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "test-only"):
            require_measured_query(fixture_query())

    def test_runtime_errors_are_not_scored_as_abstention(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "outage"):
            FakeApiClient(fail=True).ask("question", use_cache=False, seed=7)

    def test_real_evidence_still_rejects_pipeline_errors_and_cache_hits(self) -> None:
        evidence = fixture_query()
        identity = replace(evidence.retrieval.identity, provenance="real")
        evidence = replace(evidence, retrieval=replace(evidence.retrieval, identity=identity))
        require_measured_query(evidence)
        with self.assertRaisesRegex(EvaluationError, "pipeline errors"):
            require_measured_query(replace(evidence, errors=("embedding fallback",)))
        with self.assertRaisesRegex(EvaluationError, "cache hit"):
            require_measured_query(replace(evidence, cache_hit=True, original_trace_id="old"))

    def test_cache_hit_requires_original_trace(self) -> None:
        with self.assertRaisesRegex(ValueError, "original trace"):
            replace(fixture_query(), cache_hit=True)

    def test_missing_prompt_requires_explicit_skipped_generation(self) -> None:
        with self.assertRaises(ValueError):
            replace(fixture_query(), prompt_json=None)
        evidence = replace(fixture_query(), prompt_json=None, answered_from_context=False,
                           generation_skipped_reason="relevance floor", citations=())
        self.assertEqual(evidence.generation_skipped_reason, "relevance floor")

    def test_invalid_scores_and_latencies_are_rejected(self) -> None:
        passage = fixture_query().retrieval.passages[0]
        for value in (float("nan"), float("inf"), -1.01, 1.01):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(passage, score=value)
        for value in (-1.0, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(fixture_query().retrieval, latency_ms=value)

    def test_document_and_rank_identity_are_preserved(self) -> None:
        retrieval = fixture_query().retrieval
        passage = retrieval.passages[0]
        self.assertEqual((passage.doc_id, passage.doc_version, passage.page),
                         ("fixture-policy", "v1", 1))
        for field in ("doc_id", "doc_version", "text"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(passage, **{field: ""})
        with self.assertRaises(ValueError):
            replace(retrieval, passages=(replace(passage, rank=2),))
        with self.assertRaises(ValueError):
            replace(retrieval, passages=(passage, replace(passage, rank=2)))
        with self.assertRaises(ValueError):
            replace(passage, page=0)

    def test_embedding_shape_and_finite_coordinates(self) -> None:
        identity = EmbeddingIdentity("fixture", "v1", 2)
        for vector in ((1.0,), (0.0, 0.0), (float("nan"), 1.0)):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                EmbeddingBatch(identity, "synthetic_fixture", (vector,), 1.0, False)

    def test_fresh_embedding_calls_reach_client_each_time(self) -> None:
        client = FakeEmbeddingClient({"text": (1.0, 0.0)})
        for _ in range(2):
            client.embed(("text",), task="document", fresh=True)
        self.assertEqual(len(client.calls), 2)
        with self.assertRaises(EvaluationError):
            client.embed(("unknown",), task="query")

    def test_import_does_not_pull_in_partner_modules_or_fakes(self) -> None:
        code = (
            "import sys; import ragops.evalsuite.contracts; "
            "assert not any(m.startswith(('app.', 'pipeline.', 'ragops.ingest', "
            "'ragops.state', 'ragops.trace', 'fakes')) for m in sys.modules)"
        )
        subprocess.run([sys.executable, "-B", "-c", code], check=True)

    def test_schema_references_resolve(self) -> None:
        path = Path(__file__).resolve().parents[3] / "config/schemas/h0.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))

        def walk(value: object) -> None:
            if isinstance(value, dict):
                if "$ref" in value:
                    ref = value["$ref"]
                    self.assertTrue(ref.startswith("#/$defs/"))
                    self.assertIn(ref.removeprefix("#/$defs/"), schema["$defs"])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(schema)
        self.assertTrue({"golden", "suite_result", "gate_decision", "coverage_report",
                         "query_evidence"}.issubset(schema["$defs"]))


if __name__ == "__main__":
    unittest.main()

"""Offline test doubles only. Never imported by production adapters or the CLI."""

from __future__ import annotations

from dataclasses import replace

from ragops.evalsuite.contracts import (
    Citation,
    EmbeddingBatch,
    EmbeddingIdentity,
    EmbeddingTask,
    EvaluationError,
    JudgeAssessment,
    QueryEvidence,
    RankedPassage,
    RetrievalEvidence,
    RuntimeIdentity,
)


def fixture_query() -> QueryEvidence:
    identity = RuntimeIdentity(
        collection="test_only", revision="fixture-revision",
        api_image="test-only-image", config_json='{"top_k":5,"temperature":0}',
        corpus_sha256="a" * 64, pipeline_sha256="b" * 64,
        embedding=EmbeddingIdentity("fixture-2d", "fixture-v1", 2),
        provenance="synthetic_fixture",
    )
    passage = RankedPassage(
        rank=1, chunk_id="fixture-c1", doc_id="fixture-policy", doc_version="v1",
        source="self-made.txt", section="1 Attendance", page=1, score=0.8,
        text="This self-made fixture requires attendance.",
    )
    retrieval = RetrievalEvidence(
        "What does the fixture require?", identity, (passage,), '{"superseded":false}', 2.0,
    )
    return QueryEvidence(
        request_id="fixture-request", trace_id="fixture-trace", retrieval=retrieval,
        answer="Attendance is required.", answered_from_context=True,
        citations=(Citation(passage.source, passage.section, passage.page),),
        prompt_json='{"messages":[{"role":"user","content":"test-only evidence"}]}',
        generation_skipped_reason=None, cache_hit=False, original_trace_id=None,
        stage_latencies_ms=(("retrieve", 2.0), ("generate", 3.0)), guardrail_actions=(),
    )


class FakeApiClient:
    def __init__(self, evidence: QueryEvidence | None = None, *, fail: bool = False) -> None:
        self.evidence = evidence or fixture_query()
        self.fail = fail

    def identity(self) -> RuntimeIdentity:
        return self.evidence.retrieval.identity

    def retrieve(self, question: str, *, k: int, seed: int) -> RetrievalEvidence:
        if self.fail:
            raise EvaluationError("test-only simulated API outage")
        if k < 1:
            raise ValueError("k must be positive")
        return replace(self.evidence.retrieval, query=question,
                       passages=self.evidence.retrieval.passages[:k])

    def ask(self, question: str, *, use_cache: bool, seed: int) -> QueryEvidence:
        return replace(self.evidence, retrieval=self.retrieve(question, k=5, seed=seed))


class FakeEmbeddingClient:
    """Hand-computable vectors supplied by each test, without any network or model."""

    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[tuple[str, ...], EmbeddingTask, bool]] = []

    def embed(self, texts: tuple[str, ...], *, task: EmbeddingTask,
              fresh: bool = True) -> EmbeddingBatch:
        self.calls.append((texts, task, fresh))
        try:
            vectors = tuple(self.vectors[text] for text in texts)
        except KeyError as exc:
            raise EvaluationError("text not configured in test double") from exc
        return EmbeddingBatch(EmbeddingIdentity("fixture-2d", "fixture-v1", 2),
                              "synthetic_fixture", vectors, 1.0, False)


class FakeJudge:
    def assess(self, evidence: QueryEvidence, *, seed: int) -> JudgeAssessment:
        return JudgeAssessment(True, "Test label only", "fixture-judge", "v1",
                               "c" * 64, "synthetic_fixture")

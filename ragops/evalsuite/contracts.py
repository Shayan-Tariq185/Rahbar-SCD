"""Proposed H0 adapter contracts; no service calls or metric implementations.

Times are milliseconds, similarity is cosine (higher is closer), and ranks are
one-based. Real adapters must surface errors instead of substituting fixture data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

Provenance = Literal["real", "synthetic_fixture"]
EmbeddingTask = Literal["query", "document"]


class EvaluationError(RuntimeError):
    """Runtime/setup error: future CLI maps this to exit status 2."""


def _required(**values: str) -> None:
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be nonempty")


def _number(name: str, value: float, minimum: float, maximum: float | None = None) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


@dataclass(frozen=True)
class EmbeddingIdentity:
    model: str
    digest: str
    dimension: int

    def __post_init__(self) -> None:
        _required(model=self.model, digest=self.digest)
        if type(self.dimension) is not int or self.dimension < 1:
            raise ValueError("dimension must be a positive integer")


@dataclass(frozen=True)
class RuntimeIdentity:
    collection: str
    revision: str
    api_image: str
    # Resolved effective settings, not just environment-variable names/defaults.
    config_json: str
    # Identical content across differently named candidate collections has the same hash.
    corpus_sha256: str
    pipeline_sha256: str
    embedding: EmbeddingIdentity
    provenance: Provenance
    vector_sha256: str | None = None

    def __post_init__(self) -> None:
        import json

        _required(collection=self.collection, revision=self.revision, api_image=self.api_image)
        if not isinstance(json.loads(self.config_json), dict):
            raise ValueError("config_json must encode effective pipeline settings")
        for name in ("corpus_sha256", "pipeline_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if self.vector_sha256 is not None and (
            len(self.vector_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.vector_sha256)
        ):
            raise ValueError("vector_sha256 must be a lowercase SHA-256")
        if self.provenance not in ("real", "synthetic_fixture"):
            raise ValueError("unknown provenance")


@dataclass(frozen=True)
class RankedPassage:
    rank: int
    chunk_id: str
    doc_id: str
    doc_version: str
    source: str
    section: str
    page: int
    score: float
    text: str

    def __post_init__(self) -> None:
        _required(chunk_id=self.chunk_id, doc_id=self.doc_id, doc_version=self.doc_version,
                  source=self.source, section=self.section, text=self.text)
        if type(self.rank) is not int or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if type(self.page) is not int or self.page < 1:
            raise ValueError("page must be a one-based physical page number")
        _number("score", self.score, -1, 1)


@dataclass(frozen=True)
class Citation:
    source: str
    section: str
    page: int

    def __post_init__(self) -> None:
        _required(source=self.source, section=self.section)
        if type(self.page) is not int or self.page < 1:
            raise ValueError("citation page must be a positive integer")


@dataclass(frozen=True)
class RetrievalEvidence:
    query: str
    identity: RuntimeIdentity
    passages: tuple[RankedPassage, ...]
    # Canonical JSON, preserving exact production filters, including an empty object.
    filters_json: str
    latency_ms: float

    def __post_init__(self) -> None:
        import json

        _required(query=self.query)
        if not isinstance(json.loads(self.filters_json), dict):
            raise ValueError("filters_json must encode an object")
        ranks = [p.rank for p in self.passages]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("passage ranks must be ordered and contiguous from 1")
        ids = [p.chunk_id for p in self.passages]
        if len(ids) != len(set(ids)):
            raise ValueError("retrieved chunk IDs must be unique")
        _number("latency_ms", self.latency_ms, 0)


@dataclass(frozen=True)
class QueryEvidence:
    request_id: str
    trace_id: str
    retrieval: RetrievalEvidence
    answer: str
    answered_from_context: bool
    citations: tuple[Citation, ...]
    # Exact model input, including roles/schema/options, serialized as JSON.
    # Null only when generation was skipped, with an explicit reason.
    prompt_json: str | None
    generation_skipped_reason: str | None
    cache_hit: bool
    original_trace_id: str | None
    # Stable name -> measured wall-clock milliseconds; skipped stages are absent.
    stage_latencies_ms: tuple[tuple[str, float], ...]
    guardrail_actions: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        import json

        _required(request_id=self.request_id, trace_id=self.trace_id, answer=self.answer)
        if self.prompt_json is None:
            if not self.generation_skipped_reason or self.answered_from_context:
                raise ValueError("missing prompt requires a skipped, unanswered generation")
        else:
            if not isinstance(json.loads(self.prompt_json), dict):
                raise ValueError("prompt_json must encode the exact model request object")
            if self.generation_skipped_reason is not None:
                raise ValueError("generation cannot be both executed and skipped")
        if self.cache_hit and not self.original_trace_id:
            raise ValueError("cache hits must reference the original trace")
        names = [name for name, _ in self.stage_latencies_ms]
        if len(names) != len(set(names)):
            raise ValueError("stage latency names must be unique")
        for name, value in self.stage_latencies_ms:
            _required(stage=name)
            _number(name, value, 0)


@dataclass(frozen=True)
class EmbeddingBatch:
    identity: EmbeddingIdentity
    provenance: Provenance
    vectors: tuple[tuple[float, ...], ...]
    latency_ms: float
    cache_hit: bool

    def __post_init__(self) -> None:
        if self.provenance not in ("real", "synthetic_fixture"):
            raise ValueError("unknown provenance")
        _number("latency_ms", self.latency_ms, 0)
        for vector in self.vectors:
            if len(vector) != self.identity.dimension:
                raise ValueError("vector dimension differs from recorded model identity")
            if any(isinstance(v, bool) or not math.isfinite(v) for v in vector):
                raise ValueError("embedding coordinates must be finite numbers")
            if not any(vector):
                raise ValueError("zero vectors cannot support cosine measurements")


@dataclass(frozen=True)
class JudgeAssessment:
    supported: bool
    explanation: str
    judge_model: str
    judge_version: str
    rubric_sha256: str
    provenance: Provenance


class ApiClient(Protocol):
    def identity(self) -> RuntimeIdentity:
        """Read actual effective runtime config/revision; never infer it from a URL."""
        ...

    def retrieve(self, question: str, *, k: int, seed: int) -> RetrievalEvidence:
        """Same production retrieval path; no independent Chroma query implementation."""
        ...

    def ask(self, question: str, *, use_cache: bool, seed: int) -> QueryEvidence:
        """Uses deployed top-k. Evaluation defaults to no generated-answer cache."""
        ...


class EmbeddingClient(Protocol):
    def embed(self, texts: tuple[str, ...], *, task: EmbeddingTask,
              fresh: bool = True) -> EmbeddingBatch:
        """Same production model/prefix path; fresh bypasses all embedding caches."""
        ...


class Judge(Protocol):
    def assess(self, evidence: QueryEvidence, *, seed: int) -> JudgeAssessment:
        """Judge exact answer/context; raise EvaluationError on exhausted failures."""
        ...


def require_measured_query(evidence: QueryEvidence) -> None:
    """Admission check for future real-suite evidence, not a release gate."""
    if evidence.retrieval.identity.provenance != "real":
        raise EvaluationError("synthetic fixture evidence is test-only")
    if evidence.errors:
        raise EvaluationError("pipeline errors: " + "; ".join(evidence.errors))
    if evidence.cache_hit:
        raise EvaluationError("cold evaluation received a generated-answer cache hit")

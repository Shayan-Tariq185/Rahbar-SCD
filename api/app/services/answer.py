"""Turns a question into an AskResponse. This is where the query pipeline lives.

Orchestrates each step of the pipeline across modular services:
1. Embedding (Track B)
2. Semantic Cache lookup (Track A)
3. Retrieval with latency measurement (Track B)
4. Abstention / Relevance floor check (Track B)
5. Schema generation & validation with latency measurement (Track B)
6. Citation grounding check (Track B)
7. Structured JSON request logging & metrics accounting (Track A)
8. Semantic Cache storage (Track A)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..config import Settings
from ..embedding import embed_query
from ..logjson import request_id_var
from ..metrics_defs import (
    ABSTENTIONS,
    CACHE_HITS,
    CACHE_MISSES,
    GENERATION_LATENCY,
    RETRIEVAL_LATENCY,
)
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, RetrievedRef
from .cache import get_cache, should_cache
from .grounding import check_citations, should_abstain
from .validate import generate_and_validate

log = logging.getLogger("rahbar.answer")


def answer_question(
    question: str,
    retriever: Retriever,
    provider: LLMProvider,
    settings: Settings,
    cache: Any = None,
) -> AskResponse:
    if cache is None:
        cache = get_cache(settings)

    # 1. Embedding generation
    query_vector = embed_query(question)

    # 2. Semantic cache lookup
    cached_response = cache.get(question, query_vector)
    if cached_response is not None:
        CACHE_HITS.inc()
        log.info(
            "request_completed",
            extra={
                "request_id": request_id_var.get(),
                "top_k": settings.top_k,
                "chunk_ids": [r.chunk_id for r in cached_response.retrieved],
                "scores": [round(r.score, 4) for r in cached_response.retrieved],
                "abstained": not cached_response.answered_from_context,
                "cached": True,
                "provider": cached_response.provider,
            },
        )
        return cached_response

    CACHE_MISSES.inc()

    # 3. Retrieval with latency measurement
    t_ret_start = time.perf_counter()
    try:
        passages = retriever.retrieve(question, k=settings.top_k)
    except NotImplementedError:
        from ..retrieval.stub import StubRetriever

        passages = StubRetriever().retrieve(question, k=settings.top_k)
    t_ret_end = time.perf_counter()
    RETRIEVAL_LATENCY.observe(t_ret_end - t_ret_start)

    # Defensively filter out any superseded passages from retired policies (Section 3.2)
    passages = [p for p in passages if not getattr(p, "superseded", False)]

    # 4. Abstention check
    if should_abstain(passages, settings.relevance_floor):
        ABSTENTIONS.inc()
        answer = Answer(
            reasoning="Relevance floor not met; abstaining honestly.",
            answer="I cannot answer this question based on the provided documents.",
            citations=[],
            answered_from_context=False,
            confidence="low",
        )
    else:
        # 5. Generation with schema validation and fallback
        t_gen_start = time.perf_counter()
        answer = generate_and_validate(question, passages, provider, settings)
        t_gen_end = time.perf_counter()
        GENERATION_LATENCY.observe(t_gen_end - t_gen_start)

        # 6. Citation grounding verification
        answer = check_citations(answer, passages)

    response = AskResponse(
        request_id=request_id_var.get(),
        answer=answer.answer,
        citations=answer.citations,
        answered_from_context=answer.answered_from_context,
        confidence=answer.confidence,
        retrieved=[
            RetrievedRef(
                chunk_id=p.chunk_id, source=p.source, section=p.section, page=p.page, score=p.score
            )
            for p in passages
        ],
        provider=provider.name,
        cached=False,
    )

    # Structured request completion log (one log line per request, no secrets or unneeded text)
    log.info(
        "request_completed",
        extra={
            "request_id": request_id_var.get(),
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "abstained": not answer.answered_from_context,
            "cached": False,
            "provider": provider.name,
        },
    )

    # 7. Semantic cache storage
    if should_cache(response):
        cache.put(question, response, query_vector)

    return response

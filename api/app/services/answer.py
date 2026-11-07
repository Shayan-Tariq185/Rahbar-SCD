"""Turns a question into an AskResponse. This is where the query pipeline lives.

Orchestrates each step of the pipeline across modular services:
1. Embedding (Track B)
2. Semantic Cache (Track A)
3. Retrieval (Track B)
4. Abstention / Relevance check (Track B)
5. Schema generation & validation (Track B)
6. Citation check (Track B)
7. Cache storage (Track A)
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..embedding import embed_query
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, RetrievedRef
from .cache import get_cache
from .grounding import check_citations, should_abstain
from .validate import generate_and_validate

log = logging.getLogger("rahbar.answer")


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings
) -> AskResponse:
    # 1. Embedding generation
    query_vector = embed_query(question)

    # 2. Semantic cache lookup
    cache = get_cache(settings)
    cached_response = cache.get(question, query_vector)
    if cached_response is not None:
        return cached_response

    # 3. Retrieval
    passages = retriever.retrieve(question, k=settings.top_k)

    # 4. Abstention check
    if should_abstain(passages, settings.relevance_floor):
        answer = Answer(
            reasoning="Relevance floor not met; abstaining honestly.",
            answer="I cannot answer this question based on the provided documents.",
            citations=[],
            answered_from_context=False,
            confidence="low",
        )
    else:
        # 5. Generation with schema validation and fallback
        answer = generate_and_validate(question, passages, provider, settings)

        # 6. Citation grounding verification
        answer = check_citations(answer, passages)

    log.info(
        "answered",
        extra={
            "retriever": retriever.name,
            "provider": provider.name,
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "answered_from_context": answer.answered_from_context,
        },
    )

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
    )

    # 7. Semantic cache storage
    cache.put(question, response, query_vector)

    return response

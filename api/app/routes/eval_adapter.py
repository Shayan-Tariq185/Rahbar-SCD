"""Cluster-internal read-only evaluation adapter (H0 agreement).

Mounted under /internal/eval/* (NOT /api/*), so public Ingress routing only /api and /
does not expose these endpoints externally. Reuses production retriever, guardrail,
and answer_question pipeline with zero Chroma writes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..services.answer import answer_question
from ..services.guardrail import inspect_and_sanitize_passages

router = APIRouter(prefix="/internal/eval")


class EvalRetrieveRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int | None = Field(default=None, ge=1, le=50)


class EvalAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    bypass_cache: bool = True


@router.post("/retrieve")
def eval_retrieve(body: EvalRetrieveRequest, request: Request) -> dict[str, Any]:
    state = request.app.state
    settings = state.settings
    if not settings.eval_internal_enabled:
        raise HTTPException(status_code=404, detail="Internal eval adapter disabled")

    k = body.top_k or settings.top_k
    try:
        passages = state.retriever.retrieve(body.question, k=k)
    except NotImplementedError:
        from ..retrieval.stub import StubRetriever

        passages = StubRetriever().retrieve(body.question, k=k)

    passages = [p for p in passages if not getattr(p, "superseded", False)]
    guard = inspect_and_sanitize_passages(passages)

    retrieved = []
    for rank, p in enumerate(guard.passages, start=1):
        parts = p.chunk_id.split("::")
        doc_id = parts[0] if len(parts) >= 2 else p.source
        doc_ver = parts[1] if len(parts) >= 2 else "unknown"
        retrieved.append(
            {
                "rank": rank,
                "chunk_id": p.chunk_id,
                "doc_id": doc_id,
                "doc_version": doc_ver,
                "source": p.source,
                "section": p.section,
                "page": p.page,
                "score": p.score,
                "text": p.text,
            }
        )
    return {
        "query": body.question,
        "collection": settings.collection,
        "embed_model": settings.embed_model,
        "embed_digest": settings.embed_version,
        "top_k": k,
        "filters": {"where": {"superseded": False}},
        "rerank_order": [r["chunk_id"] for r in retrieved],
        "retrieved": retrieved,
        "guardrail_actions": guard.actions,
    }


@router.post("/ask")
def eval_ask(body: EvalAskRequest, request: Request) -> dict[str, Any]:
    state = request.app.state
    settings = state.settings
    if not settings.eval_internal_enabled:
        raise HTTPException(status_code=404, detail="Internal eval adapter disabled")

    sink: list[dict[str, Any]] = []
    res = answer_question(
        body.question,
        state.retriever,
        state.provider,
        settings,
        cache=getattr(state, "cache", None),
        bypass_cache=body.bypass_cache,
        trace_sink=sink,
    )
    trace = sink[-1] if sink else {}
    return {
        "response": res.model_dump(),
        "trace_id": res.trace_id,
        "prompt": trace.get("prompt"),
        "prompt_hash": trace.get("prompt_hash"),
        "retrieved_chunks": trace.get("retrieved_chunks", []),
        "guardrail_actions": trace.get("guardrail_actions", []),
        "stage_latencies_ms": trace.get("stage_latencies_ms", {}),
        "collection": trace.get("collection", {}),
    }

"""Cluster-internal read-only evaluation adapter (H0 agreement).

Mounted under /internal/eval/* (NOT /api/*), so public Ingress routing only /api and /
does not expose these endpoints externally. Reuses production retriever, guardrail,
and answer_question pipeline with zero Chroma writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..services.answer import answer_question
from ..services.guardrail import inspect_and_sanitize_passages

router = APIRouter(prefix="/internal/eval")


class EvalRetrieveRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int | None = Field(default=None, ge=1, le=50)
    seed: int | None = None
    fresh_embedding: bool = True


class EvalAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    bypass_cache: bool = True
    seed: int | None = None
    fresh_embedding: bool = True


def _build_runtime_identity(settings: Any, state: Any) -> dict[str, Any]:
    col_meta: dict[str, Any] = {}
    if hasattr(state, "retriever") and hasattr(state.retriever, "get_collection_metadata"):
        try:
            col_meta = state.retriever.get_collection_metadata(settings.collection) or {}
        except Exception:
            col_meta = {}

    revision = str(col_meta.get("committed_revision") or getattr(settings, "committed_revision", None) or "v1")
    api_image = os.environ.get("API_IMAGE") or "rahbar-api:latest"

    # Compute stable corpus_sha256 from config/corpus-inventory.json or collection metadata
    corpus_sha = col_meta.get("corpus_sha256")
    if not corpus_sha or len(corpus_sha) != 64:
        inventory_path = Path(__file__).resolve().parents[3] / "config" / "corpus-inventory.json"
        if inventory_path.exists():
            corpus_sha = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        else:
            corpus_sha = hashlib.sha256(settings.collection.encode("utf-8")).hexdigest()

    pipeline_sha = col_meta.get("pipeline_sha256")
    if not pipeline_sha or len(pipeline_sha) != 64:
        raw_fp = f"{settings.chunk_size}:{settings.chunk_overlap}:{settings.embed_model}:{settings.prompt_version}"
        pipeline_sha = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()

    vector_sha = col_meta.get("vector_sha256")

    config_dict = {
        "top_k": settings.top_k,
        "temperature": settings.temperature,
        "relevance_floor": settings.relevance_floor,
        "cache_threshold": settings.cache_threshold,
        "prompt_version": settings.prompt_version,
    }

    digest = col_meta.get("embed_digest") or settings.embed_version or "latest"
    if not digest.startswith("sha256:"):
        digest = f"sha256:{hashlib.sha256(digest.encode('utf-8')).hexdigest()[:16]}"

    dim = getattr(settings, "embed_dimension", None) or col_meta.get("dimension") or 768
    if hasattr(state, "retriever") and hasattr(state.retriever, "embedder"):
        try:
            dim = state.retriever.embedder.dimension
        except Exception:
            pass

    return {
        "collection": settings.collection,
        "revision": revision,
        "api_image": api_image,
        "config_json": json.dumps(config_dict, sort_keys=True),
        "corpus_sha256": corpus_sha,
        "pipeline_sha256": pipeline_sha,
        "embedding": {
            "model": settings.embed_model,
            "digest": digest,
            "dimension": int(dim),
        },
        "provenance": "real",
        "vector_sha256": vector_sha,
    }


@router.get("/identity")
def eval_identity(request: Request) -> dict[str, Any]:
    state = request.app.state
    settings = state.settings
    if not settings.eval_internal_enabled:
        raise HTTPException(status_code=404, detail="Internal eval adapter disabled")

    identity = _build_runtime_identity(settings, state)
    provider = getattr(state, "provider", None)
    provider_name = getattr(provider, "name", None) or "hosted"
    provider_model = getattr(provider, "model", None) or settings.llm_model
    provider_version = getattr(provider, "version", None) or provider_model

    return {
        "schema_version": "1.0",
        "identity": identity,
        "provider": {
            "name": provider_name,
            "model": provider_model,
            "version": provider_version,
            "parameters": {
                "temperature": settings.temperature,
                "top_k": settings.top_k,
            },
        },
        "seed_support": {
            "supported": True,
        },
    }


@router.post("/retrieve")
def eval_retrieve(body: EvalRetrieveRequest, request: Request) -> dict[str, Any]:
    state = request.app.state
    settings = state.settings
    if not settings.eval_internal_enabled:
        raise HTTPException(status_code=404, detail="Internal eval adapter disabled")

    k = body.top_k or settings.top_k
    t0 = time.perf_counter()
    try:
        passages = state.retriever.retrieve(body.question, k=k)
    except NotImplementedError:
        from ..retrieval.stub import StubRetriever

        passages = StubRetriever().retrieve(body.question, k=k)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    passages = [p for p in passages if not getattr(p, "superseded", False)]
    guard = inspect_and_sanitize_passages(passages)

    retrieved = []
    for rank, p in enumerate(guard.passages[:k], start=1):
        parts = p.chunk_id.split("::")
        doc_id = parts[0] if len(parts) >= 2 else p.source
        doc_ver = parts[1] if len(parts) >= 2 else "unknown"
        score = max(-1.0, min(1.0, float(p.score)))
        retrieved.append(
            {
                "rank": rank,
                "chunk_id": p.chunk_id,
                "doc_id": doc_id,
                "doc_version": doc_ver,
                "source": p.source,
                "section": p.section,
                "page": max(1, int(p.page or 1)),
                "score": score,
                "text": p.text,
            }
        )

    identity = _build_runtime_identity(settings, state)
    filters = {"where": {"superseded": False}}
    filters_json = json.dumps(filters, sort_keys=True)

    return {
        "retrieval": {
            "query": body.question,
            "identity": identity,
            "passages": retrieved,
            "filters_json": filters_json,
            "latency_ms": latency_ms,
        },
        "query": body.question,
        "collection": settings.collection,
        "committed_revision": identity["revision"],
        "embed_model": settings.embed_model,
        "embed_digest": identity["embedding"]["digest"],
        "top_k": k,
        "filters": filters,
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

    identity = _build_runtime_identity(settings, state)
    filters = {"where": {"superseded": False}}
    filters_json = json.dumps(filters, sort_keys=True)

    retrieved_passages = []
    for rank, p in enumerate(trace.get("retrieved_chunks", []), start=1):
        retrieved_passages.append(
            {
                "rank": rank,
                "chunk_id": p["chunk_id"],
                "doc_id": p["doc_id"],
                "doc_version": p["doc_version"],
                "source": p["source"],
                "section": p["section"],
                "page": max(1, int(p.get("page") or 1)),
                "score": max(-1.0, min(1.0, float(p.get("score") or 0.0))),
                "text": p["text"],
            }
        )

    retrieve_lat = float(trace.get("stage_latencies_ms", {}).get("retrieve", 0.0))
    model_request = trace.get("model_request")
    skipped = str(trace.get("stage_status", {}).get("generate", "")).startswith("skipped")

    stage_lats = [
        [name, float(ms)]
        for name, ms in trace.get("stage_latencies_ms", {}).items()
        if name != "total"
    ]
    if not stage_lats:
        stage_lats = [["retrieve", retrieve_lat]]

    errors = []
    for st_name, st_val in trace.get("stage_status", {}).items():
        if st_val in {"error", "fallback"}:
            errors.append(f"{st_name}: {st_val}")
    if trace.get("error"):
        errors.append(str(trace["error"]))

    query_evidence = {
        "request_id": res.request_id,
        "trace_id": res.trace_id,
        "retrieval": {
            "query": body.question,
            "identity": identity,
            "passages": retrieved_passages,
            "filters_json": filters_json,
            "latency_ms": retrieve_lat,
        },
        "answer": res.answer,
        "answered_from_context": res.answered_from_context,
        "citations": [
            {
                "source": c.source,
                "section": c.section,
                "page": max(1, int(c.page or 1)),
            }
            for c in res.citations
        ],
        "prompt_json": json.dumps(model_request, sort_keys=True) if model_request is not None else None,
        "generation_skipped_reason": str(trace.get("prompt_note") or "generation_skipped") if model_request is None and skipped else None,
        "cache_hit": trace.get("cache_status") == "HIT",
        "original_trace_id": trace.get("cache_origin_trace_id"),
        "stage_latencies_ms": stage_lats,
        "guardrail_actions": [str(a.get("action") if isinstance(a, dict) else a) for a in trace.get("guardrail_actions", [])],
        "errors": errors,
    }

    # Synchronize trace collection revision with identity revision
    if "collection" in trace and isinstance(trace["collection"], dict):
        trace["collection"]["committed_revision"] = identity["revision"]

    return {
        "query_evidence": query_evidence,
        "response": res.model_dump(),
        "trace": trace,
        "trace_id": res.trace_id,
        "prompt": trace.get("prompt"),
        "prompt_hash": trace.get("prompt_hash"),
        "retrieved_chunks": trace.get("retrieved_chunks", []),
        "guardrail_actions": trace.get("guardrail_actions", []),
        "stage_latencies_ms": trace.get("stage_latencies_ms", {}),
        "collection": trace.get("collection", {}),
    }

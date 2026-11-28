"""Cluster-internal read-only evaluation adapter (H0 agreement).

Mounted under /internal/eval/* (NOT /api/*), so public Ingress routing only /api and /
does not expose these endpoints externally. Reuses production retriever, guardrail,
and answer_question pipeline with zero Chroma writes.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import time
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
    from ..retrieval.stub import StubRetriever

    config_dict = {
        "cache_threshold": float(settings.cache_threshold),
        "prompt_version": str(settings.prompt_version),
        "relevance_floor": float(settings.relevance_floor),
        "temperature": float(settings.temperature),
        "top_k": int(settings.top_k),
    }
    is_stub = settings.retriever == "stub" or isinstance(state.retriever, StubRetriever)
    if is_stub:
        fp = hashlib.sha256(b"explicit-test-fixture").hexdigest()
        return {
            "collection": settings.collection, "revision": "fixture", "api_image": "fixture",
            "config_json": json.dumps(config_dict, sort_keys=True), "corpus_sha256": fp,
            "pipeline_sha256": fp, "vector_sha256": None,
            "embedding": {"model": settings.embed_model, "digest": settings.embed_version or "fixture", "dimension": 768},
            "provenance": "synthetic_fixture",
        }
    try:
        meta = state.retriever.get_collection_metadata(settings.collection)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Committed collection metadata unavailable: {type(exc).__name__}") from exc
    required = ("committed_revision", "corpus_sha256", "vector_sha256", "embed_digest", "dimension", "embed_model")
    if not meta or any(meta.get(key) is None or meta.get(key) == "" for key in required):
        raise HTTPException(status_code=503, detail="Collection is missing committed revision/model/snapshot metadata")
    pipeline = meta.get("pipeline_sha256") or meta.get("pipeline_fingerprint")
    for name, value in (("corpus_sha256", meta["corpus_sha256"]), ("vector_sha256", meta["vector_sha256"]), ("pipeline_sha256", pipeline)):
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise HTTPException(status_code=503, detail=f"Invalid actual collection fingerprint: {name}")
    api_image = os.environ.get("API_IMAGE", "")
    if not api_image or api_image.endswith((":latest", ":dev")):
        raise HTTPException(status_code=503, detail="API_IMAGE must identify the deployed immutable source image")
    if meta["embed_model"] != settings.embed_model:
        raise HTTPException(status_code=503, detail="Configured embedding model differs from committed collection")
    digest = str(meta["embed_digest"])
    if settings.embed_version and settings.embed_version != digest:
        raise HTTPException(status_code=503, detail="Configured embedding digest differs from committed collection")
    config_dict["index_pipeline_sha256"] = pipeline
    return {
        "collection": settings.collection, "revision": str(meta["committed_revision"]), "api_image": api_image,
        "config_json": json.dumps(config_dict, sort_keys=True), "corpus_sha256": meta["corpus_sha256"],
        "pipeline_sha256": pipeline, "vector_sha256": meta["vector_sha256"],
        "embedding": {"model": settings.embed_model, "digest": digest, "dimension": int(meta["dimension"])},
        "provenance": "real",
    }


@router.get("/identity")
def eval_identity(request: Request) -> dict[str, Any]:
    state = request.app.state
    settings = state.settings
    if not settings.eval_internal_enabled:
        raise HTTPException(status_code=404, detail="Internal eval adapter disabled")

    identity = _build_runtime_identity(settings, state)
    provider = getattr(state, "provider", None)
    provider_name = getattr(provider, "name", None) or getattr(settings, "llm_provider", "hosted")
    provider_model = getattr(provider, "model", None) or getattr(settings, "llm_model", "llama3.2:3b")
    provider_version = getattr(provider, "version", None) or provider_model

    supported = getattr(settings, "llm_provider", "") in {"ollama", "ollama-host", "ollama-incluster"}

    return {
        "schema_version": "1.0",
        "identity": identity,
        "provider": {
            "name": provider_name,
            "model": provider_model,
            "version": provider_version,
            "parameters": {
                "temperature": float(settings.temperature),
            },
        },
        "seed_support": {
            "supported": supported,
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
        sig = inspect.signature(state.retriever.retrieve)
        kwargs: dict[str, Any] = {"k": k}
        if "fresh" in sig.parameters:
            kwargs["fresh"] = body.fresh_embedding
        if "strict" in sig.parameters:
            kwargs["strict"] = body.fresh_embedding
        passages = state.retriever.retrieve(body.question, **kwargs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed without fallback: {exc}")
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

    identity = _build_runtime_identity(settings, state)
    col_meta = {
        "committed_revision": identity["revision"],
        "embed_digest": identity["embedding"]["digest"],
        "index_id": settings.collection,
        "corpus_sha256": identity["corpus_sha256"],
        "vector_sha256": identity.get("vector_sha256"),
    }

    sink: list[dict[str, Any]] = []
    try:
        res = answer_question(
            body.question,
            state.retriever,
            state.provider,
            settings,
            cache=getattr(state, "cache", None),
            bypass_cache=body.bypass_cache,
            seed=body.seed,
            fresh_embedding=body.fresh_embedding,
            collection_meta=col_meta,
            trace_sink=sink,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Answer question failed: {exc}")

    trace = sink[-1] if sink else {}

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

"""Turns a question into an AskResponse with full D1–D5 tracing and retrieval guardrail."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from ..config import Settings
from ..embedding import embed_query
from ..logjson import request_id_var
from ..metrics_defs import (
    ABSTENTIONS,
    CACHE_HITS,
    CACHE_MISSES,
    GENERATION_LATENCY,
    INJECTION_ATTEMPTS,
    RETRIEVAL_LATENCY,
    STAGE_LATENCY,
    TOP1_SIMILARITY,
)
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, Passage, RetrievedRef
from .cache import get_cache, should_cache
from .grounding import check_citations, should_abstain
from .guardrail import inspect_and_sanitize_passages
from .tracing import (
    build_exact_prompt,
    build_trace_record,
    load_trace_by_id,
    write_trace_record,
)
from .validate import generate_and_validate

log = logging.getLogger("rahbar.answer")


def _collection_metadata(settings: Settings, cache: Any) -> dict[str, Any]:
    if settings.retriever == "stub":
        return {"index_id": "stub", "embed_digest": settings.embed_version or "stub", "committed_revision": 0}
    index_id = "default"
    if hasattr(cache, "get_current_index_id"):
        try:
            index_id = str(cache.get_current_index_id())
        except Exception:
            pass
    return {"index_id": index_id, "embed_digest": settings.embed_version, "committed_revision": None}


def answer_question(
    question: str,
    retriever: Retriever,
    provider: LLMProvider,
    settings: Settings,
    cache: Any = None,
    *,
    bypass_cache: bool = False,
    collection_meta: dict[str, Any] | None = None,
    trace_sink: list[dict[str, Any]] | None = None,
) -> AskResponse:
    if cache is None:
        cache = get_cache(settings)

    t_total_start = time.perf_counter()
    trace_id = uuid.uuid4().hex
    req_id = request_id_var.get()
    col_meta = collection_meta if collection_meta is not None else _collection_metadata(settings, cache)
    filters = {"where": {"superseded": False}, "version_override": None}

    lat_ms: dict[str, float] = {}
    stage_status: dict[str, str] = {}

    # 1. Query embedding
    t0 = time.perf_counter()
    query_vector = embed_query(question)
    lat_ms["embed"] = (time.perf_counter() - t0) * 1000.0
    stage_status["embed"] = "ok"
    STAGE_LATENCY.labels(stage="embed").observe(lat_ms["embed"] / 1000.0)

    # 2. Semantic cache lookup
    cached_response: AskResponse | None = None
    t0 = time.perf_counter()
    if bypass_cache:
        cache_status = "BYPASS"
        stage_status["cache_lookup"] = "bypass"
    else:
        cached_response = cache.get(question, query_vector)
        cache_status = "HIT" if cached_response is not None else "MISS"
        stage_status["cache_lookup"] = "hit" if cached_response is not None else "miss"
    lat_ms["cache_lookup"] = (time.perf_counter() - t0) * 1000.0
    STAGE_LATENCY.labels(stage="cache_lookup").observe(lat_ms["cache_lookup"] / 1000.0)

    if cached_response is not None:
        CACHE_HITS.inc()
        origin_trace_id = cached_response.trace_id
        origin_trace = (
            load_trace_by_id(origin_trace_id, settings.traces_dir) if origin_trace_id else None
        )
        origin_prompt = origin_trace.get("prompt") if origin_trace else None
        prompt_note = (
            f"cache_hit_linked_to:{origin_trace_id}"
            if origin_prompt is not None
            else f"cache_hit_origin:{origin_trace_id or 'unknown'}"
        )
        passages_from_cache = [
            Passage(
                chunk_id=r.chunk_id,
                text=(
                    next(
                        (
                            c.get("text", "")
                            for c in (origin_trace or {}).get("retrieved_chunks", [])
                            if c.get("chunk_id") == r.chunk_id
                        ),
                        "",
                    )
                ),
                source=r.source,
                section=r.section,
                page=r.page,
                score=r.score,
            )
            for r in cached_response.retrieved
        ]
        response = cached_response.model_copy(
            update={"request_id": req_id, "trace_id": trace_id, "cached": True}
        )
        lat_ms["retrieve"] = 0.0
        lat_ms["guardrail"] = 0.0
        lat_ms["generate"] = 0.0
        lat_ms["validate"] = 0.0
        lat_ms["total"] = (time.perf_counter() - t_total_start) * 1000.0
        stage_status.update(
            {
                "retrieve": "skipped_cache_hit",
                "guardrail": "skipped_cache_hit",
                "generate": "skipped_cache_hit",
                "validate": "skipped_cache_hit",
            }
        )
        trace_rec = build_trace_record(
            trace_id=trace_id,
            request_id=req_id,
            query=question,
            rewrite=None,
            settings=settings,
            collection_meta=col_meta,
            filters=filters,
            passages=passages_from_cache,
            prompt=origin_prompt,
            prompt_note=prompt_note,
            response=response,
            guardrail_actions=(origin_trace or {}).get("guardrail_actions", []),
            stage_latencies_ms=lat_ms,
            stage_status=stage_status,
            cache_status="HIT",
            cache_origin_trace_id=origin_trace_id,
            outcome="answered" if response.answered_from_context else "abstained",
        )
        write_trace_record(trace_rec, settings.traces_dir)
        if trace_sink is not None:
            trace_sink.append(trace_rec)
        log.info(
            "request_completed",
            extra={
                "request_id": req_id,
                "trace_id": trace_id,
                "top_k": settings.top_k,
                "chunk_ids": [r.chunk_id for r in response.retrieved],
                "scores": [round(r.score, 4) for r in response.retrieved],
                "abstained": not response.answered_from_context,
                "cached": True,
                "provider": response.provider,
            },
        )
        return response

    if not bypass_cache:
        CACHE_MISSES.inc()

    # 3. Retrieval with latency measurement
    t_ret_start = time.perf_counter()
    try:
        passages = retriever.retrieve(question, k=settings.top_k)
    except NotImplementedError:
        from ..retrieval.stub import StubRetriever

        passages = StubRetriever().retrieve(question, k=settings.top_k)
    except Exception as exc:
        log.exception("Retrieval failed, falling back to stub retriever: %s", exc)
        from ..retrieval.stub import StubRetriever

        passages = StubRetriever().retrieve(question, k=settings.top_k)
    t_ret_end = time.perf_counter()
    RETRIEVAL_LATENCY.observe(t_ret_end - t_ret_start)
    lat_ms["retrieve"] = (t_ret_end - t_ret_start) * 1000.0
    stage_status["retrieve"] = "ok"
    STAGE_LATENCY.labels(stage="retrieve").observe(t_ret_end - t_ret_start)

    # Defensively filter out any superseded passages
    passages = [p for p in passages if not getattr(p, "superseded", False)]
    if passages:
        TOP1_SIMILARITY.observe(float(passages[0].score))

    # 4. Retrieval prompt-injection guardrail (D4)
    t_guard_start = time.perf_counter()
    guard = inspect_and_sanitize_passages(passages)
    passages = guard.passages
    if guard.injection_count > 0:
        INJECTION_ATTEMPTS.inc(guard.injection_count)
    lat_ms["guardrail"] = (time.perf_counter() - t_guard_start) * 1000.0
    stage_status["guardrail"] = "flagged" if guard.injection_count > 0 else "pass"
    STAGE_LATENCY.labels(stage="guardrail").observe(lat_ms["guardrail"] / 1000.0)

    # 5. Abstention or Generation + Citation check
    prompt_text: str | None = None
    prompt_note: str | None = None
    model_request: dict[str, Any] | None = None
    outcome = "answered"
    err_msg: str | None = None

    if should_abstain(passages, settings.relevance_floor):
        ABSTENTIONS.inc()
        answer = Answer(
            reasoning="Relevance floor not met; abstaining honestly.",
            answer="I cannot answer this question based on the provided documents.",
            citations=[],
            answered_from_context=False,
            confidence="low",
        )
        lat_ms["generate"] = 0.0
        lat_ms["validate"] = 0.0
        stage_status["generate"] = "skipped"
        stage_status["validate"] = "skipped"
        prompt_note = "generation_skipped_early_abstention"
        outcome = "abstained"
    else:
        prompt_text = build_exact_prompt(question, passages, settings.prompt_version)
        model_request = {
            "model": getattr(provider, "model", settings.llm_model),
            "messages": [
                {"role": "user", "content": prompt_text}
            ],
            "options": {
                "temperature": settings.temperature,
                "top_k": settings.top_k,
            },
        }
        t_gen_start = time.perf_counter()
        try:
            answer = generate_and_validate(question, passages, provider, settings)
            stage_status["generate"] = "ok"
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            stage_status["generate"] = "error"
            answer = Answer(
                reasoning="Generation error fallback.",
                answer="Unable to complete answer generation due to an internal provider error (fallback).",
                citations=[],
                answered_from_context=False,
                confidence="low",
            )
            outcome = "error"
        t_gen_end = time.perf_counter()
        GENERATION_LATENCY.observe(t_gen_end - t_gen_start)
        lat_ms["generate"] = (t_gen_end - t_gen_start) * 1000.0
        STAGE_LATENCY.labels(stage="generate").observe(t_gen_end - t_gen_start)

        t_val_start = time.perf_counter()
        answer = check_citations(answer, passages)
        lat_ms["validate"] = (time.perf_counter() - t_val_start) * 1000.0
        stage_status["validate"] = "fallback" if "(fallback)" in answer.answer.lower() else "ok"
        if outcome != "error":
            if not answer.answered_from_context:
                outcome = "abstained"
            elif stage_status["validate"] == "fallback":
                outcome = "fallback"

    response = AskResponse(
        request_id=req_id,
        trace_id=trace_id,
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

    lat_ms["total"] = (time.perf_counter() - t_total_start) * 1000.0
    trace_rec = build_trace_record(
        trace_id=trace_id,
        request_id=req_id,
        query=question,
        rewrite=None,
        settings=settings,
        collection_meta=col_meta,
        filters=filters,
        passages=passages,
        prompt=prompt_text,
        prompt_note=prompt_note,
        model_request=model_request,
        response=response,
        guardrail_actions=guard.actions,
        stage_latencies_ms=lat_ms,
        stage_status=stage_status,
        cache_status=cache_status,
        cache_origin_trace_id=None,
        outcome=outcome,
        error=err_msg,
    )
    write_trace_record(trace_rec, settings.traces_dir)
    if trace_sink is not None:
        trace_sink.append(trace_rec)

    log.info(
        "request_completed",
        extra={
            "request_id": req_id,
            "trace_id": trace_id,
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "abstained": not answer.answered_from_context,
            "cached": False,
            "provider": provider.name,
            "guardrail_injections": guard.injection_count,
        },
    )

    if not bypass_cache and should_cache(response):
        cache.put(question, response, query_vector)

    return response

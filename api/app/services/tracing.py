"""Structured RAGOps query trace builder and writer (D1/D2/F4).

Writes one complete JSON trace record per query to both stdout (JSON log) and
per-process JSONL files under TRACES_DIR (/traces) so multiple replicas on a
single-node RWO PVC never interleave lines.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Settings
from ..schemas import AskResponse, Passage

log = logging.getLogger("rahbar.trace")

_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"\b(?:sk|gsk|rk)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
]


def sanitize_secrets(text: str, settings: Settings | None = None) -> str:
    """Redact API keys and bearer tokens from text before logging/tracing."""
    out = text
    if settings and settings.llm_api_key:
        out = out.replace(settings.llm_api_key, "[REDACTED]")
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def build_exact_prompt(question: str, passages: list[Passage], prompt_version: str = "v1") -> str:
    """Construct the exact augmented prompt string used for grounded generation & trace replay."""
    evidence_lines: list[str] = []
    for idx, p in enumerate(passages, start=1):
        page_label = f"p. {p.page}" if p.page is not None else "p. -"
        evidence_lines.append(
            f"[{idx}] ({p.source} | {p.section} | {page_label} | chunk={p.chunk_id} | score={p.score:.4f})\n{p.text}"
        )
    evidence_block = "\n\n".join(evidence_lines) if evidence_lines else "(no passages retrieved)"
    return (
        f"[PROMPT_VERSION={prompt_version}]\n"
        "System: Answer the student's question ONLY from the numbered evidence passages below. "
        "Cite exact source, section, and page. If the evidence is insufficient, abstain.\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        f"Question: {question}"
    )


def load_trace_by_id(trace_id: str, traces_dir: str | Path) -> dict[str, Any] | None:
    """Lookup an existing trace record from JSONL files in traces_dir."""
    root = Path(traces_dir)
    if not root.exists():
        return None
    for path in sorted(root.glob("*.jsonl"), reverse=True):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("trace_id") == trace_id:
                    return dict(rec)
        except Exception:
            continue
    return None


def build_trace_record(
    *,
    trace_id: str,
    request_id: str,
    query: str,
    rewrite: str | None,
    settings: Settings,
    collection_meta: dict[str, Any],
    filters: dict[str, Any],
    passages: list[Passage],
    prompt: str | None,
    prompt_note: str | None,
    response: AskResponse,
    guardrail_actions: list[dict[str, Any]],
    stage_latencies_ms: dict[str, float],
    stage_status: dict[str, str],
    cache_status: str,
    cache_origin_trace_id: str | None,
    outcome: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a complete D1/D2 JSON trace record."""
    safe_query = sanitize_secrets(query, settings)
    safe_prompt = sanitize_secrets(prompt, settings) if prompt is not None else None
    prompt_hash = (
        hashlib.sha256(safe_prompt.encode("utf-8")).hexdigest() if safe_prompt is not None else None
    )

    chunks_out = []
    for rank, p in enumerate(passages, start=1):
        # Extract doc_id & doc_version from chunk_id convention `<doc_id>::<doc_version>::...` when available
        parts = p.chunk_id.split("::")
        doc_id = parts[0] if len(parts) >= 2 else p.source
        doc_ver = parts[1] if len(parts) >= 2 else "unknown"
        chunks_out.append(
            {
                "rank": rank,
                "rerank_order": rank,
                "chunk_id": p.chunk_id,
                "doc_id": doc_id,
                "doc_version": doc_ver,
                "source": p.source,
                "section": p.section,
                "page": p.page,
                "score": round(float(p.score), 6),
                "text": sanitize_secrets(p.text, settings),
            }
        )

    return {
        "schema_version": "1.0",
        "record_type": "ragops_trace",
        "trace_id": trace_id,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query": safe_query,
        "rewrite": rewrite,
        "model": {
            "provider": settings.llm_provider,
            "name": settings.llm_model,
            "version": settings.llm_model,
            "digest": collection_meta.get("llm_digest", ""),
        },
        "collection": {
            "name": settings.collection,
            "committed_revision": collection_meta.get("committed_revision"),
            "index_id": collection_meta.get("index_id", "default"),
            "embed_model": settings.embed_model,
            "embed_digest": collection_meta.get("embed_digest") or settings.embed_version,
        },
        "config": {
            "top_k": settings.top_k,
            "temperature": settings.temperature,
            "relevance_floor": settings.relevance_floor,
            "cache_threshold": settings.cache_threshold,
            "prompt_version": settings.prompt_version,
        },
        "filters": filters,
        "retrieved_chunks": chunks_out,
        "rerank_order": [c["chunk_id"] for c in chunks_out],
        "prompt": safe_prompt,
        "prompt_hash": prompt_hash,
        "prompt_note": prompt_note,
        "model_parameters": {
            "temperature": settings.temperature,
            "top_k": settings.top_k,
        },
        "response": {
            "answer": sanitize_secrets(response.answer, settings),
            "answered_from_context": response.answered_from_context,
            "confidence": response.confidence,
            "citations": [c.model_dump() for c in response.citations],
        },
        "citations": [c.model_dump() for c in response.citations],
        "guardrail_actions": guardrail_actions,
        "stage_latencies_ms": {k: round(v, 3) for k, v in stage_latencies_ms.items()},
        "stage_status": stage_status,
        "cache_status": cache_status,
        "cache_origin_trace_id": cache_origin_trace_id,
        "outcome": outcome,
        "error": sanitize_secrets(error, settings) if error else None,
    }


def write_trace_record(record: dict[str, Any], traces_dir: str | Path) -> Path | None:
    """Emit trace JSON to stdout and append to per-process JSONL file under traces_dir."""
    # Emit to stdout via structured JSON logger
    log.info("query_trace", extra={"trace": record, "trace_id": record.get("trace_id")})

    if not traces_dir:
        return None
    try:
        root = Path(traces_dir)
        root.mkdir(parents=True, exist_ok=True)
        host = re.sub(r"[^a-zA-Z0-9_.-]+", "_", socket.gethostname())
        out_file = root / f"traces-{host}-{os.getpid()}.jsonl"
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
        return out_file
    except Exception as exc:
        log.warning("failed to persist trace record to volume", extra={"error": str(exc)})
        return None

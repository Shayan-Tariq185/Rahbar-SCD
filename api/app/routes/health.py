"""Liveness and readiness probes (sections 4.3 and 4.4).

Liveness answers: is the process alive? (Never touches dependencies).
Readiness answers: can this pod serve user traffic right now?
Checks ChromaDB reachability, non-empty collection, embedding pin consistency,
and Redis semantic cache connectivity.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from ..config import Settings

router = APIRouter()
log = logging.getLogger("rahbar.health")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, Any]:
    """Is the pod ready to serve queries?

    Returns 200 only if:
    1. Redis is reachable and responds to ping.
    2. ChromaDB is reachable, collection exists and count() > 0 (when RETRIEVER != stub).
    3. Collection metadata embed_model matches settings.embed_model (when RETRIEVER != stub).

    Otherwise returns 503 with JSON naming the failed dependency.
    """
    settings: Settings = request.app.state.settings
    checks: dict[str, str] = {}

    # 1. Redis semantic cache check
    try:
        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is None:
            from ..services.cache import get_redis_client

            redis_client = get_redis_client(settings)
        if redis_client is not None:
            redis_client.ping()
            checks["redis"] = "ok"
        else:
            raise RuntimeError("Redis client uninitialized")
    except Exception as exc:
        log.warning("readyz failed: redis unreachable", extra={"error": str(exc)})
        response.status_code = 503
        return {
            "status": "not_ready",
            "failed": "redis",
            "detail": f"Redis ping failed: {exc}",
        }

    # 2. Local development / stub mode skips Chroma & embedding pin verification
    if settings.retriever == "stub":
        checks["chroma"] = "skipped_stub"
        checks["embedding_pin"] = "skipped_stub"
        return {"status": "ready", "checks": checks}

    # 3. ChromaDB vector store check
    try:
        chroma_client = getattr(request.app.state, "chroma_client", None)
        if chroma_client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            chroma_client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        chroma_client.heartbeat()
        collection = chroma_client.get_collection(settings.collection)
    except Exception as exc:
        log.warning("readyz failed: chroma unreachable", extra={"error": str(exc)})
        response.status_code = 503
        return {
            "status": "not_ready",
            "failed": "chroma",
            "detail": f"Chroma unreachable or collection missing: {exc}",
        }

    # Non-empty collection verification
    try:
        count = collection.count()
        if count == 0:
            log.warning("readyz failed: collection is empty", extra={"collection": settings.collection})
            response.status_code = 503
            return {
                "status": "not_ready",
                "failed": "empty_collection",
                "detail": f"Collection '{settings.collection}' has 0 chunks",
            }
        checks["chroma"] = f"ok (count={count})"
    except Exception as exc:
        response.status_code = 503
        return {
            "status": "not_ready",
            "failed": "chroma",
            "detail": f"Error querying collection count: {exc}",
        }

    # 4. Embedding model pin check (Section 4.4)
    metadata = collection.metadata or {}
    index_model = metadata.get("embed_model")
    if index_model != settings.embed_model:
        log.error(
            "readyz failed: embedding model mismatch",
            extra={
                "api_model": settings.embed_model,
                "index_model": index_model,
                "collection": settings.collection,
            },
        )
        response.status_code = 503
        return {
            "status": "not_ready",
            "failed": "embedding_pin",
            "detail": (
                f"Embedding model mismatch: API expects '{settings.embed_model}' "
                f"but collection metadata records '{index_model}'"
            ),
        }

    checks["embedding_pin"] = "ok"
    return {"status": "ready", "checks": checks}

"""The API process. It reads the index; it never builds it (section 4.2).

Run locally with stubs:   make dev     (then open http://localhost:8000)
Run in the container:     uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .logjson import configure_logging, request_id_var
from .providers.llm import get_provider
from .retrieval import get_retriever
from .routes import ask, health, metrics
from .services.cache import get_cache, get_redis_client

log = logging.getLogger("rahbar.api")


def verify_startup_embedding_pin(settings: Settings) -> tuple[bool, str | None]:
    """Check embedding model metadata on Chroma collection against settings.embed_model.

    If mismatched, logs an ERROR with exact conflicting values (api_model vs index_model)
    and keeps the application alive but not ready.
    """
    if settings.retriever == "stub":
        return True, settings.embed_model

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        collection = client.get_collection(settings.collection)
        metadata = collection.metadata or {}
        index_model = metadata.get("embed_model")

        if index_model != settings.embed_model:
            log.error(
                "embedding model mismatch between API and index",
                extra={
                    "api_model": settings.embed_model,
                    "index_model": index_model,
                    "collection": settings.collection,
                },
            )
            return False, index_model

        return True, index_model
    except Exception as exc:
        log.warning(
            "could not complete startup embedding pin check (Chroma unavailable)",
            extra={"error": str(exc), "api_model": settings.embed_model},
        )
        return False, None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.retriever = get_retriever(settings)
    app.state.provider = get_provider(settings)

    # Initialize Redis semantic cache
    redis_client = get_redis_client(settings)
    app.state.redis_client = redis_client
    app.state.cache = get_cache(settings, redis_client)

    # Perform embedding-pin verification at startup (Section 4.4)
    pin_ok, index_model = verify_startup_embedding_pin(settings)
    app.state.pin_ok = pin_ok
    app.state.index_model = index_model

    log.info(
        "api started",
        extra={
            "retriever": settings.retriever,
            "llm_provider": settings.llm_provider,
            "embed_model": settings.embed_model,
            "index_model": index_model,
            "pin_verified": pin_ok,
            "top_k": settings.top_k,
        },
    )
    yield


app = FastAPI(title="RAHBAR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")  # route template, not raw URL
        elapsed = time.perf_counter() - start
        metrics.REQUESTS.labels(path=path, status=str(status)).inc()
        metrics.LATENCY.labels(path=path).observe(elapsed)
        if path not in ("/healthz", "/readyz", "/metrics"):
            log.info(
                "request",
                extra={"path": path, "status": status, "ms": round(elapsed * 1000, 1)},
            )
        request_id_var.reset(token)


app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(ask.router)

# Development only: `make dev` serves the chat UI from this process
_ui_dir = os.environ.get("SERVE_UI_DIR")
if _ui_dir:
    app.mount("/", StaticFiles(directory=_ui_dir, html=True), name="ui")

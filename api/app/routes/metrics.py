"""Prometheus metrics endpoint at /metrics (section 4.8).

Exposes all application metrics for Prometheus scraping.
Metrics definitions are maintained in app.metrics_defs.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ..metrics_defs import (
    ABSTENTIONS,
    CACHE_HITS,
    CACHE_MISSES,
    FALLBACKS,
    GENERATION_LATENCY,
    LATENCY,
    REQUESTS,
    RETRIEVAL_LATENCY,
    TOKENS_IN,
    TOKENS_OUT,
)

router = APIRouter()

__all__ = [
    "ABSTENTIONS",
    "CACHE_HITS",
    "CACHE_MISSES",
    "FALLBACKS",
    "GENERATION_LATENCY",
    "LATENCY",
    "REQUESTS",
    "RETRIEVAL_LATENCY",
    "TOKENS_IN",
    "TOKENS_OUT",
    "router",
]


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

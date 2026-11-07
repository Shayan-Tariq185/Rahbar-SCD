"""Semantic response cache (Track A).

Provides caching interfaces. Phase 0 provides NoopCache; Phase 4 implements
RedisSemanticCache with cosine similarity matching and index_id invalidation.
"""

from __future__ import annotations

from typing import Any

from ..schemas import AskResponse


class NoopCache:
    """Pass-through cache implementation that never stores or hits."""

    def get(self, question: str, embedding: list[float] | None = None) -> AskResponse | None:
        """Lookup cached response. Always returns None in stub/NoopCache."""
        return None

    def put(
        self,
        question: str,
        response: AskResponse,
        embedding: list[float] | None = None,
    ) -> None:
        """Store response in cache. No-op in stub/NoopCache."""
        pass


def get_cache(settings: Any = None) -> NoopCache:
    """Return configured cache instance (defaults to NoopCache for now)."""
    return NoopCache()


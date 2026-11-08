"""Semantic response cache backed by Redis (Track A).

Provides cosine-similarity matching over embeddings for previously answered questions.
Cache entries are tagged with the active Chroma index_id and invalidated automatically
when re-indexing occurs. Never caches abstentions, fallbacks, or low-confidence results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from typing import Any

from ..config import Settings
from ..schemas import AskResponse

log = logging.getLogger("rahbar.cache")


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def should_cache(response: AskResponse) -> bool:
    """Determine whether a response is eligible for semantic caching.

    Never cache:
    - Honest abstentions (answered_from_context=False)
    - Low-confidence generations
    - Validation fallbacks
    """
    if not response.answered_from_context:
        return False
    if response.confidence == "low":
        return False
    if getattr(response, "is_fallback", False):
        return False
    if "(fallback)" in response.answer.lower():
        return False
    return True


def never_cache(response: AskResponse) -> bool:
    """Return True if the response must NEVER be cached (abstentions, fallbacks, low confidence)."""
    return not should_cache(response)


def invalidate_stale_index_cache(active_index_id: str, entry_index_id: str) -> bool:
    """Invalidate cache entries when Chroma index_id changes after re-indexing."""
    return active_index_id != entry_index_id


class NoopCache:
    """Pass-through cache for environments without Redis."""

    def get(self, question: str, embedding: list[float] | None = None) -> AskResponse | None:
        return None

    def put(
        self,
        question: str,
        response: AskResponse,
        embedding: list[float] | None = None,
    ) -> None:
        pass


class RedisSemanticCache:
    """Semantic cache storing embeddings and JSON responses in Redis."""

    def __init__(
        self,
        settings: Settings,
        redis_client: Any,
        chroma_client: Any = None,
        ttl_seconds: int = 86400,
    ) -> None:
        self.settings = settings
        self.redis_client = redis_client
        self.chroma_client = chroma_client
        self.ttl_seconds = ttl_seconds
        self._current_index_id = "default"
        self._last_index_id_refresh = 0.0
        self._index_id_refresh_interval = 10.0  # seconds

    def get_current_index_id(self) -> str:
        """Fetch the active index_id from Chroma collection metadata (~every 10s)."""
        now = time.monotonic()
        if now - self._last_index_id_refresh < self._index_id_refresh_interval:
            return self._current_index_id

        self._last_index_id_refresh = now
        if self.settings.retriever == "stub":
            self._current_index_id = "default"
            return self._current_index_id

        try:
            if self.chroma_client is None:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                self.chroma_client = chromadb.HttpClient(
                    host=self.settings.chroma_host,
                    port=self.settings.chroma_port,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            collection = self.chroma_client.get_collection(self.settings.collection)
            metadata = collection.metadata or {}
            new_id = metadata.get("index_id")
            if new_id:
                self._current_index_id = str(new_id)
        except Exception as exc:
            log.warning("could not refresh index_id from Chroma metadata", extra={"error": str(exc)})
        return self._current_index_id

    def get(self, question: str, embedding: list[float] | None = None) -> AskResponse | None:
        """Lookup cached response using brute-force cosine similarity over active index_id entries."""
        if not embedding or self.redis_client is None:
            return None

        try:
            current_index_id = self.get_current_index_id()
            pattern = f"rahbar:cache:{current_index_id}:*"
            keys = self.redis_client.keys(pattern)
            if not keys:
                return None

            best_sim = -1.0
            best_response_data: dict[str, Any] | None = None

            for key in keys:
                raw = self.redis_client.get(key)
                if not raw:
                    continue
                entry = json.loads(raw)
                cached_vec = entry.get("embedding")
                sim = cosine_similarity(embedding, cached_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_response_data = entry.get("response")

            if best_sim >= self.settings.cache_threshold and best_response_data:
                log.info(
                    "semantic cache hit",
                    extra={"similarity": round(best_sim, 4), "threshold": self.settings.cache_threshold},
                )
                resp = AskResponse(**best_response_data)
                resp.cached = True
                return resp

            return None
        except Exception as exc:
            # Fail open on Redis connectivity or parsing issues
            log.warning("redis cache lookup failed; failing open", extra={"error": str(exc)})
            return None

    def put(
        self,
        question: str,
        response: AskResponse,
        embedding: list[float] | None = None,
    ) -> None:
        """Store query embedding and response in Redis with a 24h TTL."""
        if not embedding or self.redis_client is None:
            return
        if not should_cache(response):
            return

        try:
            current_index_id = self.get_current_index_id()
            q_hash = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
            key = f"rahbar:cache:{current_index_id}:{q_hash}"
            payload = {
                "question": question,
                "embedding": embedding,
                "response": response.model_dump(),
                "created_at": time.time(),
            }
            self.redis_client.setex(key, self.ttl_seconds, json.dumps(payload))
        except Exception as exc:
            log.warning("redis cache write failed; failing open", extra={"error": str(exc)})


def get_redis_client(settings: Settings) -> Any:
    """Create a Redis client instance configured from Settings."""
    try:
        import redis

        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            decode_responses=True,
        )
    except Exception as exc:
        log.warning("could not initialize redis client", extra={"error": str(exc)})
        return None


def get_cache(settings: Settings, redis_client: Any = None) -> Any:
    """Return configured cache instance (RedisSemanticCache if client exists, else NoopCache)."""
    if redis_client is not None:
        return RedisSemanticCache(settings, redis_client)
    return NoopCache()

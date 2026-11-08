"""Stage 4: Embed. One vector per chunk, from the pinned model only.

Two embedders behind one function, chosen by EMBED_MODEL:
  nomic-embed-text  Ollama /api/embed (the real model).
  hashing-384       deterministic feature-hashed bag of words, no network. Used by CI and
                    dev overlays so the pipeline can run without a model.
Any other EMBED_MODEL is sent to Ollama as-is. api/app/embedding.py holds the same logic
for questions: the two files must stay in step, or the index and the questions would live
in different vector spaces (the embedding pin, section 4.4).
"""

from __future__ import annotations

import hashlib
import math
import re
import time

import httpx

from .config import IndexerSettings

HASHING_MODEL = "hashing-384"
HASHING_DIM = 384
BATCH_SIZE = 16
RETRIES = 4
# nomic-embed-text is trained with task prefixes; documents and queries use different ones.
DOCUMENT_PREFIX = "search_document: "
_TOKEN = re.compile(r"[a-z0-9]+")


def hashing_vector(text: str, dim: int = HASHING_DIM) -> list[float]:
    """Signed feature hashing of word unigrams and bigrams, L2-normalised."""
    tokens = _TOKEN.findall(text.lower())
    vector = [0.0] * dim
    for feature in tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]:
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        number = int.from_bytes(digest, "big")
        vector[number % dim] += 1.0 if (number >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


def embed(
    texts: list[str], settings: IndexerSettings, client: httpx.Client | None = None
) -> list[list[float]]:
    """Embed with settings.embed_model and nothing else."""
    if settings.embed_model == HASHING_MODEL:
        return [hashing_vector(t) for t in texts]
    prefix = DOCUMENT_PREFIX if settings.embed_model.startswith("nomic") else ""
    http = client or httpx.Client(timeout=120.0)
    vectors: list[list[float]] = []
    try:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = [prefix + t for t in texts[start:start + BATCH_SIZE]]
            vectors.extend(_embed_batch(http, settings, batch))
    finally:
        if client is None:
            http.close()
    return vectors


def _embed_batch(http: httpx.Client, settings: IndexerSettings, batch: list[str]) -> list[list[float]]:
    url = f"{settings.ollama_url.rstrip('/')}/api/embed"
    last = "no attempt made"
    for attempt in range(RETRIES):
        try:
            response = http.post(url, json={"model": settings.embed_model, "input": batch})
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            if len(embeddings) != len(batch):
                raise ValueError(f"asked for {len(batch)} embeddings, got {len(embeddings)}")
            return [list(map(float, e)) for e in embeddings]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt < RETRIES - 1:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"embedding failed after {RETRIES} attempts ({last})")

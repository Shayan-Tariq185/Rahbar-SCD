"""Query embeddings matching the indexer's embedding implementation."""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import httpx

from .config import get_settings

HASHING_MODEL = "hashing-384"
HASHING_DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+")


def hashing_vector(text: str, dim: int = HASHING_DIM) -> list[float]:
    tokens = _TOKEN.findall(text.lower())
    vector = [0.0] * dim

    features = tokens + [
        f"{first}_{second}"
        for first, second in zip(tokens, tokens[1:], strict=False)
    ]

    for feature in features:
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        number = int.from_bytes(digest, "big")
        vector[number % dim] += 1.0 if (number >> 63) & 1 else -1.0

    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


@lru_cache(maxsize=512)
def embed_query(text: str) -> list[float]:
    settings = get_settings()

    if settings.embed_model == HASHING_MODEL:
        return hashing_vector(text)

    prefix = "search_query: " if settings.embed_model.startswith("nomic") else ""

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{settings.ollama_url.rstrip('/')}/api/embed",
            json={"model": settings.embed_model, "input": [prefix + text]},
        )
        response.raise_for_status()
        embeddings = response.json()["embeddings"]

    if not embeddings:
        raise RuntimeError("embedding service returned no vectors")

    return [float(value) for value in embeddings[0]]

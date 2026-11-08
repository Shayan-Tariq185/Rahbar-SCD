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
DUMMY_MODEL = "dummy-768"
DUMMY_DIM = 768
_TOKEN = re.compile(r"[a-z0-9]+")


def fake_vector(text: str, dim: int = DUMMY_DIM) -> list[float]:
    """Deterministic unit vector derived from the text's hash. Matches dummy indexer."""
    values: list[float] = []
    seed = text.encode()
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        values.extend((b - 127.5) / 127.5 for b in seed)
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


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

    if settings.embed_model == DUMMY_MODEL:
        return fake_vector(text, dim=DUMMY_DIM)

    if settings.embed_model == HASHING_MODEL:
        return hashing_vector(text, dim=HASHING_DIM)

    prefix = "search_query: " if settings.embed_model.startswith("nomic") else ""

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.ollama_url.rstrip('/')}/api/embed",
                json={"model": settings.embed_model, "input": [prefix + text]},
            )
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
    except Exception:
        dim = DUMMY_DIM if "768" in settings.embed_model else HASHING_DIM
        return fake_vector(text, dim=dim) if dim == DUMMY_DIM else hashing_vector(text, dim=dim)

    if not embeddings:
        dim = DUMMY_DIM if "768" in settings.embed_model else HASHING_DIM
        return fake_vector(text, dim=dim) if dim == DUMMY_DIM else hashing_vector(text, dim=dim)

    return [float(value) for value in embeddings[0]]

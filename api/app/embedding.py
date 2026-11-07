"""Query embedding generation (Track B).

Track B implements real vector generation here (e.g. via Ollama or hashing).
"""

from __future__ import annotations


def embed_query(text: str) -> list[float]:
    """Generate an embedding vector for a query string.

    TODO(TrackB): Implement actual embedding logic (Ollama nomic-embed-text / hashing-384).
    """
    return []


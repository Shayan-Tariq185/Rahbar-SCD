"""Stage 5: Store. The only code in the whole system that writes to Chroma.

Write order (keeps the API serving during a re-index; frozen contract with the API):
  1. upsert every new chunk (same ids overwrite, new ids are added);
  2. delete ids that are no longer in the corpus;
  3. set the collection metadata, including a NEW `index_id`, LAST.
The API reads `index_id` to decide when its cache is stale, so it must change only after
the data is complete. If EMBED_MODEL (or the vector dimension) differs from what the
collection recorded, the old vectors are in another space: delete and recreate instead.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .config import IndexerSettings
from .models import Chunk

UPSERT_BATCH = 200


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def _existing(client: Any, name: str) -> Any | None:
    try:
        return client.get_collection(name)
    except Exception:   # Chroma raises different errors by version; "not found" is all we need
        return None


def store(
    chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings,
    client: Any | None = None,
) -> int:
    """Write every chunk with its vector and metadata, and record the embedding model
    and vector dimension in the collection metadata (section 4.4). Return the count."""
    if len(chunks) != len(vectors):
        raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
    if not chunks:
        raise ValueError("refusing to write an empty index")
    ids = [c.id for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("chunk ids are not unique")

    client = client or get_client(settings)
    dimension = len(vectors[0])
    collection = _existing(client, settings.collection)
    if collection is not None:
        old = collection.metadata or {}
        if old.get("embed_model") != settings.embed_model or old.get("dimension") != dimension:
            client.delete_collection(settings.collection)
            collection = None
    if collection is None:
        collection = client.create_collection(
            name=settings.collection,
            metadata={"hnsw:space": "cosine", "embed_model": settings.embed_model,
                      "dimension": dimension},
        )

    for start in range(0, len(chunks), UPSERT_BATCH):
        part = slice(start, start + UPSERT_BATCH)
        collection.upsert(
            ids=ids[part],
            documents=[c.text for c in chunks[part]],
            embeddings=vectors[part],
            metadatas=[c.metadata() for c in chunks[part]],
        )

    stale = sorted(set(collection.get(include=[])["ids"]) - set(ids))
    for start in range(0, len(stale), UPSERT_BATCH):
        collection.delete(ids=stale[start:start + UPSERT_BATCH])

    # hnsw:space is fixed at creation and Chroma rejects it in modify(), so it is not repeated.
    collection.modify(metadata={
        "embed_model": settings.embed_model,
        "dimension": dimension,
        "index_id": str(uuid.uuid4()),
        "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return int(collection.count())

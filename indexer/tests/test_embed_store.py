from __future__ import annotations

import math
from typing import Any

import httpx
import pytest

from pipeline.config import IndexerSettings
from pipeline.embed import embed, hashing_vector
from pipeline.models import Chunk
from pipeline.store import store


def settings(model: str = "hashing-384") -> IndexerSettings:
    return IndexerSettings(embed_model=model, chroma_host="x", chroma_port=1, collection="rahbar",
                           corpus_dir="/c", chunk_size=400, chunk_overlap=50,
                           ollama_url="http://ollama:11434")


def test_hashing_embedder_is_deterministic_unit_length_and_384_wide() -> None:
    a, b = hashing_vector("academic warning CGPA 2.00"), hashing_vector("academic warning CGPA 2.00")
    assert a == b and len(a) == 384
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-9)


def test_hashing_similarity_ranks_related_text_higher() -> None:
    q = hashing_vector("what is the attendance requirement")
    near = hashing_vector("the attendance requirement is 80 percent")
    far = hashing_vector("library fine ceiling in rupees")
    dot = lambda x, y: sum(i * j for i, j in zip(x, y, strict=True))  # noqa: E731
    assert dot(q, near) > dot(q, far)


def test_embed_with_hashing_needs_no_network() -> None:
    assert len(embed(["a b", "c d"], settings())) == 2


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ollama_embeddings_are_batched_and_prefixed() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]] * len(body["input"])})

    vectors = embed([f"t{i}" for i in range(20)], settings("nomic-embed-text"), _client(handler))
    assert len(vectors) == 20 and len(calls) == 2           # batch size 16
    assert calls[0]["model"] == "nomic-embed-text"
    assert calls[0]["input"][0] == "search_document: t0"


def test_ollama_transient_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipeline.embed.time.sleep", lambda s: None)
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"embeddings": [[0.5, 0.5]]})

    assert embed(["x"], settings("nomic-embed-text"), _client(handler)) == [[0.5, 0.5]]
    assert state["n"] == 3


def test_ollama_gives_up_with_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipeline.embed.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="embedding failed"):
        embed(["x"], settings("nomic-embed-text"), _client(lambda r: httpx.Response(500)))


# ----------------------------------------------------------------------------- store


class FakeCollection:
    def __init__(self, log: list[str], metadata: dict) -> None:
        self.log, self.metadata, self.rows = log, metadata, {}

    def upsert(self, ids, documents, embeddings, metadatas) -> None:
        self.log.append("upsert")
        for i, d, m in zip(ids, documents, metadatas, strict=True):
            self.rows[i] = (d, m)

    def get(self, include=None) -> dict:
        return {"ids": list(self.rows)}

    def delete(self, ids) -> None:
        self.log.append("delete")
        for i in ids:
            self.rows.pop(i, None)

    def modify(self, metadata) -> None:
        self.log.append("modify")
        self.metadata = metadata

    def count(self) -> int:
        return len(self.rows)


class FakeClient:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.col: FakeCollection | None = None

    def get_collection(self, name: str) -> FakeCollection:
        if self.col is None:
            raise ValueError("not found")
        return self.col

    def create_collection(self, name: str, metadata: dict) -> FakeCollection:
        self.log.append("create")
        self.col = FakeCollection(self.log, dict(metadata))
        return self.col

    def delete_collection(self, name: str) -> None:
        self.log.append("drop")
        self.col = None


def _chunks(*ids: str) -> tuple[list[Chunk], list[list[float]]]:
    chunks = [Chunk(i, f"text {i} words here", "s.pdf", "1.1 A", 1, "v", False) for i in ids]
    return chunks, [[0.1, 0.2, 0.3] for _ in ids]


def test_store_writes_in_contract_order_and_sets_index_id_last() -> None:
    client = FakeClient()
    chunks, vectors = _chunks("a", "b")
    assert store(chunks, vectors, settings(), client) == 2
    assert client.log == ["create", "upsert", "modify"]
    meta = client.col.metadata  # type: ignore[union-attr]
    assert meta["embed_model"] == "hashing-384" and meta["dimension"] == 3
    assert meta["index_id"] and meta["indexed_at"]


def test_reindex_deletes_stale_ids_and_changes_index_id() -> None:
    client = FakeClient()
    store(*_chunks("a", "b", "c"), settings(), client)
    first = client.col.metadata["index_id"]  # type: ignore[union-attr]
    client.log.clear()
    assert store(*_chunks("a", "b"), settings(), client) == 2
    assert client.log == ["upsert", "delete", "modify"]       # upsert, delete stale, id LAST
    assert client.col.metadata["index_id"] != first           # type: ignore[union-attr]
    assert sorted(client.col.rows) == ["a", "b"]              # type: ignore[union-attr]


def test_changed_embed_model_recreates_the_collection() -> None:
    client = FakeClient()
    store(*_chunks("a"), settings("hashing-384"), client)
    client.log.clear()
    store(*_chunks("a"), settings("nomic-embed-text"), client)
    assert client.log[:2] == ["drop", "create"]
    assert client.col.metadata["embed_model"] == "nomic-embed-text"  # type: ignore[union-attr]


def test_store_rejects_bad_input() -> None:
    chunks, vectors = _chunks("a", "b")
    with pytest.raises(ValueError):
        store(chunks, vectors[:1], settings(), FakeClient())
    with pytest.raises(ValueError):
        store([], [], settings(), FakeClient())
    dup, dv = _chunks("a", "a")
    with pytest.raises(ValueError):
        store(dup, dv, settings(), FakeClient())

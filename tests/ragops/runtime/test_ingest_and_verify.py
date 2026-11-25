"""Offline unit tests for M1.1 (state/incremental ingestion) and M1.2 (verification/Batch B)."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragops.ingest import (  # noqa: E402
    EmbedIdentity,
    InfrastructureError,
    RuntimeEmbedder,
    run_ingest,
    run_restore,
    run_snapshot_clone,
    run_tombstone,
)
from ragops.state import StateStore  # noqa: E402
from ragops.verify import (  # noqa: E402
    VerificationInput,
    sanitize_filename,
    verify_document,
)
from scripts.make_batch_b import generate_batch_b  # noqa: E402


class FakeVectorStore:
    """In-memory VectorStore fake for offline unit testing only."""

    def __init__(self, fail_next: bool = False) -> None:
        self.collections: dict[str, dict[str, Any]] = {}
        self.fail_next = fail_next

    def _check_fail(self) -> None:
        if self.fail_next:
            raise InfrastructureError("Simulated Chroma outage")

    def get_collection_metadata(self, collection: str) -> dict[str, Any] | None:
        self._check_fail()
        col = self.collections.get(collection)
        return dict(col["metadata"]) if col else None

    def ensure_collection(self, collection: str, metadata: dict[str, Any]) -> None:
        self._check_fail()
        if collection not in self.collections:
            self.collections[collection] = {"metadata": dict(metadata), "items": {}}

    def upsert_chunks(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._check_fail()
        items = self.collections[collection]["items"]
        for cid, doc, emb, meta in zip(ids, documents, embeddings, metadatas, strict=True):
            items[cid] = {"document": doc, "embedding": list(emb), "metadata": dict(meta)}

    def delete_ids(self, collection: str, ids: list[str]) -> None:
        self._check_fail()
        items = self.collections[collection]["items"]
        for cid in ids:
            items.pop(cid, None)

    def update_metadatas(
        self, collection: str, ids: list[str], metadatas: list[dict[str, Any]]
    ) -> None:
        self._check_fail()
        items = self.collections[collection]["items"]
        for cid, meta in zip(ids, metadatas, strict=True):
            if cid in items:
                items[cid]["metadata"] = dict(meta)

    def count_by_doc_id(self, collection: str, doc_id: str) -> int:
        self._check_fail()
        items = self.collections.get(collection, {}).get("items", {})
        return sum(1 for v in items.values() if v["metadata"].get("doc_id") == doc_id)

    def get_all(self, collection: str) -> dict[str, Any]:
        self._check_fail()
        col = self.collections[collection]
        items = col["items"]
        ids = list(items.keys())
        return {
            "metadata": dict(col["metadata"]),
            "ids": ids,
            "documents": [items[i]["document"] for i in ids],
            "embeddings": [items[i]["embedding"] for i in ids],
            "metadatas": [items[i]["metadata"] for i in ids],
        }

    def set_collection_metadata(self, collection: str, metadata: dict[str, Any]) -> None:
        self._check_fail()
        self.collections[collection]["metadata"] = dict(metadata)


class CountingEmbedder:
    """Wraps RuntimeEmbedder(hashing-384) and counts embedding invocations."""

    def __init__(self, model: str = "hashing-384") -> None:
        self.inner = RuntimeEmbedder(model, "http://127.0.0.1:0")
        self.call_count = 0
        self.texts_embedded = 0

    def identity(self) -> EmbedIdentity:
        return self.inner.identity()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.texts_embedded += len(texts)
        return self.inner.embed_texts(texts)


def _write_doc(directory: Path, name: str, doc_id: str, version: str, body: str) -> Path:
    p = directory / name
    p.write_text(
        f"---\ndoc_id: {doc_id}\nfamily_id: {doc_id}\n"
        f"title: Policy {doc_id}\ndoc_version: \"{version}\"\ndate: \"{version}-01-01\"\n---\n"
        f"# Policy {doc_id}\n\n{body}\n",
        encoding="utf-8",
    )
    return p


def test_unchanged_corpus_produces_zero_embeddings(tmp_path: Path) -> None:
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    batch = tmp_path / "batch"
    batch.mkdir()
    _write_doc(batch, "doc1.md", "doc-1", "2026", "Students must maintain 80 percent attendance across all courses.")

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder()

    res1 = run_ingest(
        collection="rahbar_a",
        batch_dir=batch,
        state=state,
        store=store,
        embedder=embedder,
        results_dir=results,
    )
    assert res1["counters"]["docs_indexed"] == 1
    assert res1["counters"]["total_embeddings"] > 0

    embedder.call_count = 0
    embedder.texts_embedded = 0

    res2 = run_ingest(
        collection="rahbar_a",
        batch_dir=batch,
        state=state,
        store=store,
        embedder=embedder,
        results_dir=results,
    )
    assert res2["counters"]["docs_unchanged"] == 1
    assert res2["counters"]["chunk_embeddings"] == 0
    assert res2["counters"]["doc_check_embeddings"] == 0
    assert res2["counters"]["total_embeddings"] == 0
    assert embedder.call_count == 0


def test_changed_doc_updates_only_changed_chunks_and_preserves_other_docs(tmp_path: Path) -> None:
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    batch = tmp_path / "batch"
    batch.mkdir()
    _write_doc(batch, "alpha.md", "alpha", "2026", "## 1. Alpha\nOriginal alpha policy text with details.")
    _write_doc(batch, "beta.md", "beta", "2026", "## 1. Beta\nUnaffected beta policy document content.")

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder()

    run_ingest(collection="rahbar_sandbox", batch_dir=batch, state=state, store=store, embedder=embedder, results_dir=results)
    beta_ids_before = [k for k in store.collections["rahbar_sandbox"]["items"] if k.startswith("beta::")]
    alpha_ids_before = [k for k in store.collections["rahbar_sandbox"]["items"] if k.startswith("alpha::")]

    # Update alpha only
    _write_doc(batch, "alpha.md", "alpha", "2026", "## 1. Alpha\nUpdated alpha policy text with extra requirements.")
    embedder.texts_embedded = 0
    res = run_ingest(collection="rahbar_sandbox", batch_dir=batch, state=state, store=store, embedder=embedder, results_dir=results)

    assert res["counters"]["docs_unchanged"] == 1
    assert res["counters"]["docs_indexed"] == 1
    assert res["counters"]["chunks_deleted"] == len(alpha_ids_before)
    beta_ids_after = [k for k in store.collections["rahbar_sandbox"]["items"] if k.startswith("beta::")]
    alpha_ids_after = [k for k in store.collections["rahbar_sandbox"]["items"] if k.startswith("alpha::")]
    assert beta_ids_after == beta_ids_before
    assert alpha_ids_after != alpha_ids_before


def test_tombstone_deletes_only_target_doc_and_partial_batch_never_deletes(tmp_path: Path) -> None:
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    batch1 = tmp_path / "batch1"
    batch2 = tmp_path / "batch2"
    batch1.mkdir()
    batch2.mkdir()
    _write_doc(batch1, "alpha.md", "alpha", "2026", "Alpha rules regarding tuition fees and registration deadlines.")
    _write_doc(batch1, "beta.md", "beta", "2026", "Beta rules regarding library textbooks and laboratory access.")
    _write_doc(batch2, "gamma.md", "gamma", "2026", "Gamma rules regarding examination seating and hall tickets.")

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder()

    run_ingest(collection="rahbar_sandbox", batch_dir=batch1, state=state, store=store, embedder=embedder, results_dir=results)
    # Ingesting a separate batch dir (simulating inbox->raw movement) must NOT delete alpha/beta
    run_ingest(collection="rahbar_sandbox", batch_dir=batch2, state=state, store=store, embedder=embedder, results_dir=results)
    assert store.count_by_doc_id("rahbar_sandbox", "alpha") > 0
    assert store.count_by_doc_id("rahbar_sandbox", "beta") > 0

    # Explicit tombstone deletes alpha completely
    tomb = run_tombstone(collection="rahbar_sandbox", doc_id="alpha", doc_version=None, state=state, store=store)
    assert tomb["deleted_chunks"] > 0
    assert store.count_by_doc_id("rahbar_sandbox", "alpha") == 0
    assert store.count_by_doc_id("rahbar_sandbox", "beta") > 0


def test_version_supersede_and_restore_and_candidate_isolation(tmp_path: Path) -> None:
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    b_old = tmp_path / "b_old"
    b_new = tmp_path / "b_new"
    b_old.mkdir()
    b_new.mkdir()

    _write_doc(b_old, "rules_2023.md", "rules", "2023", "Minimum attendance was 75 percent in the 2023 rules.")
    _write_doc(b_new, "rules_2026.md", "rules", "2026", "Minimum attendance was 80 percent in the 2026 rules.")

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder()

    run_ingest(collection="rahbar_a", batch_dir=b_old, state=state, store=store, embedder=embedder, results_dir=results)
    # Ingest newer version into rahbar_a -> 2023 becomes superseded & archived
    run_ingest(collection="rahbar_a", batch_dir=b_new, state=state, store=store, embedder=embedder, results_dir=results)
    rec_2023 = state.get_document("rahbar_a", "rules", "2023")
    rec_2026 = state.get_document("rahbar_a", "rules", "2026")
    assert rec_2023 is not None and rec_2023.status == "superseded" and rec_2023.superseded is True
    assert rec_2026 is not None and rec_2026.status == "active" and rec_2026.superseded is False

    # Snapshot clone to candidate collection does not collide or re-embed
    embedder.call_count = 0
    snap = run_snapshot_clone(src_collection="rahbar_a", dst_collection="rahbar_cand_good", state=state, store=store)
    assert snap["chunk_embeddings"] == 0
    assert snap["chunks_cloned"] > 0

    # Restore 2023 in rahbar_cand_good -> 2023 active, 2026 superseded; rahbar_a unaffected
    run_restore(collection="rahbar_cand_good", doc_id="rules", doc_version="2023", state=state, store=store, embedder=embedder)
    cand_2023 = state.get_document("rahbar_cand_good", "rules", "2023")
    cand_2026 = state.get_document("rahbar_cand_good", "rules", "2026")
    orig_2026 = state.get_document("rahbar_a", "rules", "2026")
    assert cand_2023 is not None and cand_2023.status == "active"
    assert cand_2026 is not None and cand_2026.status == "superseded"
    assert orig_2026 is not None and orig_2026.status == "active"


def test_failed_retry_recovery_and_pin_mismatch(tmp_path: Path) -> None:
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    batch = tmp_path / "batch"
    batch.mkdir()
    _write_doc(batch, "doc1.md", "doc-1", "2026", "Valid document text for crash recovery testing.")

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder("hashing-384")

    # Simulate infra failure mid-run
    failing_store = FakeVectorStore(fail_next=True)
    with pytest.raises(InfrastructureError):
        run_ingest(collection="rahbar_sandbox", batch_dir=batch, state=state, store=failing_store, embedder=embedder, results_dir=results)
    # Valid doc was NOT quarantined during infra failure
    assert state.get_document("rahbar_sandbox", "doc-1", "2026") is None

    # Retry succeeds and recovers pending revision
    res = run_ingest(collection="rahbar_sandbox", batch_dir=batch, state=state, store=store, embedder=embedder, results_dir=results)
    assert res["committed_revision"] == 1

    # Different embed model on same collection fails loudly
    bad_embedder = CountingEmbedder("dummy-768")
    with pytest.raises(InfrastructureError, match="mismatch"):
        run_ingest(collection="rahbar_sandbox", batch_dir=batch, state=state, store=store, embedder=bad_embedder, results_dir=results)


def test_writer_lock_serializes_concurrent_writers(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "datalake")
    timeline: list[tuple[str, float]] = []

    def worker(name: str) -> None:
        with state.writer_lock(timeout_seconds=5.0, owner=name).acquire():
            timeline.append((f"{name}-start", time.monotonic()))
            time.sleep(0.08)
            timeline.append((f"{name}-end", time.monotonic()))

    t1 = threading.Thread(target=worker, args=("w1",))
    t2 = threading.Thread(target=worker, args=("w2",))
    t1.start()
    time.sleep(0.01)
    t2.start()
    t1.join()
    t2.join()

    # Second writer starts only after first writer ends
    assert timeline[1][0].endswith("-end")
    assert timeline[2][0].endswith("-start")
    assert timeline[2][1] >= timeline[1][1]


def test_verify_checks_and_batch_b_e2e(tmp_path: Path) -> None:
    # Filename traversal rejected
    with pytest.raises(ValueError):
        sanitize_filename("../secret.pdf")

    # Extraction error explicitly populates all 4 check fields
    err_res = verify_document(
        VerificationInput("bad", "bad", "2026", "bad.pdf", "Bad", "2026", 0, [], extraction_error="corrupt"),
        existing_family_versions=[],
        existing_active_docs=[],
    )
    assert set(err_res.checks.keys()) == {"quality", "completeness", "recency", "uniqueness"}
    assert err_res.decision == "quarantine"
    assert "not_executable" in err_res.checks["completeness"].reason

    # Full Batch B generation (>=10 docs) and ingestion after Batch A
    datalake = tmp_path / "datalake"
    results = tmp_path / "results"
    batch_a = tmp_path / "batch_a"
    batch_b = tmp_path / "batch_b"
    batch_a.mkdir()
    _write_doc(batch_a, "academic_rules_2026.md", "academic-rules", "2026", "Minimum attendance is 80 percent.")

    summary_b = generate_batch_b(batch_b)
    assert summary_b["count"] >= 10
    assert (batch_b / "PLANTED.md").exists()

    state = StateStore(datalake)
    store = FakeVectorStore()
    embedder = CountingEmbedder("hashing-384")

    run_ingest(collection="rahbar_a", batch_dir=batch_a, state=state, store=store, embedder=embedder, results_dir=results)
    run_snapshot_clone(src_collection="rahbar_a", dst_collection="rahbar_ab", state=state, store=store)
    res_b = run_ingest(collection="rahbar_ab", batch_dir=batch_b, state=state, store=store, embedder=embedder, results_dir=results)

    # Expect: academic-rules 2027, lab-safety-a, campus-network-policy (injected), 2 fillers = 5 indexed
    # Exact dup, near-dup, corrupt pdf, garbled md, missing metadata, truncated = 6 quarantined
    # Older academic-rules 2021 = 1 archived
    assert res_b["counters"]["docs_indexed"] == 5
    assert res_b["counters"]["docs_quarantined"] == 6
    assert res_b["counters"]["docs_archived"] == 1
    # Verify indexable Batch B injection survived verification for D4 testing
    inj_rec = state.get_document("rahbar_ab", "campus-network-policy", "2027-01")
    assert inj_rec is not None and inj_rec.status == "active"
    # Verify verification report written
    assert Path(res_b["report_json"]).exists()
    assert Path(res_b["report_md"]).exists()
    report_data = json.loads(Path(res_b["report_json"]).read_text(encoding="utf-8"))
    assert len(report_data["documents"]) == 12

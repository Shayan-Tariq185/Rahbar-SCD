"""Persistent datalake state, revision tracking, and shared writer locking."""

from __future__ import annotations

import json
import os
import socket
import sys
import shutil
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WriterLockTimeout(RuntimeError):
    """Raised when the shared writer lock cannot be acquired within timeout."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DocumentRecord:
    collection: str
    doc_id: str
    doc_version: str
    family_id: str
    title: str
    source: str
    date_or_version: str
    page_count: int
    raw_hash: str
    content_hash: str
    pipeline_fingerprint: str
    status: str
    superseded: bool
    stored_path: str
    chunk_ids: list[str]
    doc_embedding: list[float] | None
    verification: dict[str, Any]
    updated_at: str


def _acquire_file_lock(fd: int) -> bool:
    if sys.platform == "win32":
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _release_file_lock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


class WriterLock:
    """Cross-process file lock serializing all Chroma & state writes.

    On single-node Minikube with a ReadWriteOnce PVC at /datalake, the Linux kernel
    automatically releases flock if a Job pod is killed; stale metadata TTL handles
    leftover metadata cleanup safely. Multi-node RWX deployments would require a
    Kubernetes Lease or distributed lock.
    """

    def __init__(
        self,
        lock_path: Path,
        timeout_seconds: float = 120.0,
        stale_ttl_seconds: float = 600.0,
        owner: str = "ragops-ingest",
    ) -> None:
        self.lock_path = lock_path
        self.meta_path = lock_path.with_suffix(".lock.meta.json")
        self.timeout_seconds = timeout_seconds
        self.stale_ttl_seconds = stale_ttl_seconds
        self.owner = owner
        self._fd: int | None = None

    def _clear_stale_meta_if_expired(self) -> bool:
        if not self.meta_path.exists():
            return False
        try:
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            acquired_epoch = float(meta.get("acquired_epoch", 0.0))
            if time.time() - acquired_epoch > self.stale_ttl_seconds:
                self.meta_path.unlink(missing_ok=True)
                return True
        except Exception:
            return False
        return False

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o664)
        acquired = False
        try:
            while True:
                if _acquire_file_lock(fd):
                    acquired = True
                    break
                self._clear_stale_meta_if_expired()
                if time.monotonic() >= deadline:
                    holder = ""
                    if self.meta_path.exists():
                        holder = f" (current holder: {self.meta_path.read_text(encoding='utf-8')})"
                    raise WriterLockTimeout(
                        f"Timed out after {self.timeout_seconds}s waiting for writer lock "
                        f"{self.lock_path}{holder}"
                    )
                time.sleep(0.05)

            self._fd = fd
            meta = {
                "owner": self.owner,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "acquired_at": utc_now_iso(),
                "acquired_epoch": time.time(),
                "ttl_seconds": self.stale_ttl_seconds,
            }
            self.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            yield
        finally:
            if acquired:
                self.meta_path.unlink(missing_ok=True)
                _release_file_lock(fd)
            os.close(fd)
            self._fd = None


class StateStore:
    """SQLite state store under /datalake/state/state.db scoped by collection + doc + version."""

    def __init__(self, datalake_dir: Path | str, db_path: Path | str | None = None) -> None:
        self.datalake_dir = Path(datalake_dir)
        self.inbox_dir = self.datalake_dir / "inbox"
        self.raw_dir = self.datalake_dir / "raw"
        self.archive_dir = self.datalake_dir / "archive"
        self.quarantine_dir = self.datalake_dir / "quarantine"
        self.state_dir = self.datalake_dir / "state"
        self.db_path = Path(db_path) if db_path else self.state_dir / "state.db"
        self.lock_path = self.state_dir / "writer.lock"
        self._ensure_dirs()
        self._init_db()

    def _ensure_dirs(self) -> None:
        for path in (
            self.inbox_dir,
            self.raw_dir,
            self.archive_dir,
            self.quarantine_dir,
            self.state_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    doc_version TEXT NOT NULL,
                    family_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    date_or_version TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    raw_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    pipeline_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    superseded INTEGER NOT NULL DEFAULT 0,
                    stored_path TEXT NOT NULL,
                    chunk_ids_json TEXT NOT NULL,
                    doc_embedding_json TEXT,
                    verification_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (collection, doc_id, doc_version)
                );

                CREATE INDEX IF NOT EXISTS idx_docs_family
                    ON documents (collection, family_id, status);

                CREATE TABLE IF NOT EXISTS collection_revisions (
                    collection TEXT PRIMARY KEY,
                    committed_revision INTEGER NOT NULL DEFAULT 0,
                    pending_revision INTEGER,
                    index_id TEXT NOT NULL,
                    embed_model TEXT NOT NULL,
                    embed_digest TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    pipeline_fingerprint TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    doc_id TEXT,
                    doc_version TEXT,
                    details_json TEXT NOT NULL
                );
                """
            )

    def writer_lock(
        self,
        timeout_seconds: float = 120.0,
        stale_ttl_seconds: float = 600.0,
        owner: str = "ragops-ingest",
    ) -> WriterLock:
        return WriterLock(
            self.lock_path,
            timeout_seconds=timeout_seconds,
            stale_ttl_seconds=stale_ttl_seconds,
            owner=owner,
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
        emb_raw = row["doc_embedding_json"]
        return DocumentRecord(
            collection=row["collection"],
            doc_id=row["doc_id"],
            doc_version=row["doc_version"],
            family_id=row["family_id"],
            title=row["title"],
            source=row["source"],
            date_or_version=row["date_or_version"],
            page_count=int(row["page_count"]),
            raw_hash=row["raw_hash"],
            content_hash=row["content_hash"],
            pipeline_fingerprint=row["pipeline_fingerprint"],
            status=row["status"],
            superseded=bool(row["superseded"]),
            stored_path=row["stored_path"],
            chunk_ids=json.loads(row["chunk_ids_json"]),
            doc_embedding=json.loads(emb_raw) if emb_raw else None,
            verification=json.loads(row["verification_json"]),
            updated_at=row["updated_at"],
        )

    def log_audit(
        self,
        collection: str,
        run_id: str,
        action: str,
        doc_id: str | None = None,
        doc_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now_iso(),
                    collection,
                    run_id,
                    action,
                    doc_id,
                    doc_version,
                    json.dumps(details or {}, sort_keys=True),
                ),
            )

    def get_revision(self, collection: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM collection_revisions WHERE collection = ?", (collection,)
            ).fetchone()
            return dict(row) if row else None

    def begin_revision(
        self,
        collection: str,
        run_id: str,
        embed_model: str,
        embed_digest: str,
        dimension: int,
        pipeline_fingerprint: str,
    ) -> int:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM collection_revisions WHERE collection = ?", (collection,)
            ).fetchone()
            if row is None:
                pending = 1
                conn.execute(
                    """
                    INSERT INTO collection_revisions (
                        collection, committed_revision, pending_revision, index_id,
                        embed_model, embed_digest, dimension, pipeline_fingerprint, updated_at
                    ) VALUES (?, 0, ?, '', ?, ?, ?, ?, ?)
                    """,
                    (
                        collection,
                        pending,
                        embed_model,
                        embed_digest,
                        dimension,
                        pipeline_fingerprint,
                        now,
                    ),
                )
            else:
                if row["pending_revision"] is not None:
                    conn.execute(
                        """
                        INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                        VALUES (?, ?, ?, 'abort_recovery', NULL, NULL, ?)
                        """,
                        (
                            now,
                            collection,
                            run_id,
                            json.dumps({"recovered_pending_revision": row["pending_revision"]}),
                        ),
                    )
                pending = int(row["committed_revision"]) + 1
                conn.execute(
                    """
                    UPDATE collection_revisions
                    SET pending_revision = ?, updated_at = ?
                    WHERE collection = ?
                    """,
                    (pending, now, collection),
                )
            return pending

    def commit_revision(
        self,
        collection: str,
        run_id: str,
        revision: int,
        index_id: str,
        embed_model: str,
        embed_digest: str,
        dimension: int,
        pipeline_fingerprint: str,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE collection_revisions
                SET committed_revision = ?, pending_revision = NULL, index_id = ?,
                    embed_model = ?, embed_digest = ?, dimension = ?,
                    pipeline_fingerprint = ?, updated_at = ?
                WHERE collection = ?
                """,
                (
                    revision,
                    index_id,
                    embed_model,
                    embed_digest,
                    dimension,
                    pipeline_fingerprint,
                    now,
                    collection,
                ),
            )
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, 'commit', NULL, NULL, ?)
                """,
                (
                    now,
                    collection,
                    run_id,
                    json.dumps({"committed_revision": revision, "index_id": index_id}),
                ),
            )

    def abort_revision(self, collection: str, run_id: str, reason: str) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE collection_revisions SET pending_revision = NULL, updated_at = ? WHERE collection = ?",
                (now, collection),
            )
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, 'abort_recovery', NULL, NULL, ?)
                """,
                (now, collection, run_id, json.dumps({"reason": reason})),
            )

    def get_document(self, collection: str, doc_id: str, doc_version: str) -> DocumentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM documents
                WHERE collection = ? AND doc_id = ? AND doc_version = ?
                """,
                (collection, doc_id, doc_version),
            ).fetchone()
            return self._row_to_record(row) if row else None

    def get_documents_by_doc_id(self, collection: str, doc_id: str) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE collection = ? AND doc_id = ? ORDER BY updated_at DESC",
                (collection, doc_id),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_family_versions(self, collection: str, family_id: str) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents
                WHERE collection = ? AND family_id = ? AND status IN ('active', 'superseded')
                ORDER BY updated_at DESC
                """,
                (collection, family_id),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_active_documents(self, collection: str) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE collection = ? AND status = 'active' ORDER BY doc_id",
                (collection,),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def upsert_document(self, rec: DocumentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    collection, doc_id, doc_version, family_id, title, source,
                    date_or_version, page_count, raw_hash, content_hash,
                    pipeline_fingerprint, status, superseded, stored_path,
                    chunk_ids_json, doc_embedding_json, verification_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (collection, doc_id, doc_version) DO UPDATE SET
                    family_id = excluded.family_id,
                    title = excluded.title,
                    source = excluded.source,
                    date_or_version = excluded.date_or_version,
                    page_count = excluded.page_count,
                    raw_hash = excluded.raw_hash,
                    content_hash = excluded.content_hash,
                    pipeline_fingerprint = excluded.pipeline_fingerprint,
                    status = excluded.status,
                    superseded = excluded.superseded,
                    stored_path = excluded.stored_path,
                    chunk_ids_json = excluded.chunk_ids_json,
                    doc_embedding_json = excluded.doc_embedding_json,
                    verification_json = excluded.verification_json,
                    updated_at = excluded.updated_at
                """,
                (
                    rec.collection,
                    rec.doc_id,
                    rec.doc_version,
                    rec.family_id,
                    rec.title,
                    rec.source,
                    rec.date_or_version,
                    rec.page_count,
                    rec.raw_hash,
                    rec.content_hash,
                    rec.pipeline_fingerprint,
                    rec.status,
                    1 if rec.superseded else 0,
                    rec.stored_path,
                    json.dumps(rec.chunk_ids),
                    json.dumps(rec.doc_embedding) if rec.doc_embedding is not None else None,
                    json.dumps(rec.verification, sort_keys=True),
                    rec.updated_at,
                ),
            )

    def mark_superseded(
        self,
        collection: str,
        doc_id: str,
        doc_version: str,
        archived_path: str,
        run_id: str,
        superseded_by: str,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = 'superseded', superseded = 1, stored_path = ?, updated_at = ?
                WHERE collection = ? AND doc_id = ? AND doc_version = ?
                """,
                (archived_path, now, collection, doc_id, doc_version),
            )
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, 'archive_superseded', ?, ?, ?)
                """,
                (now, collection, run_id, doc_id, doc_version, json.dumps({"superseded_by": superseded_by})),
            )

    def mark_deleted(
        self,
        collection: str,
        doc_id: str,
        doc_version: str,
        archived_path: str,
        run_id: str,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = 'deleted', superseded = 1, stored_path = ?, chunk_ids_json = '[]', updated_at = ?
                WHERE collection = ? AND doc_id = ? AND doc_version = ?
                """,
                (archived_path, now, collection, doc_id, doc_version),
            )
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, 'tombstone', ?, ?, ?)
                """,
                (now, collection, run_id, doc_id, doc_version, json.dumps({"archived_path": archived_path})),
            )

    def clone_collection_state(self, src_collection: str, dst_collection: str, run_id: str) -> int:
        now = utc_now_iso()
        with self._connect() as conn:
            src_rev = conn.execute(
                "SELECT * FROM collection_revisions WHERE collection = ?", (src_collection,)
            ).fetchone()
            if src_rev:
                conn.execute(
                    """
                    INSERT INTO collection_revisions (
                        collection, committed_revision, pending_revision, index_id,
                        embed_model, embed_digest, dimension, pipeline_fingerprint, updated_at
                    ) VALUES (?, 1, NULL, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (collection) DO UPDATE SET
                        committed_revision = collection_revisions.committed_revision + 1,
                        pending_revision = NULL,
                        index_id = excluded.index_id,
                        embed_model = excluded.embed_model,
                        embed_digest = excluded.embed_digest,
                        dimension = excluded.dimension,
                        pipeline_fingerprint = excluded.pipeline_fingerprint,
                        updated_at = excluded.updated_at
                    """,
                    (
                        dst_collection,
                        f"{src_rev['index_id']}-snap",
                        src_rev["embed_model"],
                        src_rev["embed_digest"],
                        src_rev["dimension"],
                        src_rev["pipeline_fingerprint"],
                        now,
                    ),
                )
            rows = conn.execute(
                "SELECT * FROM documents WHERE collection = ?", (src_collection,)
            ).fetchall()
            for row in rows:
                # Each collection owns its files. A later archive/delete in a
                # drift collection must never move a frozen baseline original.
                source_path = Path(row["stored_path"])
                area = self.raw_dir if row["status"] == "active" else (
                    self.quarantine_dir if row["status"] == "quarantined" else self.archive_dir)
                destination_path = area / dst_collection / source_path.name
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                if source_path.resolve() != destination_path.resolve():
                    shutil.copy2(source_path, destination_path)
                conn.execute(
                    """
                    INSERT INTO documents (
                        collection, doc_id, doc_version, family_id, title, source,
                        date_or_version, page_count, raw_hash, content_hash,
                        pipeline_fingerprint, status, superseded, stored_path,
                        chunk_ids_json, doc_embedding_json, verification_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (collection, doc_id, doc_version) DO UPDATE SET
                        family_id = excluded.family_id,
                        title = excluded.title,
                        source = excluded.source,
                        date_or_version = excluded.date_or_version,
                        page_count = excluded.page_count,
                        raw_hash = excluded.raw_hash,
                        content_hash = excluded.content_hash,
                        pipeline_fingerprint = excluded.pipeline_fingerprint,
                        status = excluded.status,
                        superseded = excluded.superseded,
                        stored_path = excluded.stored_path,
                        chunk_ids_json = excluded.chunk_ids_json,
                        doc_embedding_json = excluded.doc_embedding_json,
                        verification_json = excluded.verification_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        dst_collection,
                        row["doc_id"],
                        row["doc_version"],
                        row["family_id"],
                        row["title"],
                        row["source"],
                        row["date_or_version"],
                        row["page_count"],
                        row["raw_hash"],
                        row["content_hash"],
                        row["pipeline_fingerprint"],
                        row["status"],
                        row["superseded"],
                        str(destination_path),
                        row["chunk_ids_json"],
                        row["doc_embedding_json"],
                        row["verification_json"],
                        now,
                    ),
                )
            conn.execute(
                """
                INSERT INTO audit_events (ts, collection, run_id, action, doc_id, doc_version, details_json)
                VALUES (?, ?, ?, 'snapshot_clone', NULL, NULL, ?)
                """,
                (now, dst_collection, run_id, json.dumps({"source_collection": src_collection, "docs": len(rows)})),
            )
            return len(rows)

    def status_summary(self, collection: str) -> dict[str, Any]:
        with self._connect() as conn:
            rev = conn.execute(
                "SELECT * FROM collection_revisions WHERE collection = ?", (collection,)
            ).fetchone()
            rows = conn.execute(
                "SELECT * FROM documents WHERE collection = ? ORDER BY doc_id, doc_version",
                (collection,),
            ).fetchall()
            counts = {"active": 0, "superseded": 0, "quarantined": 0, "deleted": 0}
            active_chunks = 0
            docs_out = []
            for r in rows:
                st = str(r["status"])
                counts[st] = counts.get(st, 0) + 1
                chunk_ids = json.loads(r["chunk_ids_json"])
                if st == "active":
                    active_chunks += len(chunk_ids)
                docs_out.append(
                    {
                        "doc_id": r["doc_id"],
                        "doc_version": r["doc_version"],
                        "family_id": r["family_id"],
                        "status": st,
                        "superseded": bool(r["superseded"]),
                        "chunks": len(chunk_ids),
                        "source": r["source"],
                    }
                )
            events = conn.execute(
                """
                SELECT ts, run_id, action, doc_id, doc_version, details_json
                FROM audit_events WHERE collection = ?
                ORDER BY id DESC LIMIT 20
                """,
                (collection,),
            ).fetchall()
            return {
                "collection": collection,
                "revision": dict(rev) if rev else None,
                "counts": counts,
                "active_chunks": active_chunks,
                "documents": docs_out,
                "recent_events": [
                    {
                        "ts": e["ts"],
                        "run_id": e["run_id"],
                        "action": e["action"],
                        "doc_id": e["doc_id"],
                        "doc_version": e["doc_version"],
                        "details": json.loads(e["details_json"]),
                    }
                    for e in events
                ],
            }

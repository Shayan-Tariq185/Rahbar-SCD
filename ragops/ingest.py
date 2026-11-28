"""Incremental, verified RAGOps ingestion CLI & writer path (A1 + A2).

Usage:
    python -m ragops.ingest run --collection rahbar_a --batch-dir /datalake/inbox
    python -m ragops.ingest status --collection rahbar_a
    python -m ragops.ingest count --collection rahbar_a --doc-id academic-rules
    python -m ragops.ingest restore --collection rahbar_sandbox --doc-id academic-rules --version 2023
    python -m ragops.ingest tombstone --collection rahbar_sandbox --doc-id test-doc
    python -m ragops.ingest snapshot --snapshot-from rahbar_a --collection rahbar_ab
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol

from .state import DocumentRecord, StateStore, WriterLockTimeout, utc_now_iso
from .verify import (
    DEFAULT_NEAR_DUP_THRESHOLD,
    VerificationInput,
    VerificationResult,
    sanitize_filename,
    verify_document,
)

EXTRACTOR_VERSION = "ragops-ext-v1"
SUPPORTED_EXTS = {".pdf", ".md", ".txt", ".html", ".htm"}


class InfrastructureError(RuntimeError):
    """Raised on Chroma, Ollama, or storage outages (exits 2, never quarantines docs)."""


def _log(msg: str, **fields: object) -> None:
    payload = {
        "ts": utc_now_iso(),
        "logger": "ragops.ingest",
        "msg": msg,
        **fields,
    }
    print(json.dumps(payload, default=str), flush=True)


def _deterministic_vector(text: str, dim: int) -> list[float]:
    words = re.findall(r"\w+", text.lower())
    if not words:
        return [0.0] * dim
    vec = [0.0] * dim
    for w in words:
        h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16) % dim
        sign = 1.0 if int(hashlib.md5(w.encode("utf-8")).hexdigest()[8:10], 16) % 2 == 0 else -1.0
        vec[h] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@dataclass
class EmbedIdentity:
    model: str
    digest: str
    dimension: int


class Embedder(Protocol):
    def identity(self) -> EmbedIdentity: ...
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class RuntimeEmbedder:
    """Embedding adapter supporting deterministic CI pins and Ollama /api/tags + /api/embed."""

    def __init__(self, model: str, ollama_url: str, timeout_s: float = 60.0) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout_s = timeout_s
        self._identity: EmbedIdentity | None = None

    def identity(self) -> EmbedIdentity:
        if self._identity is not None:
            return self._identity
        if self.model == "hashing-384":
            self._identity = EmbedIdentity(self.model, "sha256:hashing-384", 384)
            return self._identity
        if self.model == "dummy-768":
            self._identity = EmbedIdentity(self.model, "sha256:dummy-768", 768)
            return self._identity

        import httpx

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.ollama_url}/api/tags")
                resp.raise_for_status()
                tags_data = resp.json()
        except Exception as exc:
            raise InfrastructureError(
                f"Ollama /api/tags unreachable at {self.ollama_url}: {exc}"
            ) from exc

        digest = ""
        for entry in tags_data.get("models") or []:
            name = str(entry.get("name", ""))
            base = name.split(":")[0]
            if name == self.model or base == self.model:
                digest = str(entry.get("digest", ""))
                break
        if not digest:
            raise InfrastructureError(
                f"Embedding model {self.model!r} not found in Ollama /api/tags"
            )

        # Probe vector dimension with a single small call only once during identity resolution
        probe = self.embed_texts(["dimension probe"])
        dim = len(probe[0]) if probe else 0
        if dim <= 0:
            raise InfrastructureError(f"Ollama returned empty embedding for model {self.model!r}")
        self._identity = EmbedIdentity(self.model, digest, dim)
        return self._identity

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.model == "hashing-384":
            return [_deterministic_vector(t, 384) for t in texts]
        if self.model == "dummy-768":
            return [_deterministic_vector(t, 768) for t in texts]

        import httpx

        try:
            out: list[list[float]] = []
            batch_size = 16
            with httpx.Client(timeout=self.timeout_s) as client:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    resp = client.post(
                        f"{self.ollama_url}/api/embed",
                        json={"model": self.model, "input": batch},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    embs = data.get("embeddings")
                    if not isinstance(embs, list) or len(embs) != len(batch):
                        raise InfrastructureError("Malformed /api/embed response from Ollama")
                    out.extend(embs)
            return out
        except InfrastructureError:
            raise
        except Exception as exc:
            raise InfrastructureError(f"Ollama /api/embed failed: {exc}") from exc


class VectorStore(Protocol):
    def get_collection_metadata(self, collection: str) -> dict[str, Any] | None: ...
    def ensure_collection(self, collection: str, metadata: dict[str, Any]) -> None: ...
    def upsert_chunks(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None: ...
    def delete_ids(self, collection: str, ids: list[str]) -> None: ...
    def update_metadatas(
        self, collection: str, ids: list[str], metadatas: list[dict[str, Any]]
    ) -> None: ...
    def count_by_doc_id(self, collection: str, doc_id: str) -> int: ...
    def get_all(self, collection: str) -> dict[str, Any]: ...
    def set_collection_metadata(self, collection: str, metadata: dict[str, Any]) -> None: ...


class ChromaVectorStore:
    """Thin Chroma HTTP client adapter implementing VectorStore."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                self._client = chromadb.HttpClient(
                    host=self.host,
                    port=self.port,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._client.heartbeat()
            except Exception as exc:
                raise InfrastructureError(
                    f"ChromaDB unreachable at {self.host}:{self.port}: {exc}"
                ) from exc
        return self._client

    def get_collection_metadata(self, collection: str) -> dict[str, Any] | None:
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            return dict(col.metadata or {})
        except Exception as exc:
            msg = str(exc).lower()
            if "does not exist" in msg or "not found" in msg:
                return None
            # Try list_collections fallback across chromadb versions
            try:
                names = [c.name if hasattr(c, "name") else str(c) for c in client.list_collections()]
                if collection not in names:
                    return None
            except Exception as inner:
                raise InfrastructureError(f"Chroma query failed: {inner}") from inner
            raise InfrastructureError(f"Chroma get_collection failed: {exc}") from exc

    def ensure_collection(self, collection: str, metadata: dict[str, Any]) -> None:
        client = self._get_client()
        try:
            client.get_or_create_collection(name=collection, metadata=metadata)
        except Exception as exc:
            raise InfrastructureError(f"Chroma get_or_create_collection failed: {exc}") from exc

    def upsert_chunks(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            col.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            raise InfrastructureError(f"Chroma upsert failed: {exc}") from exc

    def delete_ids(self, collection: str, ids: list[str]) -> None:
        if not ids:
            return
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            col.delete(ids=ids)
        except Exception as exc:
            raise InfrastructureError(f"Chroma delete failed: {exc}") from exc

    def update_metadatas(
        self, collection: str, ids: list[str], metadatas: list[dict[str, Any]]
    ) -> None:
        if not ids:
            return
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            col.update(ids=ids, metadatas=metadatas)
        except Exception as exc:
            raise InfrastructureError(f"Chroma metadata update failed: {exc}") from exc

    def count_by_doc_id(self, collection: str, doc_id: str) -> int:
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            res = col.get(where={"doc_id": doc_id}, include=[])
            return len(res.get("ids") or [])
        except Exception as exc:
            raise InfrastructureError(f"Chroma count_by_doc_id failed: {exc}") from exc

    def get_all(self, collection: str) -> dict[str, Any]:
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            data = col.get(include=["documents", "embeddings", "metadatas"])
            return {
                "metadata": dict(col.metadata or {}),
                "ids": list(data.get("ids") or []),
                "documents": list(data.get("documents") or []),
                "embeddings": list(data.get("embeddings") or []),
                "metadatas": list(data.get("metadatas") or []),
            }
        except Exception as exc:
            raise InfrastructureError(f"Chroma get_all failed: {exc}") from exc

    def set_collection_metadata(self, collection: str, metadata: dict[str, Any]) -> None:
        client = self._get_client()
        try:
            col = client.get_collection(collection)
            col.modify(metadata=metadata)
        except Exception as exc:
            raise InfrastructureError(f"Chroma set_collection_metadata failed: {exc}") from exc


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip = True
        elif tag in {"h1", "h2", "h3", "h4", "p", "li", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._parts.append(data.strip() + " ")

    def text(self) -> str:
        return "".join(self._parts)


def _strip_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    end_idx = 0
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = idx + 1
            break
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip("\"'")
    if end_idx == 0:
        return {}, text
    return meta, "\n".join(lines[end_idx:])


def _extract_pages_sync(path: Path, doc_version: str, superseded: bool) -> list[str]:
    """Try existing pipeline.extract first; fall back to built-in bounded extractor if stubbed."""
    try:
        from pipeline.extract import extract as a02_extract  # type: ignore

        doc = a02_extract(str(path), doc_version, superseded)
        return [p.text for p in doc.pages]
    except (ImportError, NotImplementedError):
        pass

    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        raw = path.read_text(encoding="utf-8")
        _, body = _strip_front_matter(raw)
        pages = [p.strip() for p in re.split(r"\n\s*<!--\s*pagebreak\s*-->\s*\n|\f", body) if p.strip()]
        return pages or ([body.strip()] if body.strip() else [])
    if suffix in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8")
        parser = _HtmlTextExtractor()
        parser.feed(raw)
        txt = parser.text().strip()
        return [txt] if txt else []
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(page.extract_text() or "").strip() for page in reader.pages]
    raise ValueError(f"Unsupported file extension: {suffix}")


def extract_with_timeout(
    path: Path, doc_version: str, superseded: bool, timeout_s: float = 30.0
) -> tuple[list[str], str | None]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_extract_pages_sync, path, doc_version, superseded)
        try:
            pages = future.result(timeout=timeout_s)
            return pages, None
        except FuturesTimeoutError:
            return [], f"extraction_timeout_after_{timeout_s}s"
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"


def _clean_page_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _chunk_pages(
    pages_text: list[str],
    doc_id: str,
    doc_version: str,
    source: str,
    superseded: bool,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    """Structure-aware chunker preserving section headings, page numbers, and stable IDs."""
    chunks: list[dict[str, Any]] = []
    current_section = "General"
    idx = 0
    step_words = max(1, chunk_size - min(chunk_overlap, max(0, chunk_size - 1)))

    for page_num, page_text in enumerate(pages_text, start=1):
        cleaned = _clean_page_text(page_text)
        if not cleaned:
            continue
        sections: list[tuple[str, list[str]]] = []
        buf: list[str] = []
        for line in cleaned.splitlines():
            if line.startswith("#") or re.match(r"^\d+(\.\d+)*\s+[A-Z]", line):
                if buf:
                    sections.append((current_section, buf))
                    buf = []
                current_section = line.lstrip("#").strip()[:120] or current_section
            buf.append(line)
        if buf:
            sections.append((current_section, buf))

        for sec_name, sec_lines in sections:
            words = " ".join(sec_lines).split()
            if not words:
                continue
            pos = 0
            while pos < len(words):
                piece = " ".join(words[pos : pos + chunk_size])
                text_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()[:12]
                chunk_id = f"{doc_id}::{doc_version}::{idx:04d}::{text_hash}"
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": piece,
                        "metadata": {
                            "doc_id": doc_id,
                            "family_id": doc_id,
                            "source": source,
                            "section": sec_name,
                            "page": page_num,
                            "doc_version": doc_version,
                            "superseded": superseded,
                        },
                    }
                )
                idx += 1
                if pos + chunk_size >= len(words):
                    break
                pos += step_words
    return chunks


@dataclass
class DiscoveredDoc:
    path: Path
    source: str
    doc_id: str
    family_id: str
    title: str
    doc_version: str
    date_or_version: str
    superseded: bool
    expected_pages: int | None


def _derive_family_id(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stripped = re.sub(r"[-_ ]?(?:19|20)\d{2}(?:[-_]\d{2})?$", "", stem)
    return re.sub(r"[^a-z0-9]+", "-", stripped).strip("-") or stem


def discover_batch(batch_dir: Path) -> list[DiscoveredDoc]:
    """Discover documents and real metadata from _index.json or frontmatter without inventing values."""
    if not batch_dir.exists():
        raise ValueError(f"Batch directory does not exist: {batch_dir}")
    index_file = batch_dir / "_index.json"
    out: list[DiscoveredDoc] = []

    if index_file.exists():
        entries = json.loads(index_file.read_text(encoding="utf-8"))
        for entry in entries:
            raw_file = str(entry.get("file", ""))
            safe_name = sanitize_filename(raw_file)
            full_path = batch_dir / safe_name
            if not full_path.exists():
                raise ValueError(f"Indexed file missing in batch: {full_path}")
            doc_version = str(entry.get("doc_version", ""))
            date_val = str(entry.get("date", doc_version))
            title = str(entry.get("title", ""))
            doc_id = str(entry.get("doc_id") or Path(safe_name).stem)
            family_id = str(entry.get("family_id") or _derive_family_id(doc_id))
            exp_pages = entry.get("expected_pages")
            out.append(
                DiscoveredDoc(
                    path=full_path,
                    source=safe_name,
                    doc_id=doc_id,
                    family_id=family_id,
                    title=title,
                    doc_version=doc_version,
                    date_or_version=date_val,
                    superseded=bool(entry.get("superseded", False)),
                    expected_pages=int(exp_pages) if exp_pages is not None else None,
                )
            )
        return out

    for path in sorted(batch_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if path.name.lower() in {"readme.md", "planted.md"} or path.name.startswith("_"):
            continue
        safe_name = sanitize_filename(path.name)
        meta: dict[str, str] = {}
        if path.suffix.lower() in {".md", ".txt"}:
            try:
                meta, _ = _strip_front_matter(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                meta = {}
        doc_id = meta.get("doc_id") or Path(safe_name).stem
        family_id = meta.get("family_id") or _derive_family_id(doc_id)
        doc_version = meta.get("doc_version", "")
        date_val = meta.get("date") or doc_version
        title = meta.get("title", "")
        if not title and path.suffix.lower() in {".md", ".txt"} and meta:
            # Extract real H1 heading if present in document body; do not invent if absent
            try:
                _, body = _strip_front_matter(path.read_text(encoding="utf-8"))
                for line in body.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            except UnicodeDecodeError:
                pass
        exp_pages = int(meta["expected_pages"]) if "expected_pages" in meta else None
        out.append(
            DiscoveredDoc(
                path=path,
                source=safe_name,
                doc_id=doc_id,
                family_id=family_id,
                title=title,
                doc_version=doc_version,
                date_or_version=date_val,
                superseded=meta.get("superseded", "false").lower() == "true",
                expected_pages=exp_pages,
            )
        )
    return out


def compute_pipeline_fingerprint(
    chunk_size: int, chunk_overlap: int, embed_ident: EmbedIdentity
) -> str:
    raw = (
        f"ext={EXTRACTOR_VERSION}|cs={chunk_size}|co={chunk_overlap}"
        f"|em={embed_ident.model}|ed={embed_ident.digest}|dim={embed_ident.dimension}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _verify_collection_pin(
    store: VectorStore, collection: str, embed_ident: EmbedIdentity
) -> dict[str, Any] | None:
    meta = store.get_collection_metadata(collection)
    if meta is None:
        return None
    idx_model = meta.get("embed_model")
    idx_dim = meta.get("dimension")
    idx_digest = meta.get("embed_digest")
    if idx_model and idx_model != embed_ident.model:
        raise InfrastructureError(
            f"Collection '{collection}' embed_model mismatch: expected {embed_ident.model!r}, found {idx_model!r}"
        )
    if idx_dim and int(idx_dim) != embed_ident.dimension:
        raise InfrastructureError(
            f"Collection '{collection}' dimension mismatch: expected {embed_ident.dimension}, found {idx_dim}"
        )
    if idx_digest and embed_ident.digest and idx_digest != embed_ident.digest:
        raise InfrastructureError(
            f"Collection '{collection}' embed_digest mismatch: expected {embed_ident.digest!r}, found {idx_digest!r}"
        )
    return meta


def _write_verification_reports(
    results_dir: Path,
    collection: str,
    run_id: str,
    batch_dir: Path,
    counters: dict[str, Any],
    entries: list[dict[str, Any]],
) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = results_dir / f"verify-{collection}-{ts_slug}.json"
    md_path = results_dir / f"verify-{collection}-{ts_slug}.md"

    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "collection": collection,
        "batch_dir": str(batch_dir),
        "counters": counters,
        "documents": entries,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Verification Report — `{collection}` ({run_id})",
        "",
        f"- **Generated at**: {payload['generated_at']}",
        f"- **Batch source**: `{batch_dir}`",
        f"- **Counters**: {json.dumps(counters)}",
        "",
        "| Doc ID | Version | Status / Decision | Quality | Completeness | Recency | Uniqueness | Reasons |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        checks = e.get("checks") or {}
        def _fmt(name: str) -> str:
            c = checks.get(name) or {}
            mark = "PASS" if c.get("passed") else "FAIL"
            return f"{mark}: {c.get('reason', '-')}"

        lines.append(
            f"| `{e.get('doc_id')}` | `{e.get('doc_version')}` | `{e.get('decision')}` "
            f"| {_fmt('quality')} | {_fmt('completeness')} | {_fmt('recency')} | {_fmt('uniqueness')} "
            f"| {', '.join(e.get('reasons') or [])} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run_ingest(
    *,
    collection: str,
    batch_dir: Path,
    state: StateStore,
    store: VectorStore,
    embedder: Embedder,
    results_dir: Path,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
    near_dup_threshold: float = DEFAULT_NEAR_DUP_THRESHOLD,
    extract_timeout_s: float = 30.0,
    skip_verify: bool = False,
) -> dict[str, Any]:
    run_id = f"run-{int(time.time())}-{os.getpid()}"
    embed_ident = embedder.identity()
    fp = compute_pipeline_fingerprint(chunk_size, chunk_overlap, embed_ident)

    docs = discover_batch(batch_dir)
    if not docs:
        raise ValueError(f"No documents found in {batch_dir}")

    counters: dict[str, int] = {
        "docs_seen": len(docs),
        "docs_unchanged": 0,
        "docs_indexed": 0,
        "docs_quarantined": 0,
        "docs_archived": 0,
        "chunks_seen": 0,
        "chunks_embedded": 0,
        "chunks_reused": 0,
        "chunks_deleted": 0,
        "doc_check_embeddings": 0,
        "chunk_embeddings": 0,
        "total_embeddings": 0,
    }
    report_entries: list[dict[str, Any]] = []

    with state.writer_lock(owner=f"ingest:{collection}:{run_id}").acquire():
        _verify_collection_pin(store, collection, embed_ident)
        pending_rev = state.begin_revision(
            collection,
            run_id,
            embed_ident.model,
            embed_ident.digest,
            embed_ident.dimension,
            fp,
        )
        try:
            base_meta = {
                "hnsw:space": "cosine",
                "embed_model": embed_ident.model,
                "embed_digest": embed_ident.digest,
                "dimension": embed_ident.dimension,
                "pipeline_fingerprint": fp,
            }
            store.ensure_collection(collection, base_meta)

            for doc in docs:
                raw_bytes = doc.path.read_bytes()
                raw_hash = hashlib.sha256(raw_bytes).hexdigest()
                existing = state.get_document(collection, doc.doc_id, doc.doc_version)

                # Compare hashes & fingerprint BEFORE any extraction or embedding call!
                if (
                    existing is not None
                    and existing.status == "active"
                    and existing.raw_hash == raw_hash
                    and existing.pipeline_fingerprint == fp
                ):
                    counters["docs_unchanged"] += 1
                    counters["chunks_seen"] += len(existing.chunk_ids)
                    counters["chunks_reused"] += len(existing.chunk_ids)
                    state.log_audit(
                        collection,
                        run_id,
                        "skip_unchanged",
                        doc.doc_id,
                        doc.doc_version,
                        {"raw_hash": raw_hash},
                    )
                    report_entries.append(
                        {
                            "doc_id": doc.doc_id,
                            "doc_version": doc.doc_version,
                            "family_id": doc.family_id,
                            "source": doc.source,
                            "decision": "unchanged_skipped",
                            "checks": existing.verification.get("checks", {}),
                            "reasons": ["unchanged_hash_and_fingerprint"],
                        }
                    )
                    continue

                pages_text, ext_err = extract_with_timeout(
                    doc.path, doc.doc_version, doc.superseded, timeout_s=extract_timeout_s
                )
                page_count = len(pages_text) if pages_text else 0

                if skip_verify:
                    c_hash = hashlib.sha256("\n".join(pages_text).encode("utf-8")).hexdigest()
                    ver_res = VerificationResult(
                        doc_id=doc.doc_id,
                        doc_version=doc.doc_version,
                        family_id=doc.family_id,
                        source=doc.source,
                        content_hash=c_hash,
                        checks={
                            "quality": verify_document.__globals__["CheckOutcome"](
                                ext_err is None, ext_err or "ok"
                            ),
                            "completeness": verify_document.__globals__["CheckOutcome"](
                                True, "test_skip_verify"
                            ),
                            "recency": verify_document.__globals__["CheckOutcome"](
                                True, "test_skip_verify"
                            ),
                            "uniqueness": verify_document.__globals__["CheckOutcome"](
                                True, "test_skip_verify"
                            ),
                        },
                        decision="quarantine" if ext_err else ("archive" if doc.superseded else "index"),
                        superseded=doc.superseded,
                        reasons=[ext_err] if ext_err else ["test_skip_verify"],
                    )
                else:
                    family_versions = state.get_family_versions(collection, doc.family_id)
                    active_docs = state.get_active_documents(collection)
                    v_input = VerificationInput(
                        doc_id=doc.doc_id,
                        family_id=doc.family_id,
                        doc_version=doc.doc_version,
                        source=doc.source,
                        title=doc.title,
                        date_or_version=doc.date_or_version,
                        page_count=page_count,
                        pages_text=pages_text,
                        extraction_error=ext_err,
                        expected_pages=doc.expected_pages,
                    )

                    def _embed_doc(txt: str) -> list[float]:
                        return embedder.embed_texts([txt])[0]

                    ver_res = verify_document(
                        v_input,
                        existing_family_versions=family_versions,
                        existing_active_docs=active_docs,
                        embed_doc_fn=_embed_doc,
                        near_dup_threshold=near_dup_threshold,
                    )
                    counters["doc_check_embeddings"] += ver_res.doc_check_embeddings

                report_entries.append(ver_res.to_dict())
                safe_ver = re.sub(r'["<>:|?*\\/]', '_', str(doc.doc_version or 'unknown')).strip()
                safe_doc_id = re.sub(r'["<>:|?*\\/]', '_', str(doc.doc_id)).strip()
                safe_source = re.sub(r'["<>:|?*\\/]', '_', str(doc.source)).strip()
                dest_name = f"{safe_doc_id}__{safe_ver}__{safe_source}"

                if ver_res.decision == "quarantine":
                    q_dir = state.quarantine_dir / collection
                    q_dir.mkdir(parents=True, exist_ok=True)
                    q_path = q_dir / dest_name
                    shutil.copy2(doc.path, q_path)
                    counters["docs_quarantined"] += 1
                    state.upsert_document(
                        DocumentRecord(
                            collection=collection,
                            doc_id=doc.doc_id,
                            doc_version=doc.doc_version or "unknown",
                            family_id=doc.family_id,
                            title=doc.title,
                            source=doc.source,
                            date_or_version=doc.date_or_version,
                            page_count=page_count,
                            raw_hash=raw_hash,
                            content_hash=ver_res.content_hash,
                            pipeline_fingerprint=fp,
                            status="quarantined",
                            superseded=False,
                            stored_path=str(q_path),
                            chunk_ids=[],
                            doc_embedding=None,
                            verification=ver_res.to_dict(),
                            updated_at=utc_now_iso(),
                        )
                    )
                    state.log_audit(
                        collection,
                        run_id,
                        "quarantine",
                        doc.doc_id,
                        doc.doc_version,
                        {"reasons": ver_res.reasons},
                    )
                    continue

                if ver_res.decision == "archive":
                    a_dir = state.archive_dir / collection
                    a_dir.mkdir(parents=True, exist_ok=True)
                    a_path = a_dir / dest_name
                    shutil.copy2(doc.path, a_path)
                    counters["docs_archived"] += 1
                    state.upsert_document(
                        DocumentRecord(
                            collection=collection,
                            doc_id=doc.doc_id,
                            doc_version=doc.doc_version,
                            family_id=doc.family_id,
                            title=doc.title,
                            source=doc.source,
                            date_or_version=doc.date_or_version,
                            page_count=page_count,
                            raw_hash=raw_hash,
                            content_hash=ver_res.content_hash,
                            pipeline_fingerprint=fp,
                            status="superseded",
                            superseded=True,
                            stored_path=str(a_path),
                            chunk_ids=[],
                            doc_embedding=ver_res.doc_embedding,
                            verification=ver_res.to_dict(),
                            updated_at=utc_now_iso(),
                        )
                    )
                    state.log_audit(
                        collection,
                        run_id,
                        "archive_superseded",
                        doc.doc_id,
                        doc.doc_version,
                        {"reasons": ver_res.reasons},
                    )
                    continue

                # Decision == "index": store raw original, diff chunk IDs, upsert missing, delete stale
                r_dir = state.raw_dir / collection
                r_dir.mkdir(parents=True, exist_ok=True)
                r_path = r_dir / dest_name
                shutil.copy2(doc.path, r_path)

                chunks = _chunk_pages(
                    pages_text=pages_text,
                    doc_id=doc.doc_id,
                    doc_version=doc.doc_version,
                    source=doc.source,
                    superseded=False,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                for c in chunks:
                    c["metadata"]["family_id"] = doc.family_id
                counters["chunks_seen"] += len(chunks)

                old_ids = existing.chunk_ids if existing else []
                old_id_set = set(old_ids)
                new_ids = [c["id"] for c in chunks]
                new_id_set = set(new_ids)

                to_upsert = [c for c in chunks if c["id"] not in old_id_set]
                to_delete = [cid for cid in old_ids if cid not in new_id_set]

                if to_upsert:
                    vectors = embedder.embed_texts([c["text"] for c in to_upsert])
                    counters["chunk_embeddings"] += len(to_upsert)
                    counters["chunks_embedded"] += len(to_upsert)
                    store.upsert_chunks(
                        collection=collection,
                        ids=[c["id"] for c in to_upsert],
                        documents=[c["text"] for c in to_upsert],
                        embeddings=vectors,
                        metadatas=[c["metadata"] for c in to_upsert],
                    )
                counters["chunks_reused"] += len(chunks) - len(to_upsert)

                if to_delete:
                    store.delete_ids(collection, to_delete)
                    counters["chunks_deleted"] += len(to_delete)

                # Supersede any older active version in the same family
                for old_ver in ver_res.supersedes_versions:
                    for fam_rec in state.get_family_versions(collection, doc.family_id):
                        if fam_rec.doc_version == old_ver and fam_rec.status == "active":
                            if fam_rec.chunk_ids:
                                metas = [
                                    {
                                        "doc_id": fam_rec.doc_id,
                                        "family_id": fam_rec.family_id,
                                        "source": fam_rec.source,
                                        "section": "Archived",
                                        "page": 1,
                                        "doc_version": fam_rec.doc_version,
                                        "superseded": True,
                                    }
                                    for _ in fam_rec.chunk_ids
                                ]
                                store.update_metadatas(collection, fam_rec.chunk_ids, metas)
                            arch_dir = state.archive_dir / collection
                            arch_dir.mkdir(parents=True, exist_ok=True)
                            arch_dst = arch_dir / Path(fam_rec.stored_path).name
                            if Path(fam_rec.stored_path).exists():
                                shutil.move(fam_rec.stored_path, arch_dst)
                            state.mark_superseded(
                                collection,
                                fam_rec.doc_id,
                                fam_rec.doc_version,
                                str(arch_dst),
                                run_id,
                                superseded_by=doc.doc_version,
                            )

                counters["docs_indexed"] += 1
                state.upsert_document(
                    DocumentRecord(
                        collection=collection,
                        doc_id=doc.doc_id,
                        doc_version=doc.doc_version,
                        family_id=doc.family_id,
                        title=doc.title,
                        source=doc.source,
                        date_or_version=doc.date_or_version,
                        page_count=page_count,
                        raw_hash=raw_hash,
                        content_hash=ver_res.content_hash,
                        pipeline_fingerprint=fp,
                        status="active",
                        superseded=False,
                        stored_path=str(r_path),
                        chunk_ids=new_ids,
                        doc_embedding=ver_res.doc_embedding,
                        verification=ver_res.to_dict(),
                        updated_at=utc_now_iso(),
                    )
                )
                state.log_audit(
                    collection,
                    run_id,
                    "ingest",
                    doc.doc_id,
                    doc.doc_version,
                    {
                        "chunks_total": len(new_ids),
                        "chunks_upserted": len(to_upsert),
                        "chunks_deleted": len(to_delete),
                    },
                )

            counters["total_embeddings"] = (
                counters["doc_check_embeddings"] + counters["chunk_embeddings"]
            )
            index_id = f"{collection}-rev{pending_rev}-{run_id}"

            # Calculate immutable corpus & vector snapshot fingerprints
            active_docs = state.get_active_documents(collection)
            active_doc_hashes = sorted(
                f"{d.doc_id}:{d.doc_version}:{d.content_hash}" for d in active_docs
            )
            corpus_sha256 = hashlib.sha256("\n".join(active_doc_hashes).encode("utf-8")).hexdigest()

            all_chunks = store.get_all(collection)
            chunk_pairs = sorted(zip(all_chunks.get("ids") or [], all_chunks.get("documents") or []))
            vector_str = "\n".join(f"{cid}:{doc}" for cid, doc in chunk_pairs)
            vector_sha256 = hashlib.sha256(vector_str.encode("utf-8")).hexdigest()

            store.set_collection_metadata(
                collection,
                {
                    **base_meta,
                    "committed_revision": pending_rev,
                    "index_id": index_id,
                    "indexed_at": utc_now_iso(),
                    "corpus_sha256": corpus_sha256,
                    "vector_sha256": vector_sha256,
                },
            )
            state.commit_revision(
                collection,
                run_id,
                pending_rev,
                index_id,
                embed_ident.model,
                embed_ident.digest,
                embed_ident.dimension,
                fp,
            )
        except Exception as exc:
            state.abort_revision(collection, run_id, str(exc))
            raise

    json_report, md_report = _write_verification_reports(
        results_dir=results_dir,
        collection=collection,
        run_id=run_id,
        batch_dir=batch_dir,
        counters=counters,
        entries=report_entries,
    )
    summary = {
        "run_id": run_id,
        "collection": collection,
        "committed_revision": pending_rev,
        "embed_model": embed_ident.model,
        "embed_digest": embed_ident.digest,
        "dimension": embed_ident.dimension,
        "pipeline_fingerprint": fp,
        "counters": counters,
        "report_json": str(json_report),
        "report_md": str(md_report),
    }
    _log("ingest_completed", **summary)
    return summary


def run_tombstone(
    *,
    collection: str,
    doc_id: str,
    doc_version: str | None,
    state: StateStore,
    store: VectorStore,
) -> dict[str, Any]:
    run_id = f"tombstone-{int(time.time())}-{os.getpid()}"
    deleted_chunks = 0
    deleted_versions: list[str] = []
    with state.writer_lock(owner=f"tombstone:{collection}:{doc_id}").acquire():
        rev = state.get_revision(collection)
        if not rev:
            raise ValueError(f"Unknown collection in state DB: {collection}")
        records = state.get_documents_by_doc_id(collection, doc_id)
        targets = [
            r
            for r in records
            if r.status in {"active", "superseded"}
            and (doc_version is None or r.doc_version == doc_version)
        ]
        if not targets:
            raise ValueError(f"No active/superseded records found for doc_id={doc_id!r}")

        pending_rev = state.begin_revision(
            collection,
            run_id,
            rev["embed_model"],
            rev["embed_digest"],
            int(rev["dimension"]),
            rev["pipeline_fingerprint"],
        )
        try:
            for rec in targets:
                if rec.chunk_ids:
                    store.delete_ids(collection, rec.chunk_ids)
                    deleted_chunks += len(rec.chunk_ids)
                arch_dir = state.archive_dir / collection
                arch_dir.mkdir(parents=True, exist_ok=True)
                arch_dst = arch_dir / f"deleted__{Path(rec.stored_path).name}"
                if Path(rec.stored_path).exists():
                    shutil.move(rec.stored_path, arch_dst)
                state.mark_deleted(collection, rec.doc_id, rec.doc_version, str(arch_dst), run_id)
                deleted_versions.append(rec.doc_version)

            index_id = f"{collection}-rev{pending_rev}-{run_id}"
            store.set_collection_metadata(
                collection,
                {
                    "hnsw:space": "cosine",
                    "embed_model": rev["embed_model"],
                    "embed_digest": rev["embed_digest"],
                    "dimension": int(rev["dimension"]),
                    "pipeline_fingerprint": rev["pipeline_fingerprint"],
                    "committed_revision": pending_rev,
                    "index_id": index_id,
                    "indexed_at": utc_now_iso(),
                },
            )
            state.commit_revision(
                collection,
                run_id,
                pending_rev,
                index_id,
                rev["embed_model"],
                rev["embed_digest"],
                int(rev["dimension"]),
                rev["pipeline_fingerprint"],
            )
        except Exception as exc:
            state.abort_revision(collection, run_id, str(exc))
            raise
    out = {
        "run_id": run_id,
        "collection": collection,
        "doc_id": doc_id,
        "deleted_versions": deleted_versions,
        "deleted_chunks": deleted_chunks,
    }
    _log("tombstone_completed", **out)
    return out


def run_restore(
    *,
    collection: str,
    doc_id: str,
    doc_version: str,
    state: StateStore,
    store: VectorStore,
    embedder: Embedder,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> dict[str, Any]:
    """Restore an archived/superseded version via the writer lock and supersede current active."""
    run_id = f"restore-{int(time.time())}-{os.getpid()}"
    embed_ident = embedder.identity()
    with state.writer_lock(owner=f"restore:{collection}:{doc_id}:{doc_version}").acquire():
        rev = state.get_revision(collection)
        if not rev:
            raise ValueError(f"Collection not found in state DB: {collection}")
        _verify_collection_pin(store, collection, embed_ident)
        target = state.get_document(collection, doc_id, doc_version)
        if target is None or target.status not in {"superseded", "deleted"}:
            raise ValueError(
                f"Archived/restorable record not found for doc_id={doc_id!r}, version={doc_version!r}"
            )
        archived_file = Path(target.stored_path)
        if not archived_file.exists():
            raise ValueError(f"Archived source file missing at {archived_file}")

        pending_rev = state.begin_revision(
            collection,
            run_id,
            embed_ident.model,
            embed_ident.digest,
            embed_ident.dimension,
            target.pipeline_fingerprint,
        )
        try:
            # Supersede currently active versions in the same family
            for fam_rec in state.get_family_versions(collection, target.family_id):
                if fam_rec.status == "active" and not (
                    fam_rec.doc_id == doc_id and fam_rec.doc_version == doc_version
                ):
                    if fam_rec.chunk_ids:
                        metas = [
                            {
                                "doc_id": fam_rec.doc_id,
                                "family_id": fam_rec.family_id,
                                "source": fam_rec.source,
                                "section": "Archived",
                                "page": 1,
                                "doc_version": fam_rec.doc_version,
                                "superseded": True,
                            }
                            for _ in fam_rec.chunk_ids
                        ]
                        store.update_metadatas(collection, fam_rec.chunk_ids, metas)
                    arch_dir = state.archive_dir / collection
                    arch_dir.mkdir(parents=True, exist_ok=True)
                    arch_dst = arch_dir / f"{fam_rec.doc_id}__{fam_rec.doc_version}__{fam_rec.source}"
                    if Path(fam_rec.stored_path).exists():
                        shutil.move(fam_rec.stored_path, arch_dst)
                    state.mark_superseded(
                        collection,
                        fam_rec.doc_id,
                        fam_rec.doc_version,
                        str(arch_dst),
                        run_id,
                        superseded_by=doc_version,
                    )

            # Move archived source back to raw/ and restore chunks into Chroma
            raw_dir = state.raw_dir / collection
            raw_dir.mkdir(parents=True, exist_ok=True)
            restored_raw = raw_dir / f"{doc_id}__{doc_version}__{target.source}"
            shutil.copy2(archived_file, restored_raw)

            pages_text, ext_err = extract_with_timeout(restored_raw, doc_version, False)
            if ext_err:
                raise InfrastructureError(f"Restore extraction failed: {ext_err}")

            chunks = _chunk_pages(
                pages_text=pages_text,
                doc_id=doc_id,
                doc_version=doc_version,
                source=target.source,
                superseded=False,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            for c in chunks:
                c["metadata"]["family_id"] = target.family_id
            vectors = embedder.embed_texts([c["text"] for c in chunks])
            store.upsert_chunks(
                collection=collection,
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                embeddings=vectors,
                metadatas=[c["metadata"] for c in chunks],
            )
            state.upsert_document(
                DocumentRecord(
                    collection=collection,
                    doc_id=doc_id,
                    doc_version=doc_version,
                    family_id=target.family_id,
                    title=target.title,
                    source=target.source,
                    date_or_version=target.date_or_version,
                    page_count=len(pages_text),
                    raw_hash=target.raw_hash,
                    content_hash=target.content_hash,
                    pipeline_fingerprint=target.pipeline_fingerprint,
                    status="active",
                    superseded=False,
                    stored_path=str(restored_raw),
                    chunk_ids=[c["id"] for c in chunks],
                    doc_embedding=target.doc_embedding,
                    verification=target.verification,
                    updated_at=utc_now_iso(),
                )
            )
            state.log_audit(
                collection,
                run_id,
                "restore",
                doc_id,
                doc_version,
                {"chunks_restored": len(chunks)},
            )
            index_id = f"{collection}-rev{pending_rev}-{run_id}"
            store.set_collection_metadata(
                collection,
                {
                    "hnsw:space": "cosine",
                    "embed_model": embed_ident.model,
                    "embed_digest": embed_ident.digest,
                    "dimension": embed_ident.dimension,
                    "pipeline_fingerprint": target.pipeline_fingerprint,
                    "committed_revision": pending_rev,
                    "index_id": index_id,
                    "indexed_at": utc_now_iso(),
                },
            )
            state.commit_revision(
                collection,
                run_id,
                pending_rev,
                index_id,
                embed_ident.model,
                embed_ident.digest,
                embed_ident.dimension,
                target.pipeline_fingerprint,
            )
        except Exception as exc:
            state.abort_revision(collection, run_id, str(exc))
            raise
    out = {
        "run_id": run_id,
        "collection": collection,
        "restored_doc_id": doc_id,
        "restored_version": doc_version,
        "chunks_restored": len(chunks),
    }
    _log("restore_completed", **out)
    return out


def run_snapshot_clone(
    *,
    src_collection: str,
    dst_collection: str,
    state: StateStore,
    store: VectorStore,
) -> dict[str, Any]:
    """Clone ids/documents/embeddings/metadatas to a new collection without re-embedding."""
    run_id = f"snap-{int(time.time())}-{os.getpid()}"
    with state.writer_lock(owner=f"snapshot:{src_collection}->{dst_collection}").acquire():
        src_data = store.get_all(src_collection)
        src_meta = dict(src_data.get("metadata") or {})
        src_meta.setdefault("hnsw:space", "cosine")
        src_meta["snapshot_source"] = src_collection
        src_meta["indexed_at"] = utc_now_iso()
        src_meta["index_id"] = f"{dst_collection}-snap-{run_id}"
        src_meta["committed_revision"] = 1

        store.ensure_collection(dst_collection, src_meta)
        ids = src_data.get("ids") or []
        if ids:
            store.upsert_chunks(
                collection=dst_collection,
                ids=ids,
                documents=src_data["documents"],
                embeddings=src_data["embeddings"],
                metadatas=src_data["metadatas"],
            )
        store.set_collection_metadata(dst_collection, src_meta)
        docs_cloned = state.clone_collection_state(src_collection, dst_collection, run_id)

    out = {
        "run_id": run_id,
        "source_collection": src_collection,
        "collection": dst_collection,
        "chunks_cloned": len(ids),
        "docs_cloned": docs_cloned,
        "chunk_embeddings": 0,
        "doc_check_embeddings": 0,
    }
    _log("snapshot_completed", **out)
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="RAHBAR RAGOps incremental ingestion CLI")
    sub = p.add_subparsers(dest="command", required=True)

    def _add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--collection", default=os.environ.get("CHROMA_COLLECTION", "rahbar"))
        sp.add_argument("--datalake", default=os.environ.get("RAGOPS_DATALAKE_DIR", "/datalake"))

    p_run = sub.add_parser("run", help="Verify and incrementally ingest a batch directory")
    _add_common(p_run)
    p_run.add_argument("--batch-dir", default=os.environ.get("CORPUS_DIR", "/corpus"))
    p_run.add_argument("--results-dir", default=os.environ.get("RAGOPS_RESULTS_DIR", "/results"))
    p_run.add_argument("--skip-verify", action="store_true", help="Test-only flag to bypass A1 verify")

    p_status = sub.add_parser("status", help="Inspect collection state and recent audit events")
    _add_common(p_status)

    p_count = sub.add_parser("count", help="Count stored chunks for a doc_id")
    _add_common(p_count)
    p_count.add_argument("--doc-id", required=True)

    p_restore = sub.add_parser("restore", help="Restore an archived/superseded document version")
    _add_common(p_restore)
    p_restore.add_argument("--doc-id", required=True)
    p_restore.add_argument("--version", required=True)

    p_tomb = sub.add_parser("tombstone", help="Explicitly delete a document by doc_id")
    _add_common(p_tomb)
    p_tomb.add_argument("--doc-id", required=True)
    p_tomb.add_argument("--version", default=None)

    p_snap = sub.add_parser("snapshot", help="Clone collection vectors/state without re-embedding")
    _add_common(p_snap)
    p_snap.add_argument("--snapshot-from", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    state = StateStore(Path(args.datalake))
    chroma_host = os.environ.get("CHROMA_HOST", "chroma")
    chroma_port = int(os.environ.get("CHROMA_PORT", "8000"))
    store = ChromaVectorStore(chroma_host, chroma_port)
    embed_model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    ollama_url = os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434")
    chunk_size = int(os.environ.get("CHUNK_SIZE", "400"))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", "50"))
    near_dup_threshold = float(
        os.environ.get("RAGOPS_NEAR_DUP_THRESHOLD", str(DEFAULT_NEAR_DUP_THRESHOLD))
    )
    extract_timeout_s = float(os.environ.get("RAGOPS_EXTRACT_TIMEOUT", "30.0"))
    embedder = RuntimeEmbedder(embed_model, ollama_url)

    try:
        if args.command == "run":
            res = run_ingest(
                collection=args.collection,
                batch_dir=Path(args.batch_dir),
                state=state,
                store=store,
                embedder=embedder,
                results_dir=Path(args.results_dir),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                near_dup_threshold=near_dup_threshold,
                extract_timeout_s=extract_timeout_s,
                skip_verify=args.skip_verify,
            )
            print(json.dumps(res, indent=2))
            return 0
        if args.command == "status":
            print(json.dumps(state.status_summary(args.collection), indent=2))
            return 0
        if args.command == "count":
            chroma_count = store.count_by_doc_id(args.collection, args.doc_id)
            state_recs = state.get_documents_by_doc_id(args.collection, args.doc_id)
            out = {
                "collection": args.collection,
                "doc_id": args.doc_id,
                "chroma_chunks": chroma_count,
                "state_records": [
                    {
                        "doc_version": r.doc_version,
                        "status": r.status,
                        "superseded": r.superseded,
                        "chunks": len(r.chunk_ids),
                    }
                    for r in state_recs
                ],
            }
            print(json.dumps(out, indent=2))
            return 0
        if args.command == "restore":
            res = run_restore(
                collection=args.collection,
                doc_id=args.doc_id,
                doc_version=args.version,
                state=state,
                store=store,
                embedder=embedder,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            print(json.dumps(res, indent=2))
            return 0
        if args.command == "tombstone":
            res = run_tombstone(
                collection=args.collection,
                doc_id=args.doc_id,
                doc_version=args.version,
                state=state,
                store=store,
            )
            print(json.dumps(res, indent=2))
            return 0
        if args.command == "snapshot":
            res = run_snapshot_clone(
                src_collection=args.snapshot_from,
                dst_collection=args.collection,
                state=state,
                store=store,
            )
            print(json.dumps(res, indent=2))
            return 0
    except (ValueError, WriterLockTimeout, InfrastructureError) as exc:
        _log("ingest_error", error=str(exc), error_type=type(exc).__name__)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        _log("ingest_unexpected_error", error=str(exc), error_type=type(exc).__name__)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

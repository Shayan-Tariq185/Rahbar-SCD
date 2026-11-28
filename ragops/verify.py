"""Pre-chunking document verification (A1): quality, completeness, recency, uniqueness."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .state import DocumentRecord

DEFAULT_NEAR_DUP_THRESHOLD = 0.95
MIN_TEXT_CHARS = 30
TRUNCATION_MARKERS = ("[TRUNCATED]", "<<TRUNCATED>>", "---TRUNCATED---")


def sanitize_filename(name: str) -> str:
    """Validate and return a safe basename, rejecting path traversal or absolute paths."""
    if not name or "\x00" in name:
        raise ValueError(f"Unsafe filename: {name!r}")
    if name.startswith(("/", "\\")) or ".." in Path(name).parts:
        raise ValueError(f"Path traversal rejected in filename: {name!r}")
    if "/" in name or "\\" in name:
        raise ValueError(f"Directory separators rejected in filename: {name!r}")
    return name


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def parse_version_key(version_str: str, date_str: str = "") -> tuple[int, ...]:
    """Extract comparable numeric tuple from version/date strings (e.g. '2026-06' -> (2026, 6))."""
    candidate = version_str.strip() if version_str and version_str.strip().lower() != "unknown" else date_str
    nums = [int(n) for n in re.findall(r"\d+", candidate or "")]
    return tuple(nums) if nums else (0,)


def text_sha256(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class CheckOutcome:
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "reason": self.reason}


@dataclass
class VerificationInput:
    doc_id: str
    family_id: str
    doc_version: str
    source: str
    title: str
    date_or_version: str
    page_count: int
    pages_text: list[str]
    extraction_error: str | None = None
    expected_pages: int | None = None


@dataclass
class VerificationResult:
    doc_id: str
    doc_version: str
    family_id: str
    source: str
    content_hash: str
    checks: dict[str, CheckOutcome]
    decision: str  # "index" | "archive" | "quarantine"
    superseded: bool
    reasons: list[str]
    supersedes_versions: list[str] = field(default_factory=list)
    doc_embedding: list[float] | None = None
    doc_check_embeddings: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_version": self.doc_version,
            "family_id": self.family_id,
            "source": self.source,
            "content_hash": self.content_hash,
            "checks": {k: v.to_dict() for k, v in self.checks.items()},
            "decision": self.decision,
            "superseded": self.superseded,
            "reasons": self.reasons,
            "supersedes_versions": self.supersedes_versions,
            "doc_check_embeddings": self.doc_check_embeddings,
            "notes": self.notes,
        }


def _check_quality(inp: VerificationInput, full_text: str) -> CheckOutcome:
    if inp.extraction_error:
        return CheckOutcome(False, f"extraction_failed: {inp.extraction_error}")
    if not inp.pages_text or not full_text.strip():
        return CheckOutcome(False, "empty_extracted_text")
    stripped = full_text.strip()
    if len(stripped) < MIN_TEXT_CHARS:
        return CheckOutcome(False, f"too_short ({len(stripped)} chars < {MIN_TEXT_CHARS})")
    replacement_ratio = stripped.count("\ufffd") / len(stripped)
    if replacement_ratio > 0.02:
        return CheckOutcome(False, f"garbled_replacement_chars (ratio={replacement_ratio:.3f})")
    control_chars = sum(1 for ch in stripped if ord(ch) < 32 and ch not in ("\n", "\r", "\t"))
    if control_chars / len(stripped) > 0.05:
        return CheckOutcome(False, "garbled_control_characters")
    readable = sum(1 for ch in stripped if ch.isalnum() or ch.isspace() or ch in ".,;:!?()-/%'\"")
    readable_ratio = readable / len(stripped)
    if readable_ratio < 0.45:
        return CheckOutcome(False, f"garbled_low_readable_ratio ({readable_ratio:.3f})")
    return CheckOutcome(True, "ok")


def _check_completeness(inp: VerificationInput, full_text: str, quality_ok: bool) -> CheckOutcome:
    if not quality_ok:
        return CheckOutcome(False, "not_executable: upstream quality/extraction check failed")
    missing: list[str] = []
    if not inp.source or inp.source.lower() == "unknown":
        missing.append("source")
    if not inp.title or inp.title.strip().lower() in {"unknown", "missing", "untitled", "none"}:
        missing.append("title")
    if not inp.date_or_version or inp.date_or_version.strip().lower() in {"unknown", "missing", "none"}:
        missing.append("date_or_version")
    if inp.page_count < 1:
        missing.append("page_count")
    if missing:
        return CheckOutcome(False, f"missing_required_metadata: {', '.join(missing)}")

    if inp.expected_pages is not None and inp.page_count < inp.expected_pages:
        return CheckOutcome(
            False, f"truncated_page_count: got {inp.page_count}, expected {inp.expected_pages}"
        )
    for marker in TRUNCATION_MARKERS:
        if marker in full_text:
            return CheckOutcome(False, f"truncated_marker_detected: {marker}")
    if len(inp.pages_text) > 1:
        empty_pages = sum(1 for p in inp.pages_text if len(p.strip()) < 10)
        if empty_pages / len(inp.pages_text) > 0.5:
            return CheckOutcome(
                False, f"truncated_empty_pages: {empty_pages}/{len(inp.pages_text)} pages empty"
            )
    return CheckOutcome(True, "ok")


def _check_recency(
    inp: VerificationInput,
    existing_family_versions: list[DocumentRecord],
) -> tuple[CheckOutcome, list[str]]:
    if not existing_family_versions:
        return CheckOutcome(True, "first_version_in_family"), []

    cand_key = parse_version_key(inp.doc_version, inp.date_or_version)
    active_family = [r for r in existing_family_versions if r.status == "active"]
    supersedes: list[str] = []
    for rec in active_family:
        existing_key = parse_version_key(rec.doc_version, rec.date_or_version)
        if cand_key < existing_key:
            return (
                CheckOutcome(
                    False,
                    f"older_than_active_version:{rec.doc_version} (candidate={inp.doc_version}); "
                    "routed to archive with superseded=true",
                ),
                [],
            )
        if cand_key > existing_key or rec.doc_version != inp.doc_version:
            supersedes.append(rec.doc_version)
    if supersedes:
        return CheckOutcome(True, f"newer_version_supersedes:{','.join(supersedes)}"), supersedes
    return CheckOutcome(True, "current_version_update"), []


def verify_document(
    inp: VerificationInput,
    existing_family_versions: list[DocumentRecord],
    existing_active_docs: list[DocumentRecord],
    embed_doc_fn: Callable[[str], list[float]] | None = None,
    near_dup_threshold: float = DEFAULT_NEAR_DUP_THRESHOLD,
) -> VerificationResult:
    """Run quality, completeness, recency, and uniqueness checks before chunking."""
    full_text = "\n\n".join(inp.pages_text)
    c_hash = text_sha256(full_text) if full_text.strip() else hashlib.sha256(b"").hexdigest()
    notes = [
        "Truncation detection is heuristic (markers, empty multi-page ratio, expected_pages); "
        "missing trailing punctuation alone is not treated as truncation."
    ]

    q_check = _check_quality(inp, full_text)
    c_check = _check_completeness(inp, full_text, q_check.passed)

    if not q_check.passed or not c_check.passed:
        r_check = CheckOutcome(False, "not_executable: upstream quality/completeness check failed")
        u_check = CheckOutcome(False, "skipped: upstream quality/completeness check failed")
        reasons = [f"quality:{q_check.reason}" if not q_check.passed else f"completeness:{c_check.reason}"]
        return VerificationResult(
            doc_id=inp.doc_id,
            doc_version=inp.doc_version,
            family_id=inp.family_id,
            source=inp.source,
            content_hash=c_hash,
            checks={
                "quality": q_check,
                "completeness": c_check,
                "recency": r_check,
                "uniqueness": u_check,
            },
            decision="quarantine",
            superseded=False,
            reasons=reasons,
            notes=notes,
        )

    # Check version lineage BEFORE near-duplicate rejection so valid newer policies aren't flagged as dups.
    r_check, supersedes = _check_recency(inp, existing_family_versions)
    if not r_check.passed:
        u_check = CheckOutcome(False, "skipped: recency rejected older version to archive")
        return VerificationResult(
            doc_id=inp.doc_id,
            doc_version=inp.doc_version,
            family_id=inp.family_id,
            source=inp.source,
            content_hash=c_hash,
            checks={
                "quality": q_check,
                "completeness": c_check,
                "recency": r_check,
                "uniqueness": u_check,
            },
            decision="archive",
            superseded=True,
            reasons=[f"recency:{r_check.reason}"],
            notes=notes,
        )

    other_active = [r for r in existing_active_docs if r.family_id != inp.family_id]
    for other in other_active:
        if other.content_hash == c_hash:
            u_check = CheckOutcome(
                False, f"exact_duplicate_of:{other.doc_id}@{other.doc_version}"
            )
            return VerificationResult(
                doc_id=inp.doc_id,
                doc_version=inp.doc_version,
                family_id=inp.family_id,
                source=inp.source,
                content_hash=c_hash,
                checks={
                    "quality": q_check,
                    "completeness": c_check,
                    "recency": r_check,
                    "uniqueness": u_check,
                },
                decision="quarantine",
                superseded=False,
                reasons=[f"uniqueness:{u_check.reason}"],
                supersedes_versions=supersedes,
                notes=notes,
            )

    doc_emb: list[float] | None = None
    doc_emb_calls = 0
    comparable = [r for r in other_active if r.doc_embedding]
    if embed_doc_fn is not None and other_active:
        # Compute candidate document embedding (first 4000 chars representative summary)
        doc_emb = embed_doc_fn(full_text[:4000])
        doc_emb_calls = 1
        best_sim = 0.0
        best_other: DocumentRecord | None = None
        for other in comparable:
            assert other.doc_embedding is not None
            sim = cosine_similarity(doc_emb, other.doc_embedding)
            if sim > best_sim:
                best_sim = sim
                best_other = other
        if best_other is not None and best_sim >= near_dup_threshold:
            u_check = CheckOutcome(
                False,
                f"near_duplicate_of:{best_other.doc_id}@{best_other.doc_version} "
                f"(cosine={best_sim:.4f} >= {near_dup_threshold:.2f})",
            )
            return VerificationResult(
                doc_id=inp.doc_id,
                doc_version=inp.doc_version,
                family_id=inp.family_id,
                source=inp.source,
                content_hash=c_hash,
                checks={
                    "quality": q_check,
                    "completeness": c_check,
                    "recency": r_check,
                    "uniqueness": u_check,
                },
                decision="quarantine",
                superseded=False,
                reasons=[f"uniqueness:{u_check.reason}"],
                supersedes_versions=supersedes,
                doc_embedding=doc_emb,
                doc_check_embeddings=doc_emb_calls,
                notes=notes,
            )
    elif embed_doc_fn is not None and not other_active:
        # First active doc in collection still stores its doc embedding if needed for future comparisons,
        # OR waits until another doc exists; wait: storing on first doc ensures second doc can compare!
        doc_emb = embed_doc_fn(full_text[:4000])
        doc_emb_calls = 1

    u_check = CheckOutcome(True, "unique")
    return VerificationResult(
        doc_id=inp.doc_id,
        doc_version=inp.doc_version,
        family_id=inp.family_id,
        source=inp.source,
        content_hash=c_hash,
        checks={
            "quality": q_check,
            "completeness": c_check,
            "recency": r_check,
            "uniqueness": u_check,
        },
        decision="index",
        superseded=False,
        reasons=["all_checks_passed"],
        supersedes_versions=supersedes,
        doc_embedding=doc_emb,
        doc_check_embeddings=doc_emb_calls,
        notes=notes,
    )

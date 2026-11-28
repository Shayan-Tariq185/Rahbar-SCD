"""RAGOps query trace inspection, summary, and reconstruction utilities (D1–D5)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure api/ is importable so trace building/writing has one canonical implementation.
_API_ROOT = Path(__file__).resolve().parents[1] / "api"
if _API_ROOT.exists() and str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

try:
    from app.services.tracing import (  # type: ignore  # noqa: E402
        build_exact_prompt,
        build_trace_record,
        load_trace_by_id,
        sanitize_secrets,
        write_trace_record,
    )
except ImportError:  # pragma: no cover
    build_exact_prompt = None  # type: ignore
    build_trace_record = None  # type: ignore
    load_trace_by_id = None  # type: ignore
    sanitize_secrets = None  # type: ignore
    write_trace_record = None  # type: ignore

__all__ = [
    "build_exact_prompt",
    "build_trace_record",
    "load_trace_by_id",
    "sanitize_secrets",
    "write_trace_record",
    "parse_since",
    "load_traces",
    "find_trace",
    "summarize_traces",
    "format_trace_reconstruction",
]


def parse_since(since: str | None) -> datetime | None:
    if not since or since.strip().lower() == "all":
        return None
    raw = since.strip().lower()
    now = datetime.now(timezone.utc)
    if raw.endswith("h"):
        return now - timedelta(hours=float(raw[:-1]))
    if raw.endswith("m"):
        return now - timedelta(minutes=float(raw[:-1]))
    if raw.endswith("d"):
        return now - timedelta(days=float(raw[:-1]))
    raise ValueError(f"Unsupported --since window format: {since!r} (expected e.g. 1h, 24h, 30m, all)")


def _parse_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_traces(traces_dir: str | Path, since: str | None = None) -> list[dict[str, Any]]:
    """Load and deduplicate trace records from all *.jsonl files in traces_dir."""
    root = Path(traces_dir)
    if not root.exists():
        return []
    cutoff = parse_since(since)
    by_id: dict[str, dict[str, Any]] = {}
    for jf in sorted(root.glob("*.jsonl")):
        for line in jf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = rec.get("trace_id")
            if not tid:
                continue
            if cutoff is not None:
                ts = _parse_ts(str(rec.get("timestamp", "")))
                if ts is not None and ts < cutoff:
                    continue
            by_id[str(tid)] = rec
    return sorted(by_id.values(), key=lambda r: str(r.get("timestamp", "")))


def find_trace(trace_id: str, traces_dir: str | Path) -> dict[str, Any] | None:
    for rec in load_traces(traces_dir):
        if rec.get("trace_id") == trace_id:
            return rec
    return None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 3)


def summarize_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute D3 summary metrics: top-1 similarity, abstention/cache rates, stage p95, injections."""
    total = len(traces)
    if total == 0:
        return {
            "total_queries": 0,
            "abstention_rate": 0.0,
            "cache_hit_rate": 0.0,
            "injection_attempts": 0,
            "top1_similarity": {"count": 0, "min": None, "p50": None, "mean": None, "p95": None, "max": None},
            "stage_latency_p95_ms": {},
            "outcomes": {},
        }

    top1_scores: list[float] = []
    abstentions = 0
    cache_hits = 0
    injections = 0
    outcomes: dict[str, int] = {}
    stage_samples: dict[str, list[float]] = {}

    for t in traces:
        out = str(t.get("outcome", "unknown"))
        outcomes[out] = outcomes.get(out, 0) + 1
        resp = t.get("response") or {}
        if resp.get("answered_from_context") is False:
            abstentions += 1
        if str(t.get("cache_status", "")).upper() == "HIT":
            cache_hits += 1

        chunks = t.get("retrieved_chunks") or []
        if chunks:
            score = chunks[0].get("score")
            if isinstance(score, (int, float)):
                top1_scores.append(float(score))

        for act in t.get("guardrail_actions") or []:
            if act.get("action") in {"sanitized_injection", "blocked_injection"}:
                injections += 1

        for stage, val in (t.get("stage_latencies_ms") or {}).items():
            if isinstance(val, (int, float)):
                stage_samples.setdefault(stage, []).append(float(val))

    return {
        "total_queries": total,
        "abstention_rate": round(abstentions / total, 4),
        "cache_hit_rate": round(cache_hits / total, 4),
        "injection_attempts": injections,
        "top1_similarity": {
            "count": len(top1_scores),
            "min": round(min(top1_scores), 4) if top1_scores else None,
            "p50": _percentile(top1_scores, 50),
            "mean": round(sum(top1_scores) / len(top1_scores), 4) if top1_scores else None,
            "p95": _percentile(top1_scores, 95),
            "max": round(max(top1_scores), 4) if top1_scores else None,
        },
        "stage_latency_p95_ms": {
            st: _percentile(vals, 95) for st, vals in sorted(stage_samples.items())
        },
        "outcomes": outcomes,
    }


def format_trace_reconstruction(trace: dict[str, Any]) -> str:
    """Render human-readable context + exact prompt + identity/guardrail summary for D2."""
    col = trace.get("collection") or {}
    model = trace.get("model") or {}
    cfg = trace.get("config") or {}
    resp = trace.get("response") or {}
    lines = [
        f"Trace ID:       {trace.get('trace_id')}",
        f"Request ID:     {trace.get('request_id')}",
        f"Timestamp:      {trace.get('timestamp')}",
        f"Query:          {trace.get('query')}",
        f"Rewrite:        {trace.get('rewrite')}",
        f"Collection:     {col.get('name')} (rev={col.get('committed_revision')}, index_id={col.get('index_id')})",
        f"Embed Pin:      {col.get('embed_model')} (digest={col.get('embed_digest')})",
        f"Model:          {model.get('provider')}/{model.get('name')} (temp={cfg.get('temperature')}, top_k={cfg.get('top_k')})",
        f"Filters:        {json.dumps(trace.get('filters'))}",
        f"Cache Status:   {trace.get('cache_status')} (origin={trace.get('cache_origin_trace_id')})",
        f"Outcome:        {trace.get('outcome')} (answered_from_context={resp.get('answered_from_context')}, conf={resp.get('confidence')})",
        f"Stage Status:   {json.dumps(trace.get('stage_status'))}",
        f"Latencies (ms): {json.dumps(trace.get('stage_latencies_ms'))}",
        f"Guardrails:     {json.dumps(trace.get('guardrail_actions'))}",
        "",
        "=== Retrieved Evidence (Rerank Order) ===",
    ]
    for c in trace.get("retrieved_chunks") or []:
        lines.append(
            f"[{c.get('rank')}] {c.get('chunk_id')} | doc={c.get('doc_id')}@{c.get('doc_version')} "
            f"| {c.get('source')} / {c.get('section')} p.{c.get('page')} | score={c.get('score')}"
        )
        lines.append(f"    {c.get('text')}")
    lines.extend(
        [
            "",
            f"=== Exact Prompt (sha256={trace.get('prompt_hash')}) ===",
            trace.get("prompt") or f"<no prompt generated: {trace.get('prompt_note')}>",
            "",
            "=== Response & Citations ===",
            str(resp.get("answer", "")),
            f"Citations: {json.dumps(trace.get('citations'))}",
        ]
    )
    return "\n".join(lines)

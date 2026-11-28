# Member 1 PR Summary: RAGOps Data Lifecycle, Tracing & Runtime (M1.0–M1.4)

## Overview
Implements Member 1's Assignment 03 RAGOps deliverables while preserving all Assignment 02 contracts and leaving Track B starter files untouched:
- **H0 Contracts & Runtime Foundation (M1.0)**: `docs/CONTRACTS.md`, `docs/member1/{GAP,COMMANDS,PROGRESS}.md`, `mk/ragops-runtime.mk`, `Makefile`, `k8s/tools/runtime-shell.yaml`.
- **Incremental State & Ingestion (M1.1)**: `ragops/state.py`, `ragops/ingest.py` (`run`, `status`, `count`, `restore`, `tombstone`, `--snapshot-from`), cross-process writer lock, pending/committed revision tracking, `scripts/{ingest_job,wait_job,collect_runtime,ingest_scenarios}.sh`.
- **Pre-Chunk Verification & Batch B (M1.2)**: `ragops/verify.py` (quality, completeness, recency, uniqueness; quarantine vs archive routing; JSON/MD reports) and `scripts/make_batch_b.py` (12 reproducible test fixtures).
- **Traceability, Guardrail & Eval Adapter (M1.3)**: `ragops/trace.py`, `api/app/services/guardrail.py`, `api/app/routes/eval_adapter.py`, additive trace/metrics/cache namespace updates, `scripts/{trace_show,trace_summary}.py`, `scripts/query.sh`.
- **Candidate Release & Rollback (M1.4)**: `k8s/ragops-runtime/` (PVCs, `api-candidate` Deployment+Service, `ragops-ingest` CronJob + suspended legacy `reindex`, runtime NetworkPolicies), `scripts/{release,rollback_demo,resource_sample}.sh`, `scripts/load_queries.py`.

## Verification
- Offline unit tests in `tests/ragops/runtime/` run via `python -m pytest tests/ragops/runtime -v`.
- Live Kubernetes execution evidence (Batch A/B ingest, traces, gate/release/rollback, `kubectl top`) remains pending cluster run by Member 1.

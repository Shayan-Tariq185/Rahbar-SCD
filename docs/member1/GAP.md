# Member 1 Gap Analysis (A02 Baseline vs A03 RAGOps Target)

Audited against `origin/dev` (Assignment 02 baseline) and `Member_1_RAGOps_Guide.md`.

## Summary of Real A02 State
- **Track A completed on `origin/dev`**: FastAPI API (`api/app/main.py`, `routes/ask.py`, `routes/health.py`, `routes/metrics.py`, `services/cache.py`), Kubernetes base/dev/prod/ci manifests (`k8s/`), CI/CD workflows (`.github/workflows/ci.yml`, `cd.yml`), Prometheus metrics, JSON stdout logging, and Calico deny-by-default NetworkPolicies.
- **Track B stubs remaining on `origin/dev`**: `indexer/pipeline/{extract,clean,chunk,embed,store}.py`, `api/app/embedding.py`, `api/app/retrieval/chroma.py`, `api/app/services/{grounding,validate}.py`, `api/app/providers/llm/{ollama,hosted}.py`, and `eval/run_eval.py` still contain `STARTER-TODO` / `TODO(TrackB)`. Per H0 ownership, Member 1 preserves those files untouched and implements `ragops/*` adapters/wrappers and additive API observability.

## Gap Table (A1–F5 and G)

| Requirement | Owner | Current A02 Evidence | A03 Target & Owned Paths | Status |
|---|---|---|---|---|
| **A1** Pre-chunk verification & quarantine | M1 | None (`indexer/pipeline/run.py` passes straight to extract/clean/chunk) | `ragops/verify.py`, `ragops/ingest.py`, `/datalake/{quarantine,archive}`, JSON+MD report under `/results` | Planned (M1.2) |
| **A2** Incremental state, zero-embed skip, diffing, delete, archive/restore | M1 | `indexer/pipeline/dummy.py` deletes/recreates whole collection | `ragops/state.py`, `ragops/ingest.py` (`run`, `status`, `count`, `restore`, `tombstone`, `--snapshot-from`) | Planned (M1.1) |
| **Batch B** >=10 planted fixture docs | M1 | `eval/fixtures/` has 3 small `.md` fixtures | `scripts/make_batch_b.py` generating >=10 reproducible fixtures + `PLANTED.md` | Planned (M1.2) |
| **B** Golden data, module/component/E2E eval | M2 | `eval/run_eval.py` (Track B stub) | M2 `ragops/evalsuite/`, `eval/golden*.jsonl` | Partner (M2) |
| **C1–C3** Candidate comparison, gate, rollout/undo | M2 (C1/C2), M1 (C3) | Single `api` Deployment (`k8s/base/api-deployment.yaml`) | `k8s/ragops-runtime/api-candidate.yaml`, `scripts/release.sh`, `scripts/rollback_demo.sh` | Planned (M1.4) |
| **D1–D2** Full query JSON trace & prompt reconstruction | M1 | `api/app/logjson.py` logs partial fields to stdout only | `ragops/trace.py`, `api/app/services/answer.py`, `scripts/trace_show.py` | Planned (M1.3) |
| **D3–D5** Stats summary, injection guardrail, 5-line diagnosis | M1 | `api/app/metrics_defs.py` (no injection rail or similarity histogram) | `api/app/services/guardrail.py`, `scripts/trace_summary.py`, `eval/results` + `docs/member1/REPORT-NOTES.md` | Planned (M1.3/M1.5) |
| **E1–E4** Live query coverage & drift analysis | M2 | None | M2 `ragops/coverage.py`, `scripts/coverage_job.sh` | Partner (M2) |
| **F1** K8s runtime, PVCs, ingestion Job/CronJob, single writer | M1 | `k8s/base/chroma-statefulset.yaml`, `indexer-job.yaml`, `reindex-cronjob.yaml` (`--dummy`) | `k8s/ragops-runtime/` PVCs (`/datalake`, `/results`, `/traces`), suspended legacy CronJob, `ragops-ingest` CronJob + templates, `scripts/ingest_job.sh`, `scripts/wait_job.sh` | Planned (M1.0–M1.1) |
| **F2** Eval Job & ConfigMap gate | M2 | None | M2 `k8s/eval-job.yaml`, `k8s/ragops-eval/` | Partner (M2) |
| **F3** Candidate Deploy/Service, safe release, block & undo | M1/M2 | `api-deployment.yaml` (`maxSurge=1`, `maxUnavailable=0`) | `api-candidate` Deployment+Service, `scripts/release.sh`, `scripts/rollback_demo.sh`, explicit pod env pins | Planned (M1.4) |
| **F4** Traces stdout + volume, metrics port-forward | M1 | `/metrics` endpoint exists (`api/app/routes/metrics.py`) | `/traces` PVC mount, stdout JSON trace records, `scripts/query.sh`, `scripts/collect_runtime.sh` | Planned (M1.3) |
| **F5** Measured resource requests/limits | Both | Provisional values in `k8s/base/*.yaml` | `scripts/resource_sample.sh`, `scripts/load_queries.py`, measured maxima justification | Planned (M1.4) |
| **G** Final report, screenshots, human inputs | Both | A02 `docs/` and `docs/evidence/` | `docs/member1/REPORT-NOTES.md`, `docs/member1/DEMO.md`, `report/` (M2 assembly) | Planned (M1.5) |

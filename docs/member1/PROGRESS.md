# Member 1 Progress Log

- **M1.0 (Contracts & Foundation)**: Completed repository audit against `origin/dev`, documented A03 H0 contracts in `docs/CONTRACTS.md`, created `docs/member1/GAP.md`, `docs/member1/COMMANDS.md`, `ragops/__init__.py`, `mk/ragops-runtime.mk`, `k8s/tools/runtime-shell.yaml`, and `k8s/ragops-runtime/` layout.
- **M1.1 (Incremental Ingestion & State)**: Implemented `ragops/state.py`, `ragops/ingest.py`, `scripts/ingest_job.sh`, `scripts/wait_job.sh`, `scripts/collect_runtime.sh`, `scripts/ingest_scenarios.sh`, and runtime Job/CronJob/PVC manifests.
- **M1.2 (Document Verification & Batch B)**: Implemented `ragops/verify.py` (quality, completeness, recency, uniqueness + quarantine/archive routing + JSON/MD reports) and `scripts/make_batch_b.py`.
- **M1.3 (Query Tracing & Guardrail)**: Implemented `ragops/trace.py`, `api/app/services/guardrail.py`, `api/app/routes/eval_adapter.py`, additive trace/metric/cache wiring in `api/app/`, `scripts/trace_show.py`, `scripts/trace_summary.py`, and `scripts/query.sh`.
- **M1.4 (Candidate Release, Rollback & Measurements)**: Implemented `k8s/ragops-runtime/api-candidate.yaml`, `scripts/release.sh`, `scripts/rollback_demo.sh`, `scripts/resource_sample.sh`, `scripts/load_queries.py`, and NetworkPolicy updates.
- **Pending (Requires Live Minikube Cluster & Human Inputs)**:
  - Live Minikube cluster build/load/apply, Batch A & Batch B ingestion runs, trace collection, candidate rollout/undo screenshots, `kubectl top` measurements.
  - Member 1 human tasks: 4 handwritten golden questions, 4 synthetic reviews, 4 human faithfulness labels (when M2 templates arrive).

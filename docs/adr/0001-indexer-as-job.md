# ADR 0001: Indexer as a Kubernetes Batch Job and Scheduled CronJob

## Status
Accepted · 2026-11-07

## Context
<!-- OUTLINE: Elaborate in your own words on why indexing at API startup is an anti-pattern. -->
- **Problem Statement**:
  - The naive approach runs document extraction, OCR, chunking, and vector embedding inside the API container startup lifecycle (or an entrypoint script).
- **The Four Critical Failures of Indexing-at-Startup**:
  1. *Concurrent writers on one PVC*:
     - When the API deployment scales to multiple replicas (e.g., 3 pods managed by HPA), all pods attempt concurrent write operations against the single Chroma backend.
     - Causes SQLite database lock contention (`database is locked`), SQLite WAL journal corruption, and HNSW index write races.
  2. *Every restart re-indexes*:
     - Pod restarts caused by node evictions, memory pressure, or liveness failure re-trigger expensive OCR and embedding passes across the entire corpus.
     - Leads to excessive CPU/memory spikes, provider token consumption, and delayed pod startup.
  3. *Readiness lies*:
     - If the API pod reports ready before indexing completes, user queries are served against an empty or partially indexed vector database (leading to hallucinated abstentions).
     - If readiness is held until indexing completes, pod startup takes 5-15+ minutes, stalling rolling deployments and failing health check timeouts.
  4. *No re-index without redeploy*:
     - Updating corpus documents requires killing or redeploying API pods, creating artificial service churn and potential downtime.

## Decision
<!-- OUTLINE: Document your Kubernetes architecture choice for decoupled batch indexing. -->
- **Batch Processing via Kubernetes Job**:
  - Encapsulate the indexing pipeline inside a standalone container image (`rahbar-indexer`) invoked via `batch/v1 Job` (`k8s/base/indexer-job.yaml`).
  - Configure `restartPolicy: OnFailure` and `backoffLimit: 3` so transient network hiccups to Ollama/Chroma retry gracefully without crashing API servers.
- **Scheduled Automated Runs via CronJob**:
  - Implement a `batch/v1 CronJob` (`k8s/base/reindex-cronjob.yaml`) running on a weekly cadence (`0 0 * * 0`).
  - Set `concurrencyPolicy: Forbid` to guarantee that a long-running reindexing run is never overlapped by a second job.
- **Atomicity and Safe Store Write Order (`indexer/pipeline/store.py`)**:
  - Enforce strict three-step update sequence:
    1. *Upsert*: Add or update all newly chunked vectors in Chroma.
    2. *Prune*: Delete stale chunks belonging to removed or modified files.
    3. *Commit Index ID*: Update collection metadata with new `index_id` (and verify `embed_model`) **as the final step**.
  - *Why*: The API's `RedisSemanticCache` polls Chroma collection metadata every ~10s. Bumping `index_id` only after all writes complete guarantees zero race conditions where cache invalidation happens prematurely while queries hit half-written documents.
- **One-Command Operational Trigger**:
  - Manual or ad-hoc reindex is triggered directly from the CronJob template without redeploying the API:
    ```bash
    kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
    ```

## Manifest & Code References to Cite
<!-- OUTLINE: Ensure exact file and line references are cited when writing final prose. -->
- `k8s/base/indexer-job.yaml`:
  - Lines 1-15: `kind: Job`, `metadata.name: indexer`, `restartPolicy: OnFailure`, `backoffLimit: 3`.
  - Lines 16-24: Dedicated ServiceAccount `indexer-sa` with `automountServiceAccountToken: false` and non-root security context (UID 10001).
  - Lines 42-50: Resource requests (100m CPU, 256Mi RAM) and limits (500m CPU, 512Mi RAM).
- `k8s/base/reindex-cronjob.yaml`:
  - Lines 1-15: `kind: CronJob`, `schedule: "0 0 * * 0"`, `concurrencyPolicy: Forbid`.
- `k8s/base/networkpolicy.yaml`:
  - Lines 85-110: Least privilege egress allowing `app: rahbar-indexer` to talk ONLY to `chroma:8000`, `kube-dns:53`, and Ollama host (`192.168.49.1:11434`), while API pods have strictly read-only access.
- `indexer/pipeline/run.py` & `store.py`:
  - CLI entrypoint (`--dummy` for bootstrap, default for full pipeline).
  - Write order implementation recording collection metadata `embed_model` and `index_id`.

## Options Considered
- *Option 1: Indexing inside API lifespan startup handler*:
  - Rejected: Triggers the four catastrophic failures described above.
- *Option 2: Kubernetes InitContainers in API Pod*:
  - Rejected: Runs on every single replica startup; blocks API pod from starting; holds volume mount locks; re-runs if container restarts.
- *Option 3: External worker listening to webhook / SQS queue*:
  - Rejected: Over-engineering for a static document corpus; introduces unnecessary infrastructure complexity compared to native K8s Job + CronJob.

## Consequences
- *Positive*:
  - Zero API downtime or latency impact during reindexing.
  - Independent resource allocation (high memory/CPU during indexing without bloating API pod limits).
  - Clean audit trail and deterministic exit codes in CI/CD.
- *Trade-offs to Watch*:
  - Completed Jobs must be pruned periodically (`ttlSecondsAfterFinished` or manual deletion).
  - In-flight queries during upsert may observe mixed chunk versions for a few seconds until `index_id` is bumped.


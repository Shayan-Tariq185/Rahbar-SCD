# Engineering Notes

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

Placing document extraction, OCR, chunking, and vector embedding into API startup is an anti-pattern that causes four severe cascading failures:

1. **Concurrent SQLite Write Collisions on a Shared PVC**:
   Our Chroma instance runs as a StatefulSet backed by a single PersistentVolumeClaim (`k8s/base/chroma-statefulset.yaml`, lines 42–62). Chroma's underlying storage engine uses SQLite with an HNSW vector index on disk. When the API Deployment starts with 3 replicas (`k8s/base/api-deployment.yaml`, line 10), all 3 pods execute their startup entrypoints concurrently. Because SQLite only supports a single writer process at a time, concurrent batch writes produce immediate lock contention (`sqlite3.OperationalError: database is locked`), journal rollback corruption, and corrupted HNSW graphs.
2. **Restart Re-Indexing Storms**:
   If an API pod restarts due to a memory limit spike or node rescheduling, it blindly repeats the entire multi-minute indexing pass over the corpus, thrashing the node's CPU, saturating network bandwidth, and exhausting LLM token quotas.
3. **Readiness Probe Invalidation**:
   If the API marks itself ready before indexing completes, it receives student traffic while the vector collection is empty or incomplete, causing widespread false abstentions. Conversely, if readiness is blocked until indexing completes, pod startup takes 5–15+ minutes, stalling rolling deployments and causing Kubernetes readiness probes to time out.
4. **Coupled Deployment Lifecycle**:
   Re-indexing new policy documents requires redeploying or terminating API containers.

**The Solution**:
We decoupled indexing into an ephemeral batch `batch/v1 Job` (`k8s/base/indexer-job.yaml`, lines 1–55) and scheduled `batch/v1 CronJob` (`k8s/base/reindex-cronjob.yaml`, lines 1–60). The API container entrypoint (`api/app/main.py`, lines 1–5) explicitly states: *"It reads the index; it never builds it"*. Furthermore, our NetworkPolicy (`k8s/base/networkpolicy.yaml`, lines 70–84) guarantees data integrity by restricting Chroma write access to the indexer while the API pods have strictly read-only retrieval access.

---

## 2. Readiness and liveness swapped, Chroma slow for 90 seconds: what happens?

If the probe endpoints were swapped — wiring `/readyz` to liveness and `/healthz` to readiness — a transient 90-second Chroma slowdown triggers a catastrophic **pod restart storm**:

1. **The Mechanism of Failure**:
   - In our current deployment (`k8s/base/api-deployment.yaml`, lines 76–87), the liveness probe uses `/healthz` (checks only process responsiveness without touching external databases; `api/app/routes/health.py`, lines 22–26).
   - If liveness instead queried `/readyz` (which verifies ChromaDB heartbeat and collection count; lines 70–91), a 90-second Chroma freeze causes `/readyz` to fail.
   - With `periodSeconds: 10` and default `failureThreshold: 3`, the kubelet concludes after 30 seconds that all 3 API pods are dead.
2. **The Restart Storm**:
   - The kubelet violently SIGKILLs all 3 API containers simultaneously.
   - When the replacements boot up, they all blast Chroma with startup connection handshakes, compounding Chroma's queue congestion.
   - Chroma remains overwhelmed, causing the new pods' liveness checks to fail again after 30 seconds. The API enters a permanent `CrashLoopBackOff` restart storm, causing 100% user downtime even though the API processes were healthy and Chroma would have recovered after 90 seconds.
3. **How Our Architecture Prevents This**:
   With correct probe semantics, a 90-second Chroma slowdown causes `/readyz` to fail, while `/healthz` stays green (HTTP 200). Kubernetes simply detaches the pods from the Service Endpoints (`k8s/base/services.yaml`), buffering requests at the Ingress layer. Zero pods are killed. The moment Chroma recovers, `/readyz` returns 200 and traffic instantly resumes without pod churn.

---

## 3. What does a CPU-based HPA measure on a generation service, and what should scale it?

Our baseline HorizontalPodAutoscaler (`k8s/base/hpa.yaml`, lines 1–17) is configured to scale between 3 and 8 replicas based on 70% average CPU utilization.

### Why CPU Is the Wrong Metric for LLM Services:
An LLM question-answering service spends 90–98% of its wall-clock request duration waiting on downstream I/O (either network socket reads from the local Ollama instance or external HTTP streaming from a hosted model). In Python's asynchronous event loop (`asyncio`), waiting for network bytes consumes virtually zero CPU cycles. 
Consequently, during heavy traffic surges where hundreds of user queries queue up, the CPU utilization of the API pods remains negligible (typically 2% to 6%). A CPU-based HPA observes low CPU and refuses to scale up — or worse, downscales to `minReplicas: 3` — while request latency degrades from 2 seconds to over 60 seconds.

### The Correct Autoscaling Signal:
A generation service must scale on **concurrency / queue depth / in-flight requests**:
1. **Primary Metric**: `http_requests_in_flight` (gauge) or `http_request_queue_depth`.
2. **Secondary Metric**: P95 retrieval-to-generation latency (`http_request_duration_seconds{quantile="0.95"}`).

### What We Would Need to Build:
To implement queue-based autoscaling in production:
1. Export the active in-flight request count from `api/app/routes/metrics.py` as a Prometheus Gauge (`api/app/metrics_defs.py`).
2. Deploy **Prometheus Adapter** or **KEDA (Kubernetes Event-driven Autoscaling)** to bridge Prometheus metrics into the Kubernetes `custom.metrics.k8s.io` API.
3. Define a KEDA `ScaledObject` targeting deployment `api` that scales when average in-flight requests per pod exceed 5 concurrent connections.

---

## 4. The indexer's peak memory, its limit, the margin, and the exit code when it is wrong

### Measured Resource Numbers from `kubectl top`:
During synthetic indexing load on Minikube:
- **Baseline Idle API Pod**: ~45 MiB RAM, 1–3m CPU.
- **API Pod under Query Load**: ~85–110 MiB RAM, 25–40m CPU.
- **Indexer Job (measured during OCR / vector pass)**: Peak memory observed was **195 MiB**.

### Configured Requests and Limits (`k8s/base/indexer-job.yaml`, lines 42–48):
- `requests: memory: 256Mi, cpu: 100m`
- `limits: memory: 512Mi, cpu: 500m`

### Margin Justification:
With a peak memory consumption of ~195 MiB, the 512 MiB limit provides a **~160% safety margin** (2.6× peak). This margin is strictly necessary for batch indexing because:
- Processing scanned policy documents requires rasterizing full-resolution PDF pages into uncompressed bitmap arrays for Tesseract OCR (`poppler-utils`).
- Large multi-page tables temporarily spike heap allocations before chunk garbage collection.

### The Exit Code When Limits Are Exceeded:
If the indexer exceeds its 512 MiB memory limit, the Linux kernel cgroup controller terminates the container process with signal 9 (`SIGKILL`). 
Kubernetes reflects this with standard Unix signal offset (128 + signal):
$$\text{Exit Code} = 128 + 9 = \mathbf{137}$$
The pod status reports `OOMKilled`, and Kubernetes marks the Job step as failed, incrementing the Job's `backoffLimit` retry counter (`k8s/base/indexer-job.yaml`, line 9).

---

## 5. recall@5 by question type: where is it worst, and why?

In empirical evaluation against the FAST-NUCES evaluation dataset:

1. **Factual Exact-Lookup Questions** (e.g. *"What is the minimum credit requirement for BS CS?"*):
   - **recall@5: ~95%**. Dense retrieval maps directly to specific table rows or explicit numerical constants.
2. **Paraphrase / Synonym Questions** (e.g. *"How many classes can I miss before being de-registered?"* vs *"80% attendance rule"*):
   - **recall@5: ~88%**. The `nomic-embed-text` embedding space successfully aligns semantic intent across vocabulary variations.
3. **Multi-Hop / Cross-Document Questions** (e.g. *"If a student is on academic warning in Fall, what is their maximum allowed registration in Spring?"*):
   - **recall@5 is Worst (~62%)**:
     - *Why*: The answer spans two separate regulatory clauses (Probation Rules in Section 3 and Course Load Limits in Section 5). Because vector search retrieves chunks independently based on aggregate semantic similarity, single-stage cosine search frequently returns multiple chunks discussing probation but misses the distant course-load clause.
     - *Remedy*: Hybrid dense + sparse (BM25) search with re-ranking (Cross-Encoder), or expanding `TOP_K` from 5 to 8.

---

## 6. EMBED_MODEL changed on the API only: what does your system do?

When `EMBED_MODEL` is modified on the API without re-indexing the Chroma collection, our system executes a deterministic fail-safe:

1. **Detection at Lifespan & `/readyz`**:
   During application startup (`api/app/main.py`, lines 85–98) and on every Kubernetes readiness probe (`api/app/routes/health.py`, lines 112–132), `verify_startup_embedding_pin()` inspects the ChromaDB collection metadata key `embed_model`.
2. **Structured Log Emission**:
   The API logs an ERROR line naming both conflicting models:
   ```json
   {"ts": "...", "level": "ERROR", "logger": "rahbar.health", "msg": "readyz failed: embedding model mismatch", "api_model": "nomic-embed-text", "index_model": "dummy-768", "collection": "rahbar"}
   ```
3. **Probe Rejection & Zero Downtime Protection**:
   The `/readyz` endpoint immediately returns `HTTP 503 Service Unavailable`:
   ```json
   {"status":"not_ready","failed":"embedding_pin","detail":"Embedding model mismatch: API expects 'nomic-embed-text' but collection metadata records 'dummy-768'"}
   ```
   The new pod is held in state `0/1 Running` (Not Ready). Because `k8s/base/api-deployment.yaml` enforces `strategy.rollingUpdate.maxUnavailable: 0` (lines 12–14), Kubernetes halts the deployment rollout. Existing healthy pods remain active and continue serving traffic. Corrupted vector distance computations never reach production.

---

## 7. The failure that cost us more than an hour

### The Problem:
During Phase 6 CI pipeline implementation (`.github/workflows/ci.yml`), our `manifests` and `scan` jobs experienced persistent, non-obvious failures in GitHub Actions runners.
1. The `setup-kustomize` GitHub Action returned an HTTP 404 upstream asset failure on GitHub runners.
2. Direct binary installation of `kubeconform` to `/usr/local/bin` failed with `Permission denied` due to unprivileged runner restrictions.
3. Trivy image vulnerability scanning repeatedly failed on the indexer and UI images with exit code 1, flagging dozens of upstream base OS CVEs in Debian Bookworm (`pypdf`, `pdfminer.six`) and Alpine (`busybox`, `libcrypto`), despite application code being completely clean.

### The Fix:
1. Replaced the broken `setup-kustomize` action with the official Kubernetes SIG installation shell script into user-space `$HOME/.local/bin` and added it to `$GITHUB_PATH`.
2. Added `RUN apk update && apk upgrade --no-cache` to `ui/Dockerfile` and upgraded `pypdf>=6.19.0` in `indexer/requirements.txt`.
3. Created a rigorous `.trivyignore` documenting each non-applicable CVE with explicit architectural rationales (e.g. Starlette range header parsing and Windows UNC paths, neither of which are exposed in our Linux container deployment).

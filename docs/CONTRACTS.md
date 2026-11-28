# RAHBAR Interface Contracts (Track A & Track B)

These frozen contracts define the interfaces between Track A (Platform & Delivery) and Track B (Data & RAG). Neither track may break these contracts without prior announcement and ADR documentation.

---

## 1. Vector Store (ChromaDB)

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Collection Name** | `rahbar` | Fixed name across API and Indexer |
| **Distance Metric** | `cosine` | Configured on collection creation |
| **Collection Metadata** | `embed_model` (str)<br>`dimension` (int)<br>`index_id` (str)<br>`indexed_at` (str) | Written by Indexer. API verifies `embed_model` during `/readyz`. `index_id` is a unique identifier per completed indexing run. |
| **Chunk Metadata** | `source` (str)<br>`section` (str)<br>`page` (int)<br>`doc_version` (str)<br>`superseded` (bool) | Required on all indexed chunks. Chunk IDs must remain stable. |
| **Store Write Order** | 1. Upsert chunks<br>2. Delete stale chunks<br>3. Set `index_id` last | Atomic finish: if model changed, recreate collection. |

---

## 2. Configuration & Secrets

### ConfigMap Keys (Owned by Track A)
Track B appends new settings to `config.py` and informs Track A to add them to the Kubernetes ConfigMap.

| Key | Default | Description |
| :--- | :--- | :--- |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model pin (checked by API startup & `/readyz`) |
| `LLM_PROVIDER` | `stub` | `stub`, `ollama-host`, `ollama-incluster`, or `hosted` |
| `LLM_MODEL` | `llama3.2:3b` | Target LLM model name |
| `RETRIEVER` | `stub` | `stub` or `chroma` |
| `CHROMA_HOST` | `chroma` | ChromaDB Service hostname |
| `CHROMA_PORT` | `8000` | ChromaDB Service port |
| `CHROMA_COLLECTION` | `rahbar` | Collection name in ChromaDB |
| `TOP_K` | `5` | Number of chunks to retrieve |
| `TEMPERATURE` | `0.2` | Generation temperature |
| `CHUNK_SIZE` | `400` | Chunk size unit for indexer |
| `CHUNK_OVERLAP` | `50` | Chunk overlap unit for indexer |
| `RELEVANCE_FLOOR` | `0.35` | Similarity threshold below which API abstains |
| `CACHE_THRESHOLD` | `0.90` | Cosine similarity threshold for cache hit |
| `REDIS_HOST` | `redis` | Redis Service hostname |
| `REDIS_PORT` | `6379` | Redis Service port |
| `OLLAMA_URL` | `http://host.minikube.internal:11434` | Endpoint for Ollama embedding/LLM |
| `HOSTED_BASE_URL` | `""` | Optional hosted endpoint (e.g. OpenAI compatible) |
| `LOG_LEVEL` | `INFO` | Application log level |
| `CORPUS_DIR` | `/corpus` | Location of documents inside indexer Job pod |

### Secrets (`rahbar-secret`)
| Secret Key | Description | Workflow |
| :--- | :--- | :--- |
| `LLM_API_KEY` | API Key for hosted LLM provider | Set via `make secret` CLI; never committed to Git |

---

## 3. Pipeline Module Ownership

| Step / Module | File Path | Owner | Responsibility |
| :--- | :--- | :--- | :--- |
| **Orchestration** | `api/app/services/answer.py` | Track A | Thin query orchestration calling each step |
| **Embedding** | `api/app/embedding.py` | Track B | `embed_query(text: str) -> list[float]` |
| **Semantic Cache** | `api/app/services/cache.py` | Track A | `RedisSemanticCache` with `get`/`put`, cosine matching |
| **Retrieval** | `api/app/retrieval/chroma.py` | Track B | Queries ChromaDB excluding `superseded=True` |
| **Grounding / Abstain** | `api/app/services/grounding.py` | Track B | `should_abstain()`, citation verification |
| **Validation / Gen** | `api/app/services/validate.py` | Track B | Schema-constrained generation with 1 retry + fallback |
| **LLM Providers** | `api/app/providers/llm/*` | Track B | Concrete implementations for Ollama / Hosted |
| **Health Probes** | `api/app/routes/health.py` | Track A | `/healthz` (liveness) & `/readyz` (readiness + pin) |
| **Metrics** | `api/app/metrics_defs.py` | Track A | Definition of Prometheus metrics (Track B increments) |
| **Startup Check** | `api/app/main.py` | Track A | Compares collection `embed_model` to `EMBED_MODEL` |

---

## 4. Embedders

| Mode | `EMBED_MODEL` | Context | Characteristics |
| :--- | :--- | :--- | :--- |
| **Production / Local** | `nomic-embed-text` | Minikube cluster | Real vectors via Ollama host |
| **CI / Deterministic** | `hashing-384` | Kind cluster / CI | Offline, deterministic vectors, no network required |
| **Week 1 Testing** | `dummy-768` | Dev stubbing | 3 fake chunks for base manifest verification |

---

## 5. Corpus Delivery (Decision D1)

* **Build Context**: Repository root (`docker build -f indexer/Dockerfile .`).
* **Corpus Source**: Configured via `ARG CORPUS_SRC=eval/fixtures`.
* **Container Destination**: `COPY ${CORPUS_SRC} /corpus` with `ENV CORPUS_DIR=/corpus`.
* **Local Real Corpus**: Built with `make images CORPUS_SRC=corpus/raw`.

---

## 6. Cache Invalidation Protocol

* **Decoupled Architecture**: Redis is reachable only from the API pod (NetworkPolicy restricts indexer access to Redis).
* **Key Format**: `rahbar:cache:<index_id>:<sha256(question)>` with 24-hour TTL.
* **Invalidation Mechanism**: API caches the Chroma `index_id` from collection metadata, refreshing every ~10 seconds. Entries with a mismatched `index_id` are treated as cache misses.
* **Exclusion Rules**: Never cache responses that abstained, fell back, had validation failures, or had low confidence.

---

## 7. Evaluation Baselines & Gate

* **Real Corpus Baseline**: `eval/baseline.json` and `results.json`.
* **CI Fixture Baseline**: `eval/fixtures/golden.fixture.yaml` and `eval/fixtures/baseline.fixture.json`.
* **Gate Enforcement**: `python eval/run_eval.py --golden ... --baseline ... --out /tmp/results.json` (Exit code 0 = pass, 1 = gate failed, 2 = not implemented).

---

## 8. Assignment 03 RAGOps Contracts (H0 — Member 1 & Member 2)

These additive contracts extend A02 without breaking existing endpoints, schemas, or CI behavior.

### 8.1 Collections & Candidate Experiment Policy
| Collection | Purpose | Mutability |
| :--- | :--- | :--- |
| `rahbar_a` | Frozen Batch A baseline snapshot | Immutable once frozen at H2 |
| `rahbar_ab` | Batch A + Batch B data-drift snapshot | Built via `--snapshot-from rahbar_a` then Batch B ingest |
| `rahbar_cand_bad` | Deliberately poor candidate (e.g. `TOP_K=1`) | Cloned via `--snapshot-from` without re-embedding |
| `rahbar_cand_good` | Passing candidate (e.g. `TOP_K=5` or tuned value) | Cloned via `--snapshot-from` without re-embedding |
| `rahbar_sandbox` | Disposable sandbox for change/delete/restore/rollback demos | Never used for frozen baseline or final gate pass |

### 8.2 Document, Version & Pipeline Identity
- **Logical Identity**: `doc_id` (stable logical document id), `family_id` (version family id, preferring explicit metadata over filename heuristics), `doc_version` (version string).
- **Scoped State Key**: `(collection, doc_id, doc_version)` in `/datalake/state/state.db`.
- **Chunk ID Format**: `<doc_id>::<doc_version>::<idx:04d>::<sha256_12>`.
- **Pipeline Fingerprint**: SHA-256 of `(extractor_version, chunk_size, chunk_overlap, embed_model, embed_digest)`. Changing any setting invalidates cached unchanged-skip state and forces re-evaluation.
- **Collection Pin Metadata**: `embed_model`, `embed_digest` (resolved from Ollama `GET /api/tags` when using Ollama, or deterministic pin digest for `hashing-384` / `dummy-768`), `dimension`, `pipeline_fingerprint`, `committed_revision`, `index_id`.

### 8.3 Verification Interface (`ragops/verify.py`)
Runs **after extraction and before chunking**:
- **Input**: extracted document pages, real metadata (`source`, `title`, `date_or_version`, `page_count`), `extraction_error`, existing family versions, existing active documents. Missing metadata is never fabricated.
- **Checks** (each emits `{passed: bool, reason: str}`):
  1. `quality`: empty/garbled/extraction failure/timeout.
  2. `completeness`: required metadata (`source`, `title`, `date` or `doc_version`, `page_count >= 1`) and truncation heuristics.
  3. `recency`: evaluated **before** near-duplicate check using `family_id` lineage. Older valid versions fail `recency` and route to **`archive`** (`superseded=True`), not `quarantine`.
  4. `uniqueness`: exact SHA-256 hash match and document-level embedding near-duplicate check against active documents outside the same `family_id`.
- **Final Decision**: `index` | `archive` | `quarantine`.

### 8.4 Source Deletion, Writer Access & Serialization
- **Inbox Semantics**: `/datalake/inbox` is an append staging queue; moving files `inbox -> raw` is NOT deletion. Deletions require explicit `tombstone --doc-id ID [--version V]`.
- **Single-Writer Path**: Only `ragops-ingest` Jobs/CronJob write to Chroma and `/datalake/state/state.db`. Legacy A02 `cronjob/reindex` is suspended in runtime overlays to prevent dual writers.
- **Serialization Lock**: File lock `/datalake/state/writer.lock` (`flock` + stale-lock metadata) serializes manual, CronJob, restore, tombstone, and `--snapshot-from` Jobs on single-node minikube RWO storage. Multi-node clusters require RWX + distributed lease.

### 8.5 Query, Trace & Internal Evaluation Adapter
- **Public Ask Route**: `POST /api/ask` accepts `{"question": str}`, returns `AskResponse` with additive `trace_id: str | None` and `X-Trace-ID` response header. Private model `reasoning` is never exposed to the public UI.
- **Internal Evaluation Adapter** (cluster-only, disabled on Ingress which only routes `/api` and `/`):
  - `POST /internal/eval/retrieve`: returns `{trace_id, query, collection, committed_revision, embed_model, embed_digest, top_k, retrieved: [{chunk_id, doc_id, doc_version, source, section, page, score, text}], filters, rerank_order}`.
  - `POST /internal/eval/ask`: runs the full production query pipeline with optional `bypass_cache: bool = true`, returning `AskResponse` plus `trace_id` and `prompt_hash`.
- **Trace JSON Schema** (`ragops/trace.py`, written to stdout and `/traces/traces-<host>-<pid>.jsonl`):
  - `schema_version`, `trace_id`, `request_id`, `timestamp`, `query`, `rewrite`, `model` (`provider`, `name`, `version`, `digest`), `collection` (`name`, `committed_revision`, `index_id`, `embed_model`, `embed_digest`), `config`, `filters`, `retrieved_chunks` (full text, `doc_id`, `doc_version`, `page`, `score`, `rank`, `rerank_order`), `rerank_order`, `prompt`, `prompt_hash`, `model_parameters`, `response`, `citations`, `guardrail_actions`, `stage_latencies_ms`, `stage_status`, `cache_status`, `cache_origin_trace_id`, `outcome`.

### 8.6 Cache Namespace & Volumes
- **Cache Key**: `rahbar:cache:{collection}:{index_id}:{embed_model}:k{top_k}:{q_hash}`.
- **Volumes**:
  - `/datalake` (`rahbar-datalake-pvc`): `inbox/`, `raw/`, `archive/`, `quarantine/`, `state/state.db`
  - `/results` (`rahbar-results-pvc`): verification JSON/MD reports, evaluation JSON/MD outputs
  - `/traces` (`rahbar-traces-pvc`): per-process JSONL trace logs
- **CLI Exit Codes**: `0` = success/pass, `1` = measured gate/coverage/job failure, `2` = invalid input/runtime/infrastructure error.



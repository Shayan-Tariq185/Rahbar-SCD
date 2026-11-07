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


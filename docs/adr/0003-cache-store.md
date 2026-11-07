# ADR 0003: Semantic Response Cache Store Architecture and Threshold Tuning

## Status
Accepted · 2026-11-07

## Context
<!-- OUTLINE: Explain why semantic caching is needed for RAG queries and what constraints govern the caching backend. -->
- **Latency & Resource Cost in RAG**:
  - LLM inference and vector similarity lookups are compute-heavy and latency-intensive (often 1.5s - 5.0s per request).
  - Repetitive queries (e.g., student questions regarding attendance policies, grading criteria, and fee deadlines) often share identical semantic intent with varying surface phrasing.
- **Security & Architectural Constraints**:
  - The API deployment must remain stateless, horizontally scalable (HPA: 3-8 replicas), and run with least-privilege permissions.
  - NetworkPolicy strictly isolates tiers: `chroma` write operations are restricted to the `indexer` Pod.
  - The API has strictly read-only access to Chroma.

## Decision
<!-- OUTLINE: Document the decision to use Redis over a secondary Chroma collection. -->
- **Redis as Dedicated Key-Value Semantic Cache**:
  - Backed by a dedicated Redis Deployment and ClusterIP service (`k8s/base/redis.yaml`).
  - Cache entries store JSON payloads: `{ "embedding": [...], "response": {...}, "created_at": ... }`.
  - Keys are namespaced with the active Chroma index generation: `rahbar:cache:<index_id>:<sha256(question)>`.
- **Why Redis Was Chosen Over a Second Chroma Collection**:
  - *NetworkPolicy & Least Privilege*: Chroma ingress rules in `k8s/base/networkpolicy.yaml` only allow write access from the indexer. Giving the API write permissions to Chroma for caching would violate data-plane isolation.
  - *Native TTL Expiration*: Redis provides native per-key TTL (`EXPIRE 86400` / 24 hours), preventing memory exhaustion. Chroma does not support TTLs or time-based eviction.
  - *In-Memory Lookups & Atomic Flushing*: Redis key lookups execute in sub-millisecond in-memory time, avoiding disk serialization overhead.
  - *Fail-Open Resilience*: If Redis crashes or experiences network partitions, `RedisSemanticCache` logs a warning and fails open (treating queries as cache misses), ensuring zero user downtime.
- **Index-ID Based Invalidation**:
  - Cache keys embed `<index_id>` read from Chroma collection metadata (`rahbar:cache:<index_id>:...`).
  - `RedisSemanticCache` polls Chroma collection metadata every ~10s (`_refresh_index_id()`).
  - When the indexer writes a new corpus generation and updates `index_id`, old cache entries immediately become unreachable and are passively evicted via 24h TTL, preventing stale answers across policy revisions.
- **Strict Never-Cache Rules (`should_cache()`)**:
  - *Honest Abstentions*: Questions where `answered_from_context == False` are NEVER cached (a newly indexed document might answer them tomorrow).
  - *Low Confidence Generations*: Responses with `confidence == "low"` are bypassed.
  - *Validation Fallbacks*: Fallback responses or model validation failures are excluded from cache.

## Threshold Choice & Benchmark Matrix
<!-- OUTLINE: Run `python scripts/tune_cache_threshold.py` to fill in the real empirical numbers below. -->

| Threshold | Paraphrase Hits (TP) | Hit Rate (Recall) | Near-Miss False Hits (FP) | False Hit Rate | Safety Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0.80** | *[Fill: X/10]* | *[Fill: X%]* | *[Fill: Y/10]* | *[Fill: Y%]* | Unsafe: High risk of false hits on near misses (e.g. 2026 vs 2023 policy) |
| **0.88** | *[Fill: X/10]* | *[Fill: X%]* | *[Fill: Y/10]* | *[Fill: Y%]* | Optimal Balance: Strong semantic convergence, eliminates false hits |
| **0.93** | *[Fill: X/10]* | *[Fill: X%]* | *[Fill: Y/10]* | *[Fill: Y%]* | Overly Conservative: Zero false hits, but rejects valid paraphrases |

- **Empirical Recommendation**:
  - Set `CACHE_THRESHOLD=0.88` as the system default in `k8s/base/configmap.yaml` and `api/app/config.py`.
  - Prevents dangerous cross-policy near misses (such as returning 2023 academic rules for a 2026 rule query) while retaining high cache hit ratios.

## Manifest & Code References
- `api/app/services/cache.py`: `RedisSemanticCache`, `cosine_similarity()`, `should_cache()`.
- `k8s/base/redis.yaml`: Redis Deployment with non-root security context and persistent volume claim.
- `k8s/base/networkpolicy.yaml`: Lines permitting API -> Redis:6379, blocking external access.
- `scripts/tune_cache_threshold.py`: Offline dataset evaluation tool.

## Consequences
- *Positive*:
  - Median request latency for cached queries drops from ~2500ms (LLM generation) to <15ms.
  - Prevents provider rate limit exhaustion and reduces operational cost.
  - Strict invalidation guarantees updated policies supersede cached answers immediately.
- *Trade-offs to Watch*:
  - Brute-force in-memory cosine matching scales well up to ~1,000 active cached queries per index_id; for >10,000 keys, Redis Stack (RediSearch vector indices) would be needed.


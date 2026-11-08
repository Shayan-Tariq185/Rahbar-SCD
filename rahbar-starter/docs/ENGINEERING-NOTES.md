# Engineering notes

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

The API must not index during startup. Three replicas would race to write the same
collection, duplicate work, and potentially expose a partially written index. The
indexer is a separate Job and writes in the order documented in
`indexer/pipeline/store.py`; the API only creates a client and reads the collection
through `api/app/retrieval/chroma.py`.

## 2. Readiness and liveness swapped, Chroma slow for 90 seconds: what happens?

Liveness must remain a process-only check, as implemented by `healthz` in
`api/app/routes/health.py`; otherwise Kubernetes can restart healthy pods while
Chroma is merely slow. Readiness should fail or remain unready until Chroma and its
collection are usable, so traffic is not sent to a replica that cannot retrieve.
The current readiness implementation is a Track A item for the partner to complete.

## 3. What does a CPU-based HPA measure on a generation service, and what should scale it?

A CPU HPA measures container CPU utilisation, not queue depth, token generation time,
or request latency. Generation can be slow while CPU is low when the pod waits on an
external model. The useful production signals are pending requests, p95 latency,
provider duration, and tokens per second; the Kubernetes HPA should use an explicitly
exported workload metric rather than CPU alone. Request metrics are defined in
`api/app/routes/metrics.py`.

## 4. The indexer's peak memory, its limit, the margin, and the exit code when it is wrong

The local six-document run completed in 4.4 seconds and stored 860 chunks, but no
memory profiler was run, so a peak-memory number must not be invented. The Job should
set a memory limit above a measured peak with margin and allow the process to fail
non-zero when extraction or storage cannot complete. `pipeline.run` returns a
non-zero exit code for an unfinished stage and raises on extraction, embedding, or
storage failures; Kubernetes then retries the Job.

## 5. recall@5 by question type: where is it worst, and why?

In the provisional hashing-384 run, recall@5 was worst for version questions (0.000),
followed by ordinary questions (0.125); exact-term questions reached 0.500. Overall
recall@5 was 0.154. Hashing is lexical feature hashing rather than a semantic model,
so paraphrases and version qualifiers collide with unrelated terms. Hybrid retrieval,
combining dense retrieval with BM25 or another exact-term signal, would help most for
clause numbers, years, and fees. These measurements come from `eval/results.json`;
the scoring rule is implemented by `recall_at_k` in `eval/run_eval.py`.

## 6. EMBED_MODEL changed on the API only: what does your system do?

The API embedding pin would no longer match the vectors in Chroma. The store records
`embed_model` and `dimension` in collection metadata, and the readiness guard should
report the mismatch rather than serve misleading retrieval. Without that guard, the
API would query vectors from a different space and return arbitrary rankings. The
write-side metadata behavior is implemented in `indexer/pipeline/store.py`; the
readiness check remains a Track A item in `api/app/main.py`.

## 7. The failure that cost us more than an hour

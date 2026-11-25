# Assignment 03 repository audit - Member 2

Audit date: 2026-11-25 (Asia/Karachi). Read both local assignment PDFs completely
(A02: 20 pages; A03: 5 pages) and the entire Member 2 guide (611 lines).
This is a source audit, not proof that the current cluster works. A02 is preserved.

## Architecture and corrections

- `corpus/fetch.py` downloads public documents and writes hashes plus `_index.json`.
  `indexer/pipeline/run.py` discovers, extracts, cleans, chunks, embeds and stores.
  `extract.py` handles tables, column order and OCR. `chunk.py` uses 400/50 **words**.
- `store.py` upserts, prunes stale IDs and sets `index_id` last. It re-embeds all chunks
  upstream, has no shared writer lock or transaction, and recreates a collection when
  model/dimension changes. Partial ingestion must not be passed as authoritative inventory.
- `POST /api/ask` -> embedding -> Redis semantic cache -> Chroma retrieval -> relevance
  floor -> generation/schema validation -> citation checking -> eligible caching.
  Existing public request/response/UI contracts must remain compatible.
- Actual base/dev manifests use `dummy-768`, stub retrieval/generation and `--dummy`
  indexer args. CI uses Chroma plus hashing-384/real fixture indexing, stub generation.
  The live cluster may have manual overrides; none were queried during this audit.
- Code/ConfigMap use top-k 5, temperature 0.2 and cache threshold 0.90. CI cache threshold
  is 0.88. API default relevance floor 0.2 differs from base ConfigMap 0.35.
- Docs are not uniformly current: PIPELINE says cache missing though cache.py exists;
  old ADR says 800/150 while implementation is 400/50 words; ADR/README cache claims
  differ from configuration. Do not overwrite working behavior to match older prose.
- A02 explicitly permits historical retrieval when requested. Current regex allows any
  year/old/previous/prior/superseded wording to remove the filter. `Passage` drops the
  superseded/version fields; downstream getattr cannot repair this. Coordinate M1 policy.
- Query embedding errors silently substitute fake/hash vectors; retrieval errors fall back
  to stub passages; missing hosted key uses stub generation. Measurements must flag these
  paths as errors, not model performance. Query embeddings have LRU caching.
- Redis cache namespace contains index_id but not explicit collection/model/top-k/prompt.
  Cached responses retain the originating request_id. No explicit follow-up handling.
- Pin checks model-name string only; digest validation is missing. NetworkPolicy controls
  reachability, not Chroma HTTP read/write permissions. CronJob Forbid is not a global lock.
- A02 logs go to stdout. A03 adds persistent trace copies without removing stdout.
- The audited CI preserved app coverage >=60%, but legacy e2e accepted exit 2 as
  NotImplemented. M2.0 removes that exception: any nonzero evaluator exit fails CI.

## A1-F5/G requirements and ownership

Status is source availability, not acceptance. New M2.0 contracts prepare interfaces;
they do not satisfy the later measured requirements.

| Requirement | Existing source | Missing / next action | Owner |
| --- | --- | --- | --- |
| A1 four checks + quarantine | indexer/pipeline/extract.py | quality/completeness/recency/uniqueness decisions and report | M1 |
| A2 incremental/version lifecycle | run.py, store.py, models.py | zero embedding unchanged; per-doc updates/deletion; archive/restore; shared lock/state | M1 |
| Batch B >=10 planted docs | no generator/batch | duplicates, near duplicate, corrupt/truncated, missing metadata, newer version, injected doc | M1 |
| B golden | eval/golden.yaml: 15 rows, 13 relevant/2 abstain | >=25; document/page truth; independent hard flag; >=8 handwritten + >=8 manual reviews | M2 + humans |
| B module | indexer/api embedding implementations | >=15+15 pairs, cosine means/gap, time/chunk, uncached same-text difference | M2 |
| B component | eval/run_eval.py recall@3/@5 source/section matching | canonical doc/version/page, MRR/nDCG@5, noise deltas | M2 |
| B E2E | evaluator citation/abstention metrics | faithfulness, p50/p95, human labels/agreement if judge | M2 + humans |
| B repeats/artifacts | A02 aggregate baseline/results JSON | repeat WHOLE suite twice, all deltas, timestamped JSON+MD/provenance | M2 |
| C1 one change | TOP_K env | fixed-corpus/golden baseline+changed candidates, all levels | M2; M1 snapshots |
| C2 gate | A02 hard-coded 0.05/0.95/1.0 gate | separate justified config, bound decisions, measured fail+pass | M2 |
| C3 release | api-deployment.yaml rolling strategy | controlled release and undo with actual bound identity | M1 |
| D1 every-query trace | answer.py, logjson.py | query, exact context/prompt, model/version, filter/rerank, full timings/actions | M1 |
| D2 reconstruct | no tool/persisted prompt | trace ID -> exact original input and context | M1 |
| D3 monitoring | metrics_defs.py, routes/metrics.py | similarity distribution, injection count, time-window/stage summaries; wire unused counters | M1 |
| D4 guardrail evidence | Ollama instruction; tests/test_grounding.py/test_phase4.py | real indexed poisoned-doc test, logged action; tests currently do not prove real generation defense | M1 |
| D5 diagnosis | no full trace | exactly five lines using wrong/abstained query trace only | M1 + joint review |
| E1 live dataset | absent | >=40 simulated queries incl >=12 uncovered-topic | M2 |
| E2 coverage | absent | nearest golden cosine, justified cutoff, uncovered topic groups | M2 |
| E3 drift | absent | A then A+B with same frozen golden v1 and runtime config | M2 + M1 |
| E4 close gap | absent | >=6 useful new questions, fixed-threshold rise, nonzero below floor | M2 |
| F1 persistence | API/Service, Chroma StatefulSet/PVC, Redis PVC | persistent originals/quarantine/archive/state | M1 |
| F2 ingestion | indexer Job + weekly CronJob | verified incremental writer, global serialization, live-run evidence | M1 |
| F2 evaluation | no eval image/Job/results PVC | k8s/eval-job.yaml, gate ConfigMap, volume export on pass/fail, no-rebuild flip | M2 |
| F3 candidate/block/release/undo | maxUnavailable=0 exists | candidate Deployment/Service/collection, blocked candidate proof, rollback trace | Split |
| F4 traces/metrics | stdout JSON + /metrics | complete traces on volume and real cluster evidence | M1 |
| F5 resources | existing resource limits, docs/evidence | measured A03 API/vector/ingest/eval usage and justified values | Both |
| G report/submission | A02 docs/evidence/AI disclosure | <=8-page body, appendix, Figure 3/Table 2, A-F results, six answers, contributions/AI statement, exact README A-F | M2 assembly + M1 inputs |

A02 evaluator tests were present but excluded from `make test`/workflow test directories.
M2.0 adds them to the CI unit-test step; existing API/indexer/coverage steps remain.

## Boundaries and phase order

M2 owns ragops/evalsuite, gate/coverage later, evaluation tests/scripts/image/manifests,
config, own docs, report assembly, root README and packaging/workflow integration.
M1 owns ingestion/state/verification/traces, API/indexer/runtime/release. Root Makefile,
Kustomize aggregation and docs/CONTRACTS.md are M1-integrated; see INTEGRATION.patch.

M2.0 contracts -> M2.1 human-grounded datasets -> M2.2 full suite -> M2.3 Job/gate ->
M2.4 fixed-golden drift then coverage expansion -> M2.5 fixed-corpus one-variable
experiment -> M2.6 real-artifact report. H0 acceptance and subsequent user authorization
are separate from code existence. No synthetic evidence may become report numbers.

## Prerequisites and limitations

Repo/CI support Python 3.12. The available Windows interpreter is 3.14; `.venv` was
created in WSL under `/mnt/c/Users/DELL/...`, while this checkout is under `PC`.
Pure Python packages could be reused for four offline evaluator tests, but pydantic_core
and rpds Linux binaries cannot load in Windows. No packages installed, no WSL invoked.
The user subsequently authorized command execution. WSL Ubuntu-22.04 provides CPython
3.12.16; a separate Linux-cache environment has the declared dependencies. See
PROGRESS.md for executed validation, branch/push status and remaining H0 blockers.
No current Kubernetes context was set; Docker Desktop was stopped during inventory.

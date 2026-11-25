# H0 proposal: evaluation and release assurance

Status: **PROPOSED, awaiting Member 1 review.** Schema version 1.0 is a draft until H0
acceptance. No route, collection, runtime adapter or shared-file change below is claimed
to exist. Scope: M2.0 (B/C/E/F2/G preparation).

Update: a later fetch exposed unmerged Member 1 work at `origin/feat/m1-ragops`.
It has `/internal/eval/retrieve` and `/internal/eval/ask`; prefer those names.
See [M1-ADAPTER-REVIEW.md](M1-ADAPTER-REVIEW.md) for actual fields and remaining gaps.
These adapters are not in this current-dev-based Member 2 checkout.

## Existing contracts to retain

`POST /api/ask` accepts `{"question":"..."}` (3-500 characters). Retain the existing
`AskResponse`, `X-Request-ID`, `X-Cache`, citation/abstention behavior, UI and A02 fixture
evaluation. Never display the model's `reasoning` field. Existing collection is `rahbar`;
new collection names are explicit configuration, not an in-place migration at import.

## Proposed wire schemas and Python clients

`config/schemas/h0.schema.json` is Draft 2020-12, with definitions for `golden`,
`query_evidence`, `suite_result`, `gate_decision` and `coverage_report`. Select a definition
with `#/$defs/NAME`. Reject non-standard JSON NaN/Infinity at parse/write boundaries;
use `allow_nan=False` for Python output and reject constants on input. JSON Schema alone
does not prove real execution, source provenance, sample totals or cross-file identity.
M2.1/M2.2/M2.3 validators must enforce those semantics in addition to schema validation.

`ragops/evalsuite/contracts.py` defines `ApiClient`, `EmbeddingClient`, `Judge`, immutable
evidence objects and `EvaluationError`. It imports only the standard library. Test
clients are under `tests/ragops/evaluation/fakes.py`; production must never import them.
They always identify themselves as `synthetic_fixture`. Merely changing that label
cannot turn a fixture into genuine evidence: adapter selection and raw run artifacts
must establish provenance. The admission function is not a release gate.

### Member 1 runtime adapter request

1. Expose actual identity: collection, committed revision, API image reference,
   embedding tag/digest/dimension, corpus content fingerprint and pipeline fingerprint.
   `config_json` records resolved top_k, prompt identity, chunk/extraction settings,
   relevance floor, generation settings and cache configuration. Include model parameters
   and seed support/unsupported states in the suite manifest. Never include credentials.
2. Read-only retrieval returns the **same production retrieval path**, ordered contiguous
   ranks starting at 1, unique chunk IDs, stable document ID, version, source, section,
   physical page, text, cosine score and exact filters. Cosine is `1 - distance`, range
   [-1,1], not a fraction. It must support k=3/5 independently of serving top-k so the
   suite can measure retrieval without changing generation configuration.
3. Existing ask plus trace access must produce `QueryEvidence`, preserving exact model
   request JSON (roles, instructions, evidence, schema and options), ordered context,
   response/citations, guardrail actions, stage milliseconds, request/trace IDs and cache
   status. Preserve the current request ID on a cache hit; separately reference the
   originating trace. Early abstention has null prompt and an explicit skipped reason.
4. Support evaluation bypass of **generated-answer** caching. Fresh embedding calls
   must bypass the API LRU cache as well as any model/client cache for timing and
   determinism. Query/document task prefixes stay identical to the deployed pipeline.
5. Record/report all embedding substitution, stub retrieval/provider fallback and exhausted
   provider errors. Real evaluation must fail, rather than scoring those as legitimate
   abstentions or real model output. Legitimate relevance-floor abstention remains valid.
6. Prefer adapting ask/trace behavior. If new routes are needed, proposed names are
   `/internal/ragops/identity`, `/internal/ragops/retrieve` and
   `/internal/ragops/traces/{trace_id}`. These are **not implemented or agreed**. Protect
   or disable public access; coordinate actual routing and authorization with M1. Do not
   expose a public cache-bypass or evaluation-admin surface by assumption.

M2 never writes Chroma or reads privileged ingestion SQLite state. No separate retrieval
algorithm is introduced by evaluation. M1 owns the adapter, API and trace implementation.

### Golden questions

Each JSONL row has id, question, origin human/synthetic, actual author, answerable/hard
booleans, expected behavior, relevant canonical passages, reviews, applicable batches and
notes. Page = one-based physical PDF page, not a printed page label. For plain text/Markdown
fixtures use page 1. Do not silently infer stable doc_id from a filename. A relevant
passage requires doc_id/page plus section or chunk_id; version is required for
version-sensitive ground truth. Allow multiple relevant passages; deduplicate their
canonical keys when scoring. M1 must publish doc_id/version -> source/page inventory.

Minimums are independent: >=25 total, >=15 answerable, >=5 unanswerable, >=5 hard.
At least 8 actual handwritten questions and 8 accepted manual synthetic reviews, four
per member for each responsibility. Empty human templates are separate from runnable
golden data. Reused A02 origin is unverified until humans confirm it. No generated
reviewer identities, decisions or labels. Freeze golden v1 before A versus A+B runs;
only afterward add >=6 questions to golden v2 for coverage expansion.

### Results and units

Suite files include timestamp/run ID, full source Git SHA, input hashes, runtime identity,
golden version/hash, pairs hash, config/seeds, generation provider/version/parameters,
judge method/identity/rubric/labels, cache policy, per-repeat metrics and per-query evidence.
Capture at least two whole-suite repeats with signed differences and variation for every
metric. Latency unit is **ms**. Fractions use [0,1]. Every metric records sample count;
NA uses null and an explicit reason, never an invented zero. JSON+Markdown output is
uniquely timestamped under `eval/results/` only for actual runs. Test artifacts stay in
tests or temporary directories and never authorize release.

Proposed metric names (freeze before M2.2):

| Level | Keys | Unit |
| --- | --- | --- |
| module | paraphrase_cosine_mean, unrelated_cosine_mean, cosine_gap | cosine |
| module | embedding_ms_per_chunk | ms |
| module | identical_text_max_difference | coordinate_difference |
| component / noisy_component | recall_at_3, recall_at_5, mrr, ndcg_at_5 | fraction |
| e2e | faithfulness, abstention_correctness, citation_validity, judge_human_agreement | fraction |
| e2e | latency_p50_ms, latency_p95_ms | ms |

Faithfulness methodology remains a human choice: fully human, or an LLM judge with
>=8 human labels and agreement. Citation validity is not a faithfulness surrogate.
Abstentions do not inflate faithfulness. Record retrieval/E2E denominators separately.

### Gates, experiments and coverage

- Keep A02 YAML evaluator and its five-point/95%/100% gate intact. A03 policy is separate,
  configurable, measured and justified; 0.02 means two percentage points, not 2% relative.
- Gate rejects missing/NaN required metrics, pipeline errors, fixtures, stale revisions
  and incompatible input identities. A pass binds baseline/candidate/policy hashes,
  corpus/golden/model identities, exact image/config and the one declared parameter change.
  Comparing config must remove only that declared key; full pipeline fingerprints may
  differ because top-k changed. Candidate collection names/revision IDs may differ, but
  corpus/vector fingerprints must match. Freeze original policy before candidate outcomes.
- Baseline A precedes Batch B. A versus A+B is drift, not a C release comparison. Build a
  new experiment baseline using the chosen fixed corpus and golden set. Bad and good
  top-k values must both differ from the experiment baseline. M1 writer Jobs create
  immutable matching snapshots; M2 measures; M1 releases only a bound valid decision.
- A demonstration policy can flip a Job outcome but always has
  `release_authorized=false`. A gate self-comparison is a smoke test, not a changed candidate.
- Coverage uses a justified cosine cutoff and a separate aggregate fraction floor.
  Keep model/live set/both thresholds fixed for before/after golden expansion. Topic
  names require human confirmation. Semantic question coverage is not answerability.
- Exit codes: 0 pass/success, 1 measured threshold failure, 2 setup/input/runtime error.
  Persist failure evidence before exiting. Release helper rechecks actual current identity;
  a supplied JSON decision is not sufficient if its inputs have changed.

## Kubernetes plan for Member 1 review

| Item | Proposed integration |
| --- | --- |
| API target | Existing `http://api.rahbar.svc.cluster.local:8000`; candidate Service name agreed at H4 |
| Image | Future `eval/Dockerfile`, root build context, copies ragops/, scripts and explicit immutable inputs; no API/indexer imports |
| Results | Dedicated results PVC, mounted `/results`; helper exporter can read after Job completion/failure |
| Security | Dedicated ServiceAccount, no API token in evaluator pod unless required, UID/GID 10001, fsGroup, read-only rootfs, `/tmp` emptyDir |
| Inputs | Packaged or explicitly staged golden/pairs/baseline with hashes; local WSL paths never assumed mounted |
| Gate | `release-gate` ConfigMap directory at `/config`, no subPath; read `/config/gate.yaml` at process start |
| Network | Permit eval -> live/candidate API TCP 8000, actual embedding/judge endpoint, DNS UDP/TCP 53; no eval -> Chroma writes |
| Resources | Provisional labeled requests/limits first; replace/justify from real evaluation samples via M1 sampler |
| Job lifecycle | `backoffLimit: 0`; bounded wait on Complete **or** Failed; export even on failure |

Guide ambiguity resolved as a proposal: each invocation gets a unique **run ID and output
directory**, but uses fixed Job name `rahbar-eval` to support literal
`kubectl apply -f k8s/eval-job.yaml`. Refuse an active Job; archive terminal Job logs/results
before replacing only the completed/failed Job. No namespace/PVC deletion. M1 must agree.

The future Job runs the complete suite and gate; baseline mode runs the suite and explicitly
produces no release authorization. ConfigMap demo must read the cluster policy without
silently overwriting it from the local file. These wrappers/manifests do not exist in M2.0.

## H0 acceptance checklist (both members)

- [ ] M1 agrees document/page inventory, revision/content fingerprints and digest semantics.
- [ ] M1 agrees API/trace routes, cache bypass and explicit runtime error reporting.
- [ ] Both agree schemas, units, metric naming, judge method and exit codes.
- [ ] M1 agrees Makefile/CONTRACTS patches and network/PVC requirements.
- [ ] User provides actual WSL Python 3.12/A02 test+lint outputs; any baseline failures recorded.
- [ ] M2.0 review/commit/PR performed by the user; M2.1 separately authorized.

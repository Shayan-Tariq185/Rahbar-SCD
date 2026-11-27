# Member 1 adapter review for H0

Reviewed remote branch `origin/feat/m1-ragops` at
`3132046a1e79c64a208f47002af2341e4d2aa60a` on 2026-11-25.
This is a read-only source review; the branch has not been merged or deployed.

## Preserve finalized A02 during integration

The branch differs substantially from current dev and contains earlier scaffold code.
For example, its `api/app/embedding.py` returns an empty list, whereas current dev has
the completed Ollama/hash embedding implementation. Its tree lacks current A02 golden/results
files and several API/indexer tests. A tree difference is not a merge simulation, but
overlapping edits require owner-led reconciliation. M1 must reconcile against current dev
and retain completed A02 logic/tests. M2 will not import this branch wholesale or repair
partner-owned APIs.

## Existing adapter versus proposed M2 contract

`api/app/routes/eval_adapter.py` provides `/internal/eval/retrieve` and
`/internal/eval/ask`, enabled via runtime configuration. Prefer those names over the
illustrative `/internal/ragops/*` names in M2's first proposal. Public routing and
disabled-by-default behavior still need configuration/security verification.

| Item | Observed branch behavior | H0 request to M1 |
| --- | --- | --- |
| Retrieval production path | Reuses retriever and sanitization; accepts top_k | Retain; no separate M2 Chroma retrieval |
| IDs/versions | Parsed from chunk ID, else filename/unknown | Publish canonical document inventory; reject unknown measured identities |
| Retrieval identity | Model/digest/collection returned; revision absent in actual dict | Include committed revision, vector/corpus fingerprint, dimension and effective config |
| Ask evidence | Response, prompt, chunks, guardrail actions and stage times | Include exact model request/options/schema and trace outcome/errors/status |
| Runtime metadata | Non-stub `_collection_metadata` sets committed_revision to None | Resolve actual collection metadata; no placeholder identity in measured runs |
| Filters | Adapter/trace records a fixed superseded filter | Record actual production filters, including historical overrides |
| Fallback detection | NotImplemented retrieval becomes stub; ask omits full error/status | Explicit provenance/errors; reject substitutions and outages |
| Cache bypass | Ask accepts bypass_cache=True | Retain; add fresh embedding measurement path after reconciling completed embedder |
| Exact prompt | Separate build_exact_prompt called before provider.generate | Persist exact request actually sent, not an independently reconstructed approximation |
| Image/config identity | Absent | Expose immutable image/source identity and effective configuration for gates |

These block real-suite evidence, not independent offline metric development. Publish
an agreed mapping or minimal additive adapter changes. No external message was sent automatically.

## Implemented M2 HTTP contract and release handoff (2026-11-26)

Fetched origin again: the M1 branch remains at the SHA above. M2 consumes these routes:

- `GET /internal/eval/identity`: `schema_version: "1.0"`, `identity` matching the runtime
  definition in `config/schemas/h0.schema.json`, and `provider` with actual name/model/version/parameters.
  Optional `seed_support` must report the provider's actual capability, not an assumed guarantee.
- `POST /internal/eval/retrieve`: question, top_k, seed, fresh_embedding. Preferred response
  is `{retrieval: RetrievalEvidence}`. Existing flat responses can be adapted only when
  collection, committed_revision, embed_digest and effective top_k match observed identity.
- `POST /internal/eval/ask`: question, bypass_cache, seed, fresh_embedding. Preferred response
  is `{query_evidence: QueryEvidence}` using the schema. Flat `{response, trace}` requires the
  complete actual trace and `model_request`, including exact provider messages/options.

Runtime identity binds collection, committed revision, immutable API image, effective config
JSON, corpus fingerprint, pipeline fingerprint, model/digest/dimension and provenance.
The top-k experiment additionally requires matching `vector_sha256` across baseline and
both candidate collections. M1 must generate this fingerprint from the actual immutable
chunk/vector snapshot. M2 must not guess it from corpus filenames or collection names.
Only config top_k may differ; the other effective settings must match.

M2 does not import M1 ingestion/indexer modules or write Chroma. API evaluation adapters must
reuse production logic, report pipeline errors/fallbacks and permit fresh embedding calls.
Generator answer caches are bypassed; repeated suites must generate actual answers again.
M1's default superseded filter must be explicit: historical questions need agreed historical
retrieval support or an expected abstention. The full A02 catalog contains six PDFs, including
the superseded scanned 2023 rules; the corpus inventory now records all six verified files.

The reviewed M1 release helper checks only PASS/legacy flat keys and therefore cannot yet
consume the stronger M2 decision safely. Before F3 use, M1 must require:

1. `decision == "pass"`, `release_authorized == true`, original `policy_mode == "release"`.
2. Exact baseline/candidate/policy/golden hashes, and fresh current candidate identity matching
   nested `candidate_identity` and its decision fingerprint.
3. Matching collection/revision/vector/model/config/image; apply the evaluated immutable image
   and settings to live with rolling maxUnavailable=0. A printed revision check is insufficient.
4. A failed gate leaves live PodTemplate/revision unchanged; record before/after snapshots.
5. Undo restores the known-good image/config/collection, then obtain a NEW query trace proving
   the previous collection and embedding identity. Existing historical traces are insufficient.

The ConfigMap demo always sets release_authorized=false even if thresholds permit a pass.
Do not add legacy flat decision fields merely to make the old release helper accept it.
Member 1 remains the owner of release.sh, API/trace changes and runtime manifests.

Evaluation resources live under `k8s/ragops-eval`; M1 integrates namespace/runtime first,
then the eval PVC/ServiceAccount/network policy. Wrappers apply `k8s/eval-job.yaml` literally
and use fixed Service names `api`/`api-candidate`. Confirm the actual candidate Pod labels,
host Ollama egress CIDR, results PVC fsGroup support and single-node RWO placement.
Do not reapply the entire kustomization during the ConfigMap demo: that would overwrite
the edited gate. Collect real evaluation Job CPU/memory alongside the M1 sampler and
justify the initially provisional requests/limits from those measurements.

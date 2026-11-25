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

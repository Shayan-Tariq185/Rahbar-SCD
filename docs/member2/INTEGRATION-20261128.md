# Integrated runtime verification — 28 November 2026

The user explicitly authorized integration fixes on a separate branch. Work is on
`feat/m2-integrated-evidence`, based on Member 1 commit
`ec3ba94700d1601924d85f7db178d8a1e3b65a3c`.
Neither the partner branch nor `dev` has been modified or merged by Codex.

## Verified corrections

- Preserve the native Ollama digest, require committed collection fingerprints,
  bind the immutable deployed image, and use the full pipeline SHA-256.
- Reuse the completed A02 cleaner and structure-aware chunker, with matching
  nomic document/query prefixes. Vector fingerprints include the actual vectors.
- Strict evaluation makes fresh retrieval calls, bypasses answer caches, captures
  the actual outgoing model payload, and rejects provider/schema fallbacks.
- Hosted generation encountered actual HTTP 429 responses at its 8,000 TPM limit.
  Bounded retries now respect the observed retry delay. No substitute provider
  is accepted as real evaluation evidence.
- Model request capture is isolated across concurrent API threads. Readiness
  reuses its Chroma client rather than repeatedly allocating one.
- Chroma's client rejects `hnsw:space` in metadata updates, including unchanged
  values. It is supplied at creation and omitted from audit-metadata updates.
- Model dimension is read from `/api/show`, without an embedding probe, so an
  unchanged run really makes zero embedding requests.
- The source handbooks contain text outside their physical page rectangles.
  Cropping to the actual page bounds removes hidden facing-page clauses and
  restores correct physical page/section metadata. All golden references were
  found in the corrected chunks before freezing golden v1.

## Actual operational observations

- Existing WSL cluster/profile: `minikube`; namespace: `rahbar`.
- Verified pod-accessible Ollama endpoint: `http://host.docker.internal:11434`,
  resolved to `192.168.65.254`. The old example host route did not work.
- The original A02 `rahbar` collection was preserved. A03 preparation uses
  separate collections. The historical-query path remains available for A02;
  strict A03 evaluation measures active sources with its declared filter.
- Both the initial 512Mi ingestion limit and Chroma's 512Mi limit produced
  observed OOMKilled events. Failure evidence is retained. Chroma and ingestion
  limits were raised to 1536Mi; CPU/working-set samples are being collected.
- Legacy scheduled reindexing was suspended during controlled experiments.
  The API HPA was temporarily held at three replicas. The new scheduled writer
  targets `rahbar_scheduled`, never the frozen experimental collections.
- Six original PDFs were staged only after matching their committed SHA-256s.
  The first successful recovery commit and a separate unchanged rerun both
  reported zero document-check and zero chunk embeddings. After detecting the
  visible-page issue, those are preparation evidence; the final visible-page
  baseline and its measurements must be recorded separately.

## Human work

Golden validation: 36 total, 31 answerable, five unanswerable, seven hard,
eight handwritten and eight actual synthetic reviews. Golden v1 is frozen.

Eight real answered queries were captured in Kubernetes for faithfulness review.
Shayan approved q01–q04 directly in chat. The user relayed Mahrukh's actual
approval of q05, q06, q07 and human-2-1. Their collective reasons are recorded
verbatim; no individual review reasons were invented. These labels judge support
from the exact saved context, not correctness of PDF extraction or page labels.
The packet predates the visible-page extraction correction and is retained with
its actual source identity. Calibration uses these fixed labelled answer/context
pairs; final suite generation is performed again against the corrected snapshot.

## Status

The combined application/indexer/RAGOps checks passed with 122 passed and one
OCR-dependent skip before the latest focused regression additions. Lint passed.
The integrated runtime plus evaluation Job rendered as 40 valid Kubernetes
resources with no invalid, skipped or error results.

Full baseline/drift/candidate suites, controlled release/undo, final coverage and
the completed report remain pending actual measured runs. Preparation/calibration
artifacts are not release authorization. Final scores must come from exported
Kubernetes results, never from offline fixtures.

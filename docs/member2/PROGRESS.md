# Member 2 progress

Updated 2026-11-26 (Asia/Karachi).

## Current status

Independent M2 implementation is ready for review after offline validation. Real A03 experiments, final report and submission are NOT complete. The user authorized implementation, command execution and feature pushes; the user performs merges. PR #30 (contracts) was merged into dev at 1a3e6db. Current completion branch: feat/m2-ragops-completion. No partner branch was merged.

## Implemented owned work

- B: strict golden/source provenance validation, three-level real HTTP evaluator, seeded typo noise, at least two whole-suite repeats, all metric deltas, query/trace evidence, embedding module measurements, pinned Ollama faithfulness judge and actual human-label calibration.
- C: fail-closed gate with fixed inputs, original baseline-bound policy, two-percentage-point recall drop math, quality/latency checks, matching vector snapshot and effective top-k-only comparisons. Fixture/preliminary/error/cache/stale/demo decisions cannot authorize release.
- E: nearest-golden cosine coverage, separate cutoff and aggregate floor, real calibration/policy freeze, uncovered topic groups, fixed-golden drift comparison and subsequent six-question expansion draft helper.
- F2: non-root evaluation image, dedicated results PVC/ServiceAccount/network policies, literal eval-job.yaml, coverage Job, complete/failed wait, persisted exit 0/1/2 and export after failure. ConfigMap read at process start; demo wrapper preserves the cluster edit and restores the original policy without rebuilding.
- G: editable report draft with Student 1/Student 2 placeholders and a human-work template. Native Word render inspection confirmed eight report pages and two human-template pages. They are templates, not measured final reports. Final output refuses missing evidence/editorial placeholders.
- CI: retains A02 checks and API coverage >=60%, adds owned helper lint/Bash syntax, eval resource schema validation and evaluation image build. New remote CI has not yet been observed for this completion branch.

## Actual validation

| Check | Observed result |
| --- | --- |
| M2 contracts/schemas/measurements/HTTP and Job boundaries plus A02 evaluator | 48 passed |
| M2 Ruff including owned Python helpers | Passed |
| Strict mypy | Passed, 13 source files |
| Preserved API tests and >=60% coverage gate | 27 passed, 80.61% coverage |
| Preserved indexer tests | 34 passed, 1 OCR-dependent skip |
| Evaluation kustomization with kubeconform v0.6.7, strict | 6 valid, 0 invalid/errors/skipped |
| Evaluation Job, coverage Job, exporter with kubeconform strict | 3 valid, 0 invalid/errors/skipped |
| All six A02 source PDFs | Downloaded and matched committed SHA-256; inventory records 274 physical pages |

Validation environment: Ubuntu-22.04, CPython 3.12.16 under /home/shayantariq/.cache/rahbar-m2-validation-20261125. Do not replace the broken copied .venv. Source text was cropped to visible PDF pages; scans still require OCR or visual inspection. Test fixtures remain under tests/temporary output and are never presented as real measurements.

## Human inputs and runtime blockers

The user supplied an initial eight questions and confirmed partner=1-4, self=5-8, then asked to leave questions pending while providing updated ones. The initial entries are preserved locally in eval/human_questions.pending.jsonl and are excluded from the active golden set. No review approvals were supplied or fabricated. Active golden has 28 unreviewed synthetic drafts; human minima deliberately block full validation/freezing.

Required next: eight final handwritten questions (four each), eight actual synthetic reviews (four each), then eight real answer/context faithfulness labels (four each) after preliminary runtime capture. Actual names/rolls can be filled into the editable report by the user.

Fetched origin/feat/m1-ragops again: still 3132046a1e79c64a208f47002af2341e4d2aa60a. M1 needs to reconcile its scaffold-era API/indexer changes with completed A02, supply current identity/vector fingerprints and exact model-request trace evidence, and harden the release helper to consume release_authorized and nested identities. See M1-ADAPTER-REVIEW.md. M2 does not modify partner-owned runtime/release files.

Docker client is installed; Docker Desktop's Linux daemon was unavailable during inventory. No cluster, A/B ingestion, real semantic evaluation, candidate release, rollback, coverage improvement or runtime resource measurement was performed. Bootstrap image names/resources are provisional and do not establish demo readiness. All measured outcomes remain pending the integrated real Kubernetes runtime and human inputs.

## Repository boundaries

Existing scripts/check_submission.py edit, root assignment PDFs/guides, output/, tmp/ and ignored corpus/raw are excluded from the M2 commit. Shared Makefile/CONTRACTS changes remain an unapplied integration patch for M1. A02 application/indexer code and existing YAML golden evaluator remain preserved. No merge is performed by Codex.
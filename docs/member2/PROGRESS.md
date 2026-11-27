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
- CI: retains A02 checks and API coverage >=60%, adds owned helper lint/Bash syntax, eval resource schema validation and evaluation image build. PR #31 is open as a draft into dev. Its first run passed lint, tests, manifests and all image builds; downstream scan/Kind checks were still running at this update.

## Actual validation

| Check | Observed result |
| --- | --- |
| M2 contracts/schemas/measurements/HTTP and Job boundaries plus A02 evaluator | 49 passed after final human-question integration and page-granularity regression test |
| M2 Ruff including owned Python helpers | Passed |
| Strict mypy | Passed, 13 source files |
| Preserved API tests and >=60% coverage gate | 27 passed, 80.61% coverage |
| Preserved indexer tests | 34 passed, 1 OCR-dependent skip |
| Evaluation kustomization with kubeconform v0.6.7, strict | 6 valid, 0 invalid/errors/skipped |
| Evaluation Job, coverage Job, exporter with kubeconform strict | 3 valid, 0 invalid/errors/skipped |
| All six A02 source PDFs | Downloaded and matched committed SHA-256; inventory records 274 physical pages |
| Full golden validator | Expected exit 2 observed: final human contributions remain missing |
| Shared integration patch | git apply --check passed after correcting trailing-blank-line context; patch not applied |

Validation environment: Ubuntu-22.04, CPython 3.12.16 under /home/shayantariq/.cache/rahbar-m2-validation-20261125. Do not replace the broken copied .venv. Source text was cropped to visible PDF pages; scans still require OCR or visual inspection. Test fixtures remain under tests/temporary output and are never presented as real measurements.

## Human inputs and runtime blockers

The user supplied eight final handwritten questions with source pages, confirming partner=1-4 and self=5-8. All eight source references were checked and the questions merged into the active golden set. It now contains 36 questions: 31 answerable, five unanswerable, seven hard and eight human questions. The earlier local pending draft is not an approved input. HUMAN-GROUNDTRUTH.md explains the two cross-page metadata cases and precise page-only scoring for the plagiarism question.

The user explicitly replied 'accepted all' to synthetic q01-q04 and their source summaries; four genuine user accept decisions are recorded without invented individual reasons. The partner's four synthetic reviews are pending (the user's 'Ok' acknowledged the request, not her decisions). SYNTHETIC-REVIEW.md supplies her q05-q08 packet. Then eight actual answer/context faithfulness labels (four each) are needed after preliminary runtime capture. Actual report names/rolls can be filled by the user.

Fetched origin/feat/m1-ragops again: still 3132046a1e79c64a208f47002af2341e4d2aa60a. M1 needs to reconcile its scaffold-era API/indexer changes with completed A02, supply current identity/vector fingerprints and exact model-request trace evidence, and harden the release helper to consume release_authorized and nested identities. See M1-ADAPTER-REVIEW.md. M2 does not modify partner-owned runtime/release files.

Docker client is installed; Docker Desktop's Linux daemon was unavailable during inventory. No cluster, A/B ingestion, real semantic evaluation, candidate release, rollback, coverage improvement or runtime resource measurement was performed. Bootstrap image names/resources are provisional and do not establish demo readiness. All measured outcomes remain pending the integrated real Kubernetes runtime and human inputs.

## Repository boundaries

Existing scripts/check_submission.py edit, root assignment PDFs/guides, output/, tmp/ and ignored corpus/raw are excluded from the M2 commit. Shared Makefile/CONTRACTS changes remain an unapplied integration patch for M1. A02 application/indexer code and existing YAML golden evaluator remain preserved. No merge is performed by Codex.

Implementation commit: 2d11060eae2c37ab45bf945abc4237cc6c81fba1 on feat/m2-ragops-completion. Draft PR: https://github.com/Shayan-Tariq185/Rahbar-SCD/pull/31. CI results are distinct from human acceptance and integrated runtime/demo readiness.

## Change

Add Member 2's Assignment 03 evaluator, gate, coverage workflow and evaluation Kubernetes Jobs while preserving the completed Assignment 02 API/indexer implementation. The suite measures module/retrieval/end-to-end behavior twice, records evidence and metric differences, and rejects fixture/error/cache/stale inputs for release. Gate policy is baseline-bound; the ConfigMap demo cannot authorize release.

Add provenance validators, human input/review/label tools, source checksum inventory, drift/coverage expansion helpers, persistent result export, editable report templates and the runtime handoff/runbook. CI retains the API coverage gate and existing checks, and adds evaluation image/manifest validation.

## Validation

- 48 M2 and existing evaluator tests passed; owned Ruff and strict mypy (13 files) passed.
- A02 API: 27 passed, 80.61% coverage. Indexer: 34 passed, one OCR-dependent skip.
- Kubeconform strict: six evaluation infrastructure resources and three Job/exporter resources valid, no errors/skips.
- All six corpus PDFs match committed hashes. Report templates rendered/inspected at eight and two pages.

## Integration checkpoint

Draft review: no real A03 baseline/candidate/coverage results or Kubernetes demo evidence yet. Golden handwritten questions are being revised; actual reviews and faithfulness labels remain required. M1 must reconcile its runtime branch with dev, implement the documented identity/trace additions and strengthen release.sh before release tests. Evaluation resource values/host routing remain provisional until measured.

The user merges PRs. Partner-owned runtime code, the shared Makefile/CONTRACTS patch, unrelated checker edit, raw sources and temporary renders are not included as implementation changes here.
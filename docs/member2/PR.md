## Problem and change

Assignment 03 evaluation needs explicit runtime identities, full retrieval/answer evidence
and trustworthy result provenance before Member 2 can develop independently of ingestion
and tracing. A02 currently has an aggregate evaluator and separate API/indexer contracts.

Add proposed JSON schemas and dependency-free typed API/embedding/judge interfaces with
isolated test doubles, checks rejecting fixture/error/cached query evidence, an A1-F5/G
audit and the H0 runtime handoff. Add M2 checks and existing A02 evaluator tests to CI
without removing app coverage >=60% or existing checks. Remove the legacy e2e exception
that accepted evaluator exit 2: all nonzero evaluation statuses now fail CI.
Run the same CI on feature PRs targeting dev, retaining the existing main/dev triggers.
Root Makefile/CONTRACTS changes
are supplied as an unapplied patch for Member 1. A02 application/indexer/manifests and
the YAML evaluator/golden set remain unchanged.

## Validation

- Executed offline: 12 contract tests passed; 4 existing evaluator tests passed.
- Executed offline: strict mypy passed on 3 ragops source files.
- Final combined offline pytest run: 16 passed. Python/JSON parsing passed; both supplied
  patch hunks match current source context/counts without applying them.
- After command delegation: Linux CPython 3.12.16 ran all 24 M2 schema/contract and
  evaluator tests successfully. A02 API: 27 passed, coverage 80.61%. Indexer: 34 passed,
  one OCR test skipped because system OCR tools are absent. Full Ruff passed.
- A separate Linux-cache environment installed all declared test dependencies.
  Final make test/lint and member test/lint targets all passed in that environment;
  mypy passed on 26 API, 11 indexer and 3 RAGOps source files. Docker/cluster state
  was inspected only; no deployment, measured RAG results or human labels were generated.

## Review checkpoint

H0 proposal awaits Member 1 review, especially identity/digest/page conventions, production
retrieval reuse, explicit fallback errors and cache bypass. The unmerged M1 adapter was
reviewed at a recorded SHA; M1-ADAPTER-REVIEW.md identifies interface gaps and overlapping
scaffold code needing reconciliation with finalized A02 before integration.
RUNBOOK.md contains reproducible commands. Draft review does not establish H0 acceptance
or Kubernetes/report readiness.

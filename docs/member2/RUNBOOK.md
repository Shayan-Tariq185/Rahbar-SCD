# Member 2 runbook

Updated 2026-11-26. Member 2 owns evaluation, gates, coverage, evaluation Jobs and report assembly. Preserve the Assignment 02 API/indexer implementation. Member 1 integrates ingestion, tracing, production adapters and releases. Feature PRs target dev; the user performs merges.

## Current checkpoint

The independent evaluator, gate, coverage checker, Job wrappers and editable report templates exist. Offline validation is recorded in PROGRESS.md. No real Assignment 03 baseline, release decision, coverage improvement or Kubernetes screenshot is claimed. Eight final human questions and the user's four synthetic acceptances are recorded; the partner's four synthetic reviews are pending. Files ending in `.pending.jsonl` are not approved inputs.

## Terminals and directories

PowerShell repository directory:

```powershell
Set-Location 'C:\Users\PC\Desktop\5th Semester\Software Construction and Development\Assignment-2'
wsl -d Ubuntu-22.04
```

All following Bash commands use Ubuntu-22.04 and this directory:

```bash
cd '/mnt/c/Users/PC/Desktop/5th Semester/Software Construction and Development/Assignment-2'
export RAGOPS_PY=/home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python
```

This existing CPython 3.12 environment is separate from the copied, broken `.venv`. For a new checkout create your own Python 3.12 environment, install `eval/requirements.txt` plus `eval/requirements-dev.txt`, and set RAGOPS_PY accordingly. A02 tests also require their API/indexer requirement files.

## Source documents and human work

The complete A02 source catalog is `corpus/sources.yaml`; immutable expected hashes are in `corpus/MANIFEST.md`. PDFs are downloaded under ignored `corpus/raw`. Fixture Markdown under `eval/fixtures` is test data, not authoritative source evidence. The 2023 academic rules and entrepreneurship policy are scans; text extraction without OCR is insufficient evidence for them.

```bash
"$RAGOPS_PY" scripts/eval_prepare_sources.py --all
"$RAGOPS_PY" scripts/validate_golden.py --golden eval/golden.jsonl --live eval/live_queries.jsonl --pairs eval/embedding_pairs.jsonl --draft
```

The eight final questions in `eval/human_questions.jsonl` have already been merged; do not run eval_merge_human.py again on those entries. The user's q01-q04 acceptances are recorded from chat. The remaining reviewer is the partner: she should inspect q05-q08 in SYNTHETIC-REVIEW.md and provide her actual decisions. In the interactive command below she must skip q01-q04 (already covered by the user), then review q05-q08. No agent should enter decisions for her.

```bash
"$RAGOPS_PY" scripts/review_synthetic.py --golden eval/golden.jsonl --reviewer 'Mahrukh Masroor' --limit 4
# Partner skips q01-q04 and personally reviews q05-q08; or relays her decisions in chat.
"$RAGOPS_PY" scripts/validate_golden.py --golden eval/golden.jsonl --live eval/live_queries.jsonl --pairs eval/embedding_pairs.jsonl
"$RAGOPS_PY" scripts/eval_freeze_golden.py --golden eval/golden.jsonl --out eval/golden.v1.jsonl
```

Final validation exits 2 while any required human contribution is missing. Never generate review decisions on either member's behalf. Confirm M1 doc_id/version/physical-page mapping against the inventory before freezing. Superseded 2023 documents require an explicit historical retrieval policy; downloading them does not make them available to a default superseded=false query.

## Offline checks

```bash
"$RAGOPS_PY" -m pytest -q tests/ragops/evaluation eval/test_run_eval.py
"$RAGOPS_PY" -m ruff check ragops tests/ragops/evaluation
"$RAGOPS_PY" -m mypy ragops
make test VENV=/home/shayantariq/.cache/rahbar-m2-validation-20261125
make lint VENV=/home/shayantariq/.cache/rahbar-m2-validation-20261125
```

CI also lints the owned Python helpers, checks Bash syntax, validates evaluation manifests and builds the evaluation image. These are offline/packaging checks, not real semantic-model experiment evidence.

## Integrated baseline and faithfulness labels

Prerequisite: M1 has reconciled with dev and implemented the adapter requirements in M1-ADAPTER-REVIEW.md. The live API must use a frozen Batch A collection, real model and generator, fresh evaluation embeddings, cache bypass and complete query traces. Do not ingest Batch B yet.

For initial answer collection, port-forward the live API in another WSL terminal and use the actual reachable Ollama URL. These commands become runnable only after the runtime prerequisites and golden validation pass:

```bash
kubectl port-forward -n rahbar svc/api 8000:8000
```

In the original WSL terminal, set OLLAMA_URL to the verified host endpoint. The preliminary result explicitly cannot authorize release:

```bash
"$RAGOPS_PY" -m ragops.evalsuite --target-api http://127.0.0.1:8000 --golden eval/golden.v1.jsonl --pairs eval/embedding_pairs.jsonl --embedding-url "$OLLAMA_URL" --collect-labels --out eval/results/label-collection
```

Use the exact `suite_json=` path printed above as LABEL_SUITE. Each member labels four distinct actual answer/context snapshots; this is separate from reviewing synthetic questions. In the same WSL terminal and repository directory:

```bash
"$RAGOPS_PY" scripts/eval_label_faithfulness.py --results "$LABEL_SUITE" --out eval/human_faithfulness.jsonl --reviewer 'Shayan-Tariq185' --limit 4
# Partner runs the same command herself with her actual reviewer identity.
```

The second reviewer must use the shared labels file, or combine actual label rows from separate files without duplicating evidence hashes. Final suites require at least eight distinct labels and four from each actual reviewer. Reuse the immutable calibration set and judge identity for comparisons.

## Image and Kubernetes evaluation Job

Commit evaluation image source first. In WSL, repository root:

```bash
TAG="$(git rev-parse --short=12 HEAD)-m2"
bash scripts/eval_build_image.sh --tag "$TAG"
bash scripts/eval_build_image.sh --tag "$TAG" --load --profile rahbar-a03
export RAGOPS_EVAL_IMAGE="rahbar-eval:$TAG"
```

The profile/context must match the actual M1 cluster; replace rahbar-a03 explicitly if the agreed cluster has another name. Never switch Windows/WSL kubeconfigs interchangeably. Baseline capture requires the actual human labels file:

```bash
bash scripts/eval_job.sh --target live --baseline-mode --golden eval/golden.v1.jsonl --labels eval/human_faithfulness.jsonl --image "$RAGOPS_EVAL_IMAGE" --out eval/results/baseline-a --context rahbar-a03
```

The wrapper applies literal `k8s/eval-job.yaml`, stages unique run inputs, snapshots the ConfigMap, runs the whole suite twice, persists `/results/runs/RUN_ID/job_exit.json`, waits for Complete OR Failed and exports artifacts even after gate failure. Exit 0 is success, 1 measured failure, 2 setup/runtime error. The exporter reads the same results PVC after the Job terminates; no data lake/vector-store writes are performed. Bootstrap manifests with `build-required` images are not runnable proof. Resource values and host egress CIDR are provisional until measured/verified.

## Drift, candidates and gate

Record each printed suite_json/decision_json path explicitly. Do not select an arbitrary newest file by glob. Set BASELINE_A, DRIFT_AB, CHANGE_BASELINE, BAD_SUITE and GOOD_SUITE to actual result paths before using them.

1. M1 creates a separate A+B collection through ingestion Jobs; keep A immutable. Run the same golden v1, seeds, judge, provider and pipeline configuration. Compare A versus A+B before expanding golden.
2. Choose one fixed experiment corpus and hold its chunk/vector snapshot constant. Both candidates get their own collections. Only effective top_k changes.
3. Freeze the original gate against the actual experiment baseline before inspecting candidate outcomes. It preserves quality floors and sets latency headroom from observed baseline p95.

```bash
"$RAGOPS_PY" scripts/diff_results.py "$BASELINE_A" "$DRIFT_AB" --kind drift --out eval/results/drift-comparison
"$RAGOPS_PY" scripts/eval_freeze_policy.py --baseline "$CHANGE_BASELINE" --config config/gate.yaml --out config/gate.release.yaml --rationale 'Explain the observed baseline and chosen quality/latency budget here'
```

Use eval_candidate.sh only for api-candidate; never mutate api to tune a candidate. Use its --help for exact --collection and --top-k arguments. Run a separate evaluation Job for each candidate, with `--baseline "$CHANGE_BASELINE" --gate config/gate.release.yaml --target candidate`. A deliberately low top-k is a hypothesis, not guaranteed measured failure. Report actual outcomes; do not retune thresholds to manufacture pass/fail.

For the ConfigMap demonstration, use the same image, data and candidate; run a NEW Job after each change:

```bash
bash scripts/gate_config_demo.sh --mode fail
# Repeat the same candidate Job with --use-cluster-gate (omit --gate).
bash scripts/gate_config_demo.sh --mode restore
# Repeat with --use-cluster-gate again; original policy restored exactly.
```

Demo decisions cannot authorize release. M1's release helper must require decision=pass AND release_authorized=true, validate all artifact hashes/current identities, and refuse demo or stale decisions. Its current branch needs those changes; do not use the old helper as a trusted gate. Capture live Deployment before/after rejecting a candidate and compare with check_no_rollout.py. M1 performs controlled rollout/undo, then obtains a NEW trace proving the previous collection and embedding identity.

## Coverage and golden v2

Pin the actual Ollama model digest in a provisional coverage config, then use `python -m ragops.coverage --calibration-only` to inspect real nearest-question scores. Freeze cutoff/floor with eval_freeze_coverage.py, referencing that calibration, an unchanged config and your rationale. Use the same live set and frozen policy for both measurements.

Run coverage_job.sh --help for exact inputs; supply golden v1, live_queries.jsonl, the frozen config, unique image, context and output directory. Below the floor exits 1 and fails the Job. After fixed-golden drift comparison and pre-expansion coverage exist, eval_expand_golden.py can draft six IT-gap questions into a NEW v2 draft only if that is the observed gap. Review the new questions, validate/freeze v2, then repeat coverage with identical live/config/model hashes. A coverage rise is measured evidence, not guaranteed by adding six rows. Coverage measures similarity to golden questions, not corpus answerability.

## Report and screenshots

`report/Assignment03_Report_Template.docx` is an editable eight-page draft; `report/Human_Work_Template.docx` is a two-page writing aid. Both were rendered in Word and visually checked. They contain no fabricated measurements. Populate report/inputs.json with explicit real artifact paths. Student 1/Student 2 placeholders are intentional at the user's request. The renderer refuses to call a document final while inputs or editorial placeholders remain. Final report must include actual identities, A/D/F partner findings, B/C/E tables, five trace-only diagnostic lines, six short answers, contributions, AI statement and a screenshot appendix; PDF body <=8 pages.

Screenshot commands below are for AFTER actual Jobs exist, in WSL at repository root. They do not produce missing experimental results:

```bash
kubectl get jobs,pods,pvc -n rahbar
kubectl describe job rahbar-eval -n rahbar
kubectl logs job/rahbar-eval -n rahbar
kubectl get configmap release-gate -n rahbar -o yaml
kubectl describe job rahbar-coverage -n rahbar
kubectl logs job/rahbar-coverage -n rahbar
kubectl get deploy api api-candidate -n rahbar -o wide
kubectl rollout history deployment/api -n rahbar
kubectl top pods -n rahbar
```

Capture the failing Job before the wrapper replaces it for the next run. Also capture printed actual summary/decision JSON paths, coverage before/after, M1 verification/quarantine/delta evidence, trace reconstruction, guardrail event and post-undo trace. Job logs and manifests alone do not establish those outcomes. No screenshot command is claimed executed merely because it appears here.

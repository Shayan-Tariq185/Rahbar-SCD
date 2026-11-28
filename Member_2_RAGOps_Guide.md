# Assignment 03 — RAGOps: Member 2 — Evaluation, Gates, Coverage and Report

## How to use this file

This is a self-contained handoff for one member and their Codex session. Put both assignment PDFs and this guide in the existing RAHBAR repository. Open that repository in Antigravity/Codex. Paste the master prompt once, then paste ONE phase prompt at a time. Run the terminal commands yourself, paste the output back, and continue after the phase passes. The other member uses their own guide, clone, branch and account.

This guide plans the work; it does not claim that any proposed script, endpoint, manifest, result or Make target already exists. Phase 0 must inspect the real repository and implement the agreed interfaces. Commands marked **after phase implementation** become runnable only when that phase has created their targets. Existing paths and commands must be checked against the repository before use. You supplied [Shayan-Tariq185/Rahbar-SCD](https://github.com/Shayan-Tariq185/Rahbar-SCD). Repository reads were blocked in this session (web fetch disabled and direct-host lookup failed), so its contents and current branches remain unverified. The guide points Codex at that exact repository and requires a local audit first; it does not present the old AI prompt's description as verified code.

No deadline appears in the Assignment 03 PDF: check Classroom. Its 185 marks do not provide a per-part weighting, so the workload estimates below are planning judgments.

## Context and non-negotiable submission requirements

Assignment 02 built RAHBAR: a grounded RAG service with an indexing path (extract, clean, structure-aware chunk, embed, Chroma) separate from a query path (validate, semantic cache, retrieve, augment, generate, validate, cite or abstain). It required namespace `rahbar`, an API Deployment with 3 replicas and probes, a UI, persistent Chroma/Redis, an indexer Job and CronJob, an embedding pin, JSON logs, metrics, evaluation and CI/CD. Preserve the working A02 behavior and contracts. The old prompt describes FAST documents, Windows + WSL2, host Ollama embeddings, hosted generation, and dev/main branches; verify these in code.

Assignment 03 adds data operations, three-level evaluation, a measured release gate, traceability, usage coverage and controlled Kubernetes releases.

| Part | Exact required outcome |
|---|---|
| A1 | Before chunking, every document has pass/fail and reasons for quality, completeness, recency and uniqueness. Quality covers empty/garbled/failed extraction. Completeness includes source, title, date OR version, page count and truncation. Uniqueness includes exact hash and embedding near-duplicates. Failures are quarantined, not indexed. One verification report per run. |
| A2 | Unchanged corpus embeds ZERO chunks; changed document affects only its chunks; deleted document has zero chunks by doc id. Superseded versions are archived, excluded by metadata, and restorable. |
| Batch B | At least 10 documents: at least 2 exact duplicates, 1 near-duplicate, 1 truncated/corrupt, 1 missing metadata, 1 newer version of an existing document, 1 injected instruction; run both A and B. |
| B data | At least 25 golden questions: 15 answerable with document AND page ground truth, 5 unanswerable, 5 hard; at least 8 genuinely handwritten; every question human/synthetic; at least 8 synthetic questions manually reviewed. |
| B module | At least 15 paraphrase and 15 unrelated pairs; mean cosine for each and gap; embedding time/chunk; largest difference when embedding identical text twice. |
| B component | recall@3, recall@5, MRR, nDCG@5; noise through typos OR at least 3 irrelevant documents; before/after deltas. |
| B E2E | Faithfulness, unanswerable abstention correctness, citation validity, latency p50/p95. If an LLM judges faithfulness, at least 8 human answer labels plus agreement. Fix seeds; run WHOLE suite twice; report every metric difference and variation. One command, timestamped result and summary. |
| C1–C3 | ONE pipeline parameter change, baseline/candidate three-level comparison, justified configurable gate, a failing AND passing candidate, controlled rollout and rollback. |
| D1–D2 | Every query: JSON trace id/time/query/rewrite/model+version/collection/chunks+doc ids+versions+scores/filters/rerank order/prompt hash or prompt/model parameters/response/citations/guardrail actions/stage latencies/cache status. Tool reconstructs exact context AND prompt by trace id. |
| D3–D5 | Similarity distribution, abstention/cache rates, stage p95, injection count; time-window summary; logged guardrail action on Batch B injection; 5 report lines diagnosing one wrong/abstained answer using ONLY its trace. |
| E1–E4 | At least 40 simulated live queries, about 28 in domain plus at least 12 from an uncovered topic. Nearest-golden cosine coverage with justified similarity cutoff; uncovered topic groups. Suite before/after B explains data drift. Add at least 6 golden questions; show coverage rise. Below coverage floor => nonzero exit. |
| F1–F2 | Kubernetes API Deployment and Service; persistent vector store and data lake including quarantine/archive. Ingestion Job is the vector-store writer; scheduled CronJob. Evaluation Job at `k8s/eval-job.yaml` writes results to a volume and FAILS if gate fails. Gate is a ConfigMap; edit it and flip outcome without image rebuild. |
| F3–F5 | Candidate Deployment+Service+own collection; evaluate it, release only on pass, rolling maxUnavailable=0. Block a failed candidate. Undo a bad release; NEW trace shows previous collection and embedding version. Traces stdout+volume; metrics port-forward. Resource requests/limits based on measured API/vector-store/Jobs usage. |
| G | PDF body <=8 pages, screenshot appendix excluded. Both names/roll numbers; Figure 3 stage mapping; Table 2 five qualities/measure/threshold/evidence; A–F results/release decision; six short answers; contribution table; 2–3-line AI statement. |

Submit repository URL plus report PDF with screenshot appendix. Commit real results under `eval/results/`, real trace samples under `traces/`, manifests under `k8s/`. Root README must give exact commands for A–F. Both members must make genuine commits, attend the demo and explain every part. Demo runs on Kubernetes: Docker-only gives zero for the demo. Live tasks include evaluation as a Job, opening a trace, and ingesting instructor-provided unseen documents.

## Fair division and independent development

| Workstream | Member 1: data lifecycle and runtime | Member 2: evaluation and release assurance |
|---|---|---|
| Main implementation | A1/A2, Batch B generation, D1–D5 | B, C1/C2, E1–E4 |
| Kubernetes | F1; ingestion/admin Jobs/CronJob, data/traces PVCs; API/candidate Deployment integration; F3 rollout helper | F2 evaluation Job and results PVC; gate ConfigMap; F3 candidate evaluation; evaluation/coverage images and permissions |
| Measurement | API/vector store/ingestion resources; trace and guardrail evidence | Evaluation resources; suite, gate and coverage evidence |
| Documentation | A/D/F runtime sections; stage mapping and object responsibility | B/C/E/F evaluation sections; result tables, report assembly |
| Human tasks EACH | 4 handwritten golden questions, 4 synthetic reviews, 4 human faithfulness labels if using LLM judge; own screenshots/commits and report reasoning | Same |
| Integration duties EACH | Read partner PRs, rehearse partner's features, troubleshoot owned components | Same |

Estimated effort per person: about 24–32 focused hours including review, measurements and demo practice. This is an estimate, not an assignment fact. Member 1 has deeper state/API/Kubernetes work; Member 2 has more evaluation, statistical and experiment/report work. Rebalance an optional documentation task if actual hours differ substantially. Neither member becomes the other's permanent integration/debugging service.

**Independent means parallel coding and unit testing, not zero integration.** Both can begin immediately after the small contract checkpoint. Member 1 uses a fake verifier/store and recorded suite/gate fixtures ONLY in tests. Member 2 uses fake HTTP responses/traces and a self-made fixture corpus ONLY in tests. Real results need the integrated real Kubernetes pipeline.

| Checkpoint | Member 1 publishes | Member 2 publishes | Next work unlocked |
|---|---|---|---|
| H0: contract, first work session | API response/retrieval/trace schema draft; writer/state/run interface | golden/result/gate schema draft; eval CLI and Job requirements | Both code independently |
| H1: first runnable slices | ingest+verification CLI, trace read path, valid small Batch B | golden validator, suite against fake API, gate against test results | Wire real HTTP and data |
| H2: frozen baseline | immutable Batch A collection and trace-capable API | frozen golden v1, full real suite twice, baseline manifest | Data-drift experiment before changing test set |
| H3: drift then coverage | add Batch B to separate drift collection, verification/delta inventory | suite on A+B using SAME golden v1, then coverage before/after golden v2 | C comparisons with fixed corpus/test set |
| H4: candidate integration | candidate collection and Deployment, safe rollout/undo | failed/passed gate Jobs and decision artifacts | Release demo and final report |

### File ownership (both guides use this agreement)

Member 1 owns `ragops/ingest.py`, `ragops/state.py`, `ragops/verify.py`, `ragops/trace*.py`, API changes, indexer image, `scripts/ingest_*.sh`, `scripts/trace_*.py`, `scripts/make_batch_b.py`, `scripts/release.sh`, `scripts/query.sh`, `scripts/collect_runtime.sh`, `scripts/wait_job.sh`, `scripts/resource_sample.sh`, `mk/ragops-runtime.mk`, `tests/ragops/runtime/`, `docs/member1/`, `k8s/ragops-runtime/`, `k8s/tools/runtime-shell.yaml`.

Member 2 owns `ragops/evalsuite/`, `ragops/gate.py`, `ragops/coverage.py`, `scripts/eval_*.sh`, `scripts/coverage_*.sh`, `scripts/apply_gate.py`, `scripts/validate_golden.py`, `scripts/review_synthetic.py`, `scripts/diff_results.py`, `scripts/render_report.py`, `mk/ragops-eval.mk`, `tests/ragops/evaluation/`, `eval/Dockerfile`, `eval/golden*.jsonl`, `eval/live_queries.jsonl`, `eval/embedding_pairs.jsonl`, `config/`, `k8s/ragops-eval/`, `k8s/eval-job.yaml`, `k8s/coverage-job.yaml`, `docs/member2/`, `report/`.

Member 1 is the integrator for existing root Makefile, kustomize aggregation, API dependencies and `docs/CONTRACTS.md`; Member 2 supplies exact small patches. Member 2 is the integrator for root README, Python packaging/test settings and workflows; Member 1 supplies exact patches. Do not independently rewrite a shared file. Keep `ragops/__init__.py` minimal, no eager imports. New test/package subdirectories avoid collisions. Each owns their progress file `docs/memberN/PROGRESS.md`.

## H0 shared interface contract — implement, do not assume it exists

Agree these names at H0; if the repository requires different internals, preserve these user-facing wrappers or update BOTH guides/runbooks together.

| Interface | Agreement |
|---|---|
| Collections | `rahbar_a` = frozen Batch A baseline; `rahbar_ab` = A+B drift snapshot; `rahbar_cand_bad`, `rahbar_cand_good` = same chosen experiment corpus, different values of ONE parameter. Never mutate the frozen baseline. |
| Candidate change | Prefer top-k as the only experimental variable (baseline value from real config; deliberately low vs reasonable candidate values). Still build distinct collections containing identical chunk/vector snapshots through ingestion Jobs. Same model, corpus, prompt, chunking, judge and golden version. |
| Document identity | Stable `doc_id` for logical document, separate `doc_version`; `collection` scopes index state. Chunk ids include doc id, version and content hash. Record pipeline fingerprint (chunk/extractor/embed settings). Changing chunk settings forces reconsideration. |
| Verify interface | Input extracted document + real metadata + existing family versions; output each check {passed, reason}, final decision and version lineage. Missing required metadata fails; do not invent title/date to make a negative fixture pass. |
| Source deletion | Inbox is an append queue, not the authoritative inventory. Moving a file inbox->raw is NOT deletion. Use explicit tombstones by doc id/version or a complete authoritative snapshot. Missing partial uploads never delete active data. |
| Writer access | All writes (including restore, candidate build and metadata updates) use the ingestion image as one-off Jobs; a lock shared across manual, scheduled and admin Jobs serializes writes. CronJob Forbid alone is insufficient. APIs/evaluation are application-level read-only. |
| Evaluation retrieval | M1 provides an internal read-only evaluation adapter returning ranked chunk id/doc id/version/page/score/text and actual prompt/trace reference. Adapt existing routes first; otherwise a cluster-only evaluation route, disabled or protected on public Ingress. No evaluation writes or separate query logic. |
| Ask/trace | Existing ask route/body discovered at Phase 0; `scripts/query.sh` maps to it. Return X-Trace-ID or additive trace_id. Full prompt + exact evidence persisted in trace. M2 accesses by HTTP/internal adapter or trace volume; never needs to exec privileged mutations. |
| Cache | Cache namespace includes collection, index revision, embed identity and relevant query config (including top-k/prompt). Invalidate on successful ingestion; skip cache for evaluation measurements or record explicit cold/warm policy. |
| Results | `schema_version`, run_id/time, git SHA, corpus/collection revision, golden hash/version, model+digest, parameter config, seeds, provider/judge/cache policy, metrics by level, per-query evidence, errors, real/synthetic-fixture provenance. Timestamped JSON+MD under eval/results. |
| Gate | Metrics use fractions [0,1], latency in ms, recall drop 0.02 = TWO PERCENTAGE POINTS. Reject missing/NaN metrics, mismatched test/corpus/config except the declared change, failed pipeline calls and synthetic fixture results. JSON decision includes input hashes and collection/revision/config identity. |
| Gate demo | Job mounts full ConfigMap directory at /config (no subPath dependency), reads current file at process start. New Job per threshold change, same image/data. A permissive illustrative config change demonstrates mechanics; only the justified original policy authorizes release. |
| Volumes | /datalake for originals/quarantine/archive/state; /results for eval/verification reports; /traces for traces. Export real artifacts back into repository eval/results and traces. Non-root writable volume permissions and /tmp emptyDir required. |
| CLI | `python -m ragops.ingest run|status|count|restore`; `python -m ragops.evalsuite`; `python scripts/apply_gate.py`; `python -m ragops.coverage`; `python scripts/trace_show.py`; every CLI has --help. |
| Exit codes | 0 success/pass, 1 measured gate/coverage failure, 2 invalid input/runtime/setup error; preserve distinction in logs. Evaluation Job still fails for either 1 or 2. |

### Correctness traps to fix from the old AI prompt

- “Delete all doc chunks” after upserting new chunks can delete the new ones. Compute old-id minus new-id, upsert missing vectors, then delete only stale ids. Keep unchanged chunk vectors. State is keyed by collection + document + version.
- A02 readers must not see a partially updated release as if it were atomic. Record pending/committed revision, serialize writers and make retry recovery idempotent. Use immutable candidate collections for release comparisons; document the consistency limits of in-place ingestion.
- A recency-rejected older valid version belongs in archive with superseded metadata; quality/completeness/duplicate rejects go to quarantine. Record the reason for this distinction. Restore reactivates archived content through the writer Job and preserves audit history.
- Compare hashes/fingerprints BEFORE any embedding, including document near-duplicate embeddings, so an unchanged run can truthfully show zero embedding calls. Record chunk and document-check embedding counts separately.
- Detect version families before rejecting near-duplicates: a legitimate newer policy may look almost identical to its predecessor. Prefer a stable source/family id over title heuristics; document ambiguous cases.
- Corrupt documents are per-document verification failures. Chroma/Ollama/storage failures are infrastructure failures and must fail the Job; do not quarantine every valid document during an outage.
- Truncation detection is heuristic; a document ending without punctuation is not automatically corrupt. Record what can and cannot be detected. Keep at least one plausible valid injected Batch B document indexable so D4 exercises the query guardrail.
- Ollama model digest is available through GET /api/tags. Do not assume /api/show contains a digest. Record resolved model tag/digest, dimension and any documented fallback; readiness checks identity against collection metadata.
- Plain NetworkPolicy does not distinguish Chroma read from write HTTP methods. Code and store credentials/authorization where available enforce read-only access; NetworkPolicy limits reachability.
- A hash alone cannot reconstruct a prompt. Save full prompt and exact context (or immutable content-addressed snapshots). Cache hits reference the original trace and preserve its prompt; early abstentions record generate=skipped with reason.
- Per-pod trace files on ReadWriteOnce work on one-node minikube; RWO means one NODE, not one pod. For multiple API workers use process-safe append or per-process files. Multi-node needs RWX or log collection.
- Fixed seeds and temperature 0 reduce variation; they do not guarantee determinism. Re-run real generation; do not use answer caching to manufacture identical suite runs.
- Golden hard questions may also be answerable. Use `answerable: bool` and `hard: bool`, rather than ambiguous exclusive classes; validator enforces 15/5/5 independently.
- Baseline evaluation comes BEFORE Batch B. Coverage expansion comes AFTER the fixed-golden A vs A+B drift comparison. Save golden v1 and v2 separately and their hashes.
- Docker images are build artifacts for Kubernetes. Use pinned bases and unique source tags; local-only demonstrations do not satisfy the assignment.

## Terminal conventions and setup (both members)

**PowerShell** is used only where explicitly labelled. All other command blocks are **Ubuntu/WSL Bash**, in the repository root. Never paste Bash `export`, heredocs or `$(...)` into PowerShell. Do not run Windows minikube and WSL minikube interchangeably: pick WSL minikube, kubeconfig and Docker context for the whole project.

**PowerShell: inventory; installation only if missing**
```powershell
wsl --status
wsl --list --verbose
# Only if Ubuntu is not already installed; installation may require restart:
wsl --install -d Ubuntu-22.04
# Use the actual installed distribution name shown above:
wsl -d Ubuntu-22.04
```

Start Docker Desktop manually; enable its WSL2 engine and integration for your Ubuntu distro. Open your existing repository in WSL through Antigravity. Do not re-clone over current work. For a genuinely new clone:
```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/Shayan-Tariq185/Rahbar-SCD.git rahbar-scd
cd rahbar-scd
```

**WSL: inspect tools before changing installations**
```bash
pwd
git status --short --branch
git remote -v
git --version
docker version
docker context show
kubectl version --client
minikube version
python3 --version
make --version
command -v uv
command -v gh
command -v jq
```

Use the real A02 README to install missing tools. Official references: [Docker WSL integration](https://docs.docker.com/desktop/features/wsl/), [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install), [minikube start](https://minikube.sigs.k8s.io/docs/start/), [kubectl installation](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/). Codex must give version-appropriate installation commands for the tools actually missing, not reinstall a working environment. Python 3.12/uv in the old prompt is a hypothesis; use the repo's supported version and locked dependencies. Existing A02 install command may be:
```bash
# Run ONLY after Phase 0 confirms these targets/tool versions:
make install PY="$(uv python find 3.12)"
```

**WSL: fresh LOCAL project profile (not a delete/reset command)**
```bash
minikube start -p rahbar-a03 --driver=docker --cni=calico --memory=6144 --cpus=4
minikube -p rahbar-a03 addons enable metrics-server
minikube -p rahbar-a03 addons enable ingress
kubectl config use-context rahbar-a03
kubectl config current-context
kubectl get nodes
kubectl create namespace rahbar --dry-run=client -o yaml | kubectl apply -f -
```

6 GiB/4 CPU is a starting cluster allocation from A02, not a measured workload request. Adjust to your laptop's available RAM. If reusing the working A02 cluster, select its actual context instead of creating another. Confirm Calico enforces policy; do not assume flags retrofit an existing cluster. Port-forward is sufficient for API/metrics evidence; a tunnel is only needed for the existing Ingress access method.

**PowerShell, only if Ollama is running on Windows**
Quit the existing Ollama tray/server first to avoid an address-in-use error. In a dedicated terminal:
```powershell
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

In another **PowerShell** terminal:
```powershell
ollama pull nomic-embed-text
Invoke-RestMethod http://localhost:11434/api/tags
```

Use the actual A02 embedding model if different; do not silently switch it. Limit firewall access to the local environment needed by WSL/minikube. From WSL and an allowed cluster pod, test the real Ollama URL before changing configuration. `host.minikube.internal:11434` depends on the driver/network; it is not proof of Windows-host reachability. Record the resolved address and scoped NetworkPolicy allowance.

**WSL: secret input without command-history key**
```bash
set +x
read -r -s -p "Hosted provider API key (leave empty for local provider): " LLM_API_KEY
printf '\n'
if [ -n "$LLM_API_KEY" ]; then
  SECRET_TMP="$(mktemp)"
  chmod 600 "$SECRET_TMP"
  printf 'LLM_API_KEY=%s\n' "$LLM_API_KEY" > "$SECRET_TMP"
  kubectl -n rahbar create secret generic rahbar-secret --from-env-file="$SECRET_TMP" --dry-run=client -o yaml | kubectl apply -f -
  rm -f -- "$SECRET_TMP"
fi
unset LLM_API_KEY
```

Phase 0 must confirm actual Secret/key names, including a separate judge key if needed. Do not screen-capture secrets or use `kubectl get secret -o yaml`. Keep real keys out of files, command history, logs and Git.

## Git workflow — YOU run these commands

Use your own name/email/account on your own clone. These are real tool commands, not new project helpers.
```bash
git config --local user.name "YOUR REAL NAME"
git config --local user.email "YOUR VERIFIED GITHUB EMAIL"
gh auth status
# If needed, sign in interactively:
gh auth login
git fetch origin
git status --short --branch
git switch dev
git pull --ff-only origin dev
git switch -c BRANCH_FOR_CURRENT_PHASE
```

If there is no dev branch, stop and inspect the existing branch policy with Codex; do not create a parallel history or push to main. Never discard a dirty working tree. Use one feature branch per independently reviewed phase. Replace the literal branch placeholder with that phase's suggested branch.

At the end of a phase:
```bash
git status --short
git diff --check
git diff --stat
git diff
# Stage ONLY reviewed owned files, listing actual paths:
git add PATH_ONE PATH_TWO
git diff --cached
git commit -m "DESCRIPTIVE PHASE COMMIT"
git push -u origin "$(git branch --show-current)"
gh pr create --base dev --head "$(git branch --show-current)" --title "DESCRIPTIVE PR TITLE" --body-file docs/member2/PR.md
```

Codex must write that member's PR.md before this command. Partner reviews the actual diff. Merge in GitHub only after checks and review. Update your local dev after merge, then branch for the next phase. If both began on the same dev snapshot, merge latest `origin/dev` into the feature branch and resolve with the file owner; do not force-push or rewrite history. Final dev->main uses the existing protected PR/CI policy. Evidence screenshots/results need genuine commits too. Never commit large third-party corpus PDFs: retain URLs/checksums and fetchers; commit only permitted small self-made fixtures/Batch B files.

## Common runtime command contract — required wrappers

Both Codex sessions must implement their owned wrappers, with --help, validation, visible commands, timeout/failure handling and no hidden Git actions. These are proposed commands, **not existing scripts**:

| Wrapper | Owner | Behavior |
|---|---|---|
| bash scripts/ingest_job.sh --collection NAME [--batch-dir DIR] [--snapshot-from NAME] [--mode ingest\|count\|restore\|tombstone\|status] [--doc-id ID] [--version V] | M1 | Copy documents/metadata safely, create unique Job from explicit template, take shared writer lock, run selected ingestion CLI, wait terminal state, print logs and write last-ingest.name. --snapshot-from copies identical records/vectors through the writer path for C; never rewrites source. |
| bash scripts/wait_job.sh JOB | M1 | Poll boundedly for Complete OR Failed; fail promptly on Failed, describe pending/timeouts; never wait only for Complete on a deliberately failed Job. Preserve process exit status. |
| bash scripts/query.sh --target live\|candidate --question TEXT --out DIR | M1 | Use discovered API route/payload; save headers, response, trace id and exact trace evidence. No invented /ask contract. |
| bash scripts/collect_runtime.sh --out DIR | M1 | Export real verification reports, JSONL traces and resource data from volumes/logs to repository. Deduplicate records by trace id; never truncate/overwrite prior evidence. |
| bash scripts/resource_sample.sh --label TEXT --seconds 60 --out FILE | M1 | Timestamp kubectl top samples while workload runs; retries metrics warmup; record sampling limits. |
| bash scripts/eval_job.sh --target live\|candidate --out DIR --baseline FILE --gate FILE [--repeat 2] | M2 | Render k8s/eval-job.yaml with actual API Service port, immutable image ref, current config and baseline, create fresh Job, record run manifest/job name, wait both statuses, export JSON/MD from PVC. Return gate/runtime status. |
| bash scripts/coverage_job.sh --golden FILE --live FILE --config FILE --out DIR | M2 | Run coverage on real embeddings; export files even if measured coverage exits 1. |
| bash scripts/release.sh --deployment api --candidate NAME --decision FILE | M1 | Require measured PASS matching candidate revision, model/config, corpus/golden and image; recheck collection hasn't changed; set full release env together; watch rollout; log before/after and retain rollback revision. Refuse failure/stale/mismatched decisions. |

Do not use `|| true` around gates and then declare success. For an intentionally failing demonstration, capture exit status explicitly, inspect it, save the result and continue deliberately. Wrappers must print the kubectl command they execute; screenshots can then show both wrapper invocation and real cluster operation.

## Master prompt — paste first (Member 2)

```text
Act as a senior software construction mentor specializing in Kubernetes, Docker and RAGOps. I am Member 2 of a two-student group. Assignment 02 RAHBAR is completed; Assignment 03 extends it. Read both PDFs and this member guide completely. The A03 PDF is the authority; preserve working A02 behavior. The previous AI master prompt is context, not evidence of the actual implementation.

Read README, STARTER.md if present, docs/CONTRACTS.md, architecture/pipeline/ADRs, Makefile, dependency locks, api/, indexer/, eval/, k8s/ and CI workflows. Inspect git status/remotes/branches without modifying them. Correct assumptions about paths, endpoints, model/provider, image names and existing capabilities from the code.

I run ALL Git, installation, Docker, minikube, kubectl, WSL, hosted/model API calls and screenshot commands myself. You may inspect/edit owned local files and run offline lint/unit tests if available; tell me exactly what you actually ran. Do NOT install, create/switch branches, commit, push, deploy, invoke live services or take screenshots yourself. For any such action give me an exact copy-paste command with shell, directory, terminal number, expected output SHAPE and failure diagnosis. Never claim success from an unexecuted command.

Follow the ownership table. Work only on my current phase; don't implement my partner's modules. Develop against shared schemas/fakes if their code is missing. Ask the owner for an interface patch, not a wholesale shared-file rewrite. Only H0/shared integration may modify shared files under the designated integrator.

Never fabricate metrics, screenshots, manual questions/reviews/labels or evidence. Real report numbers require our pipeline runs and committed result files. Synthetic fixture results belong under tests/, flagged test-only and rejected by release gating. Human question slots stay empty until we fill them. Every provided draft question is synthetic, not handwritten. Labeling tools record human identity and actual decision.

Use Kubernetes for all final runtime evidence. Ingestion Jobs alone mutate Chroma, serialized across manual/Cron/admin/candidate Jobs. API and eval read only. Keep A02 embedding pin, schemas, citations/abstention, security, metrics and CI. Add fields compatibly. No secrets in output or Git. Pin images and source tags; provide provisional labeled resource requests for bootstrapping, then replace/justify from measurements. Requests/limits required everywhere.

For every phase: explain changes in plain language, list files and requirement IDs, run meaningful offline checks where available, give my manual commands and screenshots with visible command+output, list unresolved human inputs and blockers, update only my progress file, write my PR.md, supply commit/PR commands, then STOP. Wait for my real outputs before claiming acceptance or starting the next phase. An unavailable local runtime is a blocker to verification, not permission to fake success.

First reply: no edits. Give a concise true architecture summary, full A1–F5/G gap table citing actual paths, my owned-file plan, H0 contract conflicts, real prerequisite commands, and next phase. No open-ended redesign.
```


## Member 2 phased work — paste one prompt at a time

Your role: evaluation + release assurance + coverage + report assembly. Your partner owns ingestion/verification/traces and runtime rollout integration. Do not write a second ingestion pipeline or take over their API files.

### M2.0 — Local audit, shared schemas and independent test harness

Suggested branch: `feat/m2-evaluation-contracts`.

```text
PHASE M2.0. Inspect both assignments and the actual existing repo. Write docs/member2/GAP.md with A1–F5/G requirements and ownership, docs/member2/PROGRESS.md and PR.md. Correct old-prompt assumptions from code. Coordinate H0 with M1: propose JSON schemas for golden questions, suite results, gate decisions, coverage reports and the read-only ranked-retrieval/trace adapter. Send M1 a small patch for docs/CONTRACTS.md rather than editing that shared file independently.

Design an ApiClient/EmbeddingClient/Judge interface, with fake clients under tests/ragops/evaluation only. The same suite uses real adapters later. Keep fake result provenance unmistakable and in tests, never eval/results report evidence. Reuse existing A02 fixtures and helpers where useful. New package ragops/evalsuite and mk/ragops-eval.mk must import without M1's modules installed. Avoid eager package imports. Give M1 a Makefile include patch.

Discover actual Python install/test commands and CI structure. As packaging/workflow integrator, keep app coverage >=60% as A02 required; add meaningful new-code tests without weakening existing checks. Give version-compatible commands for missing tools, not a blind install. Establish existing A02 tests/lint as baseline and report actual execution vs commands I must run.

Plan eval image paths, actual Service ports and result PVC permissions, gate ConfigMap mounting and network requirements for M1. Do not require direct Chroma writes or access to SQLite state. STOP.
```

H0 acceptance: both agree schemas and client interfaces; M2 can test metrics/gates with fakes while M1 builds runtime.

### M2.1 — Golden set, real human work and simulated live usage

Suggested branch: `feat/m2-golden-live-sets`.

```text
PHASE M2.1. Convert or extend A02 golden.yaml into eval/golden.jsonl, reading the actual corpus and preserving valid existing questions. Use explicit id, question, origin human|synthetic, answerable bool, hard bool, expected_behavior answer|abstain, relevant passages (doc_id, version if relevant, page and section or chunk id), reviewer identity/date for synthetic review, batch applicability, notes. Allow multiple relevant passages for multi-chunk questions and don't confuse source path with stable doc id. Ground-truth page means actual PDF page convention, documented, not an invented page.

Target >=25 total (for example 20 answerable +5 unanswerable, with >=5 of the answerable also hard); enforce minimum 15 answerable/5 unanswerable/5 hard independently. At least 8 genuinely handwritten questions: four empty human slots for each member. Draft synthetic questions only from actual documents; origin=synthetic and unreviewed until a human checks wording, answerability, source and page. Preserve provenance for reused A02 human questions ONLY if the group confirms it.

Create human template JSONL with empty question/ground-truth fields, and review_synthetic.py to show the source evidence and record actual review decisions/reviewer. Each member manually reviews >=4 synthetic questions. Don't set reviewed=true from an agent's inspection. Validator fails until >=8 real human questions and >=8 manual synthetic reviews exist; also checks required fields, duplicate ids, doc/page existence and valid classifications.

Create >=40 simulated live queries (~28 in-domain, >=12 from an uncovered topic). Label as simulated, distinguish drafts, avoid asserting these are actual collected users. The group edits them to natural user phrasing. For uncovered-corpus topics expected behavior is abstain, not a made-up answer.

Create embedding_pairs.jsonl with >=15 paraphrase and >=15 unrelated pairs, domain-grounded and correctly labelled. Produce lists of remaining human tasks and exact fill/review/validate commands. Don't advance past missing human inputs for the final measured evaluation. STOP.
```

**After implementation — both members do their human share**
```bash
python scripts/validate_golden.py --help
python scripts/review_synthetic.py --help
# Open the real template in Antigravity and write four questions yourself.
# Codex must provide a merge command that validates slots before inserting them.
python scripts/review_synthetic.py --golden eval/golden.jsonl --reviewer "YOUR REAL NAME" --limit 4
python scripts/validate_golden.py --golden eval/golden.jsonl --live eval/live_queries.jsonl
```

An initial validator failure due to empty human slots is expected pending work, not a completed B golden set. Merge each person's actual entries through reviewed commits. Freeze `eval/golden.v1.jsonl` and record its hash before H2 experiments. Preserve A02 `golden.yaml` if CI still uses it; do not silently replace the old CI contract.

### M2.2 — Complete three-level evaluation and noise/stochasticity

Suggested branch: `feat/m2-three-level-suite`.

```text
PHASE M2.2. Implement python -m ragops.evalsuite --target-api URL --golden FILE --pairs FILE --out DIR --repeat 2 with --help and real/fake adapter separation. One command runs all B metrics and writes uniquely timestamped JSON and Markdown summaries plus per-query evidence and provenance. Suite must fail on invalid input or exhausted provider/runtime errors instead of turning outages into low scores or abstention success.

Module: >=15 paraphrase and >=15 unrelated cosine means/gap; embedding wall time/chunk, same-text-twice max absolute coordinate difference. Exclude cache from determinism measurement; record model/digest/dimension, retries, timing units. Same embedding path/model as the deployed pipeline.

Component: macro recall@3/@5, MRR, nDCG@5 from actual ranked retrieval and golden relevant evidence. Define units/deduplication: compare unique canonical relevant passages (doc_id/version/page/section where available); multiple retrieved chunks from the same relevant page cannot inflate recall above 1. Document binary or graded relevance, nDCG ideal ranking/denominator and no-relevant cases. Exclude true unanswerables from retrieval recall average; still report hard cases and version-sensitive questions separately. Use M1's production read-only adapter, not a reimplementation of retrieval. Similarity/distance conversion is explicit.

Noise: choose deterministic seeded query typos (assignment OR alternative is >=3 irrelevant docs; don't require both). Keep unperturbed ground truth, measure all four retrieval metrics before/after and deltas. Ensure the typo generator actually changes eligible queries; record perturbations and any unchanged inputs.

E2E: faithfulness against exact retrieved context, abstention correctness over unanswerables, citation validity against retrieved ids/source/page, latency p50/p95 including cache policy. Do not count an unsupported abstention as a faithful answer; report denominator/NA. Judge optional: if LLM judge is used, strict structured output, temperature 0, bounded retries, explicit errors, rubric and judge identity, never trust document instructions in judge prompt. Cache judge results by answer+evidence+rubric+model/settings; record hits. Don't serve generated-answer cache during stochasticity measurement.

Generate CSV template referencing actual query ids/answers/context/trace ids for >=8 human faithfulness labels (4 each member) and compute judge/human agreement, sample size and confusion table. Never generate human judgments. If choosing fully human faithfulness instead, preserve labels/provenance and document method; do not substitute a citation-validity heuristic for faithfulness.

Repeat whole suite twice with fixed Python/numpy/provider seeds where supported, and report every metric difference, including noisy retrieval and generation; record remaining nondeterminism. Use consistent cold/warm cache and run order to make latency comparison meaningful. Store per-run identities and raw evidence.

Unit tests use hand-computable ranked lists, duplicate-page handling, no-relevant docs, malformed judge output, timeout/error propagation and seed repeatability; fake clients are test plumbing only. Package rahbar-eval with pinned base, non-root, read-only rootfs + writable /tmp/results and required dependencies. Implement make ragops-eval-image TAG=... and make ragops-eval-load PROFILE=... TAG=... with matching manifest image references. Update Make targets and CI image build without weakening A02 e2e/coverage/security gates. STOP.
```

**After implementation — offline then real**
```bash
# Use the real repository environment/test commands discovered at Phase 0:
python -m pytest tests/ragops/evaluation
python -m ragops.evalsuite --help
python scripts/validate_golden.py --golden eval/golden.v1.jsonl --live eval/live_queries.jsonl
```

M1 provides actual API readiness and the read-only adapter. Terminal 1:
```bash
kubectl port-forward svc/api -n rahbar 8000:8000
```

Replace remote Service port if different. Terminal 2:
```bash
python -m ragops.evalsuite --target-api http://127.0.0.1:8000 --golden eval/golden.v1.jsonl --pairs eval/embedding_pairs.jsonl --out eval/results/baseline-a --repeat 2
```

Local HTTP suite validates behavior, but also run it as a Kubernetes Job in M2.3. Confirm the real embedding endpoint is reachable from the caller and recorded in suite config. The wrapper must not assume WSL localhost and cluster localhost are the same service.

### M2.3 — Gate, evaluation Job, PVC and ConfigMap demonstration

Suggested branch: `feat/m2-kubernetes-eval-gate`.

```text
PHASE M2.3. Implement ragops/gate.py with scripts/apply_gate.py --baseline FILE --candidate FILE --config FILE --out DIR. Default example recall drop 0.02 means 2 percentage points, not 2%. Add justified faithfulness and p95 limits, abstention not below baseline, optional A02 citation floor. Record measured baseline and rationale before freezing policy. Fail closed on missing/NaN metrics, wrong units, pipeline errors, fixture provenance, mismatched golden/corpus/model/config except the ONE declared change, and stale collection revision. Emit per-metric table, JSON decision with input hashes, threshold hash, collection/model/config identity and exit 0 pass/1 measured fail/2 setup error.

Create k8s/eval-job.yaml exactly at that path; pinned rahbar-eval image, dedicated ServiceAccount, non-root/read-only rootfs, /tmp emptyDir, result PVC, provisional resources then measurements. Mount release-gate ConfigMap directory at /config, read /config/gate.yaml at run start. Stage golden/pairs/config/committed baseline with immutable hashes. Prefer portable packaged inputs or a clear init/copy path; don't depend on a local WSL path magically appearing in the pod. Write results before gate exits nonzero; backoffLimit 0 so deliberate gate failure is visible. Result collection must work even after the pod exits (helper pod with results PVC or supported exporter), not kubectl cp from a stopped container.

Implement scripts/eval_job.sh, eval_results.sh and coverage_job.sh contracts. eval_job.sh renders the final k8s/eval-job.yaml (fixed Job name rahbar-eval), records all inputs, checks no active Job with same name, archives old logs, deletes only completed/failed old Job, applies with kubectl apply -f k8s/eval-job.yaml, waits Complete OR Failed with timeout, exports JSON/MD even when failed and returns the actual gate/runtime status. Honor literal assignment command; don't rely on an unrendered template that kubectl cannot apply. Record last-eval.name under the caller --out directory.

The Job command runs the WHOLE Part B suite, then applies the policy to the same candidate result and committed baseline; failed suite cannot proceed to gate. M1 supplies wait_job.sh if available; keep an independent small fallback until integration. Gate ConfigMap source config/gate.yaml and manifest must remain synchronized through a generator or explicit verified render.

Add least-privilege eval->live/candidate API ingress/egress requests, embedding/judge/DNS access and results volume requirements as a patch for M1's network integrator. Evaluation NEVER writes Chroma. Measure eval pod via M1 resource sampler, save real output and justify resources.

Give commands for standalone gate unit tests, a successful actual cluster eval Job, and changing ConfigMap threshold to force a fail then restoring policy and passing with SAME image. Exclude demonstration-only permissive policy from valid release authorization. STOP.
```

**After implementation — baseline, gate and Job**
```bash
make ragops-eval-image TAG="$(git rev-parse --short=12 HEAD)-m2"
make ragops-eval-load PROFILE=rahbar-a03 TAG="$(git rev-parse --short=12 HEAD)-m2"
kubectl apply -k k8s/ragops-eval
# First capture baseline without applying a comparison gate; explicit baseline mode:
bash scripts/eval_job.sh --target live --out eval/results/baseline-a --baseline-mode --repeat 2
```

The `--baseline-mode` extension must be implemented and clearly marked “baseline capture, no release decision.” It still runs the whole suite on real data and rejects errors. Choose the actual valid result file for the committed baseline (never invent its path):
```bash
read -r -p "Real baseline suite JSON path: " BASELINE_A
test -f "$BASELINE_A"
sha256sum "$BASELINE_A" eval/golden.v1.jsonl
# This source path is then embedded/mounted for future Job comparisons by the wrapper:
bash scripts/eval_job.sh --target live --out eval/results/gate-baseline --baseline "$BASELINE_A" --gate config/gate.yaml --repeat 2
kubectl get job rahbar-eval -n rahbar
kubectl logs job/rahbar-eval -n rahbar
```

Baseline self-evaluation is a gate smoke test; it is not the “one changed passing candidate” required by C.

**ConfigMap mechanics, unchanged candidate/image**
```bash
kubectl get configmap release-gate -n rahbar -o yaml
# Back up existing ConfigMap content without storing unrelated Secrets:
kubectl get configmap release-gate -n rahbar -o json > eval/results/gate-configmap-before.json
```

Require Codex to implement `scripts/gate_config_demo.sh --mode fail|restore`. It saves the original `gate.yaml`, constructs a valid intentionally impossible threshold such as maximum p95 latency 0 ms (the schema must allow 0), updates ONLY the gate ConfigMap, never builds an image, and prints old/new threshold+image refs. On restore it uses the exact original saved policy, not newly chosen permissive numbers:
```bash
bash scripts/gate_config_demo.sh --mode fail
# --use-cluster-gate MUST read the current ConfigMap; not reapply config/gate.yaml:
bash scripts/eval_job.sh --target live --out eval/results/configmap-fail --baseline "$BASELINE_A" --use-cluster-gate
DEMO_RC=$?
printf 'Evaluation exit status: %s\n' "$DEMO_RC"
kubectl get job rahbar-eval -n rahbar
kubectl logs job/rahbar-eval -n rahbar
bash scripts/gate_config_demo.sh --mode restore
bash scripts/eval_job.sh --target live --out eval/results/configmap-restored --baseline "$BASELINE_A" --use-cluster-gate
```

Run intentional-failure blocks in an interactive shell without automatic `set -e`, so you can inspect exit status and restore config. A failure must be due to the measured threshold, not a broken Job. Show actual gate reason. Capture F2-config plus completed successful F2-eval. The wrapper must not silently overwrite the edited ConfigMap when using `--use-cluster-gate`.

### M2.4 — Fixed-test data drift, query coverage and closing the gap

Suggested branch: `feat/m2-drift-coverage`.

```text
PHASE M2.4. Follow the experiment order exactly. Preserve H2 Batch A suite and golden v1 hashes. Ask M1 to create rahbar_ab from rahbar_a then ingest Batch B through verification. Point the read-only candidate API at rahbar_ab with otherwise IDENTICAL baseline pipeline config. Run the entire B suite twice with the SAME golden v1, embedding pairs and judge/settings. scripts/diff_results.py compares suite JSONs and per-query ranks/citations/abstentions, linking changed docs/versions/filters to the verification inventory. Corpus mismatch is EXPECTED for E3 but not C release gate: this drift comparison isn't a controlled pipeline change experiment. Explain actual changes, no assumed improvement.

Implement python -m ragops.coverage --golden FILE --live FILE --config config/coverage.yaml --out DIR. Pinned model embeddings, nearest golden cosine per live query, share >= similarity cutoff. Similarity cutoff and aggregate minimum coverage are TWO separate numbers; 85% is an example aggregate floor, not a cosine threshold. Choose/justify each using our distribution and human examples. Save similarity distribution, nearest id, score, covered flag, uncovered queries and topic groups with members; human confirms topic names. Report that semantic question coverage doesn't mean corpus answerability.

Coverage exit 0 if fraction >= floor, 1 if below, 2 setup/error. Results written in all measured outcomes. Add Kubernetes coverage Job and wrapper using real model and input PVC/image staging.

After pre-expansion coverage is saved, add >=6 new questions from the uncovered topics to golden v2, preserving v1. Label new AI drafts synthetic and review honestly; unsupported topics expect abstain. Keep live queries, model and both thresholds fixed, then rerun coverage and show actual rise. Don't lower the threshold or duplicate live queries verbatim just to inflate it. If six are insufficient, inspect the uncovered topics and add useful questions; report measured rise honestly. Re-run suite on golden v2 for final regressions; do NOT compare v1 and v2 results through C gate as if test sets match.

Give me commands, evidence paths and topic-review/human tasks. STOP.
```

**After M1 ingests B into rahbar_ab and configures candidate target**
```bash
bash scripts/eval_job.sh --target candidate --out eval/results/drift-ab --baseline-mode --repeat 2
read -r -p "Real A+B suite JSON path: " DRIFT_AB
python scripts/diff_results.py "$BASELINE_A" "$DRIFT_AB" --out eval/results/drift-comparison
bash scripts/coverage_job.sh --golden eval/golden.v1.jsonl --live eval/live_queries.jsonl --config config/coverage.yaml --out eval/results/coverage-before
COVERAGE_BEFORE_RC=$?
printf 'Before coverage exit: %s\n' "$COVERAGE_BEFORE_RC"
# Add >=6 source-checked/reviewed questions to eval/golden.v2.jsonl first:
python scripts/validate_golden.py --golden eval/golden.v2.jsonl --live eval/live_queries.jsonl
bash scripts/coverage_job.sh --golden eval/golden.v2.jsonl --live eval/live_queries.jsonl --config config/coverage.yaml --out eval/results/coverage-after
COVERAGE_AFTER_RC=$?
printf 'After coverage exit: %s\n' "$COVERAGE_AFTER_RC"
```

Below-floor coverage is a valid measured failure; never suppress it. Capture E before/after summaries with nearest scores/topic lists and fixed configuration. Tell M1 the final corpus/test versions chosen for C.

### M2.5 — One-variable candidate experiments and real pass/fail release evidence

Suggested branch: `feat/m2-candidate-experiment`.

```text
PHASE M2.5. Implement the C experiment using ONE changed parameter, preferably top-k. Choose one frozen corpus (e.g. rahbar_ab after E3) and one frozen golden version for baseline/bad/good. Capture a NEW experiment baseline on that exact corpus+golden; do not gate A+B against old A results. Use M1 ingestion Jobs to clone identical chunk/vector snapshots into distinct bad/good candidate collections. Inspect collection content fingerprints to prove no accidental data or embedding difference.

Keep prompt/chunking/embed/generation/judge/seeds/cache policy fixed. Vary only top-k between baseline, deliberately poor candidate and reasonable candidate. Both candidates must actually differ from baseline; don't relabel the identical baseline as the passing changed candidate. Log all values and identities in result manifests and bind gate outputs.

Coordinate M1 to point api-candidate Deployment+Service at each collection/config, wait readiness, run full B suite twice at all three levels, compare, apply F2 Job gate. Select defensible thresholds from baseline/rationale, freeze policy before evaluating outcomes. If a proposed candidate fails, record rejection and try a justified new value; don't edit policy or remove hard questions merely to get green. C requires measured failing AND passing candidates.

Save live Deployment PodTemplate/revision before deliberately failing candidate eval and after; show they are identical and no rollout happened. Pass genuine decision JSON and result identity to M1 release.sh; do not perform rollout edits in partner files. Write docs/member2/CHANGE-EXPERIMENT.md with actual metrics/deltas, uncertainty, pass/fail, decision and links. Explain why embedding module metrics may stay stable while retrieval/E2E changes for top-k. Don't falsely force the G(b) pattern if it didn't occur.

Give exact commands and screenshot C1/C2/F3-block and the handoff for controlled rollout. STOP.
```

**After implementation and agreed M1 configuration helper**
Codex must implement `scripts/eval_candidate.sh --collection NAME --top-k K`, owned by M2. It prints and applies only the agreed evaluation target candidate Deployment env (this operational helper is a coordinated H4 exception; runtime manifests remain M1-owned), waits rollout and checks identity. It never modifies live:
```bash
# Record actual baseline top-k from real config, then choose DIFFERENT candidate values:
read -r -p "Experiment baseline top-k: " BASE_TOP_K
read -r -p "Deliberately poor candidate top-k: " BAD_TOP_K
read -r -p "Reasonable changed candidate top-k: " GOOD_TOP_K
bash scripts/eval_candidate.sh --collection rahbar_ab --top-k "$BASE_TOP_K"
bash scripts/eval_job.sh --target candidate --out eval/results/change-baseline --baseline-mode --repeat 2
read -r -p "Real experiment baseline JSON path: " EXP_BASELINE
# M1 must already have built matching candidate snapshots through ingestion Jobs.
kubectl get deployment api -n rahbar -o json > eval/results/live-before-rejected-candidate.json
bash scripts/eval_candidate.sh --collection rahbar_cand_bad --top-k "$BAD_TOP_K"
bash scripts/eval_job.sh --target candidate --out eval/results/candidate-bad --baseline "$EXP_BASELINE" --gate config/gate.yaml --repeat 2
BAD_RC=$?
printf 'Bad candidate gate exit: %s\n' "$BAD_RC"
kubectl get deployment api -n rahbar -o json > eval/results/live-after-rejected-candidate.json
python scripts/check_no_rollout.py --before eval/results/live-before-rejected-candidate.json --after eval/results/live-after-rejected-candidate.json
bash scripts/eval_candidate.sh --collection rahbar_cand_good --top-k "$GOOD_TOP_K"
bash scripts/eval_job.sh --target candidate --out eval/results/candidate-good --baseline "$EXP_BASELINE" --gate config/gate.yaml --repeat 2
GOOD_RC=$?
printf 'Good candidate gate exit: %s\n' "$GOOD_RC"
```

M2 implements `check_no_rollout.py` comparing PodTemplate and live release identity, ignoring status/resourceVersion noise. No secret values may be in captured Deployment JSON; use secretKeyRef, never literal keys. If good candidate does not pass, stop release and inspect real data. M1 releases only the passing measured revision with matching top-k and collection.

### M2.6 — Report PDF, result tables, final audit and demo practice

Suggested branch: `docs/m2-report-submission`.

```text
PHASE M2.6. Assemble report source under report/ and create scripts/render_report.py with documented dependencies and exact build command. Body <=8 pages; screenshot appendix follows and is excluded. First page both names/rolls (leave placeholders until provided). Use real committed results/trace samples, never retype/invent numbers. Programmatically generate tables from selected explicit result paths in a report-inputs manifest, not “latest *.json” which could select a fixture/failing demo run.

Include Figure 3 stage mapping (ingest, verify, data lake, retrieval-source update, offline testing, live testing, coverage), actual code files and missing items. Include Table 2 qualities (adaptability, monitorability, observability, traceability, reliability), our measure/threshold/evidence. Results A–F, noise, two-run differences, judge-human agreement if relevant, drift and coverage, gate pass/fail and release decision.

G short answers need actual facts: (a) check with most Batch B failures/missed problem and possible remedy; (b) module okay vs component/E2E poor OR why not seen; (c) archive/delete tradeoff; (d) least trusted metric and why; (e) hardest paper idea/adaptation; (f) Kubernetes object responsibilities. Merge M1's report notes; ask the humans for their experience/interpretation, not fabricated first-person stories. D5 exactly five lines derived from a wrong/abstained query's trace alone, reviewed by both.

Contribution table from actual owned work and git evidence (inspect all relevant refs, merge/squash behavior); don't use line counts as effort. Truthful 2–3-line AI statement, matching docs/AI-USAGE.md. Add uncropped labelled screenshot appendix per guide. Any absent screenshot/table/input blocks final submission readiness.

Root README exact commands A–F plus k8s/README fresh-cluster startup order with M1. Keep CI e2e and coverage/manifest/image checks working; add eval image build and meaningful offline tests. Render final PDF, check body page count and every appendix capture readable. Run available final checks (golden validation, real suite/gate/coverage artifact identity, kubeconform via existing CI-compatible commands, tests/lint, existing submission checker). Distinguish executed checks from commands I must run.

Create docs/member2/DEMO.md for evaluation Job, changing threshold without rebuild, three-level summary, coverage before/after and blocked candidate. Rehearse partner ingestion/trace/rollout commands so I can explain them. Write an A1–F5/G checklist with evidence links and unresolved blockers. Give explicit final Git and report-build commands, then STOP.
```

Suggested report body allocation (layout guidance, not required headings):

| Page | Content |
|---|---|
| 1 | Names/rolls, concise architecture, Figure 3 mapping |
| 2 | Verification, incremental/version state, Batch B findings |
| 3 | Three-level B results, noise, repeat differences |
| 4 | C baseline/bad/good/gates and release decision |
| 5 | D trace/guardrail/root cause and five-quality table |
| 6 | E drift/coverage; F objects/resources/recovery |
| 7 | Six short answers, concise and evidence-grounded |
| 8 | Contributions, AI statement, limits/references as space permits |
| Appendix | All required labelled full-terminal screenshots |

**After implementation — final manual checks**
```bash
python scripts/validate_golden.py --golden eval/golden.v2.jsonl --live eval/live_queries.jsonl
make test
make lint
# Use the actual existing schema-validation pipeline/version from CI:
kubectl kustomize k8s/overlays/prod > /tmp/rahbar-prod.yaml
kubeconform -strict -summary /tmp/rahbar-prod.yaml
# Validate standalone Job manifests too, which may not be aggregated:
kubeconform -strict -summary k8s/eval-job.yaml k8s/coverage-job.yaml
python scripts/render_report.py --inputs report/inputs.json --out report/Assignment03_RAGOps_Report.pdf
git log --all --format='%an <%ae>' --no-merges
git diff --check
```

Use the repo's actual overlay path if different. kubeconform requires installed compatible schemas and ignores no errors silently. Report build must print body and appendix page counts, fail if body exceeds eight and fail if required names/screenshots are missing. Inspect the PDF yourself for readable tables and full captures. Final dev->main PR is reviewed by both; no direct main push or fake contribution authors.

## Member 2 completion checklist

- [ ] H0 result/golden/gate/retrieval contracts agreed; fake clients only in tests.
- [ ] >=25 golden, >=15 answerable/5 unanswerable/5 hard, document/page evidence.
- [ ] >=8 actual handwritten questions + >=8 actual synthetic reviews, split equally.
- [ ] >=15 paraphrase and >=15 unrelated pairs; full B suite with all requested metrics.
- [ ] Noise deltas, whole-suite twice/seeds/differences; >=8 human answer labels and agreement if using judge.
- [ ] Baseline A saved BEFORE Batch B; drift A vs A+B on frozen golden v1.
- [ ] >=40 simulated live queries with >=12 uncovered topic; cutoff/floor justified separately.
- [ ] >=6 useful new golden questions; same-live/same-threshold coverage rise; correct nonzero below floor.
- [ ] Kubernetes eval Job literal path and apply command; results PVC export even on failed Job.
- [ ] Gate ConfigMap edit flips measured outcome with same image; original policy restored.
- [ ] ONE changed parameter; same experiment corpus/test set; distinct bad/good candidates with genuine fail AND pass.
- [ ] Failed candidate never rolled live; passing identity handed to M1; measured eval resources.
- [ ] B/C/E/F evidence, result files, report source and <=8-page PDF+appendix committed.
- [ ] Root README A–F, fresh-cluster guide, CI/test/lint/schema checks, own commits and both-member demo readiness.

## Full screenshot and evidence checklist

Every appendix capture must show the command AND its real output, uncropped, from your own cluster/runs. Use a wide terminal; split long output into sequential uncropped captures with labels rather than shrinking text beyond readability. Windows Win+Shift+S can capture the complete terminal window. Save screenshots as `report/appendix/A1-...png`, etc.; no keys visible. These labels are our checklist labels, not additional PDF rubric numbering.

| Label | Owner | Command/evidence after implementation | Must be visible |
|---|---|---|---|
| A1 | M1 | cat ACTUAL_VERIFICATION_MD (exported by collect_runtime.sh) | Batch B, each of four checks, pass/fail, reasons, final decisions |
| A2 | M1 | second ingest_job.sh on unchanged collection; kubectl logs job/ACTUAL_JOB -n rahbar | Zero chunks embedded, counts/revision and successful Job |
| B1 | M2 | cat ACTUAL_SUITE_MD; kubectl logs job/ACTUAL_EVAL_JOB -n rahbar | Module, component and E2E summary, both suite runs/deltas |
| C1/C2 | M2 | eval_job.sh against bad then good candidate; cat ACTUAL_GATE_JSON | Honest failed and passed gate values and exit states |
| D1 | M1 | python scripts/trace_show.py ID --traces-dir traces --json | One full JSON trace, all D1 fields |
| D2 | M1 | python scripts/trace_show.py ID --traces-dir traces | Exact original evidence and prompt, identity/version/filter/guardrail |
| E1/E2 | M2 | coverage_job.sh golden v1 then v2; cat ACTUAL_COVERAGE_MD | Same live set/cutoff, coverage before/after, uncovered topics |
| F1 | M1 | kubectl get all,pvc,configmap,cronjob,job -n rahbar | Deployments, Services, persistent volumes, Jobs/CronJob/config |
| F2-ingest | M1 | kubectl logs job/ACTUAL_SUCCESSFUL_INGEST -n rahbar | Completed ingestion verification/incremental counts |
| F2-eval | M2 | kubectl logs job/ACTUAL_SUCCESSFUL_EVAL -n rahbar | Completed evaluation AND gate pass, result path |
| F2-config | M2 | kubectl get configmap release-gate -n rahbar -o yaml; new eval Job logs | Threshold edit, unchanged image ref, changed gate outcome |
| F3-block | M2 | gate failure + kubectl get deploy/api -n rahbar -o yaml (no secrets in env) | Failed candidate, unchanged live release/revision |
| F3-rollout | M1 | kubectl rollout status deploy/api -n rahbar; kubectl rollout history deploy/api -n rahbar | Successful controlled rollout with zero unavailable policy |
| F3-undo | M1 | kubectl rollout undo deploy/api -n rahbar; rollout status; NEW query+trace_show | Previous collection AND embedding version after undo |
| F4 | M1 | kubectl logs ACTUAL_API_POD -n rahbar; port-forward then curl /metrics | JSON trace stdout plus metrics accessible |
| F5 | Both | kubectl top pods -n rahbar --containers; saved sample files | API/vector-store/ingest/eval measured usage and justified requests |

The rubric additionally needs changed/deleted/version-restore proofs, noise/stochasticity results, drift explanation, >=6 new questions, ConfigMap mechanism, unseen-document rehearsal and human provenance even where it does not demand a separate screenshot.

## Failure diagnosis and evidence rules

```bash
kubectl config current-context
kubectl get pods -n rahbar -o wide
kubectl get jobs -n rahbar
kubectl describe pod ACTUAL_POD -n rahbar
kubectl logs ACTUAL_POD -n rahbar
# Only for a container that restarted:
kubectl logs ACTUAL_POD -n rahbar --previous
kubectl get events -n rahbar --sort-by=.lastTimestamp
```

Use `kubectl describe job ACTUAL_JOB -n rahbar` for Job failures. ImagePullBackOff: load the exact image into the selected minikube profile and confirm imagePullPolicy. Pending PVC: inspect claim/storageclass/events/permissions. Host Ollama timeout: verify listening host, actual route and allowed egress. DNS failure after deny-by-default: check UDP AND TCP 53 to cluster DNS. Failed gate: inspect metrics and identity, not readiness alone. `kubectl top` samples usage, not exact memory peak; sample repeatedly and record limitations/observed maximum.

Do not delete the namespace/PVCs to fix a small issue. Save logs before cleaning old Jobs; unique names preserve evidence. Secrets and provider errors must be redacted from evidence without falsifying results.

## Sources and interpretation

Primary task sources: attached Assignment 02 (20 pages), Assignment 03 (5 pages), and the supplied AI prompt (reviewed as a proposal, not source authority). The supplied GitHub URL was recorded, but access failed; no live repository audit or cluster run was performed when preparing this guide.

The brief cites a 2026 paper version. A public [arXiv v1](https://arxiv.org/html/2506.03401v1) is dated 2025; use the instructor's version if supplied and record the exact version read. Read 3.2, 4.2, Table 1, Table 2, 5.1, 6.2 and Figure 3. The guide uses the assignment's specified stages and five qualities; do not replace them with a different paper edition's requirements.

Technical references: [CronJob concurrency scope](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/), [Ollama model list/digest](https://docs.ollama.com/api/tags), [minikube Docker/WSL networking](https://minikube.sigs.k8s.io/docs/drivers/docker/), [Deployment rollout/undo](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). These support implementation details, not evidence of your own run.


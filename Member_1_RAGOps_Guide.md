# Assignment 03 — RAGOps: Member 1 — Data, Traces and Kubernetes Runtime

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
gh pr create --base dev --head "$(git branch --show-current)" --title "DESCRIPTIVE PR TITLE" --body-file docs/member1/PR.md
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

## Master prompt — paste first (Member 1)

```text
Act as a senior software construction mentor specializing in Kubernetes, Docker and RAGOps. I am Member 1 of a two-student group. Assignment 02 RAHBAR is completed; Assignment 03 extends it. Read both PDFs and this member guide completely. The A03 PDF is the authority; preserve working A02 behavior. The previous AI master prompt is context, not evidence of the actual implementation.

Read README, STARTER.md if present, docs/CONTRACTS.md, architecture/pipeline/ADRs, Makefile, dependency locks, api/, indexer/, eval/, k8s/ and CI workflows. Inspect git status/remotes/branches without modifying them. Correct assumptions about paths, endpoints, model/provider, image names and existing capabilities from the code.

I run ALL Git, installation, Docker, minikube, kubectl, WSL, hosted/model API calls and screenshot commands myself. You may inspect/edit owned local files and run offline lint/unit tests if available; tell me exactly what you actually ran. Do NOT install, create/switch branches, commit, push, deploy, invoke live services or take screenshots yourself. For any such action give me an exact copy-paste command with shell, directory, terminal number, expected output SHAPE and failure diagnosis. Never claim success from an unexecuted command.

Follow the ownership table. Work only on my current phase; don't implement my partner's modules. Develop against shared schemas/fakes if their code is missing. Ask the owner for an interface patch, not a wholesale shared-file rewrite. Only H0/shared integration may modify shared files under the designated integrator.

Never fabricate metrics, screenshots, manual questions/reviews/labels or evidence. Real report numbers require our pipeline runs and committed result files. Synthetic fixture results belong under tests/, flagged test-only and rejected by release gating. Human question slots stay empty until we fill them. Every provided draft question is synthetic, not handwritten. Labeling tools record human identity and actual decision.

Use Kubernetes for all final runtime evidence. Ingestion Jobs alone mutate Chroma, serialized across manual/Cron/admin/candidate Jobs. API and eval read only. Keep A02 embedding pin, schemas, citations/abstention, security, metrics and CI. Add fields compatibly. No secrets in output or Git. Pin images and source tags; provide provisional labeled resource requests for bootstrapping, then replace/justify from measurements. Requests/limits required everywhere.

For every phase: explain changes in plain language, list files and requirement IDs, run meaningful offline checks where available, give my manual commands and screenshots with visible command+output, list unresolved human inputs and blockers, update only my progress file, write my PR.md, supply commit/PR commands, then STOP. Wait for my real outputs before claiming acceptance or starting the next phase. An unavailable local runtime is a blocker to verification, not permission to fake success.

First reply: no edits. Give a concise true architecture summary, full A1–F5/G gap table citing actual paths, my owned-file plan, H0 contract conflicts, real prerequisite commands, and next phase. No open-ended redesign.
```


## Member 1 phased work — paste one prompt at a time

Your role: data lifecycle + API observability + runtime integration. Your partner owns evaluation/gate/coverage implementation. Read their output schemas; do not implement a second suite.

### M1.0 — Inspect, settle H0, establish the runnable foundation

Suggested branch: `feat/m1-ragops-contracts`. Run the Git workflow yourself.

```text
PHASE M1.0. Inspect the actual A02 repository and both assignment PDFs. No redesign. Write docs/member1/GAP.md with every A1–F5 and G item, evidence paths and ownership. Create docs/member1/PROGRESS.md and PR.md. As shared-contract integrator, draft docs/CONTRACTS.md additions for document/version/collection identity, verification result, ingest counters, trace schema, evaluation retrieval adapter and release identity. Send M2 the contract; incorporate their golden/result/gate schemas rather than choosing those for them.

Use actual API route, request fields, Service ports, labels, config names, installed tool versions, Docker build contexts and package install mechanism. Write docs/member1/COMMANDS.md with their real values and the exact current A02 smoke-test commands. Establish mk/ragops-runtime.mk and include it from Makefile; reserve inclusion of M2's mk/ragops-eval.mk using an optional include until it arrives. Keep a single minimal ragops package initializer.

Create the runtime Kubernetes directory layout and a separate runtime shell helper manifest with pinned utility/ingester image, tar support for kubectl cp, non-root uid, fsGroup, resources, token automount off and PVC mounts. This helper copies files only; it must have no Chroma write capability. Design the cluster startup order: namespace/config/secrets/PVC/storage/services, then writer ingestion, then readiness/rollout. Do not wait for API readiness before its collection exists.

Give me existing offline test/lint commands to run, the exact setup diagnostics and the H0 handoff summary. Do not fill future success claims or report data. STOP.
```

Acceptance: actual repository facts corrected; H0 reviewed by partner; current A02 checks still pass or failures documented. M2 can begin their fake-client suite immediately. Ask Codex for a concise list of missing installations only.

### M1.1 — Persistent state and truly incremental ingestion

Suggested branch: `feat/m1-incremental-ingest`.

```text
PHASE M1.1. Implement ragops/state.py and ragops/ingest.py around the existing extractor/chunker/embed/store, plus scripts/ingest_job.sh, scripts/wait_job.sh and runtime Job/CronJob/admin templates. Scope state by collection, logical doc_id, document version and pipeline fingerprint. Store content hash, source/title/date-or-version/page count, status, chunk ids and audit events on /datalake/state/state.db; originals in raw/archive/quarantine.

Implement run, status, count --doc-id, restore --doc-id --version and explicit deletion/tombstone modes. The wrapper contract supports all these modes as unique one-off Jobs of the SAME writer image. Restore and candidate snapshot-copy must use that writer path. CronJob Forbid PLUS one shared process/file lock on single-node minikube protects scheduled/manual/admin/candidate Jobs; document limits and use a safe distributed lock if the real deployment is multi-node. Handle stale lock recovery safely.

Unchanged hash+fingerprint => no extraction/chunk embeddings/document near-dup embeddings needed; log separate embedding-call counters as well as chunks_seen/embedded/reused/deleted. For changed docs, upsert missing chunk ids before deleting only old_id minus new_id; preserve other docs. Explicit tombstones delete by the target doc/version/collection; inbox movement must never look like deletion. Collection model/digest/dimension mismatch must fail loudly. Store resolved digest from /api/tags and actual model identity.

Add recoverable pending/committed index revision and cache invalidation on committed revision. Do not pretend multi-operation Chroma writes are atomic. Keep archived source and state sufficient to reconstruct versions after rollback. Implement --snapshot-from to clone a frozen collection's ids/vectors/text/metadata into a new collection using an ingestion Job, without re-embedding; source is unchanged.

Unit tests: unchanged produces zero total embedding calls; only changed chunk ids replaced; no deleted-doc orphans; inbox->raw isn't deletion; failed retry recovers; candidate state doesn't collide; two writers serialize; restore returns old version and supersedes new. Keep verification pluggable; test-only temporary verifier is explicitly not A1 completion.

Implement make ragops-runtime-images TAG=... and make ragops-runtime-load PROFILE=... TAG=... using actual contexts, matching manifests and image references. Create persistent data lake and results PVC mounts, permissions, provisional requests/limits, ingest CronJob and helper pod. Implement scripts/collect_runtime.sh to export evidence without losing prior runs. Give my exact build/load/apply commands and commands for run twice, change, deletion count and restore; explain all counters. STOP.
```

**After phase implementation — manual commands**
Codex must replace image references/manifests with verified repo paths if needed. This workflow uses the new runtime kustomization created by this phase:
```bash
# Build targets must be supplied using the real A02 Docker contexts:
make ragops-runtime-images TAG="$(git rev-parse --short=12 HEAD)-m1"
make ragops-runtime-load PROFILE=rahbar-a03 TAG="$(git rev-parse --short=12 HEAD)-m1"
kubectl apply -k k8s/ragops-runtime
kubectl apply -f k8s/tools/runtime-shell.yaml
kubectl wait --for=condition=Ready pod/runtime-shell -n rahbar --timeout=120s
# Choose the actual downloaded A02 corpus directory and metadata sidecars:
read -r -p "Batch A directory: " BATCH_A_DIR
bash scripts/ingest_job.sh --collection rahbar_a --batch-dir "$BATCH_A_DIR"
bash scripts/ingest_job.sh --collection rahbar_a
bash scripts/collect_runtime.sh --out eval/results/m1-ingestion
```

The second run must show actual `chunks_embedded=0` AND no unnecessary document-check embeddings. Save that Job's name; final A2 screenshot is taken again with real verification enabled.

Use a self-made test document for change/delete/restore proofs, not an official policy edit disguised as authentic. Codex must generate a documented fixture-specific script at `scripts/ingest_scenarios.sh` with `--scenario changed|deleted|restore --collection NAME`; it must use the wrapper and print before/after chunk counts and unaffected doc fingerprints. Run those on `rahbar_sandbox`, never mutate the frozen `rahbar_a` snapshot:
```bash
bash scripts/ingest_scenarios.sh --scenario changed --collection rahbar_sandbox
bash scripts/ingest_scenarios.sh --scenario deleted --collection rahbar_sandbox
bash scripts/ingest_scenarios.sh --scenario restore --collection rahbar_sandbox
```

### M1.2 — Four verification checks, Batch B and A evidence

Suggested branch: `feat/m1-document-verification`.

```text
PHASE M1.2. Implement ragops/verify.py between extraction and chunking with four independently recorded pass/fail results and reasons. Quality: empty/garbled/extraction failure. Completeness: source/title/date OR version/page count plus extraction completeness/truncation heuristics. Recency: stable document family id/version/date ordering. Uniqueness: hash exact duplicates and document embedding near-duplicates with a threshold tested on representative duplicates/nonduplicates. Check version lineage first so a valid newer policy isn't rejected as a duplicate.

Quality/completeness/duplicate rejects go to quarantine and cannot enter the active index. Superseded valid versions are archived with superseded=true and excluded by normal retrieval; explicitly record the recency exception to generic quarantine routing. Preserve older versions for restore. Every document, including extraction failures and unchanged entries, has all four result fields; explain checks not executable due to bad extraction rather than silently omitting them. Infrastructure failure must fail the Job, not quarantine good files.

Produce timestamped JSON plus readable Markdown verification report per run on results PVC, later exported under eval/results. Identify batch, input hash, doc id/version, checks, final action and reasons. Keep raw input filenames safe; reject traversal. Give progress for corrupt files and bounded extraction/OCR timeouts.

Implement scripts/make_batch_b.py: reproducible >=10 small self-made fixtures grounded in the permitted actual corpus with PLANTED.md and source/checksum metadata. Include 2 exact duplicates (different file names), near duplicate, corrupt/truncated, missing metadata, newer version with a visibly changed synthetic fact, injected instruction and enough fillers. Mark edited policy facts as synthetic test fixtures. Make the injected document otherwise valid and distinct so it survives verification and reaches retrieval for D4. Don't replace the real corpus with toy data.

Tests cover every check, false-positive version/near-dup ordering, corrupt files, duplicate ownership/canonical selection, repeat zero embeddings and archived restore. Write observed threshold evidence from real runs only, leaving pending fields until I run them.

Give commands for verified Batch A then Batch B, full report display, unchanged second run, changed/deleted proofs and version restore. Alert M2 that H1 is ready, but do not ingest B into the frozen Batch A collection. STOP.
```

**After implementation — manual sequence**
```bash
python scripts/make_batch_b.py --out corpus_batch_b
cat corpus_batch_b/PLANTED.md
# Re-run A with verification, then take A2 unchanged-run evidence:
bash scripts/ingest_job.sh --collection rahbar_a --batch-dir "$BATCH_A_DIR"
bash scripts/ingest_job.sh --collection rahbar_a
# Freeze A and inform M2 to capture H2 baseline BEFORE the next two commands.
# After H2 baseline has been captured:
bash scripts/ingest_job.sh --collection rahbar_ab --snapshot-from rahbar_a
bash scripts/ingest_job.sh --collection rahbar_ab --batch-dir corpus_batch_b
bash scripts/ingest_job.sh --collection rahbar_ab --mode status
bash scripts/collect_runtime.sh --out eval/results/m1-verification
```

Use paths actually printed by export:
```bash
read -r -p "Exported verification Markdown path: " VERIFY_MD
cat "$VERIFY_MD"
read -r -p "Completed unchanged-run Job name: " INGEST_JOB
kubectl get job "$INGEST_JOB" -n rahbar
kubectl logs "job/$INGEST_JOB" -n rahbar
```

Capture A1/A2 and F2-ingest. Count/restore commands using real ids from status:
```bash
read -r -p "Actual document id: " DOC_ID
read -r -p "Actual archived version: " DOC_VERSION
bash scripts/ingest_job.sh --collection rahbar_sandbox --mode count --doc-id "$DOC_ID"
bash scripts/ingest_job.sh --collection rahbar_sandbox --mode restore --doc-id "$DOC_ID" --version "$DOC_VERSION"
```

The selected id/version must exist in the sandbox scenario, not merely in another collection. Save verification and admin outputs for G(a), G(c).

### M1.3 — Trace every query, reconstruct prompt and expose guardrail metrics

Suggested branch: `feat/m1-traceability`.

```text
PHASE M1.3. Implement D1–D5 infrastructure with additive API edits. Every query, including cache hits, early abstentions, validation fallback and errors, gets trace id and one complete trace JSON record. Include all D1 fields, request id, exact retrieved evidence text/page/version/score, full prompt plus hash, resolved model+digest and collection revision, config/top-k, stage timings with skipped status where relevant, response/citations/guardrails/cache. Never fabricate a prompt for early abstention; explain no generation. Cache hits link to original prompt/trace plus current request/cache timing.

Write each record to stdout and traces PVC; use per-pod/process files or process-safe append. Ensure non-root permissions and read-only-rootfs writable paths. Do not expose private internal reasoning in the user UI; retain contract compatibility and sanitize secrets from prompts/errors/logs.

Add cluster-internal read-only evaluation retrieval/trace access agreed at H0, reusing actual production retrieval and generation. Coordinate schema with M2. Preserve public API; keep evaluation endpoints off public Ingress or protected. Add optional trace_id and X-Trace-ID without breaking UI.

Implement retrieval injection rail with actions recorded and counted; test against the actual indexable Batch B injection. Heuristic patterns alone aren't a security proof; report limitations. Expose/report top-1 similarity distribution, abstention/cache hit rates, stage latency p95 and injection attempts. scripts/trace_show.py must print exact stored prompt/context by trace id, support --json, and error if missing; trace_summary.py supports --since 1h/24h. Samples committed to traces come from our runs, never handwritten fixture data.

Implement scripts/query.sh adapter using actual route, safe question argument handling, header/response/trace files. collect_runtime.sh exports trace files. Offline tests: trace schema in all outcomes, query unchanged, guardrail action, replay equality and tool failures. Give commands and D/F4 screenshots; select a wrong/abstained real evaluation trace later for D5, not an invented incident. STOP.
```

**After implementation — two WSL terminals**
Terminal 1 (leave running):
```bash
kubectl port-forward svc/api -n rahbar 8000:8000
```

The Service port `8000` must be verified at M1.0; if Service uses port 80, use `8000:80`. Terminal 2:
```bash
curl -fsS http://127.0.0.1:8000/metrics
read -r -p "A real corpus question: " QUESTION
bash scripts/query.sh --target live --question "$QUESTION" --out eval/results/query-demo
bash scripts/collect_runtime.sh --out eval/results/m1-traces
read -r -p "Trace id printed by query wrapper: " TRACE_ID
python scripts/trace_show.py "$TRACE_ID" --traces-dir traces --json
python scripts/trace_show.py "$TRACE_ID" --traces-dir traces
python scripts/trace_summary.py --traces-dir traces --since 1h
```

Ask a real question that retrieves the injected document in `rahbar_ab` using the candidate target configured for that collection. Confirm the retrieved chunk id and rail action; a synthetic trace or a blocked document that was never retrieved does not prove D4. Capture D1, D2, F4. D5: retrieve one actual wrong/abstained Part B query trace, and write exactly five diagnostic lines from its fields; distinguish evidence from hypotheses.

### M1.4 — Candidate Deployments, safe release, rollback and measurements

Suggested branch: `feat/m1-k8s-controlled-release`.

```text
PHASE M1.4. Complete F1/F3/F4 and runtime F5, consuming M2 suite/gate outputs. API live and candidate Deployment+own Service use separate immutable collection names. Keep A02 live 3 replicas, probes, maxSurge=1/maxUnavailable=0, preStop/termination grace and resources. Pin CHROMA_COLLECTION, EMBED_MODEL, EMBED_VERSION and experiment setting TOP_K explicitly in each Deployment pod template; rollout undo must restore all release values. Add readiness digest/dimension checks. ConfigMap-only environment changes cannot be the rollback mechanism.

Implement scripts/release.sh to bind gate decision to collection revision, config including top-k, image, corpus/golden baseline identity and measured result hashes. Refuse stale/non-pass/fixture/mismatched gate evidence. Emit before/after release state. Release switches complete configuration together, not only collection. The failed-candidate path must leave live PodTemplate unchanged. Require no active writer mutation of release collections.

Wire runtime manifests and M2's eval manifests into a fresh-cluster documented apply order without automatically launching an evaluation Job against an unbuilt collection. Preserve default-deny NetworkPolicy and DNS. Add candidate and eval Service traffic, Redis access, Ollama/provider/judge egress and ingestion/admin routes minimally. Read-only APIs do not write Chroma. Retire/suspend legacy A02 indexer CronJob to avoid two independent writers, preserving documented fixture CI mode.

Implement resource_sample.sh and a lightweight real query load driver. Measure API/vector store while serving, ingestion during an actual Job, and eval with M2. Save repeated kubectl top data under eval/results; choose/justify requests and limits from observed maxima and headroom, mark initial bootstrap values provisional. Preserve CI and non-root/read-only filesystem/ServiceAccounts for new containers.

Give my exact safe rollout, deliberately bad SANDBOX release, rollout undo and NEW post-undo trace commands. Do not automatically release a failing candidate. Explain why controlled demonstration of a bad release is an explicitly isolated exception used to demonstrate recovery, never normal gate bypass. STOP.
```

**After M2 supplies C gate artifacts — manual commands**
```bash
# Baseline/candidate data is identical; only top-k changes:
bash scripts/ingest_job.sh --collection rahbar_cand_bad --snapshot-from rahbar_ab
bash scripts/ingest_job.sh --collection rahbar_cand_good --snapshot-from rahbar_ab
# M2 configures api-candidate and runs eval Jobs for each. Do not proceed on fail.
read -r -p "Measured PASS gate JSON path for good candidate: " PASS_GATE
bash scripts/release.sh --deployment api --candidate rahbar_cand_good --decision "$PASS_GATE"
kubectl rollout status deploy/api -n rahbar --timeout=300s
kubectl rollout history deploy/api -n rahbar
```

Before release, pin a genuinely measured baseline configuration and ensure its ReplicaSet remains in revision history. Codex must create `scripts/rollback_demo.sh` that saves that explicit revision and env, deliberately rolls a poor collection/config on the **local assignment cluster only**, waits for that rollout, records the regression, then prints the exact `kubectl rollout undo --to-revision` command. It checks context/namespace and asks you to execute the printed steps; it does not silently undo production:
```bash
bash scripts/rollback_demo.sh --prepare --context rahbar-a03 --namespace rahbar
# Use the recorded revision number from the preparation output:
read -r -p "Known-good revision to restore: " GOOD_REVISION
kubectl rollout undo deploy/api -n rahbar --to-revision="$GOOD_REVISION"
kubectl rollout status deploy/api -n rahbar --timeout=300s
bash scripts/query.sh --target live --question "$QUESTION" --out eval/results/post-undo
bash scripts/collect_runtime.sh --out eval/results/rollback-demo
```

Preparation must print the commands that actually cause the bad rollout; run them and observe it before undo. An undo of an unchanged deployment is not a rollback demonstration. Open the NEW trace id and show previous collection and embedding version. A top-k change keeps the embedding version identical; that is valid, but the trace must still record and match it.

Resources: run the sampler in one terminal while the actual operation runs in another:
```bash
bash scripts/resource_sample.sh --label ingest --seconds 60 --out eval/results/resources-ingest.txt
# Repeat with --label eval and --label queries during those workloads.
kubectl top pods -n rahbar --containers
kubectl get all,pvc,configmap,cronjob,job -n rahbar
```

Capture F1/F3/F4/F5. Provide M2 measured data for report tables.

### M1.5 — Evidence, your report content and joint demo

Suggested branch: `docs/m1-runtime-evidence`.

```text
PHASE M1.5. Audit A1/A2, D1–D5, F1–F5 runtime portions against the PDF, linking every claim to real committed evidence. Add docs/member1/REPORT-NOTES.md with Figure 3 data stages, five qualities runtime measures/thresholds/evidence, G(a) verification actual counts including what was missed, G(c) archive vs delete and G(f) object responsibilities. Add D5 exactly five lines from an actual trace only. Leave measured blanks unresolved if missing; report assembly is M2's responsibility, not permission to invent values.

Create docs/member1/DEMO.md with exact ordered cluster commands and narration for: fresh-start verification, unseen batch copy+ingest+quarantine, unchanged zero embedding, full trace/prompt reconstruction, candidate stopped by gate (M2 evidence), rollout/undo plus new trace, stdout JSON and metrics, persistent data after helper/worker pod replacement without deleting PVCs. Rehearse unseen self-made PDFs/Markdown with unknown names and malformed files, not only Batch B fixtures. Infrastructure failures remain visible.

Implement runtime submission audit with existing checker compatibility; do not let an old A02 checker mistake a new contract for accidental breakage. Review partner evaluation/gate/coverage PR. Write missing evidence list, truthful contribution notes and AI-use additions. Give exact Git staging commands for owned source and real results/traces, excluding secrets and third-party PDFs. STOP after each requested demo step until I paste output.
```

You personally supply four handwritten golden questions (not AI drafts), four actual synthetic reviews and four human faithfulness labels if using a judge. Use M2's actual templates/tool and sign them honestly. Both members read/approve G(b), G(d), G(e) as well as their primary sections.

## Member 1 completion checklist

- [ ] H0/H1 schemas and real retrieval adapter delivered to M2.
- [ ] All four verification checks and >=10 Batch B documents, all required planted cases.
- [ ] Unchanged zero total embeddings, local-only change, deletion zero count, archive/restore real proofs.
- [ ] Writer serialization across Cron/manual/admin/candidate Jobs; no old CronJob competing.
- [ ] Every query trace, exact reconstruction, summaries, Batch B injection rail action.
- [ ] Three API probes and embedding model/digest pin; cache revision/config identity.
- [ ] Runtime manifests apply cleanly, persistent state/results/traces export, policies tested.
- [ ] Failed gate leaves live unchanged; successful rollout and deliberately bad release undone.
- [ ] New post-undo trace proves restored collection/model version.
- [ ] Runtime resource measurements/justified requests, screenshots A/D/F, report notes committed.
- [ ] Own genuine commits and equal human annotations; both can explain full system.

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


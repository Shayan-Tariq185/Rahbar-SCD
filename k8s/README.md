# Running the recorded RAGOps pipeline

This deployment extends Assignment 02. It does not delete its namespace, PVCs or
original `rahbar` collection. Recorded A03 experiments use separate collections.
Use the WSL Docker/minikube context consistently; do not switch to Windows
minikube commands halfway through a run.

## Terminal and working directory

Open PowerShell, then enter Ubuntu:

```powershell
Set-Location -LiteralPath 'C:\Users\PC\Desktop\5th Semester\Software Construction and Development\Assignment-2'
wsl -d Ubuntu-22.04
```

All commands below are **Ubuntu/WSL Bash**, at the repository root. The recorded
integration checkout is under `tmp/integrated-evidence`; after its PR is merged,
the ordinary repository root contains the same files. A new clone uses its own
absolute path and Python environment.

```bash
export PROFILE=minikube
export RAGOPS_PY=/home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python
export OLLAMA_URL=http://host.docker.internal:11434
export INDEXER_IMAGE=rahbar-indexer:85f796826cda-a03
export RAGOPS_EVAL_IMAGE=rahbar-eval:52989146143d-m2
```

Install the API/indexer development and evaluation requirements in a Python 3.12
virtual environment if the recorded environment does not exist. Set RAGOPS_PY to
that interpreter; do not reuse a copied Windows virtual environment in WSL.

## Fresh cluster and models

Start Docker Desktop with Ubuntu integration. In WSL:

```bash
docker info
minikube start -p "$PROFILE" --driver=docker --cni=calico --memory=6144 --cpus=4
minikube -p "$PROFILE" addons enable metrics-server
minikube -p "$PROFILE" addons enable ingress
kubectl config use-context "$PROFILE"
```

Ollama runs on Windows. Install `nomic-embed-text` and `llama3.2:3b`; their recorded
digests are in the result identities and `config/runtime-images.json`. Check
`http://localhost:11434/api/tags` in Windows and the pod-accessible endpoint before
ingestion. The observed address was `host.docker.internal` / `192.168.65.254`;
the older `host.minikube.internal` route failed on this machine. Recheck routing
and adjust the explicit /32 NetworkPolicies if moving to another environment.

Build the recorded source versions, rather than silently reusing a mutable dev
image. This helper requires normal Git access to the repository and its recorded
commits; run it from a fresh clone or the main checkout, not a Windows-created
worktree whose `.git` link Linux Git cannot resolve.

```bash
bash scripts/build_recorded_images.sh
kubectl apply -f k8s/base/namespace.yaml
```

Create `rahbar-secret` with a real hosted generation key. The recorded model is
`openai/gpt-oss-20b` at Groq's OpenAI-compatible endpoint. A missing key must not be
counted as real hosted generation. Enter it interactively; do not commit it:

```bash
read -rsp 'Hosted generation API key: ' LLM_API_KEY
printf '\n'
kubectl create secret generic rahbar-secret -n rahbar \
  --from-literal=LLM_API_KEY="$LLM_API_KEY" --dry-run=client -o yaml | kubectl apply -f -
unset LLM_API_KEY
kubectl apply -k k8s/ragops-runtime
kubectl apply -f k8s/tools/runtime-shell.yaml
kubectl apply -k k8s/ragops-eval
kubectl wait --for=condition=Ready pod/runtime-shell -n rahbar --timeout=180s
```

The API initially remains unready until its collection exists and has real
embeddings. This is expected; do not replace its model pin with a fixture model.
The new scheduled writer targets `rahbar_scheduled`, not a frozen benchmark
collection. Put a complete metadata-bearing upload in `/datalake/inbox` before
rehearsing a scheduled ingestion. The legacy A02 CronJob is suspended by the
runtime overlay.

## A and B baseline

```bash
"$RAGOPS_PY" scripts/eval_prepare_sources.py --all
"$RAGOPS_PY" scripts/stage_batch_a.py --out tmp/batch-a
bash scripts/ingest_job.sh --collection rahbar_a --batch-dir tmp/batch-a --image "$INDEXER_IMAGE" --timeout 2400
bash scripts/ingest_job.sh --collection rahbar_a --batch-dir tmp/batch-a --image "$INDEXER_IMAGE" --timeout 600
bash scripts/collect_runtime.sh --out eval/results/reproduced-a
bash scripts/eval_candidate.sh --collection rahbar_a --top-k 5 --context "$PROFILE"
bash scripts/eval_job.sh --target candidate --out eval/results/reproduced-baseline \
  --baseline-mode --image "$RAGOPS_EVAL_IMAGE" --context "$PROFILE" \
  --golden eval/golden.v1.jsonl --labels eval/human_faithfulness.jsonl \
  --embedding-url "$OLLAMA_URL"
```

Do not rerun ingestion on a frozen collection during measurement. The second
unchanged run precedes freezing its final revision. Existing frozen golden files
must not be overwritten. Capture actual result paths printed by the wrapper;
the guide's example paths are not a substitute for the new run's identities.

## Data drift and coverage

```bash
"$RAGOPS_PY" scripts/make_batch_b.py --out eval/fixtures/batch-b
bash scripts/ingest_job.sh --collection rahbar_ab --snapshot-from rahbar_a --image "$INDEXER_IMAGE"
bash scripts/ingest_job.sh --collection rahbar_ab --batch-dir eval/fixtures/batch-b --image "$INDEXER_IMAGE"
bash scripts/eval_candidate.sh --collection rahbar_ab --top-k 5 --context "$PROFILE"
bash scripts/eval_job.sh --target candidate --out eval/results/reproduced-drift \
  --baseline-mode --image "$RAGOPS_EVAL_IMAGE" --context "$PROFILE" \
  --golden eval/golden.v1.jsonl --embedding-url "$OLLAMA_URL"
```

Use `scripts/diff_results.py` with the two **explicit** exported suite paths and
the verification report. Run coverage only after this fixed-v1 comparison. Use
the same live set, model, `config/coverage.frozen.yaml` and its separate cosine
cutoff/floor for both v1 and v2. The before result is expected to fail the floor;
preserve its exit 1 and exported evidence. Do not suppress it as a setup error.

## C D F and screenshots

The final experiment, release, rollback, trace and screenshot commands are listed
in `docs/member2/DEMO.md` and the final screenshot command sheet. Candidate
configuration uses `scripts/eval_candidate.sh` and never updates the live API.
Release uses `scripts/release.sh` with its bound baseline, suite, original policy,
golden and fresh candidate API identity. A decision JSON alone cannot release.

Trace tools read the real exported JSONL files. The metrics endpoint is exposed
through `kubectl port-forward svc/api -n rahbar 8000:8000`. All screenshot commands
must be run in the user's terminal and captured without cropping; no screenshot
is fabricated by the build or report tooling.

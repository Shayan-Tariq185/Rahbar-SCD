#!/usr/bin/env bash
# Executes real measurements; any unexpected exit stops the experiment.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${RAGOPS_PY:-python3}"
BASE_RUN="${1:?Supply the explicitly selected baseline run directory}"
IMAGE="${2:?Supply the immutable evaluator image}"
OUT=eval/results/controlled-release-20261128
POLICY=config/gate.frozen.yaml
mkdir -p "$OUT"
bash scripts/eval_wait_job.sh rahbar-eval-change-base 3600
for attempt in $(seq 1 60); do
  [[ ! -f "$BASE_RUN/job_exit.json" ]] || break
  sleep 2
done
BASE="$($PY - "$BASE_RUN" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); status=json.loads((root/'job_exit.json').read_text())
assert status['exit_code']==0, status
path=root/Path(status['suite']).name
assert path.is_file()
print(path)
PY
)"
printf '%s\n' "$BASE" > "$OUT/baseline.path"
"$PY" scripts/eval_freeze_policy.py --baseline "$BASE" --out "$POLICY" --latency-headroom 2 --rationale 'Freeze before any candidate outcome. Keep all quality floors and allow two-times the worst measured repeat p95 for local CPU/hosted-provider jitter; the earlier independent A baseline varied from 3840 to 14648 ms. This is an operational allowance, not a statistical confidence interval.'
kubectl get deployment api -n rahbar -o json > "$OUT/live-before-bad.json"
kubectl set env deployment/api-candidate -n rahbar CHROMA_COLLECTION=rahbar_cand_bad TOP_K=1
kubectl rollout status deployment/api-candidate -n rahbar --timeout=180s
COMMON=(--target candidate --baseline "$BASE" --image "$IMAGE" --golden eval/golden.v1.jsonl --repeat 2 --context minikube --embedding-url http://host.docker.internal:11434 --timeout 3600)
RC=0
if bash scripts/eval_job.sh "${COMMON[@]}" --gate "$POLICY" --job-name rahbar-eval-bad --out "$OUT/bad"; then :; else RC=$?; fi
kubectl get deployment api -n rahbar -o json > "$OUT/live-after-bad.json"
"$PY" scripts/check_no_rollout.py --before "$OUT/live-before-bad.json" --after "$OUT/live-after-bad.json" | tee "$OUT/no-rollout.txt"
[[ "$RC" -eq 1 ]] || { echo "Expected measured bad-gate exit 1; got $RC. Stopping." >&2; exit 2; }
kubectl set env deployment/api-candidate -n rahbar CHROMA_COLLECTION=rahbar_cand_good TOP_K=6
kubectl rollout status deployment/api-candidate -n rahbar --timeout=180s
BACKUP="$OUT/original-configmap.json"
bash scripts/gate_config_demo.sh --mode fail --backup "$BACKUP" --job-name rahbar-eval-bad > "$OUT/configmap-demo-change.txt"
RC=0
if bash scripts/eval_job.sh "${COMMON[@]}" --use-cluster-gate --job-name rahbar-eval-good-demo --out "$OUT/good-demo"; then :; else RC=$?; fi
bash scripts/gate_config_demo.sh --mode restore --backup "$BACKUP" --job-name rahbar-eval-good-demo > "$OUT/configmap-original-restored.txt"
[[ "$RC" -eq 1 ]] || { echo "Expected measured demo exit 1; got $RC. Original policy restored. Stopping." >&2; exit 2; }
bash scripts/eval_job.sh "${COMMON[@]}" --use-cluster-gate --job-name rahbar-eval-good --out "$OUT/good"
echo 'Controlled experiment completed. Inspect bound gate decisions before release.'

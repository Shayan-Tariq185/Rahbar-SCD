#!/usr/bin/env bash
set -euo pipefail
trap 'echo "ConfigMap demo setup/runtime failure" >&2; exit 2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
MODE=""; BACKUP=eval/results/gate-demo-original.json; PY="${RAGOPS_PY:-python3}"
JOB=rahbar-eval
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) [[ $# -ge 2 ]] || exit 2; MODE="$2"; shift 2 ;;
    --backup) [[ $# -ge 2 ]] || exit 2; BACKUP="$2"; shift 2 ;;
    --job-name) [[ $# -ge 2 ]] || exit 2; JOB="$2"; shift 2 ;;
    --help|-h) echo 'Usage: gate_config_demo.sh --mode fail|restore [--backup FILE]'; exit 0 ;;
    *) exit 2 ;;
  esac
done
[[ "$MODE" == fail || "$MODE" == restore ]] || exit 2
mkdir -p "$(dirname -- "$BACKUP")"
IMAGE="$(kubectl get job "$JOB" -n rahbar -o jsonpath='{.spec.template.spec.containers[0].image}')"
if [[ "$MODE" == fail ]]; then
  [[ ! -e "$BACKUP" ]] || { echo 'Original backup already exists; restore or choose a new explicit backup' >&2; exit 2; }
  kubectl get configmap release-gate -n rahbar -o json > "$BACKUP"
  "$PY" - "$BACKUP" "${BACKUP}.demo.yaml" <<'PY'
import json,sys,yaml
from pathlib import Path
saved=json.loads(Path(sys.argv[1]).read_text())
policy=yaml.safe_load(saved['data']['gate.yaml'])
if not policy.get('frozen'): raise SystemExit('Freeze the original justified policy before this demonstration')
policy['max_p95_latency_ms']=0
policy['policy_mode']='demo'
Path(sys.argv[2]).write_text(yaml.safe_dump(policy,sort_keys=False))
print('Demo threshold: maximum p95 latency 0 ms. Demo decisions cannot authorize release.')
PY
  kubectl create configmap release-gate -n rahbar --from-file="gate.yaml=${BACKUP}.demo.yaml" --dry-run=client -o yaml | kubectl apply -f -
else
  [[ -f "$BACKUP" ]] || { echo 'No original policy backup' >&2; exit 2; }
  "$PY" - "$BACKUP" "${BACKUP}.restore.yaml" <<'PY'
import json,sys
from pathlib import Path
saved=json.loads(Path(sys.argv[1]).read_text())
Path(sys.argv[2]).write_text(saved['data']['gate.yaml'])
print('Restoring exact original gate.yaml from saved ConfigMap, without retuning.')
PY
  kubectl create configmap release-gate -n rahbar --from-file="gate.yaml=${BACKUP}.restore.yaml" --dry-run=client -o yaml | kubectl apply -f -
fi
echo "No image was built. Last evaluation image remains: $IMAGE"
echo '+ kubectl get configmap release-gate -n rahbar -o yaml'
kubectl get configmap release-gate -n rahbar -o yaml
echo 'Run a NEW eval_job.sh with --use-cluster-gate and the SAME explicit --image.'

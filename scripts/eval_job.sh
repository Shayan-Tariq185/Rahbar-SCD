#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Evaluation setup/runtime command failed" >&2; exit 2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
usage() {
  cat <<'EOF'
Usage: bash scripts/eval_job.sh --target live|candidate --out DIR
  (--baseline-mode | --baseline FILE) [--gate FILE | --use-cluster-gate]
  --image REPOSITORY:SOURCE_SHA-m2 [--golden FILE] [--pairs FILE] [--labels FILE]
  [--repeat 2] [--context rahbar-a03] [--embedding-url URL] [--timeout 7200]
Coverage: bash scripts/coverage_job.sh --golden FILE --live FILE --config FILE --out DIR --image REF
Runs only the read-only evaluation image; exports results even if the Job fails.
EOF
}
TARGET=live; OUT=""; BASELINE=""; BASELINE_MODE=0; USE_CLUSTER_GATE=0
GATE=config/gate.yaml; GATE_EXPLICIT=0; GOLDEN=eval/golden.v1.jsonl; PAIRS=eval/embedding_pairs.jsonl
LABELS=eval/human_faithfulness.jsonl; INVENTORY=config/corpus-inventory.json
JOB_OVERRIDE=""; GOLDEN_VERSION=v1
IMAGE="${RAGOPS_EVAL_IMAGE:-}"; REPEAT=2; CONTEXT=rahbar-a03; TIMEOUT=7200
EMBEDDING_URL="${OLLAMA_URL:-http://host.minikube.internal:11434}"
MODE="${RAGOPS_JOB_MODE:-suite}"; LIVE=""; COVERAGE_CONFIG=""
PY="${RAGOPS_PY:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in --help|-h|--baseline-mode|--use-cluster-gate) ;; *) [[ $# -ge 2 ]] || { usage >&2; exit 2; } ;; esac
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --target) TARGET="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --baseline) BASELINE="$2"; shift 2 ;;
    --baseline-mode) BASELINE_MODE=1; shift ;;
    --gate) GATE="$2"; GATE_EXPLICIT=1; shift 2 ;;
    --use-cluster-gate) USE_CLUSTER_GATE=1; shift ;;
    --golden) GOLDEN="$2"; shift 2 ;;
    --pairs) PAIRS="$2"; shift 2 ;;
    --labels) LABELS="$2"; shift 2 ;;
    --inventory) INVENTORY="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --job-name) JOB_OVERRIDE="$2"; shift 2 ;;
    --golden-version) GOLDEN_VERSION="$2"; shift 2 ;;
    --repeat) REPEAT="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --embedding-url) EMBEDDING_URL="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --live) LIVE="$2"; shift 2 ;;
    --config) COVERAGE_CONFIG="$2"; shift 2 ;;
    *) echo "Unknown or incomplete option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -n "$OUT" && -n "$IMAGE" && "$REPEAT" =~ ^[0-9]+$ && "$REPEAT" -ge 2 && "$TIMEOUT" =~ ^[0-9]+$ ]] || { usage >&2; exit 2; }
[[ "$TARGET" == live || "$TARGET" == candidate ]] || exit 2
[[ "$GATE_EXPLICIT" -eq 0 || "$USE_CLUSTER_GATE" -eq 0 ]] || { echo 'Choose --gate OR --use-cluster-gate' >&2; exit 2; }
for tool in kubectl "$PY"; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }; done
"$PY" scripts/validate_golden.py --golden "$GOLDEN" --inventory "$INVENTORY"
FILES=("$GOLDEN" "$INVENTORY"); NAMES=(golden.jsonl inventory.json)
if [[ "$MODE" == suite ]]; then
  [[ -f "$PAIRS" && -f "$LABELS" ]] || { echo "Pairs and actual human faithfulness labels are required" >&2; exit 2; }
  [[ "$BASELINE_MODE" -eq 1 && -z "$BASELINE" || "$BASELINE_MODE" -eq 0 && -f "$BASELINE" ]] || { echo "Choose baseline capture OR a real baseline" >&2; exit 2; }
  FILES+=("$PAIRS" "$LABELS"); NAMES+=(pairs.jsonl labels.jsonl)
  if [[ "$BASELINE_MODE" -eq 0 ]]; then FILES+=("$BASELINE"); NAMES+=(baseline.json); fi
else
  [[ "$MODE" == coverage && -f "$LIVE" && -f "$COVERAGE_CONFIG" ]] || exit 2
  FILES+=("$LIVE" "$COVERAGE_CONFIG"); NAMES+=(live.jsonl coverage.yaml)
fi
[[ "$(kubectl config current-context)" == "$CONTEXT" ]] || { echo "Refusing unexpected context; select the intended local cluster explicitly" >&2; exit 2; }
# Both modes share the exporter and results PVC. Do not replace those inputs while
# another evaluation/coverage Job is active, even when its fixed name differs.
if ! kubectl get jobs -n rahbar -o json | "$PY" -c 'import json,sys; jobs=json.load(sys.stdin)["items"]; active=[j["metadata"]["name"] for j in jobs if (j["metadata"].get("labels",{}).get("app")=="rahbar-eval" or j.get("spec",{}).get("template",{}).get("metadata",{}).get("labels",{}).get("app")=="rahbar-eval") and not any(c["type"] in {"Complete","Failed"} and c["status"]=="True" for c in j.get("status",{}).get("conditions",[]))]; print("Existing active evaluation Jobs:", active); sys.exit(1 if active else 0)'; then
  echo 'Wait for the existing evaluation/coverage Job before changing shared evaluation resources' >&2
  exit 2
fi
run() { { printf '+'; printf ' %q' "$@"; printf '\n'; } >&2; "$@"; }
JOB=rahbar-eval; MANIFEST=k8s/eval-job.yaml
if [[ "$MODE" == coverage ]]; then JOB=rahbar-coverage; MANIFEST=k8s/coverage-job.yaml; fi
if [[ -n "$JOB_OVERRIDE" ]]; then JOB="$JOB_OVERRIDE"; fi
[[ "$JOB" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ && ${#JOB} -le 63 && "$GOLDEN_VERSION" =~ ^v[12]$ ]] || exit 2
mkdir -p "$OUT"
RUN_ID="$("$PY" -c 'from ragops.evalsuite.io import run_id; print(run_id("eval").lower())')"
HOST_OUT="$OUT/$RUN_ID-host"
mkdir -p "$HOST_OUT"
if kubectl get job "$JOB" -n rahbar -o json > "$HOST_OUT/predecessor-job.json" 2>/dev/null; then
  if ! "$PY" -c 'import json,sys; j=json.load(open(sys.argv[1])); sys.exit(0 if any(c["type"] in ("Complete","Failed") and c["status"]=="True" for c in j.get("status",{}).get("conditions",[])) else 1)' "$HOST_OUT/predecessor-job.json"; then
    echo "Refusing to replace active Job $JOB" >&2; exit 2
  fi
  run kubectl logs "job/$JOB" -n rahbar > "$HOST_OUT/predecessor-job.log"
  run kubectl delete job "$JOB" -n rahbar --wait=true
fi
RENDER=("$PY" scripts/eval_render_job.py --image "$IMAGE" --run-id "$RUN_ID" --target "$TARGET" --mode "$MODE" --job-name "$JOB" --golden-version "$GOLDEN_VERSION" --repeat "$REPEAT" --embedding-url "$EMBEDDING_URL")
if [[ "$BASELINE_MODE" -eq 1 ]]; then RENDER+=(--baseline-mode); fi
run "${RENDER[@]}"
run kubectl apply -f k8s/ragops-eval/pvc.yaml -f k8s/ragops-eval/serviceaccount.yaml -f k8s/ragops-eval/networkpolicy.yaml
if [[ "$MODE" == suite && "$USE_CLUSTER_GATE" -eq 0 ]]; then
  run "$PY" scripts/eval_sync_gate.py --config "$GATE" --apply
elif [[ "$MODE" == suite ]]; then
  run kubectl get configmap release-gate -n rahbar -o json > "$HOST_OUT/gate-configmap-at-launch.json"
fi
if kubectl get pod eval-results-shell -n rahbar -o json > "$HOST_OUT/exporter-before.json" 2>/dev/null; then
  OLD_IMAGE="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["spec"]["containers"][0]["image"])' "$HOST_OUT/exporter-before.json")"
  if [[ "$OLD_IMAGE" != "$IMAGE" ]]; then run kubectl delete pod eval-results-shell -n rahbar --wait=true; fi
fi
run kubectl apply -f k8s/ragops-eval/exporter.yaml
run kubectl wait --for=condition=Ready pod/eval-results-shell -n rahbar --timeout=180s
run kubectl exec -n rahbar eval-results-shell -- mkdir -p "/results/inputs/$RUN_ID" "/results/runs/$RUN_ID"
for index in "${!FILES[@]}"; do
  run kubectl cp "${FILES[$index]}" "rahbar/eval-results-shell:/results/inputs/$RUN_ID/${NAMES[$index]}"
done
printf '%s\n' "$JOB" > "$OUT/last-eval.name"
printf '%s\n' "$RUN_ID" > "$OUT/last-run.id"
cp "$MANIFEST" "$HOST_OUT/applied-job.yaml"
run kubectl apply -f "$MANIFEST"
WAIT_RC=0
if bash scripts/eval_wait_job.sh "$JOB" "$TIMEOUT"; then :; else WAIT_RC=$?; fi
if run kubectl logs "job/$JOB" -n rahbar > "$HOST_OUT/job.log" 2>&1; then :; else echo 'Could not retrieve Job logs' >&2; fi
if run kubectl get job "$JOB" -n rahbar -o json > "$HOST_OUT/job.json"; then :; else echo 'Could not retrieve Job object' >&2; fi
EXPORT_RC=0
if bash scripts/eval_results.sh --run-id "$RUN_ID" --out "$OUT"; then :; else EXPORT_RC=$?; fi
cat "$HOST_OUT/job.log"
[[ "$EXPORT_RC" -eq 0 && -f "$OUT/$RUN_ID/job_exit.json" ]] || { echo "Result export failed; Job status=$WAIT_RC" >&2; exit 2; }
RC="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["exit_code"])' "$OUT/$RUN_ID/job_exit.json")"
echo "Actual Job exit code: $RC; exported results: $OUT/$RUN_ID"
[[ "$RC" =~ ^[012]$ ]] || exit 2
exit "$RC"

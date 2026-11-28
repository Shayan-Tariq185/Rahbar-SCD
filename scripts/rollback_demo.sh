#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/rollback_demo.sh --prepare --context rahbar-a03 --namespace rahbar [--bad-collection rahbar_cand_bad] [--bad-topk 1]

Saves the current known-good Deployment revision and env vars, checks context/namespace safety,
and prints the exact controlled local-cluster commands to roll out a deliberately poor candidate
configuration and then undo back to the saved revision.
EOF
}

MODE="prepare"
CONTEXT="rahbar-a03"
NAMESPACE="rahbar"
DEPLOYMENT="api"
BAD_COLLECTION="rahbar_cand_bad"
BAD_TOPK="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare) MODE="prepare"; shift ;;
    --execute-bad) MODE="execute-bad"; shift ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --deployment) DEPLOYMENT="$2"; shift 2 ;;
    --bad-collection) BAD_COLLECTION="$2"; shift 2 ;;
    --bad-topk) BAD_TOPK="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

CURRENT_CTX=$(kubectl config current-context 2>/dev/null || true)
if [[ "${CURRENT_CTX}" != "${CONTEXT}" ]]; then
  echo "ERROR: Current kube context '${CURRENT_CTX}' does not match expected local context '${CONTEXT}'." >&2
  echo "Switch with: kubectl config use-context ${CONTEXT}" >&2
  exit 2
fi

GOOD_REV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
GOOD_ENV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].env}')

mkdir -p eval/results
BASELINE_FILE="eval/results/rollback-baseline.json"
python3 - "${BASELINE_FILE}" "${CONTEXT}" "${NAMESPACE}" "${DEPLOYMENT}" "${GOOD_REV}" "${GOOD_ENV}" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    "context": sys.argv[2],
    "namespace": sys.argv[3],
    "deployment": sys.argv[4],
    "good_revision": sys.argv[5],
    "good_env": json.loads(sys.argv[6]) if sys.argv[6] else [],
}, indent=2), encoding="utf-8")
PY

echo "Saved known-good baseline to ${BASELINE_FILE} (good_revision=${GOOD_REV})"

if [[ "${MODE}" == "execute-bad" ]]; then
  echo "NOTE: Controlled local-assignment-cluster bad rollout demonstration (isolated exception, never normal gate bypass)."
  echo "+ kubectl set env deployment/${DEPLOYMENT} -n ${NAMESPACE} CHROMA_COLLECTION=${BAD_COLLECTION} TOP_K=${BAD_TOPK}"
  kubectl set env "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" "CHROMA_COLLECTION=${BAD_COLLECTION}" "TOP_K=${BAD_TOPK}"
  echo "+ kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s"
  kubectl rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=300s
fi

cat <<EOF

=== Controlled Bad Rollout & Recovery Steps (Local Cluster Only: ${CONTEXT}) ===
1. Apply deliberate poor candidate in local cluster (if not already run with --execute-bad):
   kubectl set env deployment/${DEPLOYMENT} -n ${NAMESPACE} CHROMA_COLLECTION=${BAD_COLLECTION} TOP_K=${BAD_TOPK}
   kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s

2. Record the regression query/trace:
   bash scripts/query.sh --target live --question "YOUR QUESTION" --out eval/results/bad-release-query

3. Undo back to saved good revision (${GOOD_REV}):
   kubectl rollout undo deployment/${DEPLOYMENT} -n ${NAMESPACE} --to-revision=${GOOD_REV}
   kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s

4. Issue a NEW query and verify restored collection + embedding version in the new trace:
   bash scripts/query.sh --target live --question "YOUR QUESTION" --out eval/results/post-undo
   bash scripts/collect_runtime.sh --out eval/results/rollback-demo
EOF

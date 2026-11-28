#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/wait_job.sh JOB [--namespace rahbar] [--timeout 300]

Polls a Kubernetes Job for Complete OR Failed condition and exits cleanly:
  0 = Complete
  1 = Failed
  2 = Invalid arguments or timeout
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -lt 1 ]]; then
  usage
  [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && exit 0 || exit 2
fi

JOB_NAME="$1"
shift
NAMESPACE="rahbar"
TIMEOUT=300

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

START_TS=$(date +%s)
echo "+ kubectl get job ${JOB_NAME} -n ${NAMESPACE}"

while true; do
  COMPLETE=$(kubectl get job "${JOB_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || true)
  FAILED=$(kubectl get job "${JOB_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)

  if [[ "${COMPLETE}" == "True" ]]; then
    echo "Job ${JOB_NAME} completed successfully."
    exit 0
  fi

  if [[ "${FAILED}" == "True" ]]; then
    echo "Job ${JOB_NAME} FAILED." >&2
    kubectl describe job "${JOB_NAME}" -n "${NAMESPACE}" >&2 || true
    kubectl logs "job/${JOB_NAME}" -n "${NAMESPACE}" --tail=100 >&2 || true
    exit 1
  fi

  NOW_TS=$(date +%s)
  ELAPSED=$((NOW_TS - START_TS))
  if (( ELAPSED >= TIMEOUT )); then
    echo "Timed out after ${TIMEOUT}s waiting for job/${JOB_NAME}" >&2
    kubectl describe job "${JOB_NAME}" -n "${NAMESPACE}" >&2 || true
    kubectl get pods -n "${NAMESPACE}" -l "job-name=${JOB_NAME}" -o wide >&2 || true
    exit 2
  fi
  sleep 2
done

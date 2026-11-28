#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/resource_sample.sh --label TEXT --seconds 60 --out FILE [--namespace rahbar] [--interval 5]

Collects timestamped `kubectl top pods -n rahbar --containers` samples while a workload runs,
retries metrics-server warmup cleanly, and records sampling methodology/limitations.
EOF
}

LABEL=""
SECONDS_TOTAL=60
OUT_FILE=""
NAMESPACE="rahbar"
INTERVAL=5

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --seconds) SECONDS_TOTAL="$2"; shift 2 ;;
    --out) OUT_FILE="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${LABEL}" || -z "${OUT_FILE}" ]]; then
  echo "ERROR: --label and --out are required" >&2
  usage >&2
  exit 2
fi

mkdir -p "$(dirname "${OUT_FILE}")"

{
  echo "# Resource Sampling Report (${LABEL})"
  echo "# Namespace: ${NAMESPACE} | Duration: ${SECONDS_TOTAL}s | Interval: ${INTERVAL}s"
  echo "# Limitation: kubectl top reports periodic cAdvisor windowed samples, not exact instantaneous peak RSS."
  echo ""
} > "${OUT_FILE}"

# Warmup retry for metrics-server
for attempt in $(seq 1 6); do
  if kubectl top pods -n "${NAMESPACE}" --containers >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for metrics-server warmup (attempt ${attempt}/6)..."
  sleep 5
done

END_TS=$(( $(date +%s) + SECONDS_TOTAL ))
SAMPLE_NUM=0
while [[ $(date +%s) -le ${END_TS} ]]; do
  SAMPLE_NUM=$((SAMPLE_NUM + 1))
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "=== Sample ${SAMPLE_NUM} (${TS}) ===" | tee -a "${OUT_FILE}"
  echo "+ kubectl top pods -n ${NAMESPACE} --containers"
  kubectl top pods -n "${NAMESPACE}" --containers 2>&1 | tee -a "${OUT_FILE}" || true
  echo "" >> "${OUT_FILE}"
  sleep "${INTERVAL}"
done

echo "Saved ${SAMPLE_NUM} samples to ${OUT_FILE}"

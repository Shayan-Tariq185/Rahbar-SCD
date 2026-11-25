#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/query.sh --target live|candidate --question TEXT --out DIR [--port 8000] [--namespace rahbar]

Queries the live (svc/api) or candidate (svc/api-candidate) service over local port-forward or
supplied port, saving headers.txt, response.json, and trace_id.txt under DIR.
EOF
}

TARGET="live"
QUESTION=""
OUT_DIR=""
PORT=""
NAMESPACE="rahbar"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --question) QUESTION="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${QUESTION}" || -z "${OUT_DIR}" ]]; then
  echo "ERROR: --question and --out are required" >&2
  usage >&2
  exit 2
fi

case "${TARGET}" in
  live) SVC="svc/api"; DEFAULT_PORT=8000 ;;
  candidate) SVC="svc/api-candidate"; DEFAULT_PORT=8001 ;;
  *) echo "ERROR: --target must be live or candidate" >&2; exit 2 ;;
esac

USE_PORT="${PORT:-${DEFAULT_PORT}}"
mkdir -p "${OUT_DIR}"

PF_PID=""
if ! curl -fsS "http://127.0.0.1:${USE_PORT}/healthz" >/dev/null 2>&1; then
  echo "+ kubectl port-forward ${SVC} -n ${NAMESPACE} ${USE_PORT}:8000"
  kubectl port-forward "${SVC}" -n "${NAMESPACE}" "${USE_PORT}:8000" >/dev/null 2>&1 &
  PF_PID=$!
  trap '[[ -n "${PF_PID}" ]] && kill "${PF_PID}" >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:${USE_PORT}/healthz" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

PAYLOAD=$(QUESTION="${QUESTION}" python3 -c 'import json,os; print(json.dumps({"question": os.environ["QUESTION"]}))')
HTTP_CODE=$(curl -sS -D "${OUT_DIR}/headers.txt" -o "${OUT_DIR}/response.json" -w "%{http_code}" \
  -X POST "http://127.0.0.1:${USE_PORT}/api/ask" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}")

echo "HTTP ${HTTP_CODE}"
cat "${OUT_DIR}/response.json"
echo ""

TRACE_ID=$(python3 - "${OUT_DIR}/response.json" "${OUT_DIR}/headers.txt" <<'PY'
import json, sys
from pathlib import Path
resp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tid = resp.get("trace_id") or ""
if not tid:
    for ln in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
        if ln.lower().startswith("x-trace-id:"):
            tid = ln.split(":", 1)[1].strip()
print(tid)
PY
)
printf '%s\n' "${TRACE_ID}" > "${OUT_DIR}/trace_id.txt"
echo "Trace ID: ${TRACE_ID}"

if [[ "${HTTP_CODE}" -ge 400 ]]; then
  exit 1
fi

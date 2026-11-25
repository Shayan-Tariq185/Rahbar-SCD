#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/collect_runtime.sh --out DIR [--namespace rahbar] [--shell-pod runtime-shell]

Exports real verification reports from /results and trace JSONL records from /traces
without overwriting or truncating prior evidence. Deduplicates traces by trace_id.
EOF
}

OUT_DIR=""
NAMESPACE="rahbar"
SHELL_POD="${RUNTIME_SHELL_POD:-runtime-shell}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT_DIR="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --shell-pod) SHELL_POD="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${OUT_DIR}" ]]; then
  echo "ERROR: --out is required" >&2
  usage >&2
  exit 2
fi

mkdir -p "${OUT_DIR}/reports" "${OUT_DIR}/traces" traces

TMP_STAGE=$(mktemp -d)
trap 'rm -rf "${TMP_STAGE}"' EXIT

echo "+ kubectl cp ${NAMESPACE}/${SHELL_POD}:/results ${TMP_STAGE}/results"
kubectl cp "${NAMESPACE}/${SHELL_POD}:/results" "${TMP_STAGE}/results" || true

echo "+ kubectl cp ${NAMESPACE}/${SHELL_POD}:/traces ${TMP_STAGE}/traces"
kubectl cp "${NAMESPACE}/${SHELL_POD}:/traces" "${TMP_STAGE}/traces" || true

if [[ -d "${TMP_STAGE}/results" ]]; then
  cp -rn "${TMP_STAGE}/results/." "${OUT_DIR}/reports/" 2>/dev/null || cp -r "${TMP_STAGE}/results/." "${OUT_DIR}/reports/"
fi

# Merge and deduplicate traces into both OUT_DIR/traces and repo traces/all_traces.jsonl
python3 - "${TMP_STAGE}/traces" "${OUT_DIR}/traces/traces.jsonl" "traces/traces.jsonl" <<'PY'
import json
import sys
from pathlib import Path

src_dir = Path(sys.argv[1])
targets = [Path(sys.argv[2]), Path(sys.argv[3])]

seen = {}
for tgt in targets:
    if tgt.exists():
        for line in tgt.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                tid = rec.get("trace_id")
                if tid:
                    seen[tid] = rec
            except json.JSONDecodeError:
                pass

if src_dir.exists():
    for jf in sorted(src_dir.glob("*.jsonl")):
        for line in jf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                tid = rec.get("trace_id")
                if tid:
                    seen[tid] = rec
            except json.JSONDecodeError:
                pass

ordered = sorted(seen.values(), key=lambda r: str(r.get("timestamp", "")))
for tgt in targets:
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_text("".join(json.dumps(r) + "\n" for r in ordered), encoding="utf-8")
print(f"Exported {len(ordered)} unique trace(s) to {targets[0]} and {targets[1]}")
PY

echo "Collected runtime artifacts under ${OUT_DIR}:"
ls -la "${OUT_DIR}/reports" || true

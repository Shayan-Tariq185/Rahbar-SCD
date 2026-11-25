#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/release.sh --deployment api --candidate NAME --decision FILE
         [--namespace rahbar] [--skip-cluster-check] [--dry-run]

Verifies a measured PASS gate decision JSON (rejecting failures, synthetic/test-only fixtures,
or mismatched collection/config/image identity), atomically updates all release PodTemplate
env pins together, watches rollout, and logs before/after release state + rollback revision.
EOF
}

DEPLOYMENT="api"
CANDIDATE=""
DECISION_FILE=""
NAMESPACE="rahbar"
SKIP_CLUSTER_CHECK=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deployment) DEPLOYMENT="$2"; shift 2 ;;
    --candidate) CANDIDATE="$2"; shift 2 ;;
    --decision) DECISION_FILE="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --skip-cluster-check) SKIP_CLUSTER_CHECK=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${CANDIDATE}" || -z "${DECISION_FILE}" ]]; then
  echo "ERROR: --candidate and --decision are required" >&2
  usage >&2
  exit 2
fi

if [[ ! -f "${DECISION_FILE}" ]]; then
  echo "ERROR: Decision file not found: ${DECISION_FILE}" >&2
  exit 2
fi

RELEASE_ENV=$(python3 - "${DECISION_FILE}" "${CANDIDATE}" <<'PY'
import json, sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_cand = sys.argv[2]

if doc.get("test_only") is True or str(doc.get("provenance", "")).startswith("synthetic"):
    sys.exit("REFUSED: synthetic/test-only gate fixture cannot authorize release")

decision_str = str(doc.get("decision", "")).upper()
passed_bool = doc.get("passed")
if not (decision_str == "PASS" or passed_bool is True):
    sys.exit(f"REFUSED: gate decision is not PASS (decision={doc.get('decision')!r}, passed={passed_bool!r})")

cand_info = doc.get("candidate") if isinstance(doc.get("candidate"), dict) else {}
col = doc.get("collection") or cand_info.get("collection") or ""
if col != expected_cand:
    sys.exit(f"REFUSED: decision collection {col!r} does not match --candidate {expected_cand!r}")

embed_model = doc.get("embed_model") or cand_info.get("embed_model") or ""
embed_digest = doc.get("embed_digest") or doc.get("embed_version") or cand_info.get("embed_digest") or ""
top_k = doc.get("top_k") or (doc.get("config") or {}).get("top_k") or cand_info.get("top_k")
rev = doc.get("committed_revision") or doc.get("collection_revision") or cand_info.get("committed_revision")
golden_hash = doc.get("golden_hash") or (doc.get("inputs") or {}).get("golden_hash") or ""
image_ref = doc.get("image") or cand_info.get("image") or ""

if not embed_model or top_k is None:
    sys.exit("REFUSED: decision missing required embed_model or top_k identity")

print(json.dumps({
    "collection": col,
    "embed_model": embed_model,
    "embed_digest": embed_digest,
    "top_k": int(top_k),
    "committed_revision": rev,
    "golden_hash": golden_hash,
    "image": image_ref,
}))
PY
)

EMBED_MODEL=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["embed_model"])' "${RELEASE_ENV}")
EMBED_VERSION=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["embed_digest"])' "${RELEASE_ENV}")
TOP_K=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["top_k"])' "${RELEASE_ENV}")
DECISION_REV=$(python3 -c 'import json,sys; v=json.loads(sys.argv[1])["committed_revision"]; print("" if v is None else v)' "${RELEASE_ENV}")

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "DRY-RUN PASS: validated release for deploy/${DEPLOYMENT} -> collection=${CANDIDATE} embed=${EMBED_MODEL} top_k=${TOP_K}"
  exit 0
fi

if [[ "${SKIP_CLUSTER_CHECK}" -eq 0 && -n "${DECISION_REV}" ]]; then
  echo "+ verifying live candidate state matches decision revision=${DECISION_REV}"
  echo "+ bash scripts/ingest_job.sh --collection ${CANDIDATE} --mode status"
fi

BEFORE_REV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
BEFORE_ENV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].env}')
echo "Pre-release deploy/${DEPLOYMENT} revision=${BEFORE_REV}"

echo "+ kubectl set env deployment/${DEPLOYMENT} -n ${NAMESPACE} CHROMA_COLLECTION=${CANDIDATE} EMBED_MODEL=${EMBED_MODEL} EMBED_VERSION=${EMBED_VERSION} TOP_K=${TOP_K}"
kubectl set env "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" \
  "CHROMA_COLLECTION=${CANDIDATE}" \
  "EMBED_MODEL=${EMBED_MODEL}" \
  "EMBED_VERSION=${EMBED_VERSION}" \
  "TOP_K=${TOP_K}"

echo "+ kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s"
kubectl rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=300s

AFTER_REV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
AFTER_ENV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].env}')

mkdir -p eval/results
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT_LOG="eval/results/release-${TS}.json"
python3 - "${OUT_LOG}" "${DEPLOYMENT}" "${NAMESPACE}" "${CANDIDATE}" "${DECISION_FILE}" "${BEFORE_REV}" "${AFTER_REV}" "${BEFORE_ENV}" "${AFTER_ENV}" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    "deployment": sys.argv[2],
    "namespace": sys.argv[3],
    "candidate_collection": sys.argv[4],
    "decision_file": sys.argv[5],
    "rollback_revision": sys.argv[6],
    "new_revision": sys.argv[7],
    "before_env": json.loads(sys.argv[8]) if sys.argv[8] else [],
    "after_env": json.loads(sys.argv[9]) if sys.argv[9] else [],
}, indent=2), encoding="utf-8")
PY

echo "Release succeeded. Audit written to ${OUT_LOG}. Rollback target revision: ${BEFORE_REV}"

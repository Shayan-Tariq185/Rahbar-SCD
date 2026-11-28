#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/ingest_job.sh --collection NAME [--batch-dir DIR] [--snapshot-from NAME]
         [--mode ingest|count|restore|tombstone|status] [--doc-id ID] [--version V]
         [--namespace rahbar] [--image rahbar-indexer:dev] [--timeout 300]

Runs the single-writer ragops.ingest CLI inside a unique Kubernetes Job and waits for completion.
EOF
}

COLLECTION=""
BATCH_DIR=""
SNAPSHOT_FROM=""
MODE="ingest"
DOC_ID=""
VERSION=""
NAMESPACE="rahbar"
IMAGE="${INDEXER_IMAGE:-rahbar-indexer:dev}"
TIMEOUT=300
SHELL_POD="${RUNTIME_SHELL_POD:-runtime-shell}"
TEMPLATE="k8s/ragops-runtime/templates/ingest-job.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --collection) COLLECTION="$2"; shift 2 ;;
    --batch-dir) BATCH_DIR="$2"; shift 2 ;;
    --snapshot-from) SNAPSHOT_FROM="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --doc-id) DOC_ID="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --namespace|-n) NAMESPACE="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${COLLECTION}" ]]; then
  echo "ERROR: --collection is required" >&2
  usage >&2
  exit 2
fi

if [[ -n "${SNAPSHOT_FROM}" && "${MODE}" == "ingest" ]]; then
  MODE="snapshot"
fi

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "ERROR: Job template missing at ${TEMPLATE}" >&2
  exit 2
fi

REMOTE_BATCH="/datalake/inbox/active-${COLLECTION}"
if [[ "${MODE}" == "ingest" && -n "${BATCH_DIR}" ]]; then
  if [[ ! -d "${BATCH_DIR}" ]]; then
    echo "ERROR: --batch-dir '${BATCH_DIR}' does not exist" >&2
    exit 2
  fi
  TS_STAGE=$(date -u +%Y%m%dT%H%M%SZ)
  REMOTE_BATCH="/datalake/inbox/${COLLECTION}-${TS_STAGE}"
  echo "+ kubectl exec ${SHELL_POD} -n ${NAMESPACE} -- mkdir -p ${REMOTE_BATCH}"
  kubectl exec "${SHELL_POD}" -n "${NAMESPACE}" -- mkdir -p "${REMOTE_BATCH}"
  echo "+ kubectl cp ${BATCH_DIR}/. ${NAMESPACE}/${SHELL_POD}:${REMOTE_BATCH}/"
  kubectl cp "${BATCH_DIR}/." "${NAMESPACE}/${SHELL_POD}:${REMOTE_BATCH}/"
fi

case "${MODE}" in
  ingest)
    CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"run\", \"--collection\", \"${COLLECTION}\", \"--batch-dir\", \"${REMOTE_BATCH}\"]"
    ;;
  status)
    CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"status\", \"--collection\", \"${COLLECTION}\"]"
    ;;
  count)
    [[ -z "${DOC_ID}" ]] && { echo "ERROR: --doc-id required for count" >&2; exit 2; }
    CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"count\", \"--collection\", \"${COLLECTION}\", \"--doc-id\", \"${DOC_ID}\"]"
    ;;
  restore)
    [[ -z "${DOC_ID}" || -z "${VERSION}" ]] && { echo "ERROR: --doc-id and --version required for restore" >&2; exit 2; }
    CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"restore\", \"--collection\", \"${COLLECTION}\", \"--doc-id\", \"${DOC_ID}\", \"--version\", \"${VERSION}\"]"
    ;;
  tombstone)
    [[ -z "${DOC_ID}" ]] && { echo "ERROR: --doc-id required for tombstone" >&2; exit 2; }
    if [[ -n "${VERSION}" ]]; then
      CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"tombstone\", \"--collection\", \"${COLLECTION}\", \"--doc-id\", \"${DOC_ID}\", \"--version\", \"${VERSION}\"]"
    else
      CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"tombstone\", \"--collection\", \"${COLLECTION}\", \"--doc-id\", \"${DOC_ID}\"]"
    fi
    ;;
  snapshot)
    [[ -z "${SNAPSHOT_FROM}" ]] && { echo "ERROR: --snapshot-from required for snapshot" >&2; exit 2; }
    CLI_ARGS="[\"python\", \"-m\", \"ragops.ingest\", \"snapshot\", \"--snapshot-from\", \"${SNAPSHOT_FROM}\", \"--collection\", \"${COLLECTION}\"]"
    ;;
  *)
    echo "ERROR: Invalid --mode '${MODE}'" >&2
    exit 2
    ;;
esac

JOB_NAME="ragops-${MODE}-$(date +%s)-$$"
TMP_MANIFEST=$(mktemp)
trap 'rm -f "${TMP_MANIFEST}"' EXIT

sed \
  -e "s|__JOB_NAME__|${JOB_NAME}|g" \
  -e "s|__NAMESPACE__|${NAMESPACE}|g" \
  -e "s|__IMAGE__|${IMAGE}|g" \
  -e "s|__ARGS__|${CLI_ARGS}|g" \
  "${TEMPLATE}" > "${TMP_MANIFEST}"

echo "+ kubectl apply -f ${TMP_MANIFEST} (job/${JOB_NAME})"
kubectl apply -f "${TMP_MANIFEST}"

mkdir -p eval/results
printf '%s\n' "${JOB_NAME}" > eval/results/last-ingest.name

STATUS=0
if bash scripts/wait_job.sh "${JOB_NAME}" --namespace "${NAMESPACE}" --timeout "${TIMEOUT}"; then
  :
else
  STATUS=$?
fi

echo "+ kubectl logs job/${JOB_NAME} -n ${NAMESPACE}"
kubectl logs "job/${JOB_NAME}" -n "${NAMESPACE}"
exit ${STATUS}

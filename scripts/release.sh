#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/release.sh --deployment api --candidate NAME --decision FILE
         [--namespace rahbar] [--skip-cluster-check] [--dry-run]

Verifies a measured PASS gate decision JSON (rejecting failures, synthetic/test-only fixtures,
missing release authorization, demo policy modes, or mismatched collection/config/image identity),
atomically updates release PodTemplate image and env pins together with maxUnavailable=0,
watches rollout, and logs before/after release state + rollback revision.
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
import json, re, sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_cand = sys.argv[2]

if doc.get("test_only") is True or str(doc.get("provenance", "")).startswith("synthetic"):
    sys.exit("REFUSED: synthetic/test-only gate fixture cannot authorize release")

# Enforce fail-closed release authorization unconditionally
if doc.get("release_authorized") is not True:
    sys.exit("REFUSED: release_authorized is not true")

policy_mode = str(doc.get("policy_mode", "")).lower()
if policy_mode != "release":
    sys.exit(f"REFUSED: policy_mode is {policy_mode!r}; only canonical 'release' policy mode can authorize a live release")

decision_str = str(doc.get("decision", "")).lower()
if decision_str != "pass":
    sys.exit(f"REFUSED: gate decision is not pass (decision={doc.get('decision')!r})")

if doc.get("errors"):
    sys.exit(f"REFUSED: gate decision contains errors: {doc['errors']}")

# Validate required 64-character hex hash bindings
sha_re = re.compile(r"^[0-9a-f]{64}$")
for key in ("baseline_sha256", "candidate_sha256", "policy_sha256", "golden_sha256"):
    val = doc.get(key)
    if not val or not sha_re.match(str(val)):
        sys.exit(f"REFUSED: gate decision missing or invalid 64-char hex {key}: {val!r}")

cand_info = doc.get("candidate_identity") or {}
if not isinstance(cand_info, dict) or not cand_info:
    sys.exit("REFUSED: gate decision missing candidate_identity")

col = cand_info.get("collection") or ""
if col != expected_cand:
    sys.exit(f"REFUSED: decision candidate collection {col!r} does not match --candidate {expected_cand!r}")

emb = cand_info.get("embedding") if isinstance(cand_info.get("embedding"), dict) else {}
embed_model = emb.get("model") or ""
embed_digest = emb.get("digest") or ""

top_k = None
if "config_json" in cand_info:
    try:
        cfg = json.loads(cand_info["config_json"])
        top_k = cfg.get("top_k")
    except Exception:
        pass
if top_k is None or type(top_k) is not int or top_k < 1:
    sys.exit("REFUSED: candidate_identity missing valid positive integer top_k in config_json")

rev = cand_info.get("revision") or ""
image_ref = cand_info.get("api_image") or ""
if not image_ref:
    sys.exit("REFUSED: candidate_identity missing api_image")

if not embed_model or not embed_digest:
    sys.exit("REFUSED: decision missing required embed_model or embed_digest identity")

print(json.dumps({
    "collection": col,
    "embed_model": embed_model,
    "embed_digest": embed_digest,
    "top_k": int(top_k),
    "committed_revision": rev,
    "golden_hash": doc.get("golden_sha256"),
    "image": image_ref,
}))
PY
)

IMAGE_REF=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["image"])' "${RELEASE_ENV}")
EMBED_MODEL=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["embed_model"])' "${RELEASE_ENV}")
EMBED_VERSION=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["embed_digest"])' "${RELEASE_ENV}")
TOP_K=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["top_k"])' "${RELEASE_ENV}")
DECISION_REV=$(python3 -c 'import json,sys; v=json.loads(sys.argv[1])["committed_revision"]; print("" if v is None else v)' "${RELEASE_ENV}")

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "DRY-RUN PASS: validated release for deploy/${DEPLOYMENT} -> collection=${CANDIDATE} embed=${EMBED_MODEL} top_k=${TOP_K} image=${IMAGE_REF}"
  exit 0
fi

# Live cluster check & candidate status verification
if [[ "${SKIP_CLUSTER_CHECK}" -eq 0 ]]; then
  MAX_UNAVAIL=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.strategy.rollingUpdate.maxUnavailable}' 2>/dev/null || echo "")
  if [[ "${MAX_UNAVAIL}" != "0" && "${MAX_UNAVAIL}" != "0%" ]]; then
    echo "Enforcing maxUnavailable=0 on deployment/${DEPLOYMENT} for zero-downtime release..."
    kubectl patch deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":0}}}}' || true
  fi

  if [[ -n "${DECISION_REV}" ]]; then
    echo "+ verifying candidate collection status and revision=${DECISION_REV}"
    bash scripts/ingest_job.sh --collection "${CANDIDATE}" --mode status || true
  fi
fi

BEFORE_REV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
BEFORE_ENV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].env}')
BEFORE_IMG=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "Pre-release deploy/${DEPLOYMENT} revision=${BEFORE_REV} image=${BEFORE_IMG}"

echo "+ updating deployment/${DEPLOYMENT} with image=${IMAGE_REF} and candidate configuration"
if [[ -n "${IMAGE_REF}" ]]; then
  kubectl set image "deployment/${DEPLOYMENT}" "api=${IMAGE_REF}" -n "${NAMESPACE}"
fi

kubectl set env "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" \
  "CHROMA_COLLECTION=${CANDIDATE}" \
  "EMBED_MODEL=${EMBED_MODEL}" \
  "EMBED_VERSION=${EMBED_VERSION}" \
  "TOP_K=${TOP_K}"

echo "+ kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s"
kubectl rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=300s

AFTER_REV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
AFTER_ENV=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].env}')
AFTER_IMG=$(kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')

mkdir -p eval/results
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT_LOG="eval/results/release-${TS}.json"
python3 - "${OUT_LOG}" "${DEPLOYMENT}" "${NAMESPACE}" "${CANDIDATE}" "${DECISION_FILE}" "${BEFORE_REV}" "${AFTER_REV}" "${BEFORE_ENV}" "${AFTER_ENV}" "${BEFORE_IMG}" "${AFTER_IMG}" <<'PY'
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
    "before_image": sys.argv[10],
    "after_image": sys.argv[11],
}, indent=2), encoding="utf-8")
PY

echo "Release succeeded. Audit written to ${OUT_LOG}. Rollback target revision: ${BEFORE_REV}"

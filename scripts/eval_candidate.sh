#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Candidate configuration setup/runtime failure" >&2; exit 2' ERR
COLLECTION=""; TOP_K=""; CONTEXT=rahbar-a03
while [[ $# -gt 0 ]]; do
  case "$1" in
    --collection) [[ $# -ge 2 ]] || exit 2; COLLECTION="$2"; shift 2 ;;
    --top-k) [[ $# -ge 2 ]] || exit 2; TOP_K="$2"; shift 2 ;;
    --context) [[ $# -ge 2 ]] || exit 2; CONTEXT="$2"; shift 2 ;;
    --help|-h) echo 'Usage: eval_candidate.sh --collection NAME --top-k K [--context rahbar-a03]'; exit 0 ;;
    *) exit 2 ;;
  esac
done
[[ "$COLLECTION" =~ ^rahbar_[a-z0-9_]+$ && "$TOP_K" =~ ^[0-9]+$ && "$TOP_K" -ge 1 && "$TOP_K" -le 50 ]] || exit 2
[[ "$(kubectl config current-context)" == "$CONTEXT" ]] || { echo 'Unexpected context' >&2; exit 2; }
echo "+ kubectl set env deployment/api-candidate -n rahbar CHROMA_COLLECTION=$COLLECTION TOP_K=$TOP_K"
kubectl set env deployment/api-candidate -n rahbar "CHROMA_COLLECTION=$COLLECTION" "TOP_K=$TOP_K"
kubectl rollout status deployment/api-candidate -n rahbar --timeout=300s
kubectl get deployment api-candidate -n rahbar -o jsonpath='{.spec.template.spec.containers[0].env}'
printf '\nCandidate only; live Deployment api was not changed. Suite Job must verify runtime identity.\n'

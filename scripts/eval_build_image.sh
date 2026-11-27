#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Evaluation image setup/build failed" >&2; exit 2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
TAG=""; PROFILE=rahbar-a03; LOAD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) [[ $# -ge 2 ]] || exit 2; TAG="$2"; shift 2 ;;
    --profile) [[ $# -ge 2 ]] || exit 2; PROFILE="$2"; shift 2 ;;
    --load) LOAD=1; shift ;;
    --help|-h) echo 'Usage: eval_build_image.sh --tag SOURCE_SHA-m2 [--load --profile rahbar-a03]'; exit 0 ;;
    *) exit 2 ;;
  esac
done
[[ "$TAG" =~ ^[0-9a-f]{12,40}-m2$ ]] || { echo 'Use a unique SOURCE_SHA-m2 tag' >&2; exit 2; }
SHA="$(git rev-parse HEAD)"
[[ "$SHA" == "${TAG%-m2}"* ]] || { echo 'Tag must identify the current source commit' >&2; exit 2; }
if [[ "$LOAD" -eq 1 ]]; then
  echo "+ minikube -p $PROFILE image load rahbar-eval:$TAG"
  minikube -p "$PROFILE" image load "rahbar-eval:$TAG"
  exit 0
fi
PATHS=(ragops/evalsuite ragops/gate.py ragops/coverage.py eval/Dockerfile eval/requirements.txt config/schemas)
git diff --quiet HEAD -- "${PATHS[@]}" || { echo 'Commit evaluation image source before building' >&2; exit 2; }
[[ -z "$(git ls-files --others --exclude-standard -- "${PATHS[@]}")" ]] || { echo 'Uncommitted evaluation source files' >&2; exit 2; }
echo "+ docker build -f eval/Dockerfile --build-arg SOURCE_GIT_SHA=$SHA -t rahbar-eval:$TAG ."
docker build -f eval/Dockerfile --build-arg "SOURCE_GIT_SHA=$SHA" -t "rahbar-eval:$TAG" .
docker image inspect "rahbar-eval:$TAG" --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

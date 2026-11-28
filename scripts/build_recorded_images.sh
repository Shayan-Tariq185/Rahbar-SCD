#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${RAGOPS_PY:-python3}"
STAGE="$(mktemp -d)"
trap 'rm -rf -- "$STAGE"' EXIT
"$PY" -c 'import json; d=json.load(open("config/runtime-images.json")); [print(role,v["source_git_sha"],v["image"]) for role,v in d["images"].items()]' > "$STAGE/images.txt"
while read -r role sha image; do
  [[ "$sha" =~ ^[0-9a-f]{40}$ && "$role" =~ ^(api|indexer|eval)$ ]] || exit 2
  mkdir "$STAGE/$role"
  git archive "$sha" | tar -xf - -C "$STAGE/$role"
  case "$role" in
    api) docker build -f "$STAGE/$role/api/Dockerfile" -t "$image" "$STAGE/$role/api" ;;
    indexer) docker build -f "$STAGE/$role/indexer/Dockerfile" --build-arg CORPUS_SRC=eval/fixtures -t "$image" "$STAGE/$role" ;;
    eval) docker build -f "$STAGE/$role/eval/Dockerfile" --build-arg "SOURCE_GIT_SHA=$sha" -t "$image" "$STAGE/$role" ;;
  esac
  minikube -p "${PROFILE:-minikube}" image load "$image"
done < "$STAGE/images.txt"
docker build -t rahbar-ui:dev ui
minikube -p "${PROFILE:-minikube}" image load rahbar-ui:dev

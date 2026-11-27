#!/usr/bin/env bash
set -euo pipefail
RUN_ID=""; OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --help|-h) echo 'Usage: eval_results.sh --run-id ID --out DIR'; exit 0 ;;
    *) exit 2 ;;
  esac
done
[[ "$RUN_ID" =~ ^[a-z0-9-]+$ && -n "$OUT" ]] || exit 2
[[ ! -e "$OUT/$RUN_ID" ]] || { echo 'Refusing to overwrite an earlier export' >&2; exit 2; }
mkdir -p "$OUT"
printf '+ kubectl cp rahbar/eval-results-shell:/results/runs/%s %q\n' "$RUN_ID" "$OUT/$RUN_ID"
kubectl cp "rahbar/eval-results-shell:/results/runs/$RUN_ID" "$OUT/$RUN_ID"

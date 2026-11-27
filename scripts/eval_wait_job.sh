#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == --help ]]; then echo 'Usage: eval_wait_job.sh JOB [TIMEOUT_SECONDS]'; exit 0; fi
JOB="${1:?Job required}"; TIMEOUT="${2:-7200}"; START=$SECONDS
[[ "$JOB" =~ ^[a-z0-9-]+$ && "$TIMEOUT" =~ ^[0-9]+$ ]] || exit 2
while (( SECONDS - START < TIMEOUT )); do
  COMPLETE="$(kubectl get job "$JOB" -n rahbar -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')"
  FAILED="$(kubectl get job "$JOB" -n rahbar -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')"
  if [[ "$COMPLETE" == True ]]; then echo "Job $JOB Complete"; exit 0; fi
  if [[ "$FAILED" == True ]]; then echo "Job $JOB Failed"; kubectl describe job "$JOB" -n rahbar; exit 1; fi
  sleep 2
done
echo "Timed out waiting for Job $JOB" >&2
kubectl describe job "$JOB" -n rahbar
kubectl get pods -n rahbar -l "job-name=$JOB" -o wide
exit 2

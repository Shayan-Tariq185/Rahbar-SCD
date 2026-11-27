#!/usr/bin/env bash
set -euo pipefail
export RAGOPS_JOB_MODE=coverage
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/eval_job.sh" "$@"

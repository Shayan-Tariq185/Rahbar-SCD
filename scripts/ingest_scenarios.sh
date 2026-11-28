#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/ingest_scenarios.sh --scenario changed|deleted|restore --collection NAME

Executes self-made fixture proofs on a sandbox collection (refuses frozen rahbar_a/rahbar_ab)
using scripts/ingest_job.sh and prints before/after chunk counts and unaffected doc state.
EOF
}

SCENARIO=""
COLLECTION="rahbar_sandbox"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --collection) COLLECTION="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${SCENARIO}" ]]; then
  echo "ERROR: --scenario is required" >&2
  usage >&2
  exit 2
fi

if [[ "${COLLECTION}" == "rahbar_a" || "${COLLECTION}" == "rahbar_ab" ]]; then
  echo "ERROR: Refusing to mutate frozen collection '${COLLECTION}'. Use rahbar_sandbox." >&2
  exit 2
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/sandbox_alpha.md" <<'MD'
---
doc_id: sandbox-alpha
family_id: sandbox-alpha
title: Sandbox Alpha Policy (Synthetic Fixture)
doc_version: "2026-01"
date: "2026-01-10"
---
# Sandbox Alpha Policy (Synthetic Fixture)

## 1. Clause One
Synthetic baseline clause for testing incremental change without touching unaffected docs.
MD

cat > "${TMP_DIR}/sandbox_beta.md" <<'MD'
---
doc_id: sandbox-beta
family_id: sandbox-beta
title: Sandbox Beta Policy (Synthetic Fixture)
doc_version: "2026-01"
date: "2026-01-10"
---
# Sandbox Beta Policy (Synthetic Fixture)

## 1. Stable Clause
This document stays unchanged across all sandbox scenarios to verify unaffected preservation.
MD

echo "=== Seeding sandbox baseline (${COLLECTION}) ==="
bash scripts/ingest_job.sh --collection "${COLLECTION}" --batch-dir "${TMP_DIR}"
echo "=== Baseline status (unaffected doc = sandbox-beta) ==="
bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode status

case "${SCENARIO}" in
  changed)
    echo "=== Scenario: changed (updating sandbox-alpha while keeping sandbox-beta identical) ==="
    cat > "${TMP_DIR}/sandbox_alpha.md" <<'MD'
---
doc_id: sandbox-alpha
family_id: sandbox-alpha
title: Sandbox Alpha Policy (Synthetic Fixture)
doc_version: "2026-01"
date: "2026-01-10"
---
# Sandbox Alpha Policy (Synthetic Fixture)

## 1. Clause One
Synthetic baseline clause for testing incremental change without touching unaffected docs.

## 2. Added Clause Two
New synthetic clause added in place to confirm only sandbox-alpha chunks are embedded/updated.
MD
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --batch-dir "${TMP_DIR}"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode count --doc-id sandbox-alpha
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode count --doc-id sandbox-beta
    ;;

  deleted)
    echo "=== Scenario: deleted (explicit tombstone of sandbox-alpha) ==="
    echo "--- Before deletion count ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode count --doc-id sandbox-alpha
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode tombstone --doc-id sandbox-alpha
    echo "--- After deletion count (must be 0) ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode count --doc-id sandbox-alpha
    echo "--- Unaffected doc count (sandbox-beta) ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode count --doc-id sandbox-beta
    ;;

  restore)
    echo "=== Scenario: restore (supersede sandbox-alpha 2026-01 with 2027-01, then restore 2026-01) ==="
    cat > "${TMP_DIR}/sandbox_alpha.md" <<'MD'
---
doc_id: sandbox-alpha
family_id: sandbox-alpha
title: Sandbox Alpha Policy (Synthetic Fixture v2027)
doc_version: "2027-01"
date: "2027-01-10"
---
# Sandbox Alpha Policy (Synthetic Fixture v2027)

## 1. Clause One
Updated synthetic 2027 policy superseding 2026-01 so 2026-01 moves to archive.
MD
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --batch-dir "${TMP_DIR}"
    echo "--- Status before restore ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode status
    echo "--- Restoring archived 2026-01 ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode restore --doc-id sandbox-alpha --version "2026-01"
    echo "--- Status after restore ---"
    bash scripts/ingest_job.sh --collection "${COLLECTION}" --mode status
    ;;

  *)
    echo "ERROR: Unknown scenario '${SCENARIO}'" >&2
    exit 2
    ;;
esac

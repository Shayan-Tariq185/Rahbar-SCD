# Verification Report — `rahbar_b_verify` (run-1795878890-1)

- **Generated at**: 2026-11-28T15:14:58Z
- **Batch source**: `/datalake/inbox/rahbar_b_verify-20261128T151447Z`
- **Counters**: {"docs_seen": 13, "docs_unchanged": 0, "docs_indexed": 5, "docs_quarantined": 7, "docs_archived": 1, "chunks_seen": 13, "chunks_embedded": 13, "chunks_reused": 0, "chunks_deleted": 0, "doc_check_embeddings": 6, "chunk_embeddings": 13, "total_embeddings": 19}

| Doc ID | Version | Status / Decision | Quality | Completeness | Recency | Uniqueness | Reasons |
|---|---|---|---|---|---|---|---|
| `academic-rules` | `2027` | `index` | PASS: ok | PASS: ok | PASS: newer_version_supersedes:2026-06 | PASS: unique | all_checks_passed |
| `lab-safety-a` | `2026-09` | `index` | PASS: ok | PASS: ok | PASS: first_version_in_family | PASS: unique | all_checks_passed |
| `lab-safety-copy` | `2026-09` | `quarantine` | PASS: ok | PASS: ok | PASS: first_version_in_family | FAIL: exact_duplicate_of:lab-safety-a@2026-09 | uniqueness:exact_duplicate_of:lab-safety-a@2026-09 |
| `lab-safety-near-dup` | `2026-09` | `quarantine` | PASS: ok | PASS: ok | PASS: first_version_in_family | FAIL: near_duplicate_of:lab-safety-a@2026-09 (cosine=0.9839 >= 0.95) | uniqueness:near_duplicate_of:lab-safety-a@2026-09 (cosine=0.9839 >= 0.95) |
| `corrupt-scan-doc` | `2026-10` | `quarantine` | FAIL: extraction_failed: PdfminerException: No /Root object! - Is this really a PDF? | FAIL: not_executable: upstream quality/extraction check failed | FAIL: not_executable: upstream quality/completeness check failed | FAIL: skipped: upstream quality/completeness check failed | quality:extraction_failed: PdfminerException: No /Root object! - Is this really a PDF? |
| `garbled-text-doc` | `2026-10` | `quarantine` | FAIL: too_short (18 chars < 30) | FAIL: not_executable: upstream quality/extraction check failed | FAIL: not_executable: upstream quality/completeness check failed | FAIL: skipped: upstream quality/completeness check failed | quality:too_short (18 chars < 30) |
| `missing-meta-doc` | `` | `quarantine` | PASS: ok | FAIL: missing_required_metadata: title, date_or_version | FAIL: not_executable: upstream quality/completeness check failed | FAIL: skipped: upstream quality/completeness check failed | completeness:missing_required_metadata: title, date_or_version |
| `truncated-hostel-doc` | `2026-10` | `quarantine` | PASS: ok | FAIL: truncated_page_count: got 1, expected 4 | FAIL: not_executable: upstream quality/completeness check failed | FAIL: skipped: upstream quality/completeness check failed | completeness:truncated_page_count: got 1, expected 4 |
| `academic-rules` | `2021` | `archive` | PASS: ok | PASS: ok | FAIL: older_than_active_version:2027 (candidate=2021); routed to archive with superseded=true | FAIL: skipped: recency rejected older version to archive | recency:older_than_active_version:2027 (candidate=2021); routed to archive with superseded=true |
| `campus-network-policy` | `2027-01` | `index` | PASS: ok | PASS: ok | PASS: first_version_in_family | PASS: unique | all_checks_passed |
| `library-loan-policy` | `2027-01` | `index` | PASS: ok | PASS: ok | PASS: first_version_in_family | PASS: unique | all_checks_passed |
| `exam-conduct-policy` | `2027-01` | `index` | PASS: ok | PASS: ok | PASS: first_version_in_family | PASS: unique | all_checks_passed |
| `lab-safety-second-copy` | `2026-09` | `quarantine` | PASS: ok | PASS: ok | PASS: first_version_in_family | FAIL: exact_duplicate_of:lab-safety-a@2026-09 | uniqueness:exact_duplicate_of:lab-safety-a@2026-09 |

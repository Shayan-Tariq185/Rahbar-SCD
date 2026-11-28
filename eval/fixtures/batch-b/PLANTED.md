# Batch B Planted Test Fixtures

All files in this directory are self-made synthetic fixtures (`>=10` documents) for Assignment 03 Part A1/A2/D4 verification.

| File | Doc ID | Version | Expected Decision | Notes |
|---|---|---|---|---|
| `b01_academic_rules_2027.md` | `academic-rules` | `2027` | `INDEX (supersedes older active version in family)` | Newer version of academic-rules family with synthetic 82% attendance & 2.10 CGPA. |
| `b02_lab_safety_a.md` | `lab-safety-a` | `2026-09` | `INDEX (first unique copy)` | Canonical valid document for exact & near duplicate comparison. |
| `b03_lab_safety_copy.md` | `lab-safety-copy` | `2026-09` | `QUARANTINE (exact_duplicate)` | Byte-for-byte identical text to b02_lab_safety_a.md under different filename/doc_id. |
| `b04_lab_safety_near_dup.md` | `lab-safety-near-dup` | `2026-09` | `QUARANTINE (near_duplicate)` | Single-word edits vs b02_lab_safety_a.md; different hash, high cosine similarity. |
| `b05_corrupt_scan.pdf` | `corrupt-scan-doc` | `2026-10` | `QUARANTINE (quality extraction failure)` | Malformed PDF bytes causing extractor error without crashing job. |
| `b06_garbled_text.md` | `garbled-text-doc` | `2026-10` | `QUARANTINE (quality garbled/short)` | Replacement characters and non-printable control characters. |
| `b07_missing_metadata.md` | `missing-meta-doc` | `` | `QUARANTINE (completeness missing metadata)` | Valid body text but intentionally missing title and date/doc_version metadata. |
| `b08_truncated_policy.md` | `truncated-hostel-doc` | `2026-10` | `QUARANTINE (completeness truncated)` | Contains truncation marker and expected_pages=4 vs actual 1. |
| `b09_academic_rules_2021.md` | `academic-rules` | `2021` | `ARCHIVE (recency older_than_active, superseded=true)` | Older version of academic-rules arriving after 2026/2027; archived not quarantined. |
| `b10_campus_network_injected.md` | `campus-network-policy` | `2027-01` | `INDEX (valid distinct doc; D4 retrieval guardrail must sanitize injection)` | Plausible valid document with embedded prompt-injection directive for D4 testing. |
| `b11_library_loan_2027.md` | `library-loan-policy` | `2027-01` | `INDEX (clean filler)` | Distinct valid library fixture. |
| `b12_exam_conduct_2027.md` | `exam-conduct-policy` | `2027-01` | `INDEX (clean filler)` | Distinct valid examination conduct fixture. |
| `b13_lab_safety_second_copy.md` | `lab-safety-second-copy` | `2026-09` | `QUARANTINE (second exact_duplicate)` | Second byte-for-byte duplicate of the canonical b02 lab document. |

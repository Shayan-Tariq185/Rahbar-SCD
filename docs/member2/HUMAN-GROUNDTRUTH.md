# Human golden questions: source and retrieval references

The user supplied these eight final questions and explicitly attributed questions 1-4
to Member 1 and 5-8 to Member 2. Their wording is preserved in
`eval/human_questions.jsonl` and merged once into `eval/golden.jsonl`. Member identities
use the existing Git identities Mahrukh Masroor and Shayan-Tariq185. The earlier pending
draft is not an approved evaluation input.

All eight questions are answerable from checksum-verified source PDFs. Printed page
numbers and physical PDF page numbers differ. No answer or review was invented for a
human author. The source checks below are agent checks, not human synthetic reviews.

| ID | Source PDF | Printed page | Physical evidence page | Retrieval ground truth |
| --- | --- | --- | --- | --- |
| human-1-1 | Academic Rules 2026 | 3 | 9 | p9, rule 1.20 |
| human-1-2 | Academic Rules 2026 | 4 | 10 | p10, rule 1.21 |
| human-1-3 | Academic Rules 2026 | 4 | 10 | p10, rule 1.22 |
| human-1-4 | Academic Rules 2026 | 4 | 10 | p10, rule 1.25 |
| human-2-1 | Academic Rules 2026 | 6 | 12 | p12, rules 2.4 and 2.5 |
| human-2-2 | Academic Rules 2026 | 6-7 | 12-13 | p12, rule 2.7, whose chunk includes its continuation |
| human-2-3 | Student Handbook 2026 | 3 | 11 | p11, item 12. |
| human-2-4 | Student Handbook 2026 | 5 | 13 | document/version/p13; no guessed section annotation |

## Why the cross-page cases differ

The preserved A02 chunker stores the first page of a chunk. A read-only check using its
extract/clean/chunk functions on the relevant original PDF page windows confirmed that
rule 2.7's lower-repeat-grade answer is in a chunk starting on PDF page 12. Counting page
13 as a second required clause would invent a second retrieval target for one clause.

For the plagiarism passage, visible-page text and the preserved extraction path assign
different section labels. The production extraction window produced answer-containing
chunks with page metadata 12 and 13 under a preceding item's label. The final reference
therefore retains the user's correct evidence page 13 and deliberately uses page-level
ground truth. Assignment B requires document and page; section/chunk annotations are
optional precision. The evaluator still requires exact document, version and page, and
enforces section/chunk identity whenever supplied. It does not globally ignore clauses.

These were local read-only extraction/chunk inspections, not ingestion Jobs, vector-store
queries or retrieval measurements. Member 1 must confirm document IDs, physical page
metadata and extraction/chunk fingerprints against the actual runtime before golden v1
is frozen. M2 did not modify the A02 indexer/extractor to make these references fit.

## Actual review state

The user explicitly accepted synthetic q01-q04 in chat after seeing the question wording
and source fact summaries. Four accept decisions are recorded with that exact provenance;
no individual reasons are attributed to the user. The reply `Ok` to the request for partner
reviews is an acknowledgement, not acceptance by the partner. No partner decisions are
recorded. Her actual q05-q08 reviews remain pending; see SYNTHETIC-REVIEW.md.

Current dataset: 36 questions, 31 answerable, five unanswerable, seven hard, eight human
questions and four accepted synthetic reviews. Full validation must still reject it until
the partner's four genuine synthetic reviews are supplied. Faithfulness labels are a
separate later task on real generated answers and their exact contexts.

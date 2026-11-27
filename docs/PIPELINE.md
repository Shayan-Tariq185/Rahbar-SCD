# Indexing and retrieval pipeline

## Extraction
The 2023 undergraduate rules PDF required OCR on pages whose text layer contained fewer
than 40 non-whitespace characters. OCR was cached under `/tmp/rahbar-extract` during
local runs. The pipeline uses pdfplumber tables first, then removes table objects from
the page before reading running text.

For the Student Handbook page 25 table, the naive extractor interleaved the library
loan columns and nearby prose. The pipeline preserves each row with its header labels,
for example `Undergraduate: 04 | Renew Period: 02 | Loan Limit: 02 Weeks`, before
cleaning. Some scanned glyphs remain imperfect; OCR quality depends on Tesseract.

## Cleaning
Cleaning normalises tabs and repeated spaces, joins alphabetic hyphenated line breaks,
removes standalone page-number lines, and removes short repeated edge lines appearing
on more than half of the pages. Numbered clause headings are deliberately preserved,
including `1.21`, because they are required for section-aware chunking and citations.

## Chunking
The shipped configuration is 400 words with 50 words of overlap. Words are whitespace
separated; the 2026 local index produced 860 chunks across six documents. Chunk ids are
stable document-position ids and each chunk stores source, section, page, doc_version,
and superseded metadata.

| Size (tokens) | Overlap (tokens) | recall@5 | Chunks stored |
| --- | --- | --- | --- |
| 200 | 20 | 0.154 | 1022 |
| 400 | 50 | 0.154 (hashing-384 provisional run) | 860 |
| 600 | 100 | 0.154 | 819 |

## Embedding
The local reproducible run used `hashing-384`, dimension 384. The pin is
`EMBED_MODEL`, read by both `indexer/pipeline/config.py` and `api/app/config.py`.
The index records `embed_model` and `dimension` in Chroma metadata; the store recreates
the collection when either changes. A final production run should use
`nomic-embed-text` rather than the deterministic CI embedder.

## Semantic cache
No semantic cache was shipped in this Track B implementation. The API therefore does
not claim cache hits or cache thresholds; cache implementation belongs to the partner's
Track A work.

## Evaluation method
`eval/run_eval.py` matches each golden `(source, section)` pair against the top-k
retrieved passages. A section matches exactly or when the retrieved section starts
with the golden section plus a space, so golden `5.4` matches
`5.4 Academic Warning`. Citation validity requires an exact source, section, and page
tuple in the retrieved list. The provisional hashing-384 baseline passed the abstention
gate only after setting `RELEVANCE_FLOOR=0.40`; its recall should not be treated as the
final semantic-model result.

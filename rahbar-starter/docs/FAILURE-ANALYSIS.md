# Failure analysis

## Stage A · extraction without OCR
- **What we broke:** Disabled the OCR fallback in `indexer/pipeline/extract.py`.
- **Symptom:** Scanned pages from the 2023 rules document produced empty or nearly empty
  chunks, so attendance clauses were missing from retrieval.
- **Diagnosis, as if we had not caused it:** Extraction output shows pages with no text
  while the document page count remains normal. Comparing `pipeline.stats` output with
  and without OCR exposes the missing clause.
- **Remedy:** Restore the less-than-40-visible-character check and the pdf2image plus
  pytesseract fallback, retaining `Page.ocr=True`.

## Stage E · superseded-document filter
- **What we broke:** Removed `where={"superseded": False}` for ordinary retrieval.
- **Symptom:** A current-policy question could return the older 2023 policy even when
  the 2026 policy was intended.
- **Diagnosis, as if we had not caused it:** Retrieval responses show an old source or
  doc_version among top results for an unqualified question; Chroma metadata identifies
  the stale chunk with `superseded: true`.
- **Remedy:** Keep the superseded filter for ordinary questions and bypass it only when
  the question explicitly mentions a year or old/previous/superseded wording.

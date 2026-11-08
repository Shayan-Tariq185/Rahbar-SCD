# Corpus

Source: FAST-NUCES (NUCES) public website · Documents: 6 · Pages: 274

Downloaded with `make fetch` from `corpus/sources.yaml`; per-file URL, size and SHA-256 are in `corpus/MANIFEST.md`. The PDFs are not committed (`corpus/raw/` is gitignored).

| Document | Pages | `doc_version` | `superseded` | Text layer |
| --- | ---: | --- | --- | --- |
| Undergraduate Academic Rules (Aug 2023) | 26 | 2023-08 | true | almost none: 22 words, 3 fonts (scanned) |
| Academic Rules Handbook (Jun 2026) | 58 | 2026-06 | false | yes (9,669 words) |
| Student Handbook (Jun 2026) | 64 | 2026-06 | false | yes (11,053 words) |
| Annual Report 2023-24 | 85 | 2023-24 | false | yes (28,854 words) |
| Annual Report 2019-20 | 33 | 2019-20 | false | yes (7,057 words) |
| Faculty Entrepreneurship and Technical Start-ups Policy | 8 | 2022-05 | false | none: 0 words, 0 fonts (scanned) |

| # | Required property | Document(s) that provide it | Evidence or notes |
| --- | --- | --- | --- |
| 1 | At least 6 documents, 40 pages | All six | 6 documents, 274 pages (58 + 33 + 85 + 8 + 64 + 26), counted with `pdfinfo`. |
| 2 | Two versions of one policy | Undergraduate Academic Rules Aug 2023 (old) and Academic Rules Handbook Jun 2026 (current) | The 2023 file has `doc_version: "2023-08"`, `superseded: true`; the 2026 file has `"2026-06"`, `false`. The flags are written to `corpus/raw/_index.json` by `fetch.py` and read by the indexer, then stored as chunk metadata. The retriever filters on `superseded=false`. Note the 2023 version is scanned, so its text exists only after OCR. |
| 3 | Scanned, image-only PDF | Faculty Entrepreneurship and Technical Start-ups Policy (also the 2023 rules) | `pdftotext` returns 0 words and `pdffonts` lists 0 fonts for the policy. The 2023 rules return 22 words and 3 fonts across 26 pages (essentially image-only). Both need OCR. |
| 4 | A table with real information | Student Handbook (Jun 2026), page 33 | Library loan table: patron group (PhD, Graduate, Undergraduate), loan limit, renewals, loan period, fine rate (PKR 10/item/day), fine ceiling (PKR 5,000). pdfplumber extracts it as clean rows; the plain-text view interleaves it with the neighbouring column. |
| 5 | Long definitions | Student Handbook (Jun 2026) | "Policy on Generative AI Based Tools" (section XII), the Plagiarism list (which includes using generative AI tools to generate content) and "Harassment means and includes ...". A fixed-size chunker can cut these mid-definition. |
| 6 | A deliberately absent topic | Not in the corpus: hostel and transport facilities | The prospectus "Transport and Hostel Facilities" PDF was left out on purpose. Students plausibly ask about hostels and transport, so the golden set asks about them and expects the system to abstain. |
| 7 | Exact-term content | Academic Rules Handbook (Jun 2026) | Clause 1.21 (100% attendance required, shortfall may be condoned by the HoD), clause 1.22 (consequence of failing attendance), grade `FA` ("Fail due to shortage of attendance"), and the Academic Warning / Probation section. Student Handbook has the PKR 5,000 fine ceiling. |

Documents considered and dropped: the Prospectus academic rules PDF (it repeats the 2026 rules with different clause numbers, which would make retrieval targets ambiguous) and the HTML fee and grading pages (they would need an HTML extractor and add little the PDFs do not already cover).

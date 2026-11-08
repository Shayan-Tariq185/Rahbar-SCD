# ADR 0002: Structure-aware word chunking

## Status
Accepted · 2026-11-08

## Context
The corpus contains numbered clauses, long definitions, OCR text, and tables. A fixed
character split can separate a clause heading from its answer or split a table row from
its headers, which harms both retrieval and citation validity.

## Decision
Split documents at headings and numbered clauses, then pack paragraphs and sentences
using whitespace-separated words. Ship 400 words with 50 words of overlap. Each chunk
keeps its section, first page, document version, and superseded flag, and receives a
stable document-position id. Table rows remain atomic units.

## Options considered
We measured 200/20, 400/50, and 600/100 on the six-document corpus using the
deterministic `hashing-384` embedder. They produced 1022, 860, and 819 chunks
respectively, with recall@5 of 0.154 for each provisional run. The 400/50 setting was
chosen as the middle storage cost and a safer context size for generation. A future
semantic-model run should repeat the experiment before changing the shipped setting.

## Consequences
Section-aware chunks improve citation targeting and preserve definitions, but overlap
increases storage and repeated context. Word counts are simple and deterministic, but
they are only an approximation of model token counts. The implementation is in
`indexer/pipeline/chunk.py`.

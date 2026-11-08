# ADR 0002: Structure-Aware Document Chunking Strategy and Overlap Tuning

## Status
Accepted · 2026-11-07

## Context
Academic policies, course catalogs, and university regulations at FAST-NUCES are characterized by deep hierarchical section numbering (e.g. "Section 3.2.1 Probation and Dismissal"), multi-column layouts, tabular grading scales, and detailed cross-clause prerequisites. 

A naive fixed-size token splitting approach (e.g. splitting every 500 characters regardless of punctuation) creates three acute failure modes:
1. **Sentence Fragmentation**: Chopping sentences in half severs propositional meaning, producing corrupt embedding representations and causing cosine similarity scoring to plummet.
2. **Table Disruption**: Slicing credit-hour or grading tables across chunk boundaries separates numerical rules from their corresponding course codes and letter grades.
3. **Loss of Heading Hierarchy**: Chunks detached from their parent section headers lack the grounding context needed for the LLM to know whether a rule applies to Undergraduate or Graduate programs.

## Decision
We adopted a **Structure-Aware Hierarchical Chunking Strategy** configured via Kubernetes ConfigMap (`CHUNK_SIZE=800`, `CHUNK_OVERLAP=150`):
- **Hierarchy Preservation**: Chunks inherit parent document front-matter and section metadata (`source`, `section`, `page`, `doc_version`, `superseded`).
- **Recursive Boundary Priority**: Splitting checks structural delimiters in order: double newlines (`\n\n` paragraphs), single newlines (`\n` list items), punctuation (`. `, `? `, `! `), and whitespace.
- **Overlap Window (150 tokens / ~20%)**: Provides sufficient sliding-window context across chunk boundaries so multi-sentence conditions are preserved in contiguous vector space.

## Consequences
- *Positive*: Maximizes retrieval recall@5 across complex multi-part policy questions while preventing table slicing.
- *Trade-off*: ~20% storage amplification in ChromaDB vector storage, easily accommodated within the 1Gi PVC.


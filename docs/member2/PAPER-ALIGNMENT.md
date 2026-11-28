# Paper alignment review

Reviewed 2026-11-27. The supplied paper was read in full: 19 PDF pages, including
Figures 2 and 3, Tables 1 and 2, both use cases and the closing declarations. Figure 2
(p4), Figure 3 (p8), Table 1 (p10) and Table 2 (p13) were also checked visually.
The five-page Assignment 03 PDF was reread alongside it. Document contents were treated
as source material, not instructions overriding the user's request or ownership rules.

## Reference

Xiwei Xu, Hans Weytjens, Dawen Zhang, Qinghua Lu, Ingo Weber and Liming Zhu. 2026.
RAGOps: Operating and Managing Retrieval-Augmented Generation Pipelines. Preprint,
19 pages. SSRN abstract 7353461: https://ssrn.com/abstract=7353461.
The supplied PDF describes itself as not peer reviewed. Its SHA-256 is
`ad5f8bcbcdcdef8e39ff760fa9796a519171e5a18bfd4be69d7293f46bdc3ec1`.
The source PDF is retained at the user-provided location and is not added to the repository.

## Findings against the implementation

| Paper reference | Assignment/project implementation | Assessment and limits |
| --- | --- | --- |
| Sections 3.2 and 4; Figure 3 p8 | Separate serving path and writer ingestion Jobs; seven data-management stages mapped in report | Design aligns. Runtime integration and actual stage evidence remain pending. Ordinary CI/CD supplies the software lifecycle above the data loop. |
| Sections 4.2.1-4.2.4, pp9-10 | Verification before chunking, versioned raw/archive/quarantine state, incremental chunk/vector updates | M1-owned implementation and run evidence. Rejected versions and infrastructure failures must remain distinguishable. |
| Section 4.2.5; Table 1 p10 | Embedding cosine/timing/determinism; retrieval recall/MRR/nDCG and noise; answer faithfulness/citations/abstention/latency | Three-level design aligns. Table 1 gives example metrics, not a requirement to implement every benchmark or BLEU/ROUGE/BERTScore. Actual A03 scores are not yet measured. |
| Section 4.2.5 p11; section 6.2 p14 | Whole suite twice, fixed seeds, raw evidence and per-metric variation | Seeds reduce variability, not proof of determinism. Metric definitions, denominators, judge calibration and dataset identities must be reported. |
| Sections 4.1(d), 4.2.5 and 4.2.6 | Baseline/candidate comparisons, original-policy release gate, candidate Deployment and controlled rollout/undo | Concrete Kubernetes/configuration mechanisms come from Assignment C/F, not a numerical release policy prescribed by the paper. Integration/evidence pending. |
| Section 4.2.7, pp11-12 | Nearest-golden query embedding cosine; separate cutoff/floor; uncovered topics and golden v2 | Matches the paper's query-coverage option. Coverage does not prove that source documents answer a query. Retrieval/generation/vocabulary coverage are broader options not implemented by this query-only checker. |
| Sections 3.2.3 and 5.1; Table 2 p13 | Guardrail events, retrieval relevance, context-support evaluation, complete query trace/reconstruction, resource sampling | The report needed more specific mappings. Current corrections name those measures and disclose unmeasured toxicity/usefulness scores and bandwidth. |

## Corrections made to the report builder and new draft

- Kept the seven mandatory Figure 3 data stages and added concrete file paths where the
  old table gave only an architectural description. Assignment G explicitly requests
  those seven stages; it does not require another seven-row DevOps table.
- Corrected Table 2 observability to cover retrieval injection/relevance and generation
  context adherence, rather than only generic runtime failures.
- Corrected Table 2 reliability to include measured resource usage, rather than only
  rollout/persistence. Rollout and rollback remain additional Assignment F evidence.
- Retained traceability's version/routing/grounded-source chain and exact prompt/context
  reconstruction; monitoring remains based on predefined quality/latency/change metrics.
- Replaced the unverified paper-reference placeholder with the supplied paper's exact
  authors, title, preprint status, identifier and relevant page numbers.
- Clarified that the paper's 85 percent coverage example is an aggregate floor, not a
  required cosine similarity score. Both local thresholds still need justification.

## Scope boundaries and report limitations

Paper section 4.2.2 lists quality, completeness, recency, consistency and uniqueness.
Assignment A1 explicitly requires four: quality, completeness, recency and uniqueness.
Automated contradiction/consistency detection is therefore a disclosed paper extension,
not a newly imposed implementation requirement. Duplicate detection does not prove
contradiction detection.

The paper also discusses active human experts as retrieval sources, multimodal inputs,
knowledge graphs, retrieval-interleaved generation, shadow testing and user A/B tests.
Those are not all required by this assignment. Human golden questions/reviews do not
constitute runtime human-in-the-retrieval. Batch A versus A+B data drift is not the
paper's user A/B deployment experiment. The assignment's forty-query log is simulated
usage, and must not be reported as observations from real production users.

The paper recommends keeping old-domain tests while extending tests for new domains.
This project's fixed golden v1 comparison followed by a separate v2 expansion preserves
that backward check and avoids changing the benchmark during a drift comparison.

No paper reading creates missing experiment evidence. The four pending partner reviews,
real answer/context faithfulness labels, runtime contract integration, Kubernetes runs,
measurements, screenshots and evidence-based short answers remain outstanding.
The new `report/Assignment03_Report_PaperAligned_Draft.docx` preserves Student 1/Student 2
placeholders and pending result fields. The earlier editable template is left unchanged.

These changes affect the report builder/documentation only. No A02 serving/indexing code,
M1-owned runtime files, evaluator/gate/coverage algorithms or thresholds were changed.

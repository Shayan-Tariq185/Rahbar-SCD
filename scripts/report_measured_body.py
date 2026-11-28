"""Eight report pages populated from explicit, validated measured artifacts."""
from __future__ import annotations

from collections import Counter


def build(inputs, artifacts, p, table, page_break):
    def number(value, digits=4):
        return 'Pending' if value is None else f'{value:.{digits}g}'

    def metric(name, level, key, repeat=0):
        source = artifacts.get(name)
        return source['runs'][repeat][level][key]['value'] if source else None

    def text(key, default='Pending measured evidence'):
        return inputs.get('narratives', {}).get(key, default)

    pages = []
    page = p('RAHBAR Assignment 03 RAGOps Report', 'Title')
    page += table(['Student', 'Roll number', 'Responsibility'],
                  [[s['name'], s['roll'] or '________________', s['role']] for s in inputs['students']],
                  [2700, 2100, 4560])
    page += p(text('outcome'))
    page += p('Architecture and Figure 3 mapping', 'Heading1')
    page += p('The completed Assignment 02 indexing and query paths are retained. A single ingestion writer verifies and versions documents on persistent storage, then updates Chroma. The API retrieves, sanitizes evidence, generates and validates citations. Evaluation uses that same production path with fresh requests and answer-cache bypass.')
    page += table(['Figure 3 stage', 'Pipeline and file', 'Remaining limitation'], [
        ['Ingest', 'Writer Job; ragops/ingest.py', 'Source metadata must accompany uploads'],
        ['Verify', 'Four checks before chunking; ragops/verify.py', 'Truncation and near-duplicate checks are heuristic'],
        ['Update data lake', 'Originals, quarantine, archive and SQLite; ragops/state.py', 'Single-node lock; no distributed transaction'],
        ['Update retrieval sources', 'Incremental chunks/vectors and committed pins; ragops/ingest.py', 'Mutable ingestion is not an atomic multi-store transaction'],
        ['Offline testing', 'Three levels and two repeats; ragops/evalsuite/runner.py', 'Small golden set and human calibration sample'],
        ['Live testing', 'Simulated queries, traces and metrics; API and ragops/trace.py', 'Simulated usage is not production traffic'],
        ['Check coverage', 'Nearest-golden cosine; ragops/coverage.py', 'Test-question coverage does not prove answerability'],
    ], [1700, 3900, 3760])
    page += p('The mapping uses Figure 3 of the supplied 2026 paper, p8. Immutable collections separate baseline, data drift and candidate experiments. The original A02 collection is preserved.')
    pages.append(page)

    page = p('Document verification and lifecycle results', 'Heading1')
    verification = artifacts.get('verification_b', {})
    counters = verification.get('counters', {})
    caught = Counter()
    for doc in verification.get('documents', []):
        for check, outcome in doc.get('checks', {}).items():
            reason = str(outcome.get('reason', ''))
            if not outcome.get('passed') and not reason.startswith(('skipped', 'not_executable')):
                caught[check] += 1
    page += table(['Check', 'Before chunking', 'Batch B failures'], [
        ['Quality', 'Empty, garbled or failed extraction', str(caught['quality']) if verification else 'Pending'],
        ['Completeness', 'Source/title/date or version/pages and truncation checks', str(caught['completeness']) if verification else 'Pending'],
        ['Recency', 'Family/version lineage; older valid versions archived', str(caught['recency']) if verification else 'Pending'],
        ['Uniqueness', 'Exact content hash and pinned-model near-duplicate cosine', str(caught['uniqueness']) if verification else 'Pending'],
    ], [1600, 5860, 1900])
    page += p('Batch B outcomes: ' + (', '.join(f'{key}={counters.get(key, "Pending")}' for key in
                    ('docs_seen', 'docs_indexed', 'docs_quarantined', 'docs_archived')) if verification else 'Pending'))
    page += p(text('batch_b'))
    page += p('Incremental and version proofs', 'Heading2')
    page += p(text('unchanged'))
    page += p(text('changed_deleted_restore'))
    page += p('The Batch A PDFs were accepted only after matching the six recorded source hashes. Cropping to physical PDF bounds corrected hidden facing-page text; the active documents retain real page/section metadata. All golden references were checked against the resulting chunks before evaluation.')
    page += p('Storage and consistency', 'Heading2')
    page += p('Originals, quarantine, archive and state reside on the data-lake PVC. Snapshot collections copy their own originals, so archiving in A+B cannot move Batch A files. All vector mutations use ingestion/admin Jobs and a shared file lock. Failed setup attempts and recovery evidence are retained; a document rejection is distinct from an infrastructure failure.')
    pages.append(page)

    page = p('Three level offline evaluation', 'Heading1')
    rows = []
    for level, names in (
        ('module', ['paraphrase_cosine_mean', 'unrelated_cosine_mean', 'cosine_gap', 'embedding_ms_per_chunk', 'identical_text_max_difference']),
        ('component', ['recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5']),
        ('e2e', ['faithfulness', 'abstention_correctness', 'citation_validity', 'latency_p50_ms', 'latency_p95_ms', 'judge_human_agreement'])):
        for key in names:
            a, b = metric('baseline_a', level, key), metric('baseline_a', level, key, 1)
            rows.append([key.replace('_', ' '), number(a), number(b), number(b-a if a is not None and b is not None else None)])
    page += table(['Metric', 'Run 1', 'Run 2', 'Delta'], rows, [4860, 1500, 1500, 1500])
    page += p('Cosines use cosine units; rates/ranks use fractions; times use milliseconds. Delta is run 2 minus run 1. Embedding determinism is the largest coordinate difference for identical text. Every metric delta and absolute variation is also retained in the JSON and summary.')
    base = artifacts.get('baseline_a')
    noise = []
    if base:
        for key in ('recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5'):
            noise.append([key.replace('_', ' ')] + [number(run['noise_deltas'][key]['delta']) for run in base['runs'][:2]])
    page += table(['Typo noise minus clean', 'Run 1 delta', 'Run 2 delta'], noise or [['Pending', '', '']], [4860, 2250, 2250])
    page += p(text('evaluation_method'))
    page += p(text('judge_calibration'))
    pages.append(page)

    page = p('Controlled pipeline change and release', 'Heading1')
    rows = []
    for label, key in [('Baseline', 'change_baseline'), ('Poor candidate', 'candidate_bad'), ('Changed candidate', 'candidate_good')]:
        source = artifacts.get(key)
        rows.append([label, str(source['config']['top_k']) if source else 'Pending',
                     number(metric(key, 'component', 'recall_at_5')), number(metric(key, 'e2e', 'faithfulness')),
                     number(metric(key, 'e2e', 'citation_validity')), number(metric(key, 'e2e', 'latency_p95_ms'))])
    page += table(['Target', 'Top k', 'Recall 5', 'Faithful', 'Citations', 'p95 ms'], rows, [2160, 800, 1600, 1600, 1600, 1600])
    page += p(text('experiment_control'))
    page += p('Original policy frozen before candidate outcomes', 'Heading2')
    page += p(text('gate_policy'))
    gate_rows = []
    for key in ('gate_bad', 'gate_good'):
        gate = artifacts.get(key)
        gate_rows.append([key.replace('_', ' '), gate['decision'] if gate else 'Pending',
                          str(gate['release_authorized']) if gate else 'Pending'])
    page += table(['Measured gate', 'Decision', 'Release authorized'], gate_rows, [3960, 2400, 3000])
    page += p(text('gate_decision'))
    page += p('Kubernetes release and reversal', 'Heading2')
    page += p(text('release'))
    page += p(text('rollback'))
    page += p('A failed candidate is never released. The separate rollback fault is an explicitly controlled operator test, not the rejected candidate. Image and configuration pins change together; rollback is verified with a new cache-bypassed trace.')
    pages.append(page)

    page = p('Traceability and operational qualities', 'Heading1')
    page += table(['Table 2 quality', 'Measure and threshold', 'Evidence'], [
        ['Adaptability', 'Versioned source and top-k changes; recall loss no more than 0.02', 'Incremental/version Jobs and controlled comparison'],
        ['Monitorability', text('monitoring_thresholds'), 'Stage p95, similarity/rates, source revision and Job outcomes'],
        ['Observability', text('observability_thresholds'), 'Answer/context calibration, faithfulness and injection actions'],
        ['Traceability', 'Every measured query has exact context and outgoing model payload', 'Trace IDs, source/model versions, filters and prompt reconstruction'],
        ['Reliability', 'Measured resource headroom; zero unavailable rollout; recovery proof', 'Resource samples, rollout history and post-undo trace'],
    ], [1700, 3900, 3760])
    page += p('The five qualities follow Table 2 of the supplied paper, p13. Dedicated toxicity/usefulness scores and network bandwidth were not measured; this limitation is separate from the assignment release/recovery checks.')
    page += p('Diagnosis using only one recorded trace', 'Heading2')
    for line in inputs.get('trace_diagnosis') or ['Pending trace diagnosis']:
        page += p(line)
    page += p('Human diagnosis reviewers: ' + ', '.join(inputs.get('trace_diagnosis_reviewers', [])))
    page += p(text('trace_summary'))
    pages.append(page)

    page = p('Data drift usage coverage and cluster operation', 'Heading1')
    rows = []
    for label, key in [('Golden v1', 'coverage_before'), ('Golden v2', 'coverage_after')]:
        source = artifacts.get(key)
        rows.append([label, f"{source['coverage']:.1%}" if source else 'Pending',
                     str(source['similarity_cutoff']) if source else 'Pending',
                     f"{source['coverage_floor']:.0%}" if source else 'Pending',
                     str(source['exit_code']) if source else 'Pending'])
    page += table(['Golden', 'Coverage', 'Cosine', 'Floor', 'Exit'], rows, [2400, 1900, 1700, 1700, 1660])
    page += p(text('coverage'))
    page += p(text('drift'))
    page += p('Kubernetes responsibilities', 'Heading2')
    page += table(['Object', 'RAGOps responsibility'], [
        ['API and candidate Deployments/Services', 'Serve pinned collections; rolling updates with maxUnavailable zero'],
        ['Chroma StatefulSet and PVC', 'Persistent vectors; API/evaluation application paths are read-only'],
        ['Data-lake and trace PVCs', 'Persistent originals, quarantine/archive/state and JSON traces'],
        ['Ingestion Job and CronJob', 'Only writer image; shared lock serializes manual/scheduled/admin writes'],
        ['Evaluation/coverage Jobs and result PVC', 'Two-repeat measurement, persisted exit codes and threshold failures'],
        ['Gate ConfigMap', 'Policy read at Job start; change threshold without rebuilding image'],
    ], [3400, 5960])
    page += p(text('configmap_demo'))
    page += p(text('resources'))
    pages.append(page)

    page = p('Short answers', 'Heading1')
    prompts = [('a', 'Verification findings'), ('b', 'Module and pipeline quality'), ('c', 'Archive versus deletion'),
               ('d', 'Least trusted metric'), ('e', 'Hardest paper idea and adaptation'), ('f', 'Object responsibilities')]
    for key, title in prompts:
        page += p(title, 'Heading2')
        page += p(inputs.get('short_answers', {}).get(key) or 'Pending measured interpretation')
    pages.append(page)

    page = p('Contributions evidence and limitations', 'Heading1')
    page += table(['Member', 'Work completed', 'Evidence'], [
        ['Student 1', 'Data lifecycle, verification/Batch B, trace tools and initial runtime/release integration; four questions, four synthetic reviews and four answer labels', text('member1_evidence')],
        ['Student 2', 'Evaluation, gate, coverage, runtime integration fixes, executed experiments and report assembly; four questions, four synthetic reviews and four answer labels', text('member2_evidence')],
    ], [1600, 5560, 2200])
    page += p('AI assistance statement', 'Heading2')
    page += p('Codex assisted with code, integration fixes, command execution and report drafting. Both members supplied their handwritten questions, actual reviews and answer labels. Reported measurements come from exported Kubernetes runs; AI-generated test questions and Batch B documents are marked synthetic.')
    page += p('Reproduction and evidence', 'Heading2')
    page += p(text('evidence_index'))
    page += p(text('reproducibility'))
    page += p('Limitations', 'Heading2')
    page += p(text('limitations'))
    page += p('References', 'Heading2')
    page += p('Xu, X., Weytjens, H., Zhang, D., Lu, Q., Weber, I. and Zhu, L. (2026). RAGOps Operating and Managing Retrieval Augmented Generation Pipelines. Supplied 19-page preprint, SSRN 7353461: Figure 3 p8, Table 1 p10 and Table 2 p13. Assignment 02 RAHBAR and Assignment 03 RAGOps provide the task requirements.')
    pages.append(page)
    return page_break().join(pages)

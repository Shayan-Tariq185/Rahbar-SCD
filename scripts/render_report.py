#!/usr/bin/env python3
"""Build an editable eight-page report or human-work template from explicit inputs.

Uses standard OOXML, without requiring an Office library or modifying A02 code.
Final submission mode refuses missing results, human inputs or screenshots.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from eval_bootstrap import ROOT

from ragops.evalsuite.io import read_json
from ragops.gate import measured_suite

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def paragraph(text: str = "", style: str | None = None) -> str:
    properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{properties}<w:r><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r></w:p>'


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def table(headers: list[str], rows: list[list[str]], widths: list[int] | None = None) -> str:
    widths = widths or [9360 // len(headers)] * len(headers)
    border = ''.join(f'<w:{side} w:val="single" w:sz="4" w:color="D9D9D9"/>'
                     for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    body = [f'<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblBorders>{border}</w:tblBorders>'
            '<w:tblCellMar><w:top w:w="85" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
            '<w:bottom w:w="85" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
            '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>' +
            ''.join(f'<w:gridCol w:w="{width}"/>' for width in widths) + '</w:tblGrid>']
    for index, cells in enumerate([headers] + rows):
        shade = '17365D' if index == 0 else ('F2F6FA' if index % 2 == 0 else 'FFFFFF')
        body.append('<w:tr>' + ('<w:trPr><w:tblHeader/></w:trPr>' if index == 0 else '<w:trPr><w:cantSplit/></w:trPr>'))
        for width, text in zip(widths, cells, strict=True):
            formatting = '<w:b/><w:color w:val="FFFFFF"/>' if index == 0 else '<w:color w:val="000000"/>'
            body.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                        f'<w:shd w:fill="{shade}"/><w:vAlign w:val="center"/></w:tcPr>'
                        '<w:p><w:pPr><w:spacing w:after="20" w:line="240" w:lineRule="auto"/></w:pPr>'
                        f'<w:r><w:rPr>{formatting}<w:sz w:val="19"/></w:rPr>'
                        f'<w:t xml:space="preserve">{escape(str(text))}</w:t></w:r></w:p></w:tc>')
        body.append('</w:tr>')
    body.append('</w:tbl>')
    return ''.join(body) + paragraph()


def save_docx(path: Path, body: str) -> None:
    styles = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
<w:sz w:val="21"/><w:color w:val="000000"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
<w:spacing w:after="100" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="0" w:after="220"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="44"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="140" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="100" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="23"/><w:color w:val="000000"/></w:rPr></w:style></w:styles>'''
    section = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1080" w:right="1273" w:bottom="1080" w:left="1273" w:header="360" w:footer="360"/></w:sectPr>'
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}{section}</w:body></w:document>'
    content_types = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    relationships = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    document_rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for name, text in {'[Content_Types].xml': content_types, '_rels/.rels': relationships,
                           'word/document.xml': document, 'word/styles.xml': styles,
                           'word/_rels/document.xml.rels': document_rels}.items():
            archive.writestr(name, text)


def load_artifacts(inputs: dict, *, draft: bool) -> tuple[dict, list[str]]:
    artifacts = {}
    missing = []
    for name, value in inputs['artifacts'].items():
        if not value:
            missing.append(name)
            continue
        path = (ROOT / value).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f'Invalid explicit artifact path: {name}')
        artifact = read_json(path)
        if name in {'baseline_a', 'drift_ab', 'change_baseline', 'candidate_bad', 'candidate_good'}:
            measured_suite(artifact)
        if artifact.get('provenance') == 'synthetic_fixture' or artifact.get('test_only'):
            raise ValueError('Test-only artifacts cannot populate report evidence')
        artifacts[name] = artifact
    if not draft:
        for student in inputs['students']:
            if not student['roll'].strip() or student['name'].startswith('Student '):
                missing.append('actual student names and roll numbers')
        if len(inputs.get('trace_diagnosis', [])) != 5 or len(inputs.get('trace_diagnosis_reviewers', [])) < 2:
            missing.append('five trace-only diagnostic lines reviewed by both members')
        if any(not text.strip() for text in inputs['short_answers'].values()):
            missing.append('six actual short answers')
        if len(inputs.get('screenshots', [])) < 10:
            missing.append('required screenshot appendix')
        if missing:
            raise ValueError('Submission inputs incomplete: ' + ', '.join(missing))
    return artifacts, missing


def value(artifacts: dict, artifact: str, level: str, name: str, repeat: int = 0) -> str:
    if artifact not in artifacts:
        return 'Pending'
    number = artifacts[artifact]['runs'][repeat][level][name]['value']
    return 'NA' if number is None else f'{number:.4g}'


def report_body(inputs: dict, artifacts: dict) -> str:
    pages = []
    page = paragraph('RAHBAR RAGOps Assignment 03 Report', 'Title')
    page += table(['Student', 'Roll number', 'Responsibility'],
                  [[s['name'], s['roll'] or '________________', s['role']] for s in inputs['students']], [2700, 2200, 4460])
    page += paragraph('This report documents data verification, evaluation, traceability, usage coverage and controlled Kubernetes releases for RAHBAR. Complete the student details and evidence fields from recorded pipeline runs before submission.')
    page += paragraph('Pipeline stage mapping', 'Heading1')
    page += table(['Figure 3 stage', 'Implementation', 'Evidence or remaining work'], [
        ['Ingest', 'ragops/ingest.py through writer Jobs', 'Member 1 integration and run evidence'],
        ['Verify', 'ragops/verify.py before chunking', 'Batch B verification report'],
        ['Update data lake', 'ragops/ingest.py and ragops/state.py on data PVC', 'Persistence and restore proof'],
        ['Update retrieval sources', 'ragops/ingest.py commits chunk/vector revisions', 'Incremental counts and vector fingerprints'],
        ['Offline testing', 'ragops/evalsuite/runner.py and k8s/eval-job.yaml', 'Two complete measured suite repeats'],
        ['Live testing', 'scripts/load_queries.py and ragops/trace.py', 'Simulated queries and actual trace samples'],
        ['Check coverage', 'ragops/coverage.py and coverage Job', 'Fixed-policy coverage before and after expansion'],
    ], [1900, 3500, 3960])
    page += paragraph('Architecture', 'Heading2')
    page += paragraph('Figure 3 (paper p8) links these seven data stages to the software lifecycle. Indexing and serving remain separate. Ingestion Jobs write Chroma and persistent lifecycle state. Evaluation calls the production API. Gate policies are ConfigMaps; results are written to a PVC.')
    pages.append(page)
    page = paragraph('Data verification and version updates', 'Heading1')
    page += table(['Check', 'Measure', 'Recorded result'], [
        ['Quality', 'Empty garbled or failed extraction', 'Pending verification artifact'],
        ['Completeness', 'Source title date or version pages truncation', 'Pending verification artifact'],
        ['Recency', 'Document family and version lineage', 'Pending verification artifact'],
        ['Uniqueness', 'Exact hashes and embedding near duplicates', 'Pending verification artifact'],
    ], [1700, 4200, 3460])
    page += paragraph('Batch B', 'Heading2')
    page += paragraph('Record at least ten documents including two exact duplicates, one near duplicate, one corrupt or truncated file, missing metadata, a newer version and an injected instruction. Insert actual per-check counts and reasons. Paper section 4.2.2 also discusses consistency; automated contradiction detection is outside the four required A1 checks and is not claimed here.')
    page += paragraph('Incremental and recovery evidence', 'Heading2')
    for text in ['Unchanged run chunks embedded and document-check calls: __________________',
                 'Changed document and unaffected document fingerprints: __________________',
                 'Deleted document ID and remaining chunk count: __________________',
                 'Archived version restored through writer Job: __________________',
                 'Verification report and writer Job names: __________________']:
        page += paragraph(text)
    page += paragraph('Explain which check caught the most planted problems, one missed problem and a concrete remedy. Distinguish document rejection from infrastructure failure.')
    pages.append(page)
    page = paragraph('Offline evaluation at three levels', 'Heading1')
    rows = []
    for level, names in [('module', ['paraphrase_cosine_mean', 'unrelated_cosine_mean', 'cosine_gap', 'embedding_ms_per_chunk', 'identical_text_max_difference']),
                         ('component', ['recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5']),
                         ('e2e', ['faithfulness', 'abstention_correctness', 'citation_validity', 'latency_p50_ms', 'latency_p95_ms'])]:
        for name in names:
            rows.append([level + ' ' + name.replace('_', ' '), value(artifacts, 'baseline_a', level, name),
                         value(artifacts, 'baseline_a', level, name, 1)])
    page += table(['Metric', 'Run 1', 'Run 2'], rows, [5960, 1700, 1700])
    page += paragraph('Noise and repeat variation', 'Heading2')
    page += paragraph('Insert all four noisy retrieval deltas and every repeat difference from the saved summaries. Seeds and cache policies remain fixed; explain provider or timing variation rather than assuming deterministic generation.')
    page += paragraph('Human provenance and judge calibration', 'Heading2')
    page += paragraph('Record eight handwritten questions, eight manually reviewed synthetic questions, and eight human faithfulness labels split equally between the members. Insert agreement, confusion counts and the exact label and rubric hashes. Citation validity does not establish faithfulness.')
    pages.append(page)
    page = paragraph('One variable experiment and release decision', 'Heading1')
    rows = []
    for label, name in [('Baseline', 'change_baseline'), ('Bad candidate', 'candidate_bad'), ('Good candidate', 'candidate_good')]:
        top_k = artifacts[name]['config']['top_k'] if name in artifacts else 'Pending'
        rows.append([label, str(top_k), value(artifacts, name, 'component', 'recall_at_5'),
                     value(artifacts, name, 'e2e', 'faithfulness'), value(artifacts, name, 'e2e', 'latency_p95_ms')])
    page += table(['Target', 'Top k', 'Recall at 5', 'Faithfulness', 'p95 ms'], rows, [2360, 1000, 2000, 2000, 2000])
    page += paragraph('Original policy and rationale', 'Heading2')
    page += paragraph('Insert the frozen original thresholds and measured baseline rationale. Recall drop 0.02 means two percentage points. Bind corpus and vector snapshots, golden hash, model digest, image and configuration. Demonstration thresholds never authorize release.')
    page += paragraph('Candidate gate outcomes', 'Heading2')
    for key in ['gate_bad', 'gate_good']:
        artifact = artifacts.get(key)
        text = 'Pending measured decision' if artifact is None else f"{artifact['decision']}; release authorized {artifact['release_authorized']}"
        page += paragraph(key.replace('_', ' ').title() + ': ' + text)
    page += paragraph('Controlled rollout and rollback', 'Heading2')
    for text in ['Rejected candidate left live PodTemplate and revision unchanged: __________________',
                 'Released collection image and Deployment revision: __________________',
                 'Bad release and restored known-good revision: __________________',
                 'New post-undo trace showing prior collection and embedding version: __________________']:
        page += paragraph(text)
    pages.append(page)
    page = paragraph('Traceability and operational qualities', 'Heading1')
    page += table(['Table 2 quality', 'Measure and threshold', 'Evidence'], [
        ['Adaptability', 'Versioned source/config changes; recall drop at most 0.02 under justified policy', 'Incremental updates and candidate comparison'],
        ['Monitorability', 'Relevance quality latency and source changes; insert frozen alert thresholds', 'Metrics time-window summary and revision history'],
        ['Observability', 'Retrieval injection/relevance; generation context support meets justified faithfulness floor', 'Guardrail trace and judged answer/context evidence'],
        ['Traceability', 'Version routing and grounded-source chain; exact context and request reconstruct', 'Trace IDs document/model versions filters and prompt replay'],
        ['Reliability', 'Peak CPU/memory versus measured requests/limits; rollout and recovery checks', 'API vector-store and Job samples; rollout/undo evidence'],
    ], [1800, 4000, 3560])
    page += paragraph('Paper Table 2 (p13) guides these measures. Insert actual thresholds and evidence. Dedicated toxicity/usefulness scores and network bandwidth are not measured; rollout and recovery are additional assignment checks.')
    page += paragraph('Five line diagnosis from one trace', 'Heading2')
    lines = inputs.get('trace_diagnosis') or [f'Line {i} from the selected trace: __________________' for i in range(1, 6)]
    for line in lines:
        page += paragraph(line)
    page += paragraph('Trace ID __________________')
    page += paragraph('Student 1 review __________________  Student 2 review __________________')
    page += paragraph('The diagnosis must use only the selected wrong or abstained answer trace. Identify the relevant chunk, document version, score or filter and distinguish recorded facts from hypotheses.')
    pages.append(page)
    page = paragraph('Usage coverage data drift and Kubernetes', 'Heading1')
    coverage_rows = []
    for label, name in [('Before expansion', 'coverage_before'), ('After expansion', 'coverage_after')]:
        result = artifacts.get(name)
        coverage_rows.append([label] + ([f"{result['coverage']:.2%}", str(result['similarity_cutoff']), f"{result['coverage_floor']:.2%}"] if result else ['Pending'] * 3))
    page += table(['Golden version', 'Coverage', 'Cosine cutoff', 'Coverage floor'], coverage_rows, [3300, 2020, 2020, 2020])
    page += paragraph('Keep the live set, embedding model and both thresholds identical. List uncovered topics, six useful additions and measured coverage rise. Paper section 4.2.7 uses 85 percent as an example coverage floor, not a required cosine cutoff. Justify both thresholds; question coverage does not establish corpus answerability.')
    page += paragraph('Fixed golden data drift', 'Heading2')
    page += paragraph('Compare Batch A with A plus B using frozen golden v1 before expanding tests. Link changed ranks, versions, citations and abstentions to the verification inventory. Record actual changes without assuming improvement.')
    page += table(['Kubernetes object', 'RAGOps responsibility'], [
        ['API and candidate Deployments and Services', 'Serve explicit collection and model configurations'],
        ['Chroma StatefulSet and data lake PVCs', 'Persist vectors originals quarantine archive and state'],
        ['Ingestion Job and CronJob', 'Serialize all vector-store mutations through one writer path'],
        ['Evaluation and coverage Jobs and results PVC', 'Execute measured suites persist outcomes fail on thresholds'],
        ['Gate ConfigMap', 'Change policy without rebuilding the evaluation image'],
    ], [4000, 5360])
    page += paragraph('Measured API vector-store ingestion and evaluation CPU and memory with justified headroom: __________________. Provisional requests are not measurements.')
    pages.append(page)
    page = paragraph('Short answers and interpretation', 'Heading1')
    prompts = {'a': 'Verification results and missed problem', 'b': 'Module versus component or answer quality',
               'c': 'Archive versus delete tradeoff', 'd': 'Least trusted metric and why',
               'e': 'Hardest paper idea and actual adaptation', 'f': 'Kubernetes object responsibilities'}
    for key, title in prompts.items():
        page += paragraph(title, 'Heading2')
        page += paragraph(inputs['short_answers'].get(key) or 'Write your evidence-grounded answer here. Use actual results and your own interpretation.')
    pages.append(page)
    page = paragraph('Contributions and AI assistance', 'Heading1')
    page += table(['Member', 'Actual work', 'Evidence'], [
        ['Student 1', 'Enter completed data lifecycle trace runtime and report work', 'Enter genuine commits and run artifacts'],
        ['Student 2', 'Evaluation gate coverage tooling and report assembly', 'Enter genuine commits and measured artifacts'],
    ], [1800, 4800, 2760])
    page += paragraph('AI assistance statement', 'Heading2')
    page += paragraph('Codex assisted with evaluation tooling, tests and this report template. Human-written questions, manual reviews and labels must be supplied by the group; reported measurements must come from executed pipeline runs.')
    page += paragraph('Submission audit', 'Heading2')
    for text in ['Both names and roll numbers entered on the first page',
                 'A to F result files trace samples and all manifests committed',
                 'Original gate frozen before candidate outcomes and measured fail and pass saved',
                 'README commands and fresh-cluster startup instructions verified',
                 'Screenshot appendix contains uncropped commands and real output',
                 'Both members can explain the complete pipeline and rehearse unseen ingestion']:
        page += paragraph('[  ] ' + text)
    page += paragraph('References', 'Heading2')
    page += paragraph('Xu, X., Weytjens, H., Zhang, D., Lu, Q., Weber, I. and Zhu, L. (2026). RAGOps: Operating and Managing Retrieval-Augmented Generation Pipelines. Preprint, 19 pages, SSRN 7353461. Figure 3 p8; Table 1 p10; Table 2 p13. Also: Assignment 02 RAHBAR and Assignment 03 RAGOps. Record the selected run artifact hashes.')
    pages.append(page)
    return page_break().join(pages)


def human_body() -> str:
    pages = []
    for member in (1, 2):
        page = paragraph(f'Student {member} Human Work Template', 'Title')
        page += paragraph('Write four original questions yourself. Use the verified source inventory and physical PDF pages. Do not copy an AI draft and label it handwritten. Record your actual name in the JSONL entries before merging them.')
        for number in range(1, 5):
            page += paragraph(f'Question {number}', 'Heading2')
            for text in ['Your question __________________________________________________________',
                         'Author __________________  Answerable yes or no ______  Hard yes or no ______',
                         'Document ID __________________________  Version ________________________',
                         'Physical PDF page ______  Section or chunk ID __________________________',
                         'Expected answer or abstention and evidence notes _________________________']:
                page += paragraph(text)
        page += paragraph('After writing your questions, manually review four synthetic questions with review_synthetic.py. Faithfulness labeling is a separate task performed on real generated answers and exact retrieved contexts.')
        pages.append(page)
    return page_break().join(pages)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=ROOT / 'report/inputs.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--human-template', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.out.suffix.lower() != '.docx':
        raise ValueError('Editable output must be .docx; export PDF with the documented Word renderer and check its page count')
    if args.out.exists() and not args.overwrite:
        raise ValueError('Refusing to overwrite an editable document; choose another path or explicit --overwrite')
    if args.human_template:
        body = human_body()
        missing = []
    else:
        inputs = read_json(args.inputs)
        artifacts, missing = load_artifacts(inputs, draft=args.draft)
        if inputs.get('measured_report'):
            from report_measured_body import build
            body = build(inputs, artifacts, paragraph, table, page_break)
        else:
            body = report_body(inputs, artifacts)
        if not args.draft and ('____' in body or 'Pending' in body):
            raise ValueError('Report still contains editorial placeholders; finish the editable draft before submission')
    save_docx(args.out, body)
    print(f'Created editable document: {args.out}')
    print('Report body target: 8 pages; human template target: 2 pages. Render and inspect before delivery.')
    if missing:
        print('Pending evidence fields: ' + ', '.join(missing))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f'report input error: {exc}', file=sys.stderr)
        raise SystemExit(2)

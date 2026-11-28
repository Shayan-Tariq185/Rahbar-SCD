#!/usr/bin/env python3
"""Stage the six real Batch A PDFs only after verifying recorded source hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'corpus/raw')
    parser.add_argument('--out', type=Path, default=ROOT / 'tmp/batch-a')
    args = parser.parse_args()
    inventory = json.loads((ROOT / 'config/corpus-inventory.json').read_text())
    entries = []
    args.out.mkdir(parents=True, exist_ok=True)
    for doc in inventory['documents']:
        source = args.source_dir / doc['source']
        if hashlib.sha256(source.read_bytes()).hexdigest() != doc['verified_sha256']:
            raise ValueError(f"Source checksum differs: {source.name}")
        shutil.copy2(source, args.out / source.name)
        family = 'academic-rules' if 'academic-rules' in doc['doc_id'] else (
            'annual-report' if 'annual-report' in doc['doc_id'] else doc['doc_id'])
        entries.append({'file': doc['source'], 'doc_id': doc['doc_id'], 'family_id': family,
                        'title': doc['title'], 'doc_version': doc['doc_version'],
                        'superseded': doc['superseded'], 'expected_pages': doc['pages']})
    entries.sort(key=lambda row: (row['doc_id'] not in {
        'academic-rules-handbook-jun-2026', 'student-handbook-jun-2026'}, row['doc_id']))
    (args.out / '_index.json').write_text(json.dumps(entries, indent=2))
    print(f'Verified and staged {len(entries)} original PDFs into {args.out}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f'Batch A staging failed: {exc}')

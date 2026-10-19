#!/usr/bin/env python3
"""Read a local pinned notebook archive without executing or extracting code."""
import argparse
import collections
import hashlib
import json
import zipfile
from pathlib import Path

COMMIT = '3aec5fa09788d6659c6e1eac79cdc503340d9694'
URL = f'https://raw.githubusercontent.com/malusamayo/GitHubAPI-Crawler/{COMMIT}/evaluation_materials/sample-notebooks.zip'
SHA256 = 'b645e3efb3fb5dcaf5dadb0b33d441d6816aede4af8a17ce482a5116f9896ca1'
TERMS = {'TargetEncoder', 'LeaveOneOutEncoder', 'CatBoostEncoder', 'StackingClassifier',
         'StackingRegressor', 'CalibratedClassifierCV', 'cross_val_predict', 'cross_val_score',
         'KFold', 'StratifiedKFold', 'GridSearchCV', 'train_test_split'}


def main():
    parser = argparse.ArgumentParser(description=f'Download separately from {URL}')
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new receipt path.')
    digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    if digest != SHA256:
        raise ValueError('Archive pin mismatch.')
    rows = []
    with zipfile.ZipFile(args.archive) as archive:
        for name in sorted(n for n in archive.namelist() if n.endswith('.ipynb') and not n.startswith('__MACOSX/')):
            raw = archive.read(name)
            row = {'name': name, 'sha256': hashlib.sha256(raw).hexdigest()}
            try:
                notebook = json.loads(raw)
                code = '\n'.join(''.join(c.get('source', [])) for c in notebook.get('cells', [])
                                 if c.get('cell_type') == 'code')
            except (ValueError, AttributeError, TypeError) as exc:
                row.update(status='INVALID_NOTEBOOK', error=type(exc).__name__)
            else:
                row.update(status='SOURCE_ONLY', named_mentions={t: code.count(t) for t in sorted(TERMS) if t in code})
            rows.append(row)
    result = {'source_commit': COMMIT, 'source_url': URL,
              'archive_bytes': args.archive.stat().st_size, 'archive_sha256': digest,
              'notebooks': len(rows), 'status_counts': dict(collections.Counter(r['status'] for r in rows)),
              'notebooks_with_name_mentions': {t: sum(t in r.get('named_mentions', {}) for r in rows) for t in sorted(TERMS)},
              'limitations': 'Text mention census, not symbol resolution or execution. Comments and strings can match; aliased imports can be missed. No data completeness, leakage verdict, or detector coverage inferred.',
              'rows': rows}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()

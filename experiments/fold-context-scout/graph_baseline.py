#!/usr/bin/env python3
"""Strong sanity baseline with the same manually supplied operator semantics."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.model_selection import KFold

from run import feature_dependencies


def reaches(graph, start, targets):
    seen, pending = set(), [start]
    while pending:
        node = pending.pop()
        if node in targets:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return False


def verdict(arm, train, test, seed):
    # Every explicit dependency becomes an edge. This baseline has exactly the
    # same trusted semantic information as the proposed set-union analysis.
    graph = {}
    all_rows = np.arange(len(train) + len(test))
    if arm == 'global_oof':
        deps = feature_dependencies(all_rows, seed, crossfit=True)
        for row in all_rows:
            graph[('feature', int(row))] = [('label', int(x)) for x in deps[row]]
    else:
        deps = feature_dependencies(train, seed, crossfit=arm == 'nested_crossfit')
        for row, dep in zip(train, deps):
            graph[('feature', int(row))] = [('label', int(x)) for x in dep]
        for row in test:
            graph[('feature', int(row))] = [('label', int(x)) for x in train]
    graph['model'] = [('feature', int(x)) for x in train] + [('label', int(x)) for x in train]
    graph['predict'] = ['model'] + [('feature', int(x)) for x in test]
    return reaches(graph, 'predict', {('label', int(x)) for x in test})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new receipt path.')
    source = Path(__file__).with_name('receipt-instrumented.json')
    receipt = json.loads(source.read_text())
    baseline = []
    for seed in range(10):
        for fold, (train, test) in enumerate(KFold(5, shuffle=True, random_state=seed + 101).split(np.zeros(600))):
            for arm in receipt['summary']:
                baseline.append({'seed': seed, 'fold': fold, 'arm': arm,
                                 'dependency_flagged': verdict(arm, train, test, seed + 701)})
    indexed = {(r['seed'], r['fold'], r['arm']): r for r in receipt['rows']}
    mismatches = [r for r in baseline if r['dependency_flagged'] !=
                  (indexed[(r['seed'], r['fold'], r['arm'])]['outer_test_label_paths'] > 0)]
    result = {'rows': len(baseline), 'disagreements': mismatches,
              'source_receipt_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'claim': 'Simple graph reachability ties the set-union analysis when given the same explicit operator dependencies. No new inference algorithm or superiority established.',
              'baseline_rows': baseline, 'sota': False}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'baseline_rows'}, indent=2))


if __name__ == '__main__':
    main()

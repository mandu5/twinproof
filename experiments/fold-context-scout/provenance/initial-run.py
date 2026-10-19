#!/usr/bin/env python3
"""Scoped label-dependency mechanism check; no automatic notebook analysis."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import sklearn
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import TargetEncoder


HERE = Path(__file__).resolve().parent


def encoder(seed):
    return TargetEncoder(target_type='continuous', smooth=10.0, cv=5,
                         shuffle=True, random_state=seed)


def feature_dependencies(ids, seed, crossfit):
    """A conservative label-support set for the trusted smoothed encoder."""
    ids = np.asarray(ids)
    if not crossfit:
        return [frozenset(ids.tolist()) for _ in ids]
    deps = [None] * len(ids)
    for fit, transform in KFold(5, shuffle=True, random_state=seed).split(ids):
        fit_labels = frozenset(ids[fit].tolist())
        for row in transform:
            deps[row] = fit_labels
    return deps


def predict(arm, X, y, train, test, seed):
    enc = encoder(seed)
    if arm == 'global_oof':
        features = enc.fit_transform(X, y)
        z_train, z_test = features[train], features[test]
        deps = feature_dependencies(np.arange(len(y)), seed, crossfit=True)
        train_deps = [deps[i] for i in train]
        test_deps = [deps[i] for i in test]
    else:
        if arm == 'nested_crossfit':
            z_train = enc.fit_transform(X[train], y[train])
            train_deps = feature_dependencies(train, seed, crossfit=True)
        else:
            enc.fit(X[train], y[train])
            z_train = enc.transform(X[train])
            train_deps = feature_dependencies(train, seed, crossfit=False)
        z_test = enc.transform(X[test])
        test_deps = [frozenset(train.tolist()) for _ in test]
    model = Ridge(alpha=1.0, solver='cholesky').fit(z_train, y[train])
    # A fitted estimator can depend on both training labels and training features.
    model_deps = frozenset(train.tolist()).union(*train_deps)
    prediction_deps = model_deps.union(*test_deps)
    return model.predict(z_test), {
        'outer_test_label_paths': len(prediction_deps.intersection(test.tolist())),
        'train_rows_with_self_label_feature_path': sum(int(row in dep) for row, dep in zip(train, train_deps)),
        'train_rows': len(train),
        'encoder_fit_operations': 6 if arm != 'train_only_without_internal_crossfit' else 1,
        'regressor_fits': 1,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new receipt path; historical results are immutable.')
    protocol_bytes = (HERE / 'protocol.json').read_bytes()
    protocol = json.loads(protocol_bytes)
    start = time.perf_counter()
    rows = []
    for seed in range(10):
        rng = np.random.default_rng(seed)
        X = np.column_stack([rng.integers(0, 30, 600), rng.integers(0, 150, 600)])
        effects = rng.normal(size=30)
        y = effects[X[:, 0]] + rng.normal(scale=0.8, size=600)
        for fold, (train, test) in enumerate(KFold(5, shuffle=True, random_state=seed + 101).split(X)):
            changed = y.copy()
            changed[test] += np.random.default_rng(seed * 100 + fold + 1001).normal(scale=2.0, size=len(test))
            assert np.array_equal(y[train], changed[train])
            for arm in protocol['arms']:
                before, deps = predict(arm, X, y, train, test, seed + 701)
                after, after_deps = predict(arm, X, changed, train, test, seed + 701)
                assert deps == after_deps
                rows.append({'seed': seed, 'fold': fold, 'arm': arm, **deps,
                             'max_prediction_delta': float(np.max(np.abs(before - after))),
                             'predictions_sha256': hashlib.sha256(before.tobytes()).hexdigest(),
                             'intervened_predictions_sha256': hashlib.sha256(after.tobytes()).hexdigest()})
    by_arm = {}
    for arm in protocol['arms']:
        selected = [r for r in rows if r['arm'] == arm]
        by_arm[arm] = {'fold_runs': len(selected),
                      'dependency_flagged': sum(r['outer_test_label_paths'] > 0 for r in selected),
                      'prediction_changed': sum(r['max_prediction_delta'] > 1e-12 for r in selected),
                      'self_label_feature_flagged': sum(r['train_rows_with_self_label_feature_path'] > 0 for r in selected),
                      'max_prediction_delta': max(r['max_prediction_delta'] for r in selected)}
    receipt = {'protocol_sha256': hashlib.sha256(protocol_bytes).hexdigest(),
               'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'python': platform.python_version(), 'numpy': np.__version__, 'sklearn': sklearn.__version__,
               'seconds': time.perf_counter() - start, 'summary': by_arm, 'rows': rows,
               'fit_counts_both_executions': {'encoder': 2 * sum(r['encoder_fit_operations'] for r in rows),
                                             'regressor': 2 * sum(r['regressor_fits'] for r in rows)},
               'scope': protocol['dependency_scope'], 'sota': False,
               'published_baselines_run': [], 'external_programs': 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()

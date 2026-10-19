import importlib

import pytest

from twinproof.world_model import PythonModel, Transition


def api():
    try:
        return importlib.import_module('twinproof.world_audit')
    except ModuleNotFoundError:
        pytest.fail('world-model audit is not implemented')


def test_trace_conflict_bound_counts_multiplicity_not_all_pairs():
    rows = [Transition(i, [[0]], 'A', [[x]]) for i, x in enumerate([1, 1, 2])]
    r = api().trace_conflicts(rows)
    assert r['transitions'] == 3
    assert r['ambiguous_input_groups'] == 1
    assert r['minimum_observation_only_errors'] == 1
    assert r['conflicts'][0]['indices'] == [0, 1, 2]
    assert api().trace_conflicts([])['minimum_observation_only_errors'] == 0


def test_refinement_separates_witnesses_without_irrelevant_field():
    assert api().separating_fields([{'phase', 'noise'}, {'phase'}, {'route'}]) == ['phase', 'route']
    with pytest.raises(ValueError, match='unseparable'):
        api().separating_fields([set()])


SOURCE = '''\
phase = 0
noise = 0
def step(grid, action):
    global phase, noise
    noise += 1
    if action == 'tick':
        phase = 1
    if action == 'open' and phase == 1:
        return [[1]]
    return grid
'''


def test_snapshot_isolation_alone_does_not_repair_observation_key():
    m = api()
    model = PythonModel(SOURCE)
    root = model.snapshot()
    args = (model, [[0]], root, ['open', 'tick'], [[1]])
    observation = m.bounded_search(*args, fields=[], max_depth=3, max_expansions=20)
    full = m.bounded_search(*args, fields=None, max_depth=3, max_expansions=20)
    refined = m.bounded_search(*args, fields=['phase'], max_depth=3, max_expansions=20)
    assert observation['status'] == 'EXHAUSTED'
    assert full['path'] == refined['path'] == ['tick', 'open']
    assert refined['calls'] > 0 and refined['expansions'] < full['expansions']
    assert root == {'phase': 0, 'noise': 0}


def test_search_budget_and_already_reached_target_are_explicit():
    m = api()
    model = PythonModel(SOURCE)
    r = m.bounded_search(model, [[0]], model.snapshot(), ['tick', 'open'], [[1]],
                         fields=None, max_depth=10, max_expansions=0)
    assert r['status'] == 'BUDGET_EXHAUSTED' and r['calls'] == 0
    r = m.bounded_search(model, [[0]], model.snapshot(), ['tick'], [[0]],
                         fields=None, max_depth=0, max_expansions=0)
    assert r['status'] == 'FOUND' and r['path'] == []


def test_summary_retains_unknown_and_unsupported_families():
    s = api().summarize([{'game': 'a', 'status': 'OK', 'trace': {'ambiguous_input_groups': 1}},
                         {'game': 'b', 'status': 'UNSUPPORTED'}, {'game': 'c', 'status': 'TIMEOUT', 'model_calls': None}])
    assert s['families'] == 3 and s['runtime_completed'] == 1
    assert s['status_counts'] == {'OK': 1, 'UNSUPPORTED': 1, 'TIMEOUT': 1}
    assert api().summarize([])['runtime_completed'] == 0


def test_complete_small_audit_reconciles_calls_and_replay():
    p = {'env': 'test', 'w': 1, 'h': 1, 'n': 3, 'f0': '0',
         'acts': ['tick', 'open', 'open'], 'deltas': ['', '0001', ''],
         'model': {'src': SOURCE}}
    r = api().audit_model(p, budget=200)
    assert r['status'] == 'OK' and r['replay_matches'] == 3
    assert r['model_calls'] == r['replay_calls'] + r['post_replay_used']
    assert r['post_replay_used'] <= 200
    assert all(c['equal'] for c in r['fresh_replay_checks'])


def test_candidate_exception_keeps_cost_and_failed_input():
    src = '''\
def step(grid, action):
    if action == 'B' and grid[0][0] == 0:
        raise IndexError('candidate defect')
    return [[1]]
'''
    p = {'env': 'test', 'w': 1, 'h': 1, 'n': 2, 'f0': '0',
         'acts': ['A', 'B'], 'deltas': ['0001', ''], 'model': {'src': src}}
    result = api().audit_model(p)
    assert result['status'] == 'MODEL_ERROR'
    assert result['model_calls'] > result['replay_calls'] == 2
    assert result['failed_call']['action'] == 'B'
    assert result['failed_call']['phase'] == 'branch_probe'
    assert result['reason'] == 'IndexError: candidate defect'


def test_zero_post_replay_budget_never_spends_prefix_or_probe_calls():
    p = {'env': 'test', 'w': 1, 'h': 1, 'n': 1, 'f0': '0',
         'acts': ['tick'], 'deltas': [''], 'model': {'src': SOURCE}}
    r = api().audit_model(p, budget=0)
    assert r['model_calls'] == 1
    assert r['fresh_replay_checks'] == [] and r['branch_checks'] == []

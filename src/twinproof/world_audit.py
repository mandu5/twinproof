"""Reproducible finite witnesses for insufficient world-model state keys."""
from __future__ import annotations

import hashlib
import json
import pickle
import time
import zlib
from collections import Counter, defaultdict, deque

from .world_model import PythonModel, UnsupportedModel, decode_showcase, graph_data, state_key


def grid_bytes(grid):
    return json.dumps(grid, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(grid_bytes(value)).hexdigest()


def trace_conflicts(transitions) -> dict:
    groups = defaultdict(list)
    for row in transitions:
        groups[(grid_bytes(row.before), row.action)].append(row)
    conflicts, errors = [], 0
    for (grid, action), rows in groups.items():
        counts = Counter(grid_bytes(row.after) for row in rows)
        errors += len(rows) - max(counts.values())
        if len(counts) > 1:
            conflicts.append({'indices': [r.index for r in rows], 'action': action,
                              'input_sha256': hashlib.sha256(grid).hexdigest(),
                              'successor_sha256': [digest(r.after) for r in rows],
                              'distinct_successors': len(counts)})
    return {'transitions': len(transitions), 'unique_inputs': len(groups),
            'ambiguous_input_groups': len(conflicts),
            'minimum_observation_only_errors': errors, 'conflicts': conflicts}


def separating_fields(conflicts) -> list[str]:
    """Greedy finite hitting set; not a proof of unobserved equivalence."""
    remaining = [set(x) for x in conflicts]
    if any(not x for x in remaining):
        raise ValueError('unseparable witness: differing fields are empty')
    selected = []
    while remaining:
        counts = Counter(field for row in remaining for field in row)
        field = min(counts, key=lambda x: (-counts[x], x))
        selected.append(field)
        remaining = [row for row in remaining if field not in row]
    return selected


def differing_fields(left, right):
    return sorted(k for k in left.keys() | right.keys()
                  if k not in left or k not in right or graph_data(left[k]) != graph_data(right[k]))


def bounded_search(model, grid, snapshot, actions, target, *, fields=None,
                   max_depth=3, max_expansions=100) -> dict:
    """Constructed reachability task inside the model, not a game-score claim."""
    start_calls = model.calls
    started = time.perf_counter()
    queue = deque([(grid, snapshot, [])])
    seen = {state_key(grid, snapshot, fields)}
    expanded = 0
    depth_limited = False
    while queue:
        current, state, path = queue.popleft()
        if current == target:
            return {'status': 'FOUND', 'path': path, 'expansions': expanded,
                    'unique_states': len(seen), 'calls': model.calls - start_calls,
                    'seconds': time.perf_counter() - started}
        if len(path) >= max_depth:
            depth_limited = True
            continue
        if expanded >= max_expansions:
            return {'status': 'BUDGET_EXHAUSTED', 'path': None, 'expansions': expanded,
                    'unique_states': len(seen), 'calls': model.calls - start_calls,
                    'seconds': time.perf_counter() - started}
        expanded += 1
        for action in actions:
            result, next_state = model.predict(current, action, state)
            key = state_key(result, next_state, fields)
            if key not in seen:
                seen.add(key)
                queue.append((result, next_state, path + [action]))
    return {'status': 'DEPTH_EXHAUSTED' if depth_limited else 'EXHAUSTED',
            'path': None, 'expansions': expanded, 'unique_states': len(seen),
            'calls': model.calls - start_calls, 'seconds': time.perf_counter() - started}


def _pack(state):
    return zlib.compress(pickle.dumps(state, protocol=5), level=1)


def _unpack(data):
    # Only internal, freshly generated data. Never load external pickle artifacts.
    return pickle.loads(zlib.decompress(data))


class _CandidateFailure(Exception):
    pass


def audit_model(payload, budget=2000) -> dict:
    if type(budget) is not int or budget < 0:
        raise ValueError('post-replay budget must be a nonnegative integer')
    ledger = {'calls': 0, 'phases': Counter(), 'partial': {}, 'started': time.perf_counter()}
    try:
        result = _audit_model(payload, budget, ledger)
        assert result.get('model_calls', 0) == ledger['calls'], 'unreconciled model calls'
        result['call_phases'] = dict(ledger['phases'])
        return result
    except _CandidateFailure as exc:
        return {**ledger['partial'], 'status': 'MODEL_ERROR', 'reason': str(exc),
                'failed_call': ledger['failed_call'], 'model_calls': ledger['calls'],
                'call_phases': dict(ledger['phases']),
                'seconds': time.perf_counter() - ledger['started']}


def _audit_model(payload, budget, ledger) -> dict:
    def predict(model, grid, action, state=None, phase='branch_probe'):
        ledger['calls'] += 1
        ledger['phases'][phase] += 1
        try:
            return model.predict(grid, action, state)
        except Exception as exc:
            ledger['failed_call'] = {'phase': phase, 'action': action,
                                     'grid_sha256': digest(grid), 'call_number': ledger['calls']}
            raise _CandidateFailure(f'{type(exc).__name__}: {exc}') from exc

    started = time.perf_counter()
    rows = decode_showcase(payload)
    result = {'game': payload['env'], 'status': 'OK', 'trace': trace_conflicts(rows),
              'scope': 'teacher-forced released transcript; no original agent/planner score'}
    ledger['partial'] = result
    try:
        model = PythonModel(payload['model']['src'])
    except UnsupportedModel as exc:
        return {**result, 'status': 'UNSUPPORTED', 'reason': str(exc), 'model_calls': 0,
                'seconds': time.perf_counter() - started}
    memories, predictions, matches = [], [], 0
    initial = model.snapshot()
    for row in rows:
        memories.append(_pack(model.snapshot()))
        predicted, _ = predict(model, row.before, row.action, phase='replay')
        predictions.append(digest(predicted))
        matches += predicted == row.after
    replay_calls = model.calls
    result.update(replay_matches=matches, replay_calls=replay_calls,
                  snapshot_storage_compressed_bytes=sum(map(len, memories)),
                  global_fields=sorted(initial),
                  declared_global_writes=model.census['declared_global_writes'])
    if not rows:
        return {**result, 'model_calls': model.calls, 'seconds': time.perf_counter() - started}

    # Correct-baseline checks include all calls used to reconstruct prefixes.
    replay_checks = []
    validation_calls = 0
    for index in sorted({min(50, len(rows) - 1), min(150, len(rows) - 1)}):
        if model.calls - replay_calls + validation_calls + index + 2 > budget:
            continue
        fresh = PythonModel(payload['model']['src'])
        for row in rows[:index + 1]:
            prediction, _ = predict(fresh, row.before, row.action, phase='fresh_prefix')
        validation_calls += fresh.calls
        actual, _ = predict(model, rows[index].before, rows[index].action, _unpack(memories[index]), phase='snapshot_validation')
        replay_checks.append({'index': index, 'equal': prediction == actual,
                              'prefix_calls': fresh.calls, 'isolated_sha256': digest(actual)})
    result['fresh_replay_checks'] = replay_checks

    # First learn distinctions from observed repeated inputs only.
    groups = defaultdict(list)
    for row in rows:
        groups[(grid_bytes(row.before), row.action)].append(row.index)
    witnesses = []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        i = indices[0]
        left = _unpack(memories[i])
        for j in indices[1:]:
            if predictions[i] == predictions[j]:
                continue
            right = _unpack(memories[j])
            fields = differing_fields(left, right)
            witnesses.append({'left_index': i, 'right_index': j, 'suffix': [rows[i].action],
                              'fields': fields, 'left_state_sha256': state_key(rows[i].before, left),
                              'right_state_sha256': state_key(rows[j].before, right),
                              'left_output_sha256': predictions[i], 'right_output_sha256': predictions[j],
                              'both_match_recorded_successor': predictions[i] == digest(rows[i].after)
                              and predictions[j] == digest(rows[j].after)})
    try:
        fields = separating_fields([w['fields'] for w in witnesses])
        refinement_status = 'WITNESSED_ONLY' if witnesses else 'NO_WITNESS'
    except ValueError:
        fields = sorted(initial)
        refinement_status = 'FULL_STATE_FALLBACK'
    result.update(witnesses=witnesses, refined_fields=fields, refinement_status=refinement_status)

    # Branch excursions, including repeated inputs where a shared runtime matters.
    # Frozen key above is not revised after these counterfactual outcomes.
    chosen = sorted(set(w['left_index'] for w in witnesses) |
                    {i * (len(rows) - 1) // 15 for i in range(16)})
    pool = [a for a, _ in sorted(Counter(r.action for r in rows).items(), key=lambda x: (-x[1], x[0]))[:8]]
    branch_checks, key_failures = [], []
    result['branch_checks'] = branch_checks
    result['counterfactual_key_witnesses'] = key_failures
    audit_calls_start = model.calls
    for i in chosen:
        for excursion in dict.fromkeys([rows[i].action] + pool):
            if model.calls - replay_calls + validation_calls + 4 > budget:
                break
            root = _unpack(memories[i])
            expected, _ = predict(model, rows[i].before, rows[i].action, root)
            predict(model, rows[i].before, excursion, root)
            contaminated, _ = predict(model, rows[i].before, rows[i].action)
            isolated, _ = predict(model, rows[i].before, rows[i].action, root)
            branch_checks.append({'index': i, 'excursion': excursion, 'action': rows[i].action,
                                  'shared_equal': contaminated == expected,
                                  'isolated_equal': isolated == expected,
                                  'expected_sha256': digest(expected), 'shared_sha256': digest(contaminated)})
            # A genuine model self-loop can change hidden state without changing observation.
            # Distinguish it with the next (fixed) observed action; these are new contexts.
            if model.calls - replay_calls + validation_calls + 3 > budget:
                continue
            moved, moved_state = predict(model, rows[i].before, excursion, root)
            if moved != rows[i].before or state_key(moved, root) == state_key(moved, moved_state):
                continue
            suffix = rows[min(i + 1, len(rows) - 1)].action
            a, _ = predict(model, moved, suffix, root)
            b, _ = predict(model, moved, suffix, moved_state)
            if a != b:
                key_failures.append({'index': i, 'prefix_extension': [excursion], 'suffix': [suffix],
                                     'differing_fields': differing_fields(root, moved_state),
                                     'observation_key_collides': True,
                                     'refined_key_collides': state_key(moved, root, fields) == state_key(moved, moved_state, fields),
                                     'full_key_collides': state_key(moved, root) == state_key(moved, moved_state),
                                     'left_output_sha256': digest(a), 'right_output_sha256': digest(b)})
    result.update(branch_checks=branch_checks, counterfactual_key_witnesses=key_failures,
                  branch_model_calls=model.calls - audit_calls_start,
                  fresh_prefix_calls=validation_calls, model_calls=model.calls + validation_calls,
                  post_replay_budget=budget, post_replay_used=model.calls - replay_calls + validation_calls,
                  seconds=time.perf_counter() - started)
    return result


def summarize(records):
    ok = [r for r in records if r['status'] == 'OK']
    return {'families': len(records), 'status_counts': dict(Counter(r['status'] for r in records)),
            'runtime_completed': len(ok),
            'trace_alias_families': [r['game'] for r in records if r.get('trace', {}).get('ambiguous_input_groups', 0)],
            'runtime_alias_families': [r['game'] for r in ok if r.get('witnesses')],
            'model_calls': sum(r.get('model_calls') or 0 for r in records),
            'unknown_cost_families': [r['game'] for r in records if r['status'] in {'TIMEOUT', 'ERROR'}],
            'shared_branch_mismatches': sum(not c['shared_equal'] for r in ok for c in r.get('branch_checks', [])),
            'isolated_branch_mismatches': sum(not c['isolated_equal'] for r in ok for c in r.get('branch_checks', [])),
            'branch_checks': sum(len(r.get('branch_checks', [])) for r in ok),
            'fresh_replay_checks': sum(len(r.get('fresh_replay_checks', [])) for r in ok),
            'fresh_replay_mismatches': sum(not c['equal'] for r in ok for c in r.get('fresh_replay_checks', [])),
            'counterfactual_witnesses': sum(len(r.get('counterfactual_key_witnesses', [])) for r in ok),
            'unrepaired_counterfactual_witnesses': sum(c['refined_key_collides'] for r in ok for c in r.get('counterfactual_key_witnesses', [])),
            'sota': False, 'claim': 'Finite diagnostic and repair study; no general or original-agent performance claim.'}

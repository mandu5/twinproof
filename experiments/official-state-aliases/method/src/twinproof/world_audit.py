"""Standalone extraction of the executed bounded search; other audits omitted."""
from collections import deque
import time
from .world_model import state_key

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

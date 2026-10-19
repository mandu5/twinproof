import copy
import importlib

import pytest


def api():
    try:
        return importlib.import_module('twinproof.world_model')
    except ModuleNotFoundError:
        pytest.fail('world-model state adapter is not implemented')


def test_decode_hex_trace_and_reject_invalid_delta():
    m = api()
    p = {'w': 2, 'h': 2, 'n': 2, 'f0': '0123',
         'acts': ['ACTION1', 'ACTION2'], 'deltas': ['001f', '0030']}
    rows = m.decode_showcase(p)
    assert rows[0].before == [[0, 1], [2, 3]]
    assert rows[0].after == rows[1].before == [[0, 15], [2, 3]]
    assert rows[1].after == [[0, 15], [2, 0]]
    for bad in ['004f', '001', 'zzzz', '-01f', '+01f', ' 01f']:
        with pytest.raises(ValueError):
            m.decode_showcase({**p, 'deltas': [bad, '0030']})
    with pytest.raises(ValueError):
        m.decode_showcase({**p, 'acts': 'AB'})


def test_isolated_branches_preserve_cross_global_aliases():
    m = api()
    src = '''\
left = []
right = left
counter = 0
def step(grid, action):
    global counter
    counter += 1
    left.append(action)
    return [[len(right), counter]]
def goal_reached(grid):
    return False
'''
    model = m.PythonModel(src)
    root = model.snapshot()
    a, state_a = model.predict([[0, 0]], 'A', root)
    b, state_b = model.predict([[0, 0]], 'B', root)
    assert a == b == [[1, 1]]
    assert state_a['left'] is state_a['right']
    assert state_b['left'] == ['B']
    assert root['left'] == []
    result, _ = model.predict(a, 'C', state_a)
    assert result == [[2, 2]]


def test_state_key_preserves_tuple_keys_types_aliases_and_dict_order():
    m = api()
    x = []
    shared = {'a': x, 'b': x, 'lookup': {(1, 2): 3}}
    assert m.state_key([[1]], shared) == m.state_key([[1]], copy.deepcopy(shared))
    assert m.state_key([[1]], shared) != m.state_key([[1]], {**shared, 'b': []})
    assert m.state_key([[1]], {'x': [1]}) != m.state_key([[1]], {'x': (1,)})
    assert m.state_key([[1]], {'x': {'a': 1, 'b': 2}}) != m.state_key([[1]], {'x': {'b': 2, 'a': 1}})
    assert m.state_key([[1]], {'x': 1, 'noise': 9}, ['x']) == m.state_key([[1]], {'x': 1, 'noise': 0}, ['x'])


@pytest.mark.parametrize('source', [
    'def step(grid, action, cache=[]):\n cache.append(action)\n return grid',
    'import random\ndef step(grid, action):\n return [[random.randint(0, 1)]]',
    'def step(grid, action):\n return open("private").read()',
    'class State:\n n = 0\ndef step(grid, action):\n return grid',
    'def step(grid, action):\n return globals()[action]',
])
def test_unsupported_state_and_effects_are_explicit(source):
    m = api()
    with pytest.raises(m.UnsupportedModel):
        m.PythonModel(source)


def test_restore_removes_later_created_global():
    m = api()
    model = m.PythonModel('def step(grid, action):\n global extra\n extra = 1\n return grid')
    root = model.snapshot()
    _, later = model.predict([[0]], 'A', root)
    assert later['extra'] == 1
    model.restore(root)
    assert 'extra' not in model.snapshot()


def test_runtime_does_not_mutate_callers_grid():
    m = api()
    model = m.PythonModel('def step(grid, action):\n grid[0][0] = 2\n return grid')
    grid = [[0]]
    out, _ = model.predict(grid, 'A')
    assert grid == [[0]] and out == [[2]]


def test_allowlisted_imported_deepcopy_is_not_model_default_state():
    m = api()
    model = m.PythonModel('from copy import deepcopy\ndef step(grid, action):\n return deepcopy(grid)')
    result, state = model.predict([[1]], 'A')
    assert result == [[1]] and state == {}


def test_alias_between_returned_grid_and_global_state_is_not_silently_broken():
    m = api()
    model = m.PythonModel('saved = []\ndef step(grid, action):\n global saved\n saved = grid\n return grid')
    with pytest.raises(m.UnsupportedModel, match='grid.*global'):
        model.predict([[0]], 'A')


def test_dunder_data_is_branch_state():
    m = api()
    model = m.PythonModel('__counter=0\ndef step(grid, action):\n global __counter\n __counter += 1\n return [[__counter]]')
    root = model.snapshot()
    assert root['__counter'] == 0
    assert model.predict([[0]], 'A', root)[0] == model.predict([[0]], 'A', root)[0] == [[1]]


@pytest.mark.parametrize('src', [
    'history=[]\nappend=history.append\ndef step(grid, action):\n append(action)\n return [[len(history)]]',
    'pop=[1,2,3].pop\ndef step(grid, action):\n return [[pop()]]',
    'Alias=list[[]]\ndef step(grid, action):\n return grid',
])
def test_hidden_alias_carriers_are_explicitly_unsupported(src):
    with pytest.raises(api().UnsupportedModel):
        api().PythonModel(src)


def test_changing_code_binding_is_not_silently_outside_snapshot():
    m = api()
    model = m.PythonModel('def helper():\n return 0\ndef step(grid, action):\n global helper\n helper=lambda:1\n return grid')
    with pytest.raises(m.UnsupportedModel, match='binding'):
        model.predict([[0]], 'A')


def test_set_snapshot_is_rejected_and_keys_keep_observable_iteration():
    m = api()
    with pytest.raises(m.UnsupportedModel, match='set'):
        m.PythonModel('s=set([0,32,40,48])\ndef step(grid, action):\n return [list(s)]')
    a, b = set(), set()
    a.add(0); a.add(8)
    b.add(8); b.add(0)
    assert list(a) != list(b)
    assert m.state_key([[0]], {'s': a}) != m.state_key([[0]], {'s': b})

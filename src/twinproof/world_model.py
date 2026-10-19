"""Audited-subset Python world models and explicit branch state.

This is a research adapter, not a security sandbox or a Python verifier.
Run inspected third-party sources in resource-bounded child processes.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
import types
from dataclasses import dataclass
from typing import Any


class UnsupportedModel(ValueError):
    """An effect or state carrier is outside the audited subset."""


@dataclass
class Transition:
    index: int
    before: list[list[int]]
    action: str
    after: list[list[int]]


def decode_showcase(payload: dict) -> list[Transition]:
    w, h, n = (payload[k] for k in ('w', 'h', 'n'))
    if any(type(v) is not int or v <= 0 for v in (w, h)) or type(n) is not int or n < 0:
        raise ValueError('invalid dimensions/count')
    if w * h > 4096:
        raise ValueError('delta encoding supports at most 4096 cells')
    initial, actions, deltas = (payload[k] for k in ('f0', 'acts', 'deltas'))
    if not isinstance(initial, str) or len(initial) != w * h:
        raise ValueError('initial frame size mismatch')
    if not re.fullmatch('[0-9a-fA-F]+', initial):
        raise ValueError('initial frame is not exact hexadecimal')
    if not isinstance(actions, list) or not isinstance(deltas, list):
        raise ValueError('actions and deltas must be arrays')
    if len(actions) != n or len(deltas) != n:
        raise ValueError('trace length mismatch')
    try:
        flat = [int(c, 16) for c in initial]
    except ValueError as exc:
        raise ValueError('invalid initial frame') from exc
    rows = []
    for index, (action, delta) in enumerate(zip(actions, deltas)):
        if (not isinstance(action, str) or not isinstance(delta, str) or len(delta) % 4
                or re.fullmatch('[0-9a-fA-F]*', delta) is None):
            raise ValueError('invalid action/delta')
        before = [flat[j:j + w] for j in range(0, w * h, w)]
        for j in range(0, len(delta), 4):
            pos, color = int(delta[j:j + 3], 16), int(delta[j + 3], 16)
            if pos >= len(flat):
                raise ValueError('delta index outside frame')
            flat[pos] = color
        after = [flat[j:j + w] for j in range(0, w * h, w)]
        rows.append(Transition(index, before, action, after))
    return rows


def graph_data(value: Any) -> Any:
    """Encode types, container identity and dictionary insertion order."""
    memo: dict[int, int] = {}

    def visit(v):
        kind = type(v)
        if v is None or kind in (bool, int, str):
            return [kind.__name__, v]
        if kind is float:
            if not math.isfinite(v):
                raise UnsupportedModel('non-finite state')
            return ['float', v.hex()]
        if kind is bytes:
            return ['bytes', v.hex()]
        if kind not in (list, tuple, dict, set, frozenset):
            raise UnsupportedModel(f'unsupported state type: {kind.__name__}')
        if id(v) in memo:
            return ['ref', memo[id(v)]]
        token = len(memo)
        memo[id(v)] = token
        if kind is dict:
            contents = [[visit(k), visit(val)] for k, val in v.items()]
        elif kind in (set, frozenset):
            # Iteration order is observable. PythonModel rejects sets in snapshots
            # because deepcopy/pickle need not preserve this order.
            contents = [visit(x) for x in v]
        else:
            contents = [visit(x) for x in v]
        return [kind.__name__, token, contents]

    return visit(value)


def state_key(grid, snapshot: dict, fields=None) -> str:
    names = sorted(snapshot if fields is None else fields)
    state = [(name, snapshot[name]) for name in names if name in snapshot]
    raw = json.dumps(graph_data((grid, state)), separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _immutable(value) -> bool:
    return (value is None or type(value) in (bool, int, float, str, bytes)
            or type(value) in (tuple, frozenset) and all(_immutable(x) for x in value))


def _mutable_ids(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return set()
    seen.add(id(value))
    if type(value) not in (list, tuple, dict, set, frozenset):
        return set()
    result = {id(value)} if type(value) in (list, dict, set) else set()
    children = list(value.keys()) + list(value.values()) if type(value) is dict else value
    for child in children:
        result.update(_mutable_ids(child, seen))
    return result


def _check_snapshot_data(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return
    seen.add(id(value))
    if type(value) in (set, frozenset):
        raise UnsupportedModel('set/frozenset iteration is not preserved by snapshot serialization')
    if type(value) in (list, tuple, dict):
        children = list(value.keys()) + list(value.values()) if type(value) is dict else value
        for child in children:
            _check_snapshot_data(child, seen)


def _safe_alias(value):
    return isinstance(value, type) or _immutable(value) or (
        isinstance(value, types.GenericAlias) and all(_safe_alias(x) for x in value.__args__))


RESERVED = {'__name__', '__builtins__', '__doc__', '__annotations__'}


ALLOWED_IMPORTS = {'__future__', 'copy', 'math', 'base64', 'zlib', 'json',
                   'collections', 'itertools', 'functools', 'bisect', 're', 'typing', 'hashlib'}
FORBIDDEN_CALLS = {'open', 'eval', 'exec', 'compile', '__import__', 'globals',
                   'locals', 'vars', 'setattr', 'delattr', 'input', 'breakpoint'}


def inspect_source(source: str) -> dict:
    tree = ast.parse(source)
    imports, reasons, mutated = set(), [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imports.add(node.module or '')
            if node.level:
                reasons.append('relative import')
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Nonlocal)):
            reasons.append(type(node).__name__)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
            reasons.append('function decorator')
        if isinstance(node, ast.Global):
            mutated.update(node.names)
            if RESERVED.intersection(node.names):
                reasons.append('reserved binding mutation')
        if isinstance(node, ast.Name):
            if node.id == '__annotations__' or node.id in RESERVED and isinstance(node.ctx, ast.Store):
                reasons.append('reserved metadata access/mutation')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            reasons.append(f'call:{node.func.id}')
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            reasons.append('dunder attribute')
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Attribute) for t in targets):
                reasons.append('attribute mutation')
    reasons.extend(f'import:{name}' for name in imports if name not in ALLOWED_IMPORTS)
    return {'imports': sorted(imports), 'declared_global_writes': sorted(mutated),
            'unsupported': sorted(set(reasons))}


class PythonModel:
    def __init__(self, source: str):
        self.census = inspect_source(source)
        if self.census['unsupported']:
            raise UnsupportedModel('; '.join(self.census['unsupported']))
        self.namespace = {'__name__': 'twinproof_inspected_model', '__builtins__': __builtins__}
        exec(compile(source, '<inspected-world-model>', 'exec'), self.namespace)
        if not callable(self.namespace.get('step')):
            raise UnsupportedModel('no step(grid, action) function')
        self._code_names = set()
        for name, value in self.namespace.items():
            if isinstance(value, types.BuiltinFunctionType) and getattr(value, '__self__', None) is not None:
                if not isinstance(value.__self__, types.ModuleType):
                    raise UnsupportedModel('data-bound built-in method hides receiver state')
            if isinstance(value, types.GenericAlias) and not _safe_alias(value):
                raise UnsupportedModel('mutable GenericAlias argument')
            if isinstance(value, types.FunctionType) and value.__module__ == self.namespace['__name__']:
                if value.__closure__ or not all(_immutable(x) for x in (value.__defaults__ or ())):
                    raise UnsupportedModel('closure or mutable function default')
                if not all(_immutable(x) for x in (value.__kwdefaults__ or {}).values()):
                    raise UnsupportedModel('mutable keyword default')
                if value.__dict__:
                    raise UnsupportedModel('function attribute state')
            if name in RESERVED or isinstance(value, (types.ModuleType, types.FunctionType,
                                                           types.BuiltinFunctionType, types.GenericAlias, type)):
                self._code_names.add(name)
            elif name == 'annotations' and type(value).__module__ == '__future__':
                self._code_names.add(name)
        self._fixed_bindings = {name: self.namespace[name] for name in self._code_names}
        self.snapshot()  # Fail immediately for unsupported global data carriers.
        self.calls = 0

    def snapshot(self) -> dict:
        if any(self.namespace.get(name) is not value for name, value in self._fixed_bindings.items()):
            raise UnsupportedModel('excluded code/module binding changed')
        values = {k: v for k, v in self.namespace.items() if k not in self._code_names}
        # Validate all roots as a single graph, then copy as a single graph.
        graph_data(values)
        _check_snapshot_data(values)
        return copy.deepcopy(values)

    def restore(self, state: dict) -> None:
        graph_data(state)
        _check_snapshot_data(state)
        if self._code_names.intersection(state):
            raise UnsupportedModel('snapshot attempts to replace a fixed code binding')
        self.namespace.update(self._fixed_bindings)
        for key in list(self.namespace):
            if key not in self._code_names:
                del self.namespace[key]
        self.namespace.update(copy.deepcopy(state))

    def predict(self, grid, action, snapshot=None):
        if snapshot is not None:
            self.restore(snapshot)
        self.calls += 1
        result = self.namespace['step'](copy.deepcopy(grid), action)
        if (not isinstance(result, list) or not result or
                any(not isinstance(row, list) or len(row) != len(result[0]) for row in result) or
                any(type(x) is not int for row in result for x in row)):
            raise UnsupportedModel('step did not return a rectangular integer grid')
        globals_data = {k: v for k, v in self.namespace.items() if k not in self._code_names}
        if _mutable_ids(result) & _mutable_ids(globals_data):
            raise UnsupportedModel('returned grid aliases global data; combined state carrier required')
        return copy.deepcopy(result), self.snapshot()

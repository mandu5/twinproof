"""Conditional trace equivalence with caller-supplied creation witnesses.

This checks observations under a trusted contract. It neither infers identifier
roles from string shape nor proves that the supplied contract describes intent.
"""

import json
import re
from typing import Any

from .state import Verdict, _validate, compare_states


def _pointer(value: str) -> tuple[str, ...]:
    if type(value) is not str or (value and not value.startswith("/")):
        raise ValueError("Expected a JSON Pointer")
    if re.search(r"~(?![01])", value):
        raise ValueError("Invalid JSON Pointer escape")
    return tuple(p.replace("~1", "/").replace("~0", "~")
                 for p in value.split("/")[1:]) if value else ()


def _matches(pattern, path):
    return len(pattern) == len(path) and all(a == "*" or a == b for a, b in zip(pattern, path))


def _resolve(payload, path):
    for part in path:
        if type(payload) is list:
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError("Invalid array index in witness")
            payload = payload[int(part)]
        elif type(payload) is dict:
            payload = payload[part]
        else:
            raise ValueError("Witness path crosses a scalar")
    return payload


def _contract(contract, step_count):
    if type(contract) is not dict or set(contract) != {"namespaces", "bindings"}:
        raise ValueError("Contract requires exactly namespaces and bindings")
    namespaces, bindings = contract["namespaces"], contract["bindings"]
    if type(namespaces) is not dict or type(bindings) is not list:
        raise ValueError("Invalid contract container types")
    roles = {"values": [], "keys": []}
    for name, spec in namespaces.items():
        if not name or type(spec) is not dict or set(spec) != {"values", "keys"}:
            raise ValueError("Namespace requires a name, values and keys")
        for kind in roles:
            if type(spec[kind]) is not list:
                raise ValueError("Role paths must be lists")
            for value in spec[kind]:
                pattern = _pointer(value)
                for previous, _ in roles[kind]:
                    if len(pattern) == len(previous) and all(
                        a == b or a == "*" or b == "*" for a, b in zip(pattern, previous)
                    ):
                        raise ValueError("Overlapping identifier roles")
                roles[kind].append((pattern, name))
    grouped = [[] for _ in range(step_count)]
    for binding in bindings:
        required = {"step", "namespace", "expected", "observed", "path"}
        if type(binding) is not dict or set(binding) != required:
            raise ValueError("Malformed creation witness")
        step = binding["step"]
        if type(step) is not int or not 0 <= step < step_count:
            raise ValueError("Creation step is outside the trace")
        if binding["namespace"] not in namespaces:
            raise ValueError("Unknown witness namespace")
        if any(type(binding[k]) is not str or not binding[k] for k in ("expected", "observed")):
            raise ValueError("Fresh identifiers must be nonempty strings")
        path = _pointer(binding["path"])
        if not path or path[0] != "result" or _role(roles, "values", path) != binding["namespace"]:
            raise ValueError("Creation must be witnessed at a declared result ID path")
        grouped[step].append((binding, path))
    return roles, grouped


def _role(roles, kind, path):
    return next((name for pattern, name in roles[kind] if _matches(pattern, path)), None)


def _walk(value, roles, visit, path=()):
    name = _role(roles, "values", path)
    if name is not None and type(value) is str:
        visit(name, value)
    if type(value) is dict:
        key_name = _role(roles, "keys", path)
        for key, child in value.items():
            if key_name is not None:
                visit(key_name, key)
            _walk(child, roles, visit, path + (key,))
    elif type(value) is list:
        for i, child in enumerate(value):
            _walk(child, roles, visit, path + (str(i),))


def _normalize(value, roles, mapping, path=()):
    def token(name, identifier):
        # Tag bound and unbound IDs separately: a corrupt unbound value that
        # happens to equal the reference's ID must not acquire that binding.
        if type(identifier) is str and identifier in mapping[name]:
            return [name, "bound", mapping[name][identifier]]
        return [name, "literal", identifier]

    name = _role(roles, "values", path)
    if name is not None:
        return ["identifier", token(name, value)]
    if type(value) is dict:
        key_name = _role(roles, "keys", path)
        # Encode every node and key, including ordinary JSON. Otherwise a raw
        # candidate array/key could equal our ID token after renamed ID keys
        # align locations with different role interpretations.
        return ["object", {
            json.dumps(["identifier", token(key_name, key)] if key_name else ["literal", key], ensure_ascii=False):
            _normalize(child, roles, mapping, path + (key,))
            for key, child in value.items()
        }]
    if type(value) is list:
        return ["array", [_normalize(child, roles, mapping, path + (str(i),)) for i, child in enumerate(value)]]
    return ["scalar", value]


def compare_traces(reference: Any, candidate: Any, contract: Any) -> Verdict:
    """Compare complete ordered observations under explicit ID creation bindings.

    UNKNOWN denotes malformed or contradictory evidence. FAIL denotes an observed
    difference, including an unbound identifier. Timestamps are always exact;
    callers should control the clock before recording traces when appropriate.
    Difference paths are in the normalized observation, not the raw ID-key path.
    """
    try:
        for value in (reference, candidate, contract):
            _validate(value, set())
        for trace in (reference, candidate):
            if type(trace) is not dict or set(trace) != {"initial", "steps"} or type(trace["steps"]) is not list:
                raise ValueError("Trace requires exactly initial and a steps list")
        if len(reference["steps"]) != len(candidate["steps"]):
            return compare_states(reference, candidate)
        roles, grouped = _contract(contract, len(reference["steps"]))
        namespaces = contract["namespaces"]
        mappings = [{name: {} for name in namespaces} for _ in range(2)]
        seen = [{name: set() for name in namespaces} for _ in range(2)]
        normalized = [[], []]
        for side, trace in enumerate((reference, candidate)):
            _walk(trace["initial"], roles, lambda n, v, side=side: seen[side][n].add(v))
        for step, pair in enumerate(zip(reference["steps"], candidate["steps"])):
            for binding, path in grouped[step]:
                name = binding["namespace"]
                identifiers = (binding["expected"], binding["observed"])
                token_index = len(mappings[0][name])
                for side, identifier in enumerate(identifiers):
                    if _resolve(pair[side], path) != identifier:
                        raise ValueError("Creation witness disagrees with the trace")
                    if identifier in seen[side][name] or identifier in mappings[side][name]:
                        raise ValueError("Creation witness reuses an existing identifier")
                    mappings[side][name][identifier] = token_index
            for side, payload in enumerate(pair):
                normalized[side].append(_normalize(payload, roles, mappings[side]))
                _walk(payload, roles, lambda n, v, side=side: seen[side][n].add(v))
        return compare_states(
            {"initial": reference["initial"], "steps": normalized[0]},
            {"initial": candidate["initial"], "steps": normalized[1]})
    except (ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
        return Verdict("UNKNOWN", reason=str(exc))

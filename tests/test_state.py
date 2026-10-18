import copy
import math

import pytest

from twinproof.state import compare_states


@pytest.mark.parametrize(
    "expected,observed,status,paths",
    [
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}, "PASS", []),
        ({"keep": 8, "changed": 2}, {"keep": 0, "changed": 2}, "FAIL", ["/keep"]),
        ({}, {"ghost": None}, "FAIL", ["/ghost"]),
        ({"gone": None}, {}, "FAIL", ["/gone"]),
        ({"a.b": 2, "x/y": {"~": 3}}, {"a.b": 4, "x/y": {"~": 8}}, "FAIL", ["/a.b", "/x~1y/~0"]),
        ([1, 2], [2, 1], "FAIL", ["/0", "/1"]),
        ([1], [1, None], "FAIL", ["/1"]),
        ({"enabled": True}, {"enabled": 1}, "FAIL", ["/enabled"]),
        ({"n": 1}, {"n": 1.0}, "PASS", []),
        (None, {}, "FAIL", [""]),
        ({"timestamp": "new"}, {"timestamp": "old"}, "FAIL", ["/timestamp"]),
    ],
)
def test_complete_state_catches_corruption(expected, observed, status, paths):
    result = compare_states(expected, observed)
    assert result.status == status
    assert [d.path for d in result.differences] == paths


@pytest.mark.parametrize("invalid", [math.nan, math.inf, {1: "key"}, (1, 2), {"x": object()}])
def test_non_json_state_is_unknown_even_when_both_sides_match(invalid):
    assert compare_states(invalid, invalid).status == "UNKNOWN"


def test_missing_is_distinguished_from_explicit_null():
    result = compare_states({"x": None}, {})
    difference = result.differences[0]
    assert difference.expected_present is True
    assert difference.observed_present is False
    assert difference.expected is None


def test_comparison_does_not_mutate_inputs():
    a, b = {"nested": [{"x": 1}]}, {"nested": [{"x": 2}]}
    originals = copy.deepcopy((a, b))
    compare_states(a, b)
    assert (a, b) == originals


def test_cycles_return_unknown_instead_of_recursing_forever():
    cycle = []
    cycle.append(cycle)
    assert compare_states(cycle, []).status == "UNKNOWN"

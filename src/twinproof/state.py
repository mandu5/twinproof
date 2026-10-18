"""Complete JSON-state comparison, without implicit volatile-field masks."""

from dataclasses import asdict, dataclass
from decimal import Decimal
import math
from typing import Any, Literal


@dataclass(frozen=True)
class Difference:
    path: str
    expected_present: bool
    observed_present: bool
    expected: Any
    observed: Any


@dataclass(frozen=True)
class Verdict:
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    differences: tuple[Difference, ...] = ()
    reason: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _validate(value: Any, ancestors: set[int], depth: int = 0) -> None:
    if depth > 128:
        raise ValueError("JSON nesting exceeds supported depth 128")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Nonfinite number is not JSON")
        return
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError("Nonfinite number is not JSON")
        return
    if type(value) not in (dict, list):
        raise ValueError(f"Unsupported JSON type: {type(value).__name__}")
    if id(value) in ancestors:
        raise ValueError("Cyclic value is not JSON")
    ancestors.add(id(value))
    try:
        if isinstance(value, dict):
            if any(type(key) is not str for key in value):
                raise ValueError("JSON object keys must be strings")
            children = value.values()
        else:
            children = value
        for child in children:
            _validate(child, ancestors, depth + 1)
    finally:
        ancestors.remove(id(value))


def _segment(key: str | int) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def compare_states(expected: Any, observed: Any) -> Verdict:
    """Compare JSON values; invalid inputs produce UNKNOWN, never equality.

    Numeric 1 and 1.0 are equal JSON numbers, while True and 1 differ. A missing
    field differs from null. The inputs and their nested objects are not changed.
    """
    try:
        _validate(expected, set())
        _validate(observed, set())
    except (ValueError, RecursionError) as exc:
        return Verdict("UNKNOWN", reason=str(exc))

    differences: list[Difference] = []

    def visit(left: Any, right: Any, path: str) -> None:
        if type(left) is dict and type(right) is dict:
            for key in sorted(left.keys() | right.keys()):
                child_path = path + "/" + _segment(key)
                if key not in left or key not in right:
                    differences.append(Difference(child_path, key in left, key in right,
                                                  left.get(key), right.get(key)))
                else:
                    visit(left[key], right[key], child_path)
        elif type(left) is list and type(right) is list:
            for index in range(max(len(left), len(right))):
                child_path = path + "/" + str(index)
                if index >= len(left) or index >= len(right):
                    differences.append(Difference(
                        child_path, index < len(left), index < len(right),
                        left[index] if index < len(left) else None,
                        right[index] if index < len(right) else None))
                else:
                    visit(left[index], right[index], child_path)
        else:
            numbers = type(left) in (int, float, Decimal) and type(right) in (int, float, Decimal)
            if (type(left) is not type(right) and not numbers) or left != right:
                differences.append(Difference(path, True, True, left, right))

    visit(expected, observed, "")
    return Verdict("FAIL" if differences else "PASS", tuple(differences))

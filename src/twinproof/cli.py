import argparse
from decimal import Decimal, DecimalException
import json
from pathlib import Path

from .state import compare_states


def read_json(path: Path):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-JSON numeric constant: {value}")

    def decimal_number(text):
        try:
            return Decimal(text)
        except DecimalException as exc:
            raise ValueError("JSON number exceeds supported precision/exponent range") from exc

    return json.loads(path.read_text(), object_pairs_hook=object_pairs,
                      parse_constant=invalid_constant, parse_float=decimal_number)


def _exact_json(value) -> str:
    """Preserve Decimal values as numeric tokens in mismatch diagnostics.

    Delegate escaping and ordinary scalar serialization to json.dumps; converting
    Decimal to float here would corrupt the evidence we just compared.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Cannot serialize a nonfinite JSON number")
        return str(value)
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(key, ensure_ascii=False) + ": " + _exact_json(child)
                                for key, child in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_exact_json(child) for child in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TwinProof: state comparison and oracle audits")
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="Compare complete JSON states")
    compare.add_argument("expected", type=Path)
    compare.add_argument("observed", type=Path)
    trace = commands.add_parser("trace", help="Compare traces with trusted ID creation witnesses")
    trace.add_argument("reference", type=Path)
    trace.add_argument("candidate", type=Path)
    trace.add_argument("contract", type=Path)
    run = commands.add_parser("audit", help="Audit pinned EnvSimBench graders without inference")
    run.add_argument("--snapshot", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "trace":
            from .trace import compare_traces
            verdict = compare_traces(read_json(args.reference), read_json(args.candidate), read_json(args.contract))
            print(_exact_json(verdict.as_dict()))
            return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[verdict.status]
        if args.command == "compare":
            verdict = compare_states(read_json(args.expected), read_json(args.observed))
            print(_exact_json(verdict.as_dict()))
            return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[verdict.status]
        from .audit import audit
        summary = audit(args.snapshot, args.output)
        brief = {k: summary[k] for k in ("experiment", "samples", "environments", "constructed_cases", "claims")}
        brief["error_count"] = len(summary["errors"])
        print(json.dumps(brief))
        return 2 if summary["errors"] else 0
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"status": "UNKNOWN", "reason": str(exc)}))
        return 2

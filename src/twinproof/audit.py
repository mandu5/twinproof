"""Oracle audit, not a simulator leaderboard. Every payload uses the reference."""

from collections import Counter, defaultdict
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter
from typing import Any

from .state import compare_states
from .upstream import load_grader, manifest, verified_bytes


@dataclass(frozen=True)
class AuditCase:
    family: str
    target: dict
    should_pass: bool


def replacement_changes(before: dict, target: dict) -> list[dict]:
    """Set complete top-level values through the original supported patch API."""
    def path(key):
        return [key] if "." in key else key

    changes = [{"type": "delete", "path": path(key)} for key in before if key not in target]
    changes.extend({"type": "modify" if key in before else "add", "path": path(key), "value": value}
                   for key, value in target.items())
    return changes


def _deleted_paths(before, after, prefix=()):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before):
            if key not in after:
                yield prefix + (key,)
            else:
                yield from _deleted_paths(before[key], after[key], prefix + (key,))


def _boolean_paths(value, prefix=()):
    if type(value) is bool:
        yield prefix
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _boolean_paths(value[key], prefix + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _boolean_paths(child, prefix + (index,))


def _parent(value, path):
    for key in path[:-1]:
        value = value[key]
    return value


def build_cases(before: dict, after: dict) -> list[AuditCase]:
    cases = [AuditCase("gold_identity", copy.deepcopy(after), True)]
    extra = copy.deepcopy(after)
    key = "__twinproof_unexpected__"
    while key in before or key in after:
        key += "_"
    extra[key] = "deliberately corrupted audit state"
    cases.append(AuditCase("extra_field", extra, False))

    deleted = list(_deleted_paths(before, after))
    if deleted:
        wrong = copy.deepcopy(after)
        for path in deleted:
            _parent(wrong, path)[path[-1]] = None
        cases.append(AuditCase("null_for_deleted", wrong, False))

    boolean = next(_boolean_paths(after), None)
    if boolean:
        wrong = copy.deepcopy(after)
        parent = _parent(wrong, boolean)
        parent[boolean[-1]] = int(parent[boolean[-1]])
        cases.append(AuditCase("boolean_as_number", wrong, False))
    return cases


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def audit(snapshot_dir: Path, output_dir: Path) -> dict:
    pins = manifest()
    data_path = "Benchmark/9.choice_final_combined-167env.json"
    raw = verified_bytes(snapshot_dir / data_path, pins["files"][data_path]["sha256"])
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != 400:
        raise ValueError("Pinned dataset must contain exactly 400 rows")
    graders = {name: load_grader(snapshot_dir / name, info["sha256"])
               for name, info in pins["files"].items() if name.startswith("Evaluation/")}
    output_dir.mkdir(parents=True, exist_ok=False)
    counts = defaultdict(Counter)
    errors = []
    rejected_gold = []
    state_counts = Counter()
    start = perf_counter()
    environments = set()
    case_count = 0

    with (output_dir / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for index, row in enumerate(rows):
            detail = row["step_detail"]
            before, after = detail["config_before"], detail["config_after"]
            env_id = row["task_info"]["env_id"]
            environments.add(env_id)
            state_counts["unchanged" if compare_states(before, after).status == "PASS" else "changed"] += 1
            cases = build_cases(before, after)
            for case in cases:
                case_count += 1
                observation = detail["observation"]
                feedback = observation.get("content") if isinstance(observation, dict) else observation
                prediction = {"feedback": feedback, "config_changes": replacement_changes(before, case.target)}
                # This independent serialized check protects the construction labels.
                if (_canonical(case.target) == _canonical(after)) != case.should_pass:
                    raise ValueError(f"Invalid constructed label for row {index}, {case.family}")
                checked = compare_states(after, case.target)
                statuses = {"twinproof_full_state": checked.status,
                            "canonical_json_serialization": "PASS" if _canonical(after) == _canonical(case.target) else "FAIL",
                            "python_equality": "PASS" if after == case.target else "FAIL"}
                row_errors = {}
                for name, grader in graders.items():
                    try:
                        step = grader.functions["extract_steps"](row)[0]
                        result = grader.evaluate(step, prediction)
                        if "error" in result:
                            raise ValueError(result["error"])
                        if _canonical(result["predicted_after"]) != _canonical(case.target):
                            raise ValueError("Original patch reconstruction differs from intended state")
                        statuses[name] = "PASS" if result["config_change_correct"] else "FAIL"
                        if case.family == "gold_identity" and statuses[name] == "FAIL":
                            changes = result["changes_true"]
                            has_deletion = any(c["type"] == "removed" for c in changes)
                            rejected_gold.append({"row": index, "env_id": env_id, "grader": name,
                                                  "has_deletion": has_deletion,
                                                  "paths": [c["path"] for c in changes]})
                    except Exception as exc:
                        statuses[name] = "UNKNOWN"
                        row_errors[name] = str(exc)
                        errors.append({"row": index, "family": case.family, "grader": name, "error": str(exc)})

                for name, status in statuses.items():
                    tally = counts[(name, case.family)]
                    tally["n"] += 1
                    tally[status.lower()] += 1
                    tally["false_accept"] += status == "PASS" and not case.should_pass
                    tally["false_reject"] += status == "FAIL" and case.should_pass
                record = {"row": index, "env_id": env_id, "family": case.family,
                          "should_pass": case.should_pass, "verdicts": statuses,
                          "reference_sha256": _digest(after), "candidate_sha256": _digest(case.target),
                          "mismatch_paths": [d.path for d in checked.differences], "errors": row_errors}
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "schema_version": 1, "experiment": "ground_truth_assisted_oracle_audit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": pins, "python": platform.python_version(),
        "samples": len(rows), "environments": len(environments), "constructed_cases": case_count,
        "state_counts": dict(state_counts), "elapsed_seconds": perf_counter() - start,
        "model_api_calls": 0, "gpu_jobs": 0,
        "grader_configuration": {"thinking": False, "max_retries": 0, "optional_json_repair": False,
                                 "measurement": "config_change_correct only; feedback is not scored"},
        "results": [{"grader": name, "family": family, **dict(tally)} for (name, family), tally in sorted(counts.items())],
        "gold_rejections": rejected_gold, "errors": errors,
        "claims": {"SOTA": False, "simulator_accuracy_measured": False, "model_rankings_recomputed": False,
                   "independent_novelty_established": False, "external_user_validation": False},
        "limits": [
            "All predictions are deterministic constructions using ground truth, not model outputs.",
            "Repeated mutations and multiple samples per environment are not independent observations.",
            "Canonical JSON is a strong simple baseline and may tie TwinProof on these constructions.",
            "Canonical serialization is not a general semantic comparator: 1 and 1.0 serialize differently.",
            "No historical model rankings can be corrected without their raw predictions.",
            "This audit inspects the pinned public scripts, not unpublished evaluation runs.",
            "These known-reference tests do not validate the proposed nondeterminism-aware method."
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary

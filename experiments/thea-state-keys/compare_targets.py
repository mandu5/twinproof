"""Compare all 80 reproduced target rows against frozen results, excluding timing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipts", type=Path, nargs=4, help="Four fresh experiment.py targets receipts")
    args = parser.parse_args()
    rows = []
    all_calls = 0
    for path in args.receipts:
        receipt = json.loads(path.read_text())
        if receipt["exit_code"] != 0 or receipt["timed_out"]:
            raise ValueError(f"Incomplete shard: {path}")
        records = [json.loads(line) for line in receipt["stdout"].splitlines()]
        rows.extend(record for record in records if record.get("stage") == "target_result")
        finished = [record for record in records if record.get("stage") == "finished"]
        if len(finished) != 1:
            raise ValueError(f"Missing unique completion record: {path}")
        all_calls += finished[0]["all_engine_calls"]
    expected = json.loads((PACKAGE / "receipts/original/goal-v2-rows.json").read_text())["rows"]
    def indexed(items):
        result = {}
        for row in items:
            key = row["task_id"], row["method"]
            if key in result:
                raise ValueError(f"Duplicate task/arm: {key}")
            result[key] = {name: value for name, value in row.items() if name != "seconds"}
        return result
    if indexed(rows) != indexed(expected):
        raise AssertionError("Reproduced routes/counters/outcomes differ from frozen results")
    final = json.loads((PACKAGE / "receipts/original/final-result.json").read_text())
    if all_calls != final["all_engine_calls"]:
        raise AssertionError("Total setup/search/replay call accounting differs")
    print(json.dumps({"matched_target_rows": len(rows), "all_engine_calls": all_calls, "comparison_excludes": ["seconds"]}))


if __name__ == "__main__":
    main()

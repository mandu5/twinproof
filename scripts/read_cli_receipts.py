"""Decode downloaded CI logs without calling a network service."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

from twinproof.cli_receipts import decode_logs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, default=120)
    args = parser.parse_args()
    receipts, raw, environments = decode_logs(args.log.read_text(), args.expected_cases)
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.joinpath("receipts.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in receipts))
    args.output.joinpath("raw.json.gz").write_bytes(gzip.compress(json.dumps(raw, sort_keys=True).encode(), mtime=0))
    args.output.joinpath("environment.json").write_text(json.dumps(environments, indent=2) + "\n")
    grouped = {}
    for receipt in receipts:
        key = f"{receipt['family']}/{receipt['run']}/{receipt['mode']}"
        grouped.setdefault(key, []).append(receipt)
    summary = {"schema": 1, "cases": len(receipts),
               "log_sha256": hashlib.sha256(args.log.read_bytes()).hexdigest(),
               "verdicts": dict(Counter(r["verdict"] for r in receipts)),
               "application_calls": sum(r["application_calls"] for r in receipts),
               "setup_calls": sum(r["setup_calls"] for r in receipts),
               "groups": []}
    for key, rows in sorted(grouped.items()):
        summary["groups"].append({"group": key, "cases": len(rows),
                                 "verdicts": dict(Counter(r["verdict"] for r in rows)),
                                 "median_application_calls": median(r["application_calls"] for r in rows),
                                 "median_reference_calls": median(r["reference_calls"] for r in rows),
                                 "median_total_process_calls": median(r["total_process_calls"] for r in rows),
                                 "witnesses": sorted(set(json.dumps(r["witness"]) for r in rows))})
    args.output.joinpath("summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

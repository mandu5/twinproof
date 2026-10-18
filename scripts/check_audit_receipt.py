"""Check the published oracle-audit counts in CI; no dataset redistribution."""
import json
from pathlib import Path
import sys


actual = json.loads(Path(sys.argv[1]).read_text())
expected = json.loads((Path(__file__).resolve().parents[1] / "results/2026-10-18/summary.json").read_text())
for key in ("samples", "environments", "constructed_cases", "state_counts", "results", "errors"):
    if actual[key] != expected[key]:
        raise SystemExit(f"Audit regression in {key}")
print("Published audit counts reproduced")

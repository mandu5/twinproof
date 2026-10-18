"""Compare runtime pilot counts, not platform-dependent timing or trace hashes."""
import json
from pathlib import Path
import sys


actual = json.loads(Path(sys.argv[1]).read_text())
expected = json.loads((Path(__file__).resolve().parents[1] / "results/stage1/final-run/summary.json").read_text())
for key in ("environments_total", "environment_status", "observations", "categories", "free_status",
            "coupled_status", "canonical_free_status", "attempted_calls", "method_executions", "inference_calls"):
    if actual[key] != expected[key]:
        raise SystemExit(f"Runtime pilot regression in {key}: {actual[key]} != {expected[key]}")
print("Published runtime pilot counts reproduced")

"""Launch bounded offline workers using this active virtual environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["witnesses", "targets"])
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New receipt path; refuses overwriting existing evidence")
    parser.add_argument("--shard", type=int, choices=range(4), default=0)
    args = parser.parse_args()
    inputs, output = args.inputs.expanduser().resolve(), args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Receipt already exists: {output}")
    command = [sys.executable, "-I", "-B", str(PACKAGE / "worker.py"), args.mode, "--inputs", str(inputs), "--shard", str(args.shard)]
    mac_sandbox = Path("/usr/bin/sandbox-exec")
    kernel_guard = "unavailable; Python audit guard only, not a general adversarial-code sandbox"
    if sys.platform == "darwin" and mac_sandbox.is_file():
        profile = '(version 1) (allow default) (deny network*) (deny file-write*) (allow file-write* (literal "/dev/null"))'
        command = [str(mac_sandbox), "-p", profile] + command
        kernel_guard = "macOS sandbox-exec denies network and file writes"
    environment = {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
    started = time.monotonic()
    report = {
        "schema_version": 1, "command": command, "mode": args.mode, "shard": args.shard,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "dependency_versions": {name: metadata.version(name) for name in ["numpy", "scipy", "zstandard", "certifi"]},
        "requirements_sha256": hashlib.sha256((PACKAGE / "requirements.txt").read_bytes()).hexdigest(),
        "kernel_guard": kernel_guard, "environment_keys": sorted(environment),
        "wall_timeout_seconds": 90, "cpu_limit_seconds": 75,
        "portable_runner_sha256": {name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() for name in ["experiment.py", "worker.py", "model_runtime.py", "fetch_inputs.py"]},
        "pins_sha256": hashlib.sha256((PACKAGE / "pins.json").read_bytes()).hexdigest(),
    }
    try:
        process = subprocess.run(command, cwd=PACKAGE, env=environment, capture_output=True, text=True, timeout=90)
        report.update(exit_code=process.returncode, timed_out=False, stdout=process.stdout, stderr=process.stderr)
    except subprocess.TimeoutExpired as error:
        report.update(exit_code=None, timed_out=True, stdout=error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or "", stderr=error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or "", unfinished_engine_call_count="UNKNOWN")
    report["seconds"] = time.monotonic() - started
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"receipt": str(output), "exit_code": report["exit_code"], "timed_out": report["timed_out"], "seconds": report["seconds"], "stderr": report["stderr"][:2000]}))
    if report["exit_code"] != 0:
        raise SystemExit(1)
    for line in report["stdout"].splitlines():
        record = json.loads(line)
        if record.get("stage") == "fixed_witness_replay":
            print(json.dumps({"checks_passed": len(record["checks"]), "all_engine_calls": record["all_engine_calls"]}))


if __name__ == "__main__":
    main()

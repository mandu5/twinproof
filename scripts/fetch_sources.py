#!/usr/bin/env python3
"""Fetch the pinned public sources using curl's system certificate store."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twinproof.upstream import manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/envsimbench")
    args = parser.parse_args()
    pins = manifest()
    receipts = []
    for name, info in pins["files"].items():
        target = args.output / name
        url = f"https://raw.githubusercontent.com/cookieApril/EnvSimBench/{pins['commit']}/{name}"
        raw = target.read_bytes() if target.exists() else subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "90", url],
            capture_output=True, check=True).stdout
        if hashlib.sha256(raw).hexdigest() != info["sha256"] or len(raw) != info["bytes"]:
            raise ValueError(f"Source verification failed; no file overwritten: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(target.name + ".partial")
            temporary.write_bytes(raw)
            temporary.replace(target)
        receipts.append({"path": name, "url": url, **info})
        print(f"Verified {name} ({len(raw)} bytes)")
    (args.output / "fetch-receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Container-only entrypoint. Third-party stdout is captured, never streamed."""
import argparse
import base64
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

from twinproof.cli_pilot import MODES, experiment


def emit(label, value):
    print(label + " " + json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=("zoxide", "dstask"))
    parser.add_argument("--seeds", default="0,1,2,3,4")
    args = parser.parse_args()
    if not Path("/.dockerenv").exists() or platform.system() != "Linux":
        raise SystemExit("Released programs may execute only in the Linux container capsule")
    manifest = json.loads(Path("/inputs/verified.json").read_text())
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                   "packages": {name: importlib.metadata.version(name)
                                for name in ("aalpy", "pydot", "pyparsing")}}
    emit("TWINPROOF_ENVIRONMENT", {"family": args.family, **environment, **manifest})
    reference = ["/inputs/reference"]
    pairs = [("reference_control", reference)] + [
        (item["run"], [sys.executable, "/inputs/" + item["file"]])
        for item in manifest["implementations"]]
    for run, candidate in pairs:
        for mode in MODES:
            for seed in map(int, args.seeds.split(",")):
                result, raw = experiment(args.family, reference, candidate,
                                         Path("/state/experiment"), mode, seed)
                key = f"{args.family}/{run}/{mode}/{seed}"
                payload = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
                result.update(case_id=key, run=run, raw_sha256=hashlib.sha256(payload).hexdigest())
                emit("TWINPROOF_RECEIPT", result)
                encoded = base64.b64encode(gzip.compress(payload, mtime=0)).decode()
                chunks = [encoded[i:i + 12000] for i in range(0, len(encoded), 12000)]
                for number, chunk in enumerate(chunks):
                    emit("TWINPROOF_RAW", {"case_id": key, "part": number,
                                           "parts": len(chunks), "gzip_base64": chunk})


if __name__ == "__main__":
    main()

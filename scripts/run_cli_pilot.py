"""Fetch checksum-pinned artifacts, then run only in a constrained Linux container.

No build script, trajectory, cached test, or benchmark test is extracted or read.
Receipts travel through stdout; GitHub artifact storage is not required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from twinproof.artifacts import checked_bytes, source_member


ROOT = Path(__file__).resolve().parents[1]


def fetch(url, size, digest, destination):
    if not destination.exists():
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                        "--max-time", "120", "--max-filesize", str(size),
                        "--output", str(destination), url], check=True)
    return checked_bytes(destination.read_bytes(), digest, size)


def prepare(family, manifest, directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = next(item for item in manifest["families"] if f"__{family}." in item["id"])
    ref = source["reference_binary"]
    fetch(ref["url"], ref["bytes"], ref["sha256"], directory / "reference")
    (directory / "reference").chmod(0o555)
    verified = {"family": family, "task_id": source["id"], "reference_sha256": ref["sha256"],
                "source_manifest_sha256": hashlib.sha256(
                    (ROOT / "sources/programbench-pilot.json").read_bytes()).hexdigest(),
                "source_scope": manifest["source_scope"], "image": manifest["image"],
                "implementations": []}
    for index, run in enumerate(manifest["runs"]):
        item = next(i for i in run["implementations"] if i["task_id"] == source["id"])
        archive = fetch(item["archive_url"], item["archive_bytes"], item["archive_sha256"],
                        directory / f"download-{index}.tar.gz")
        if len(item["source_entries"]) != 1:
            raise ValueError("pilot accepts exactly one verified Python source per program")
        entry = item["source_entries"][0]
        output = f"candidate-{index}.py"
        (directory / output).write_bytes(source_member(archive, entry))
        # The archive never enters the execution container, only selected source bytes.
        verified["implementations"].append({"run": run["id"], "file": output,
                                            "source_sha256": entry["sha256"],
                                            "archive_sha256": item["archive_sha256"]})
    (directory / "verified.json").write_text(json.dumps(verified, indent=2) + "\n")
    return verified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=("zoxide", "dstask"))
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--fetch-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "sources/programbench-pilot.json").read_text())
    cache = ROOT / ".cache/programbench" / args.family
    verified = prepare(args.family, manifest, cache)
    print("TWINPROOF_VERIFIED " + json.dumps(verified, sort_keys=True), flush=True)
    if args.fetch_only:
        return
    with tempfile.TemporaryDirectory(prefix="twinproof-build-") as build:
        build = Path(build)
        (build / "requirements.txt").write_bytes((ROOT / "sources/cli-requirements.txt").read_bytes())
        (build / "Dockerfile").write_text(
            f"FROM {manifest['image']}\n"
            "RUN apt-get update && apt-get install -y --no-install-recommends git "
            "&& rm -rf /var/lib/apt/lists/*\n"
            "COPY requirements.txt /requirements.txt\n"
            "RUN python -m pip install --no-cache-dir --require-hashes -r /requirements.txt\n")
        subprocess.run(["docker", "build", "--platform", "linux/amd64", "--tag", "twinproof-cli-pilot", str(build)], check=True)
    # Mount a separate allowlist directory, excluding downloads and repository state.
    with tempfile.TemporaryDirectory(prefix="twinproof-inputs-") as inputs:
        inputs = Path(inputs)
        inputs.chmod(0o755)
        for filename in ["reference", "verified.json"] + [i["file"] for i in verified["implementations"]]:
            dest = inputs / filename
            dest.write_bytes((cache / filename).read_bytes())
            dest.chmod(0o555 if filename == "reference" else 0o444)
        command = ["docker", "run", "--rm", "--platform", "linux/amd64",
                   "--network", "none", "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--pids-limit", "64",
                   "--memory", "256m", "--cpus", "1", "--user", "65534:65534",
                   "--tmpfs", "/state:rw,noexec,nosuid,size=64m,mode=1777",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                   "--mount", f"type=bind,src={inputs},dst=/inputs,readonly",
                   "--mount", f"type=bind,src={ROOT / 'src'},dst=/app/src,readonly",
                   "--mount", f"type=bind,src={ROOT / 'scripts/cli_capsule.py'},dst=/app/capsule.py,readonly",
                   "--env", "PYTHONPATH=/app/src", "--env", "PYTHONDONTWRITEBYTECODE=1",
                   "twinproof-cli-pilot", "python", "/app/capsule.py",
                   "--family", args.family, "--seeds", args.seeds]
        subprocess.run(command, check=True, timeout=1100)


if __name__ == "__main__":
    main()

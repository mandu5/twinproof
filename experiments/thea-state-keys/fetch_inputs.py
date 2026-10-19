"""Download pinned public inputs; never execute or redistribute archive contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import ssl
import tarfile
import tempfile
import urllib.request
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check(path: Path, entry: dict) -> None:
    if not path.is_file() or path.stat().st_size != entry["bytes"]:
        raise ValueError(f"Missing file or size mismatch: {path}")
    if digest(path) != entry["sha256"]:
        raise ValueError(f"SHA256 mismatch: {path}")


def safe_path(root: Path, relative: str) -> Path:
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside selected cache: {relative}")
    return result


def verified_inputs(root: Path, pins: dict | None = None) -> list[dict]:
    pins = pins or json.loads((PACKAGE / "pins.json").read_text())
    entries = pins["archive_members"] + pins["support"]
    for entry in entries:
        check(safe_path(root, entry["path"]), entry)
    return entries


def download(entry: dict, destination: Path, context: ssl.SSLContext) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        check(destination, entry)
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "THEA-state-key-reproduction/1"})
        with urllib.request.urlopen(request, context=context, timeout=60) as response, temporary.open("wb") as output:
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > entry["bytes"]:
                    raise ValueError("Download exceeded pinned size")
                output.write(block)
        check(temporary, entry)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True, help="Input destination; all paths are relative to this directory")
    parser.add_argument("--archive", type=Path, help="Optional local copy of the exact pinned archive; still hash checked")
    args = parser.parse_args()
    import certifi
    import zstandard

    root = args.cache.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    pins = json.loads((PACKAGE / "pins.json").read_text())
    context = ssl.create_default_context(cafile=certifi.where())
    archive = args.archive.expanduser().resolve() if args.archive else root / "downloads" / "bp35.archive.tar.zst"
    if args.archive:
        check(archive, pins["archive"])
    else:
        download(pins["archive"], archive, context)
    allowlist = {entry["archive_member"]: entry for entry in pins["archive_members"]}
    found = set()
    with tempfile.TemporaryDirectory(prefix="extract-", dir=root) as staging_name:
        staging = Path(staging_name)
        with archive.open("rb") as compressed:
            with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
                with tarfile.open(fileobj=stream, mode="r|") as tar:
                    for member in tar:
                        if member.name not in allowlist:
                            continue
                        if member.name in found or not member.isfile():
                            raise ValueError(f"Duplicate or non-regular allowed member: {member.name}")
                        entry = allowlist[member.name]
                        if member.size != entry["bytes"]:
                            raise ValueError(f"Archive member size mismatch: {member.name}")
                        target = safe_path(staging, entry["path"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with tar.extractfile(member) as source, target.open("wb") as output:
                            shutil.copyfileobj(source, output)
                        check(target, entry)
                        found.add(member.name)
        if found != set(allowlist):
            raise ValueError(f"Missing allowed members: {sorted(set(allowlist) - found)}")
        for entry in pins["archive_members"]:
            destination = safe_path(root, entry["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                check(destination, entry)
            else:
                safe_path(staging, entry["path"]).replace(destination)
    for entry in pins["support"]:
        download(entry, safe_path(root, entry["path"]), context)
    entries = verified_inputs(root, pins)
    receipt = {
        "schema_version": 1,
        "commit": pins["commit"],
        "archive_sha256": pins["archive"]["sha256"],
        "archive_bytes": pins["archive"]["bytes"],
        "extracted_archive_files": len(pins["archive_members"]),
        "verified_input_files": len(entries),
        "verified_input_bytes": sum(entry["bytes"] for entry in entries),
        "pins_sha256": digest(PACKAGE / "pins.json"),
    }
    (root / "input-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

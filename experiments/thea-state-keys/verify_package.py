"""Verify packaged file hashes and published receipt projection hashes offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((PACKAGE / "manifest.json").read_text())
    for entry in manifest["files"]:
        path = PACKAGE / entry["path"]
        if path.stat().st_size != entry["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Package integrity mismatch: {entry['path']}")
    provenance = json.loads((PACKAGE / "receipts/provenance.json").read_text())
    for entry in provenance["published_receipts"]:
        path = PACKAGE / entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["published_sha256"]:
            raise ValueError(f"Published receipt changed: {entry['path']}")
    print(json.dumps({"verified_package_files": len(manifest["files"]), "published_receipts": len(provenance["published_receipts"])}))


if __name__ == "__main__":
    main()

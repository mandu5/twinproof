"""Download the exact reviewed ClawForge runtime-pilot snapshot (about 41 MB)."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path(".cache/clawforge"))
    args = parser.parse_args()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "sources/clawforge.json").read_text())
    for item in manifest["files"]:
        path = args.destination / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            url = f"https://raw.githubusercontent.com/zeng-yirong/EnvCraft/{manifest['commit']}/{item['path']}"
            temp = path.with_suffix(path.suffix + ".part")
            subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                            "--max-time", "120", url, "-o", str(temp)], check=True)
            data = temp.read_bytes()
            if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"Downloaded hash mismatch: {item['path']}")
            temp.replace(path)
        data = path.read_bytes()
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Cached hash mismatch: {item['path']}")
    print(json.dumps({"verified_files": len(manifest["files"]), "commit": manifest["commit"]}))


if __name__ == "__main__":
    main()

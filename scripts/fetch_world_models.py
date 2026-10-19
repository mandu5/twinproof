#!/usr/bin/env python3
"""Pin public showcase artifacts without redistributing their model sources."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from twinproof.world_model import decode_showcase, inspect_source

BASE = 'https://arc-agi-3-twin.vercel.app/'


def fetch(url, path):
    data = path.read_bytes() if path.exists() else subprocess.run(
        ['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '45', url],
        capture_output=True, check=True).stdout
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache/branch-models')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'sources/world-model-corpus.json')
    args = parser.parse_args()
    catalog_raw = fetch(BASE + 'showcase.json', args.cache / 'showcase.json')
    catalog = json.loads(catalog_raw)
    rows = []
    for game in catalog['games']:
        name = game['env']
        if not re.fullmatch(r'[a-z0-9]{4}', name):
            raise ValueError('invalid game identifier')
        url = BASE + f'games/{name}.json'
        raw = fetch(url, args.cache / f'{name}.json')
        payload = json.loads(raw)
        source = payload['model']['src'].encode()
        if payload['env'] != name or len(source) != payload['model']['bytes']:
            raise ValueError(f'{name}: model identity/byte count mismatch')
        transitions = decode_showcase(payload)
        rows.append({'game': name, 'url': url, 'artifact_bytes': len(raw),
                     'artifact_sha256': hashlib.sha256(raw).hexdigest(),
                     'source_bytes': len(source), 'source_sha256': hashlib.sha256(source).hexdigest(),
                     'trace_transitions': len(transitions), 'census': inspect_source(source.decode()),
                     'split': 'development' if name in {'dc22', 'sp80', 'ft09', 'cd82'} else 'outcome_unseen'})
        print(name, len(transitions), 'static', rows[-1]['census']['unsupported'])
    manifest = {'schema': 1, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'catalog_url': BASE + 'showcase.json',
                'catalog_sha256': hashlib.sha256(catalog_raw).hexdigest(),
                'license_scope': 'No third-party model source redistributed; website artifact license unconfirmed.',
                'scope': 'Static corpus census, not runtime or original agent reproduction.', 'models': rows}
    if args.manifest.exists():
        old = json.loads(args.manifest.read_text())
        if old['models'] != rows or old['catalog_sha256'] != manifest['catalog_sha256']:
            raise ValueError('pinned manifest differs; use a new explicit manifest path for a new version')
    else:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

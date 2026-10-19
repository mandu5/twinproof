#!/usr/bin/env python3
"""Run one pinned family per bounded clean-environment child process."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from twinproof.world_audit import audit_model, summarize, trace_conflicts
from twinproof.world_model import decode_showcase


def failure_record(game, pin, artifact, status, reason, seconds):
    """Preserve failed families; only derive trace statistics from verified bytes."""
    expected = pin['artifact_sha256']
    result = {'game': game, 'status': status, 'reason': reason, 'seconds': seconds,
              'model_calls': None, 'split': pin['split'], 'artifact_sha256': None,
              'expected_artifact_sha256': expected, 'actual_artifact_sha256': None,
              'trace_status': 'UNAVAILABLE'}
    try:
        raw = artifact.read_bytes()
    except OSError as exc:
        result['trace_error'] = f'{type(exc).__name__}: {exc}'
        return result
    actual = hashlib.sha256(raw).hexdigest()
    result['actual_artifact_sha256'] = actual
    if actual != expected:
        result['trace_status'] = 'PIN_MISMATCH'
        return result
    result['artifact_sha256'] = actual
    try:
        result['trace'] = trace_conflicts(decode_showcase(json.loads(raw)))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result['trace_status'] = 'INVALID'
        result['trace_error'] = f'{type(exc).__name__}: {exc}'
    else:
        result['trace_status'] = 'PINNED_VALID'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', nargs='*')
    parser.add_argument('--worker')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=int, default=2000)
    parser.add_argument('--seconds', type=int, default=90)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'sources/world-model-corpus.json').read_text())
    pins = {row['game']: row for row in manifest['models']}
    if args.worker:
        resource.setrlimit(resource.RLIMIT_CPU, (args.seconds, args.seconds))
        raw = (ROOT / '.cache/branch-models' / f'{args.worker}.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != pins[args.worker]['artifact_sha256']:
            raise ValueError('source artifact pin mismatch')
        result = audit_model(json.loads(raw), args.budget)
        result.update(artifact_sha256=pins[args.worker]['artifact_sha256'],
                      source_sha256=pins[args.worker]['source_sha256'], split=pins[args.worker]['split'],
                      peak_rss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      rss_unit='bytes' if platform.system() == 'Darwin' else 'KiB')
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        return
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    games = args.games or sorted(pins)
    if any(game not in pins for game in games) or len(games) != len(set(games)):
        raise ValueError('unknown or duplicate game')
    config = {'schema': 1, 'started_at': datetime.now(timezone.utc).isoformat(), 'games': games,
              'budget': args.budget, 'wall_seconds_per_family': args.seconds,
              'parallel_workers': 2, 'python': sys.version, 'platform': platform.platform(),
              'git_head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
              'source_file_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                    for name in ['src/twinproof/world_model.py', 'src/twinproof/world_audit.py',
                                                 'scripts/run_world_audit.py', 'sources/world-model-corpus.json']}}
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')

    def run(game):
        started = time.perf_counter()
        target = output / f'{game}.json'
        with tempfile.TemporaryDirectory(prefix='twinproof-model-') as temp:
            env = {'PATH': os.defpath, 'HOME': temp, 'TMPDIR': temp, 'LANG': 'C.UTF-8',
                   'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1'}
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', game,
                       '--output', str(target), '--budget', str(args.budget), '--seconds', str(args.seconds)]
            if platform.system() == 'Darwin' and Path('/usr/bin/sandbox-exec').exists():
                profile = ('(version 1)(deny default)(allow process*)(allow file-read*)'
                           '(allow sysctl-read)(allow mach-lookup)(deny network*)'
                           f'(allow file-write* (subpath "{temp}") (subpath "{output}"))')
                command = ['/usr/bin/sandbox-exec', '-p', profile] + command
            process = subprocess.Popen(command, cwd=temp, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=args.seconds)
                status = 'ERROR' if process.returncode else None
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                status = 'TIMEOUT'
            (output / f'{game}.log').write_bytes(stdout + stderr)
            if not status:
                try:
                    result = json.loads(target.read_text())
                    if not isinstance(result, dict) or not {'status', 'seconds'} <= result.keys():
                        raise ValueError('worker returned an invalid receipt')
                except (OSError, ValueError) as exc:
                    status = 'ERROR'
                    stderr += f'\n{type(exc).__name__}: {exc}'.encode()
            if status:
                result = failure_record(game, pins[game], ROOT / '.cache/branch-models' / f'{game}.json',
                                        status, stderr.decode(errors='replace')[-1800:],
                                        time.perf_counter() - started)
                target.write_text(json.dumps(result, indent=2) + '\n')
            print(game, result['status'], round(result['seconds'], 3), flush=True)
            return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(run, games))
    result = summarize(records)
    result['receipt_hashes'] = {f'{game}.json': hashlib.sha256((output / f'{game}.json').read_bytes()).hexdigest() for game in games}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

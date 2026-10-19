"""Failure rows must retain the denominator without attributing unpinned bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    'world_runner', Path(__file__).resolve().parents[1] / 'scripts/run_world_audit.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize('body', [None, b'{broken', b'{"acts":"not a trace"}'])
def test_failed_worker_retains_row_for_unreadable_trace(tmp_path, body):
    artifact = tmp_path / 'bad.json'
    if body is not None:
        artifact.write_bytes(body)
    expected = hashlib.sha256(body or b'missing').hexdigest()
    pin = {'artifact_sha256': expected, 'source_sha256': 'source', 'split': 'holdout'}
    row = runner.failure_record('bad', pin, artifact, 'ERROR', 'worker failed', 1.0)
    assert row['game'] == 'bad' and row['status'] == 'ERROR'
    assert row['model_calls'] is None and 'trace' not in row
    assert row['expected_artifact_sha256'] == expected
    assert row['trace_status'] in {'UNAVAILABLE', 'INVALID'}
    assert row['actual_artifact_sha256'] == (expected if body is not None else None)
    summary = runner.summarize([row])
    assert summary['families'] == 1 and summary['runtime_completed'] == 0


def test_pin_mismatch_never_attributes_other_bytes_trace(tmp_path):
    artifact = tmp_path / 'changed.json'
    body = json.dumps({'env': 'changed', 'w': 1, 'h': 1, 'n': 1, 'f0': '0',
                       'acts': ['A'], 'deltas': ['0001']}).encode()
    artifact.write_bytes(body)
    pin = {'artifact_sha256': 'different', 'source_sha256': 'source', 'split': 'holdout'}
    row = runner.failure_record('changed', pin, artifact, 'ERROR', 'pin mismatch', 1.0)
    assert row['actual_artifact_sha256'] == hashlib.sha256(body).hexdigest()
    assert row['expected_artifact_sha256'] == 'different'
    assert row['artifact_sha256'] is None and 'trace' not in row
    assert row['trace_status'] == 'PIN_MISMATCH'


def test_failed_worker_can_count_valid_pinned_trace(tmp_path):
    artifact = tmp_path / 'valid.json'
    body = json.dumps({'env': 'valid', 'w': 1, 'h': 1, 'n': 1, 'f0': '0',
                       'acts': ['A'], 'deltas': ['0001']}).encode()
    artifact.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    pin = {'artifact_sha256': digest, 'source_sha256': 'source', 'split': 'holdout'}
    row = runner.failure_record('valid', pin, artifact, 'TIMEOUT', 'timeout', 2.0)
    assert row['trace']['transitions'] == 1
    assert row['trace_status'] == 'PINNED_VALID'
    assert row['actual_artifact_sha256'] == row['expected_artifact_sha256'] == digest
    assert row['model_calls'] is None

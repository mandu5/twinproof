import base64
import gzip
import hashlib
import json

import pytest

from twinproof.cli_receipts import decode_logs


def transcript():
    payload = b'{"reference":[{"stdout":"alpha"}],"candidate":[]}'
    receipt = {"case_id": "a", "raw_sha256": hashlib.sha256(payload).hexdigest()}
    raw = {"case_id": "a", "part": 0, "parts": 1,
           "gzip_base64": base64.b64encode(gzip.compress(payload)).decode()}
    return ("job\tdate TWINPROOF_RECEIPT " + json.dumps(receipt) + "\n"
            "job\tdate TWINPROOF_RAW " + json.dumps(raw)), receipt, raw


def test_logs_recover_exact_hash_verified_transcript():
    logs, _, _ = transcript()
    receipts, raw, environments = decode_logs(logs, expected_cases=1)
    assert receipts[0]["case_id"] == "a"
    assert raw == {"a": {"reference": [{"stdout": "alpha"}], "candidate": []}}
    assert environments == []


def test_missing_raw_data_cannot_be_a_complete_receipt():
    logs, _, _ = transcript()
    with pytest.raises(ValueError, match="missing"):
        decode_logs(logs.splitlines()[0], expected_cases=1)


def test_wrong_hash_is_rejected_even_when_gzip_and_json_are_valid():
    logs, receipt, _ = transcript()
    receipt["raw_sha256"] = "0" * 64
    logs = "TWINPROOF_RECEIPT " + json.dumps(receipt) + "\n" + logs.splitlines()[1]
    with pytest.raises(ValueError, match="hash"):
        decode_logs(logs, expected_cases=1)


def test_duplicate_case_or_incomplete_matrix_is_rejected():
    logs, _, _ = transcript()
    with pytest.raises(ValueError, match="duplicate"):
        decode_logs(logs + "\n" + logs.splitlines()[0], expected_cases=1)
    with pytest.raises(ValueError, match="count"):
        decode_logs(logs, expected_cases=2)

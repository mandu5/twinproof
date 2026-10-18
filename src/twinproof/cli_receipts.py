"""Recover and verify complete CLI pilot transcripts from CI logs."""
import base64
import gzip
import hashlib
import json
import re


def decode_logs(logs, expected_cases):
    receipts, chunks, environments = {}, {}, []
    pattern = re.compile(r"TWINPROOF_(RECEIPT|RAW|ENVIRONMENT) (\{.*\})$")
    for line in logs.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        label, data = match.groups()
        value = json.loads(data)
        if label == "ENVIRONMENT":
            environments.append(value)
        elif label == "RECEIPT":
            if value["case_id"] in receipts:
                raise ValueError("duplicate case receipt")
            receipts[value["case_id"]] = value
        else:
            parts = chunks.setdefault(value["case_id"], {})
            if value["part"] in parts:
                raise ValueError("duplicate raw part")
            parts[value["part"]] = value
    if len(receipts) != expected_cases:
        raise ValueError(f"case count mismatch: {len(receipts)} != {expected_cases}")
    if set(receipts) != set(chunks):
        raise ValueError("missing or unexpected raw transcripts")
    decoded = {}
    for key, receipt in receipts.items():
        parts = chunks[key]
        count = next(iter(parts.values()))["parts"]
        if set(parts) != set(range(count)) or any(p["parts"] != count for p in parts.values()):
            raise ValueError("missing raw part or inconsistent count")
        payload = gzip.decompress(base64.b64decode("".join(parts[i]["gzip_base64"] for i in range(count)), validate=True))
        if hashlib.sha256(payload).hexdigest() != receipt["raw_sha256"]:
            raise ValueError("raw transcript hash mismatch")
        decoded[key] = json.loads(payload)
    return list(receipts.values()), decoded, environments

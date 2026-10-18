"""Pinned upstream evaluation with deterministic text at the external API boundary.

Only the reviewed function definitions are compiled. Module-level imports, CLI,
threads and API construction never run. This is not a sandbox for arbitrary code.
"""

import ast
import copy
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
import time
from types import SimpleNamespace


def manifest() -> dict:
    return json.loads(files("twinproof").joinpath("sources.json").read_text())


def verified_bytes(path: Path, expected_sha256: str) -> bytes:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {path.name}: {actual}")
    return raw


class OfflineGrader:
    def __init__(self, functions: dict):
        self.functions = functions

    def evaluate(self, step: dict, prediction: dict) -> dict:
        text = json.dumps(prediction, ensure_ascii=False, allow_nan=False)

        def create(**kwargs):
            if kwargs.get("model") != "offline-audit-fixture":
                raise ValueError("Unexpected model request")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return self.functions["evaluate_sample"](
            step, "offline-audit-fixture", 0, client, max_retries=0, thinking=False)


def load_grader(path: Path, expected_sha256: str) -> OfflineGrader:
    source = verified_bytes(path, expected_sha256)
    allowed_hashes = {
        info["sha256"] for name, info in manifest()["files"].items()
        if name.startswith("Evaluation/")
    }
    if expected_sha256 not in allowed_hashes:
        raise ValueError("Source is not a reviewed, pinned upstream grader")
    names = {"diff_dicts", "extract_steps", "action_to_call", "extract_json",
             "extract_first_json_block", "parse_to_obj", "apply_change", "evaluate_sample"}
    tree = ast.parse(source, filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    found = {node.name for node in selected}
    required = names - {"extract_first_json_block"}
    if not required <= found:
        raise ValueError(f"Missing original grader functions: {required - found}")
    # Match the original SFT script's supported fallback when its optional
    # json_repair dependency is absent. All outer prediction payloads are valid
    # JSON, and this audit measures state correctness, not feedback parsing.
    namespace = {"json": json, "copy": copy, "re": re, "time": time,
                 "REPAIR_AVAILABLE": False, "repair_json": None}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return OfflineGrader(namespace)

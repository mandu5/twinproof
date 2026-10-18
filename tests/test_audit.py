import copy
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from twinproof.audit import build_cases, replacement_changes
from twinproof.cli import read_json
from twinproof.state import compare_states
from twinproof.upstream import load_grader, manifest


@pytest.fixture(params=["Evaluation/10.eval_model.py", "Evaluation/10.SFT-evaluation.py"])
def grader(request):
    root = Path(os.environ.get("TWINPROOF_SNAPSHOT", ".cache/envsimbench"))
    path = root / request.param
    if not path.exists():
        pytest.skip("Run scripts/fetch_sources.py or set TWINPROOF_SNAPSHOT")
    return load_grader(path, manifest()["files"][request.param]["sha256"])


def step(before, after):
    return {"config_before": before, "config_after": after,
            "action": {"name": "fixture", "arguments": {}},
            "observation": {"content": "ok"}, "env_code": ""}


def payload(before, target):
    return {"feedback": "ok", "config_changes": replacement_changes(before, target)}


def test_original_grader_rejects_correct_deletion(grader):
    case = step({"drop": 1, "keep": 2}, {"keep": 2})
    out = grader.evaluate(case, payload(case["config_before"], {"keep": 2}))
    assert out["predicted_after"] == {"keep": 2}
    assert out["config_change_correct"] is False
    assert compare_states(case["config_after"], out["predicted_after"]).status == "PASS"


def test_original_grader_accepts_corrupted_unchanged_state(grader):
    case = step({"x": 1}, {"x": 1})
    out = grader.evaluate(case, payload({"x": 1}, {"x": 1, "bad": 2}))
    assert out["config_change_correct"] is True
    assert compare_states({"x": 1}, out["predicted_after"]).status == "FAIL"


def test_original_grader_conflates_null_with_removed_key(grader):
    case = step({"drop": 1, "keep": 2}, {"keep": 2})
    out = grader.evaluate(case, payload(case["config_before"], {"drop": None, "keep": 2}))
    assert out["config_change_correct"] is True
    assert compare_states(case["config_after"], out["predicted_after"]).status == "FAIL"


def test_original_grader_splits_literal_dotted_keys(grader):
    case = step({"nested": {"a.b": 1}}, {"nested": {"a.b": 2}})
    out = grader.evaluate(case, payload(case["config_before"], case["config_after"]))
    assert out["predicted_after"] == {"nested": {"a.b": 2}}
    assert out["config_change_correct"] is False


def test_original_grader_ignores_bool_number_corruption(grader):
    case = step({"enabled": False}, {"enabled": True})
    out = grader.evaluate(case, payload(case["config_before"], {"enabled": 1}))
    assert out["config_change_correct"] is True
    assert compare_states({"enabled": True}, out["predicted_after"]).status == "FAIL"


def test_hash_mismatch_is_rejected_before_executing_source(tmp_path):
    source = tmp_path / "untrusted.py"
    marker = tmp_path / "executed"
    source.write_text(f"open({str(marker)!r}, 'w').write('bad')")
    with pytest.raises(ValueError, match="SHA-256"):
        load_grader(source, "0" * 64)
    assert not marker.exists()


def test_mutation_labels_and_eligibility_are_independent_literals():
    before = {"gone": 1, "keep": 2, "enabled": True}
    after = {"keep": 2, "enabled": True}
    cases = {c.family: c for c in build_cases(before, after)}
    assert cases["gold_identity"].target == after
    assert cases["gold_identity"].should_pass is True
    assert cases["null_for_deleted"].target == {"gone": None, "keep": 2, "enabled": True}
    assert cases["null_for_deleted"].should_pass is False
    assert cases["boolean_as_number"].target["enabled"] == 1
    assert type(cases["boolean_as_number"].target["enabled"]) is int
    assert cases["extra_field"].should_pass is False


def test_case_generation_keeps_input_and_skips_ineligible_mutations():
    before, after = {"x": 1}, {"x": 2}
    saved = copy.deepcopy((before, after))
    cases = build_cases(before, after)
    assert {c.family for c in cases} == {"gold_identity", "extra_field"}
    assert (before, after) == saved


@pytest.mark.parametrize("text", ['{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}'])
def test_ambiguous_json_is_rejected(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_json(path)


def test_cli_returns_fail_with_precise_path(tmp_path):
    expected, observed = tmp_path / "a.json", tmp_path / "b.json"
    expected.write_text('{"x": null}')
    observed.write_text('{}')
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    process = subprocess.run([sys.executable, "-m", "twinproof", "compare", str(expected), str(observed)],
                             capture_output=True, text=True, env=env)
    assert process.returncode == 1
    result = json.loads(process.stdout)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"] == "/x"


def test_cli_malformed_json_returns_unknown_without_traceback(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{')
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    process = subprocess.run([sys.executable, "-m", "twinproof", "compare", str(path), str(path)],
                             capture_output=True, text=True, env=env)
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "UNKNOWN"
    assert "Traceback" not in process.stderr


@pytest.mark.parametrize(
    "left,right,status",
    [
        ('1e-400', '0', 'FAIL'),
        ('9007199254740992.0', '9007199254740993.0', 'FAIL'),
        ('0.10000000000000001', '0.1', 'FAIL'),
        ('1', '1.0', 'PASS'),
    ],
)
def test_cli_preserves_distinct_json_numeric_values(tmp_path, left, right, status):
    expected, observed = tmp_path / "a.json", tmp_path / "b.json"
    expected.write_text('{"x":' + left + '}')
    observed.write_text('{"x":' + right + '}')
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    process = subprocess.run([sys.executable, "-m", "twinproof", "compare", str(expected), str(observed)],
                             capture_output=True, text=True, env=env)
    assert process.returncode == (0 if status == "PASS" else 1)
    result = json.loads(process.stdout, parse_float=Decimal)
    assert result["status"] == status
    if status == "FAIL":
        difference = result["differences"][0]
        assert difference["expected"] == Decimal(left)
        assert difference["observed"] == Decimal(right)

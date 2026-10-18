import json
from pathlib import Path
import sys
import time

import pytest

from twinproof.cli_pilot import (Budget, BudgetExhausted, CliRunner, confirm,
                                 experiment, observe_query, observe_tasks, run_command, search)


def test_timeout_is_unknown_and_counted(tmp_path):
    budget = Budget(2)
    out = run_command([sys.executable, "-c", "import time;time.sleep(3)"],
                      tmp_path, {}, budget, timeout=0.03)
    assert out["status"] == "TIMEOUT"
    assert budget.calls == 1


def test_budget_never_starts_an_extra_command(tmp_path):
    budget = Budget(1)
    run_command([sys.executable, "-c", "pass"], tmp_path, {}, budget)
    with pytest.raises(BudgetExhausted):
        run_command([sys.executable, "-c", "pass"], tmp_path, {}, budget)
    assert budget.calls == 1


def test_invalid_task_json_is_not_an_empty_state():
    with pytest.raises(ValueError):
        observe_tasks("not json")


def test_task_projection_retains_behavior_and_ignores_only_declared_fields():
    task = dict(id=1, uuid="a", summary="alpha", status="open", notes="", tags=["b", "a"],
                project="red", priority="P2", due="0001-01-01T00:00:00Z", created="NOW", resolved="NOW")
    projected = observe_tasks(json.dumps([task]))
    assert projected == [{"id": 1, "summary": "alpha", "status": "open", "notes": "",
                          "tags": ["a", "b"], "project": "red", "priority": "P2", "due": "0001-01-01T00:00:00Z"}]
    task["summary"] = "wrong task"
    assert observe_tasks(json.dumps([task])) != projected


@pytest.mark.parametrize("value", ["{}", '[{"id":true}]', '[{"id":1}]'])
def test_missing_or_wrong_type_task_fields_rejected(value):
    with pytest.raises(ValueError):
        observe_tasks(value)


def test_confirmation_needs_two_stable_paired_replays():
    assert confirm([[1], [1]], [[2], [2]]) == "CONFIRMED_DIFFERENCE"
    assert confirm([[1], [1]], [[1], [1]]) == "NO_DIFFERENCE_OBSERVED"
    assert confirm([[1], [2]], [[2], [2]]) == "UNKNOWN"
    assert confirm([[1]], [[2]]) == "UNKNOWN"
    assert confirm([[None], [None]], [[2], [2]]) == "UNKNOWN"


@pytest.fixture
def simple_zoxide(tmp_path):
    path = tmp_path / "fixture.py"
    path.write_text('''import json, os, pathlib, sys
p=pathlib.Path(os.environ['_ZO_DATA_DIR'])/'data.json'
state=json.loads(p.read_text()) if p.exists() else []
if sys.argv[1]=='add':
 state.append(sys.argv[2]);p.write_text(json.dumps(state))
elif sys.argv[1]=='query':
 print('\\n'.join(state),end='\\n' if state else '')
''')
    return [sys.executable, str(path)]


def test_state_persists_within_sequence_and_reset_removes_it(tmp_path, simple_zoxide):
    runner = CliRunner("zoxide", simple_zoxide, tmp_path / "state", Budget(20))
    runner.reset()
    value = runner.step("add_alpha")
    assert value["state"] == [str(runner.fixture / "alpha")]
    assert runner.budget.calls == 2
    runner.reset()
    assert runner.step("query_all")["state"] == []
    assert runner.resets == 2
    assert runner.budget.calls == 4


def test_search_reports_exhaustion_without_equivalence_claim(tmp_path, simple_zoxide):
    budget = Budget(16)
    ref = CliRunner("zoxide", simple_zoxide, tmp_path / "ref", budget)
    cand = CliRunner("zoxide", simple_zoxide, tmp_path / "cand", budget)
    # The same logical fixture path must be used on both sides.
    cand.fixture = ref.fixture
    result = search(ref, cand, ["query_all"], "breadth_first", seed=0, limit=8)
    assert result["status"] == "NO_DIFFERENCE_FOUND_WITHIN_BUDGET"
    assert result["search_calls"] <= 8


def test_output_limit_is_unknown(tmp_path):
    out = run_command([sys.executable, "-c", "print('x'*100000)"], tmp_path, {}, Budget(1))
    assert out["status"] == "OUTPUT_LIMIT"


def test_experiment_confirms_a_real_persistent_state_bug_and_accounts_calls(tmp_path, simple_zoxide):
    faulty = tmp_path / "faulty.py"
    faulty.write_text("import sys\nif sys.argv[1]=='query': print('lost-state')\n")
    result, raw = experiment("zoxide", simple_zoxide, [sys.executable, str(faulty)],
                             tmp_path / "capsule", "breadth_first", 0)
    assert result["verdict"] == "CONFIRMED_DIFFERENCE"
    assert result["witness"] == ["add_alpha"]
    assert len(result["confirmation"]["reference"]) == 2
    # Two processes per step, two programs, discovery plus two fresh repetitions.
    assert result["application_calls"] == 12
    assert result["total_process_calls"] == len(raw["reference"]) + len(raw["candidate"])
    assert result["reference_calls"] == result["candidate_calls"] == 6


def test_experiment_preserves_no_difference_as_bounded_unknown(tmp_path, simple_zoxide):
    result, _ = experiment("zoxide", simple_zoxide, simple_zoxide,
                           tmp_path / "capsule", "breadth_first", 1, total_budget=8,
                           search_budget=8, alphabet=["query_all"])
    assert result["verdict"] == "NO_DIFFERENCE_FOUND_WITHIN_BUDGET"
    assert result["application_calls"] == 8
    assert result["confirmation"] == {"reference": [], "candidate": []}


def test_unknown_search_mode_is_rejected_before_any_process(tmp_path, simple_zoxide):
    with pytest.raises(ValueError, match="mode"):
        experiment("zoxide", simple_zoxide, simple_zoxide, tmp_path / "capsule", "typo", 0)


def test_tag_output_is_a_set_of_lines_and_project_count_is_preserved():
    assert observe_query("query_tags", "work\nhome\n") == ["home", "work"]
    project = dict(name="red", taskCount=2, resolvedCount=1, active=True, priority="P1",
                   created="volatile", resolved="volatile")
    assert observe_query("query_projects", json.dumps([project])) == [
        dict(name="red", taskCount=2, resolvedCount=1, active=True, priority="P1")]
    project["taskCount"] = True
    with pytest.raises(ValueError):
        observe_query("query_projects", json.dumps([project]))


@pytest.mark.parametrize("mode", ["random_prefix", "aalpy_random_word", "candidate_state_cover"])
def test_other_search_methods_run_real_subprocesses_under_budget(tmp_path, simple_zoxide, mode):
    if mode == "aalpy_random_word":
        pytest.importorskip("aalpy")
    result, raw = experiment("zoxide", simple_zoxide, simple_zoxide,
                             tmp_path / "capsule", mode, 42, total_budget=16,
                             search_budget=16, alphabet=["query_all"])
    assert result["verdict"] == "NO_DIFFERENCE_FOUND_WITHIN_BUDGET"
    assert 0 < result["application_calls"] <= 16
    assert result["total_process_calls"] == len(raw["reference"]) + len(raw["candidate"])
    assert result["attempted_words"] > 0


def test_discovery_instability_cannot_be_confirmed_by_two_later_equal_runs(tmp_path, simple_zoxide):
    program = tmp_path / "changing.py"
    counter = tmp_path / "volatile-counter"
    program.write_text(f'''import pathlib,sys
p=pathlib.Path({str(counter)!r})
if sys.argv[1]=='query':
 n=int(p.read_text()) if p.exists() else 0
 p.write_text(str(n+1));print('first' if n==0 else 'later')
''')
    result, _ = experiment("zoxide", simple_zoxide, [sys.executable, str(program)],
                           tmp_path / "capsule", "breadth_first", 0)
    assert result["verdict"] == "UNKNOWN"


def test_unknown_discovery_cannot_be_erased_by_successful_confirmation():
    assert confirm([[1], [1]], [[1], [1]],
                   discovery={"reference": [None], "candidate": [2]}) == "UNKNOWN"


def test_task_observer_membership_is_part_of_state(tmp_path):
    task = dict(id=1, summary="alpha", status="pending", notes="", project="", priority="P2",
                due="0001-01-01T00:00:00Z", tags=[])
    values = []
    for index, observed_in in enumerate(("show-open", "show-templates")):
        program = tmp_path / f"observer-{index}.py"
        program.write_text(f"import sys\nprint({json.dumps([task])!r} if sys.argv[1]=={observed_in!r} else '[]')\n")
        runner = CliRunner("dstask", [sys.executable, str(program)], tmp_path / f"root-{index}", Budget(8))
        runner.reset()
        values.append(runner.step("add_alpha"))
    assert all(value is not None for value in values)
    assert values[0]["state"] != values[1]["state"]


def test_deep_json_is_unknown_and_does_not_break_subsequent_valid_steps(tmp_path):
    program = tmp_path / "nested.py"
    flag = tmp_path / "first-read"
    program.write_text(f'''import pathlib,sys
p=pathlib.Path({str(flag)!r})
if sys.argv[1]=='show-open' and not p.exists():
 p.touch();print('['*1100+'0'+']'*1100)
else: print('[]')
''')
    runner = CliRunner("dstask", [sys.executable, str(program)], tmp_path / "root", Budget(12))
    runner.reset()
    assert runner.step("add_alpha") is None
    assert runner.step("add_alpha") is not None


def test_successful_parent_cannot_leave_a_background_child(tmp_path):
    marker = tmp_path / "child-survived"
    child = f"import time,pathlib;time.sleep(.25);pathlib.Path({str(marker)!r}).touch()"
    parent = f"import subprocess,sys;subprocess.Popen([sys.executable,'-c',{child!r}])"
    result = run_command([sys.executable, "-c", parent], tmp_path, {}, Budget(1), timeout=0.1)
    time.sleep(0.35)
    assert not marker.exists()
    assert result["status"] == "DESCENDANT_PROCESS"


def test_invalid_utf8_is_unknown_and_original_bytes_are_retained(tmp_path):
    results = [run_command([sys.executable, "-c", f"import os;os.write(1,bytes([{byte}]))"],
                           tmp_path, {}, Budget(1)) for byte in (254, 255)]
    assert all(r["status"] == "INVALID_UTF8" for r in results)
    assert results[0]["stdout_bytes_base64"] != results[1]["stdout_bytes_base64"]

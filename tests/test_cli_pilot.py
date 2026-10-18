import json
from pathlib import Path
import sys

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

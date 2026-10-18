import importlib.util
from pathlib import Path

import pytest


def load_runner():
    path = Path(__file__).parents[1] / "scripts/run_runtime_pilot.py"
    spec = importlib.util.spec_from_file_location("runtime_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CODE = '''
from datetime import datetime
import uuid
from copy import deepcopy
class Example:
    def _load_scenario(self, state): self.state = deepcopy(state)
    def get_env_state(self): return deepcopy(self.state)
    def create(self, name: str):
        key = str(uuid.uuid4())
        self.state[key] = {"name": name, "created": datetime.now().isoformat()}
        return {"id": key}
    def fail(self): raise ValueError("intentional")
    def reject(self): return {"error": "expected rejection"}
'''


def test_same_seed_and_clock_replay_exactly_different_runtime_does_not():
    runner = load_runner()
    a = runner.execute(CODE, "Example", {}, "create", {"name": "one"}, 0, 0)
    b = runner.execute(CODE, "Example", {}, "create", {"name": "one"}, 1, 7)
    c = runner.execute(CODE, "Example", {}, "create", {"name": "one"}, 0, 0)
    assert a == c
    assert a != b
    assert a["category"] == "changed"


def test_rejections_and_exceptions_remain_in_receipts():
    runner = load_runner()
    report = runner.run_environment(CODE, "Example", {})
    assert len(report["cases"]) == 3
    assert {r["category"] for r in report["cases"]} == {"changed", "exception", "returned_error"}
    assert sum(r["coupled_status"] == "PASS" for r in report["cases"]) == 3


@pytest.mark.parametrize("code", ["import subprocess", "open('x', 'w')", "eval('1+1')", "import os", "x.__class__"])
def test_static_gate_rejects_side_effect_surface(code):
    assert load_runner().static_gate(code)


def test_arguments_use_values_from_released_initial_state():
    runner = load_runner()
    code = ('class Example:\n def query(self, user_id: str, limit: int = 20): pass\n'
            ' def _load_scenario(self, state): pass\n def get_env_state(self): return {}\n')
    method = runner.load_environment(code, "Example", 0, 0).query
    assert runner.arguments(method, {"users": {"a": {"user_id": "user-a"}}}) == {"user_id": "user-a"}


def test_unique_environment_class_is_resolved_by_interface_not_filename():
    runner = load_runner()
    code = CODE.replace("class Example:", "class ReleasedAPI:")
    instance = runner.load_environment(code, "DifferentFilename", 0, 0)
    assert hasattr(instance, "_load_scenario")


def test_filename_wrapper_without_state_interface_does_not_override_real_api():
    runner = load_runner()
    code = CODE.replace("class Example:", "class ReleasedAPI:") + '\nclass Example: pass\n'
    instance = runner.load_environment(code, "Example", 0, 0)
    assert hasattr(instance, "get_env_state")


def test_ambiguous_class_selection_abstains():
    runner = load_runner()
    code = CODE + CODE.replace("class Example:", "class Second:")
    with pytest.raises(ValueError, match="Ambiguous"):
        runner.load_environment(code, "Missing", 0, 0)


def test_canonical_baseline_abstains_on_non_json_instead_of_stringifying():
    runner = load_runner()
    payload = {"before": {}, "after": {"values": {1, 2}}, "result": {}, "category": "changed", "method_executed": True}
    row = runner.receipt("Fixture", "one", "method", {}, [payload, payload, payload])
    assert row["canonical_free_status"] == "UNKNOWN"


def test_live_getter_and_return_values_are_snapshotted_before_mutation():
    class Environment:
        def __init__(self): self.state = {"items": []}
        def get_env_state(self): return self.state
        def add(self):
            self.state["items"].append("created")
            return self.state
    runner = load_runner()
    env = Environment()
    observation = runner.transition(env, "add", [], {})
    assert observation["before"] == {"items": []}
    assert observation["after"] == {"items": ["created"]}
    assert observation["category"] == "changed"
    env.state["items"].append("later")
    assert observation["after"] == observation["result"] == {"items": ["created"]}


@pytest.mark.parametrize("method,kwargs", [("missing", {}), ("fail", {"unexpected": 1})])
def test_unsupported_dispatch_is_unknown_and_not_an_execution(method, kwargs):
    runner = load_runner()
    output = runner.execute(CODE, "Example", {}, method, kwargs, 0, 0)
    assert output["category"] == "dispatch_error"
    assert output["method_executed"] is False
    row = runner.receipt("Fixture", "bad", method, kwargs, [output, output, output])
    assert row["coupled_status"] == row["free_status"] == row["canonical_free_status"] == "UNKNOWN"
    assert row["method_executions"] == 0


def test_exception_in_a_valid_method_is_still_a_real_execution():
    runner = load_runner()
    output = runner.execute(CODE, "Example", {}, "fail", {}, 0, 0)
    assert output["category"] == "exception"
    assert output["method_executed"] is True

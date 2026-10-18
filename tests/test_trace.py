from copy import deepcopy
import json

import pytest

from twinproof.trace import compare_traces


def fixture():
    left = {"initial": {"state": {"items": {"old": {"id": "old", "name": "old"}}}},
            "steps": [{"result": {"id": "ref-1"}, "state": {
                "items": {"old": {"id": "old", "name": "old"},
                          "ref-1": {"id": "ref-1", "name": "hello"}},
                "selected": "ref-1"}},
                {"result": {"id": "ref-1"}, "state": {"selected": "ref-1"}}]}
    right = json.loads(json.dumps(left).replace("ref-1", "cand-1"))
    contract = {"namespaces": {"item": {
        "values": ["/result/id", "/state/items/*/id", "/state/selected"],
        "keys": ["/state/items"]}},
        "bindings": [{"step": 0, "namespace": "item", "expected": "ref-1",
                      "observed": "cand-1", "path": "/result/id"}]}
    return left, right, contract


def test_consistent_creation_and_later_references_pass_without_mutation():
    left, right, contract = fixture()
    before = deepcopy((left, right, contract))
    assert compare_traces(left, right, contract).status == "PASS"
    assert (left, right, contract) == before


@pytest.mark.parametrize("kind", ["dangling", "raw_expected", "text", "extra", "old", "timestamp", "bool"])
def test_corruption_is_not_normalized_away(kind):
    left, right, contract = fixture()
    if kind == "dangling":
        right["steps"][1]["state"]["selected"] = "cand-2"
    elif kind == "raw_expected":
        right["steps"][1]["state"]["selected"] = "ref-1"
    elif kind == "text":
        left["steps"][0]["state"]["items"]["ref-1"]["name"] = "ref-1"
        right["steps"][0]["state"]["items"]["cand-1"]["name"] = "cand-1"
    elif kind == "extra":
        right["steps"][1]["state"]["extra"] = True
    elif kind == "old":
        right["steps"][0]["state"]["items"]["old"]["id"] = "cand-1"
    elif kind == "timestamp":
        left["steps"][1]["time"] = "2026-10-18T00:00:00Z"
        right["steps"][1]["time"] = "2026-10-18T00:00:01Z"
    else:
        left["steps"][1]["flag"] = True
        right["steps"][1]["flag"] = 1
    verdict = compare_traces(left, right, contract)
    assert verdict.status == "FAIL"
    assert verdict.differences


@pytest.mark.parametrize("kind", ["missing_origin", "reused_initial", "duplicate", "late", "unknown_namespace", "overlap", "bad_pointer", "bad_step"])
def test_untrustworthy_metadata_abstains(kind):
    left, right, contract = fixture()
    binding = contract["bindings"][0]
    if kind == "missing_origin":
        binding["path"] = "/result/missing"
    elif kind == "reused_initial":
        binding["expected"] = "old"
        left["steps"][0]["result"]["id"] = "old"
    elif kind == "duplicate":
        contract["bindings"].append(deepcopy(binding))
    elif kind == "late":
        binding["step"] = 1
    elif kind == "unknown_namespace":
        binding["namespace"] = "unknown"
    elif kind == "overlap":
        contract["namespaces"]["other"] = {"values": ["/result/*"], "keys": []}
    elif kind == "bad_pointer":
        contract["namespaces"]["item"]["values"].append("/invalid~2path")
    else:
        binding["step"] = True
    assert compare_traces(left, right, contract).status == "UNKNOWN"


def test_unbound_uuid_is_compared_exactly():
    a = {"initial": {}, "steps": [{"id": "5c745c10-9974-4998-a4ee-cd39ed72c18a"}]}
    b = {"initial": {}, "steps": [{"id": "7434733e-d969-4b81-8df7-d366fc90e8df"}]}
    assert compare_traces(a, b, {"namespaces": {}, "bindings": []}).status == "FAIL"


def test_step_order_and_initial_state_are_exact():
    left, right, contract = fixture()
    right["initial"]["state"]["items"]["old"]["name"] = "changed"
    assert compare_traces(left, right, contract).status == "FAIL"
    left, right, contract = fixture()
    right["steps"].reverse()
    assert compare_traces(left, right, contract).status == "FAIL"


def test_non_string_identifier_is_a_failure():
    left, right, contract = fixture()
    right["steps"][1]["state"]["selected"] = 1
    assert compare_traces(left, right, contract).status == "FAIL"


def test_cli_trace(tmp_path, capsys):
    from twinproof.cli import main
    left, right, contract = fixture()
    paths = []
    for name, value in zip(("reference", "candidate", "contract"), (left, right, contract)):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        paths.append(str(path))
    assert main(["trace", *paths]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


@pytest.mark.parametrize("collision", ["value", "key"])
def test_normalized_tokens_cannot_collide_with_ordinary_json(collision):
    contract = {"namespaces": {"item": {
        "values": ["/result/id", "/state/items/ref-1/value"],
        "keys": ["/state/items", "/state/items/ref-1/links"]}},
        "bindings": [{"step": 0, "namespace": "item", "expected": "ref-1",
                      "observed": "cand-1", "path": "/result/id"}]}
    a = {"initial": {}, "steps": [{"result": {"id": "ref-1"}, "state": {"items": {"ref-1": {}}}}]}
    b = {"initial": {}, "steps": [{"result": {"id": "cand-1"}, "state": {"items": {"cand-1": {}}}}]}
    left, right = a["steps"][0]["state"]["items"]["ref-1"], b["steps"][0]["state"]["items"]["cand-1"]
    if collision == "value":
        left["value"] = "ref-1"
        right["value"] = ["item", "bound", 0]
    else:
        left["links"] = {"ref-1": True}
        right["links"] = {json.dumps(["item", "bound", 0]): True}
    assert compare_traces(a, b, contract).status == "FAIL"

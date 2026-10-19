"""Read-only experiment worker. Invoke through experiment.py, inside a clean venv."""

from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
import time
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))


def install_guards(inputs: Path) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (75, 75))
    except ImportError:
        raise RuntimeError("This bounded worker requires a POSIX platform")
    allowed = [PACKAGE, inputs, Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
    allowed += [Path(name) for name in ["/System/Library", "/usr/lib", "/usr/share/zoneinfo"]]
    mutations = {"os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.symlink", "os.link", "os.truncate", "os.utime"}

    def audit(event, args):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork"} or event in mutations:
            raise PermissionError(f"Worker side effect denied: {event}")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode = args[1]
            flags = args[2]
            if (isinstance(mode, str) and any(flag in mode for flag in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                raise PermissionError(f"Worker write denied: {path}")
            if path != Path("/dev/null") and not any(path.is_relative_to(root) for root in allowed):
                raise PermissionError(f"Worker read outside declared inputs/runtime denied: {path}")

    sys.addaudithook(audit)


def witnesses(runtime):
    specs = json.loads((PACKAGE / "derived/witnesses.json").read_text())["witnesses"]
    rows = []
    for witness in specs:
        states = []
        hashes = {}
        for arm in ("a", "b"):
            state = runtime.initial(witness["initial_attempt"])
            for action in witness[arm + "_history"]:
                state, status = runtime.step(state, action)
            state_hash = runtime.state_hash(state)
            if state_hash != witness["state_payload_sha256"][arm]:
                raise AssertionError((witness["id"], arm, "full reconstructed state differs from frozen snapshot"))
            hashes[arm] = state_hash
            states.append(state)
        a, b = states
        if runtime.key(a) != runtime.key(b) or runtime.jsonable(runtime.key(a)) != witness["original_key"]:
            raise AssertionError("Frozen original-key collision not reproduced")
        different = int(runtime.np.count_nonzero(runtime.sio.current_map(a) != runtime.sio.current_map(b)))
        if different != witness["different_grid_cell_count"]:
            raise AssertionError("Frozen grid difference count changed")
        separations = {
            "original": runtime.key(a) != runtime.key(b),
            "repaired_three": runtime.small_key(a) != runtime.small_key(b),
            "union_298": runtime.union_key(a) != runtime.union_key(b),
            "full_grid": runtime.grid_key(a) != runtime.grid_key(b),
        }
        if witness["id"] == "holdout-frozen-key-failure" and separations["repaired_three"]:
            raise AssertionError("Expected frozen three-cell key false negative disappeared")
        results = {}
        for arm, state in zip(("a", "b"), states):
            for action in witness["distinguishing"]["suffix"]:
                state, status = runtime.step(state, action)
            results[arm] = runtime.physical(state, status)
            if results[arm] != witness["distinguishing"][arm + "_result"]:
                raise AssertionError("Frozen shared-suffix physical result changed")
        rows.append({
            "witness_id": witness["id"], "original_witness_sha256": witness["original_witness_sha256"],
            "state_payload_sha256": hashes, "original_key": witness["original_key"],
            "different_grid_cell_count": different, "separated": separations,
            "common_suffix": witness["distinguishing"]["suffix"], "results": results,
            "passed": True,
        })
    print(json.dumps({"stage": "fixed_witness_replay", "checks": rows, "all_engine_calls": runtime.calls}), flush=True)


def target_setup(runtime):
    folder = runtime.source / "client/session/level_08_attempt_04"
    initial = runtime.initial("level_08_attempt_04")
    actions, states = [], [initial]
    for metadata in sorted(folder.glob("step_*_metadata.json")):
        action = runtime.parse_action(json.loads(metadata.read_text())["action_input"])
        state, status = runtime.step(states[-1], action)
        expected = runtime.load_frame(folder / metadata.name.replace("_metadata.json", "_final.txt"))
        if not runtime.np.array_equal(runtime.sio.state_renderer(state), expected):
            raise AssertionError(f"Archived attempt 4 pixel replay mismatch: {metadata.name}")
        actions.append(action)
        states.append(state)
    replay_calls = runtime.calls
    a_folder = runtime.source / "client/session/level_08_attempt_01"
    a_root = runtime.initial("level_08_attempt_01")
    for metadata in sorted(a_folder.glob("step_*_metadata.json"))[:8]:
        a_root, status = runtime.step(a_root, runtime.parse_action(json.loads(metadata.read_text())["action_input"]))
    a_signature = runtime.goal_key(a_root)
    candidates, root_seen = [], set()
    for index in range(8, len(states) - 4):
        signature = runtime.goal_key(states[index])
        if signature in root_seen or signature == a_signature or signature == runtime.goal_key(states[index + 4]):
            continue
        root_seen.add(signature)
        candidates.append({"task_id": f"attempt4-prefix{index:02d}-to-{index+4:02d}", "root_index": index, "target_index": index + 4})
        if len(candidates) >= 20:
            break
    frozen = json.loads((PACKAGE / "derived/tasks.json").read_text())["tasks"]
    if candidates != frozen:
        raise AssertionError("Declared target cohort differs from original deterministic selection")
    plan = json.loads((runtime.source / "level_8_winning_plan.json").read_text())
    state, first_terminal = initial, None
    for index, action in enumerate(plan, 1):
        state, status = runtime.step(state, action)
        if str(status) != "RUNNING":
            first_terminal = index
            break
    published = {"actions_in_file": len(plan), "executed": index, "status": str(status), "first_terminal": first_terminal, "position": [state["avatar_top"], state["avatar_left"]]}
    print(json.dumps({
        "stage": "setup", "task_count": len(candidates), "tasks": candidates,
        "replay_calls": replay_calls, "replay_pixels_exact": True, "published_plan_replay": published,
        "frozen_small_coordinates": runtime.small, "frozen_union_coordinate_count": len(runtime.union),
        "budget_per_arm": 150, "horizon": 4, "setup_engine_calls": runtime.calls,
        "search_order": "best first by exact target grid mismatch, then pose distance; not an admissible heuristic",
        "goal_definition": "exact current_map plus avatar pose/facing/gravity; model-only recorded future target",
    }), flush=True)
    return states, candidates


def search_target(runtime, states, task, method, key_function):
    before, began = runtime.calls, time.monotonic()
    start, target = states[task["root_index"]], states[task["target_index"]]
    goal, goal_grid = runtime.goal_key(target), runtime.sio.current_map(target).copy()
    runtime.sio._MAP_CACHE.clear()

    def heuristic(state):
        return (int(runtime.np.count_nonzero(runtime.sio.current_map(state) != goal_grid)), abs(state["avatar_top"] - target["avatar_top"]) + abs(state["avatar_left"] - target["avatar_left"]))

    counter = 0
    queue = [(heuristic(start), 0, counter, start, [])]
    best_depth = {key_function(start): 0}
    expanded, generated, found = 0, 0, None
    while queue and expanded < 150:
        _, _, _, state, path = heapq.heappop(queue)
        if len(path) >= 4 or len(path) > best_depth.get(key_function(state), 10**9):
            continue
        expanded += 1
        for action in runtime.actions(state):
            nxt, status = runtime.step(state, action)
            generated += 1
            new_path = path + [action]
            if str(status) == "RUNNING" and runtime.goal_key(nxt) == goal:
                found = new_path
                break
            if status != runtime.RUNNING or not runtime.trusted(nxt):
                continue
            token = key_function(nxt)
            if best_depth.get(token, 10**9) <= len(new_path):
                continue
            best_depth[token] = len(new_path)
            counter += 1
            heapq.heappush(queue, (heuristic(nxt), len(new_path), counter, nxt, new_path))
        if found is not None:
            break
    if found is not None:
        replay = start
        for action in found:
            replay, status = runtime.step(replay, action)
        if str(status) != "RUNNING" or runtime.goal_key(replay) != goal:
            raise AssertionError("Returned route does not replay to the declared target")
    return {
        "stage": "target_result", "protocol": "goal-directed-amendment-v2", "task_id": task["task_id"],
        "method": method, "found": found is not None, "route": found, "route_length": len(found) if found is not None else None,
        "route_replay_verified": found is not None, "shortestness": "not certified; inadmissible shared ordering",
        "expanded": expanded, "generated": generated, "engine_calls": runtime.calls - before,
        "unique_keys": len(best_depth), "pending": len(queue), "complete_horizon": not queue and found is None,
        "budget_exhausted": expanded >= 150 and found is None, "seconds": time.monotonic() - began,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["witnesses", "targets"])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--shard", type=int, choices=range(4), default=0)
    args = parser.parse_args()
    inputs = args.inputs.resolve()
    install_guards(inputs)
    from fetch_inputs import verified_inputs
    verified_inputs(inputs)
    from model_runtime import Runtime
    runtime = Runtime(PACKAGE, inputs)
    if args.mode == "witnesses":
        witnesses(runtime)
    else:
        states, candidates = target_setup(runtime)
        methods = [("original", runtime.key), ("repaired_three", runtime.small_key), ("union_298", runtime.union_key), ("full_grid", runtime.grid_key)]
        for task in candidates[args.shard * 5:(args.shard + 1) * 5]:
            for method, key_function in methods:
                print(json.dumps(search_target(runtime, states, task, method, key_function)), flush=True)
        print(json.dumps({"stage": "finished", "all_engine_calls": runtime.calls}), flush=True)


if __name__ == "__main__":
    main()

"""Own-code adapter for unchanged, hash-verified external THEA functions."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


class Runtime:
    def __init__(self, package: Path, inputs: Path):
        self.package = package
        self.source = inputs / "source/runs/bp35/agent_run"
        sys.path[:0] = [str(self.source), str(inputs / "support")]
        import numpy as np
        import load_initial_full_frame
        import world_model_state_io as sio
        from game_status import RUNNING
        from session_tools import _action_from_input, _load_ascii_frame
        from world_model_engine import stop_is_trusted, world_model_engine

        load_initial_full_frame.INITIAL_FULL_FRAMES_DIR = self.source / "initial_full_frames"
        self.np, self.sio, self.RUNNING = np, sio, RUNNING
        self.parse_action, self.load_frame = _action_from_input, _load_ascii_frame
        self.engine, self.trusted = world_model_engine, stop_is_trusted
        self.calls = 0
        pins = json.loads((package / "pins.json").read_text())
        planner = self.source / "world_model_main_planner.py"
        lines = planner.read_text().splitlines(keepends=True)
        namespace = {name: getattr(sio, name) for name in [
            "avatar_screen_top", "door_handle", "door_open", "current_map", "GRAVITY_FLIP_DOORS"
        ]}
        for name, entry in pins["function_slices"].items():
            first, last = entry["first_line"], entry["last_line"]
            fragment = "".join(lines[first - 1:last])
            if hashlib.sha256(fragment.encode()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Function slice hash mismatch: {name}")
            exec(compile("\n" * (first - 1) + fragment, str(planner), "exec"), namespace)
        self.key, self.door_clicks = namespace["_key"], namespace["door_clicks"]
        features = json.loads((package / "derived/frozen-features.json").read_text())
        self.small = features["small"]
        self.union = features["union"]

    def step(self, state, action):
        self.calls += 1
        return self.engine(state, action)

    def initial(self, attempt):
        frame = self.source / "client/session" / attempt / "initial_frame.txt"
        return self.sio.initial_state_reconstruction(8, self.load_frame(frame))

    def actions(self, state):
        return self.door_clicks(state) + [{"name": "ACTION4"}, {"name": "ACTION3"}]

    def jsonable(self, value):
        if isinstance(value, self.np.ndarray):
            return {"ndarray": value.tolist(), "dtype": str(value.dtype), "shape": list(value.shape)}
        if isinstance(value, self.np.generic):
            return value.item()
        if isinstance(value, dict):
            return {str(key): self.jsonable(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.jsonable(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted([self.jsonable(item) for item in value], key=repr)
        return value

    def state_hash(self, state):
        raw = json.dumps(self.jsonable(state), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def physical(self, state, status):
        return [state["avatar_top"], state["avatar_left"], state["facing"], state["gravity"], str(status), self.trusted(state)]

    def small_key(self, state):
        grid = self.sio.current_map(state)
        return self.key(state), tuple(int(grid[row, col]) for row, col in self.small)

    def union_key(self, state):
        grid = self.sio.current_map(state)
        return self.key(state), bytes(int(grid[row, col]) for row, col in self.union)

    def grid_key(self, state):
        return self.key(state), self.sio.current_map(state).tobytes()

    def goal_key(self, state):
        return (state["avatar_top"], state["avatar_left"], state["facing"], state["gravity"], self.sio.current_map(state).tobytes())

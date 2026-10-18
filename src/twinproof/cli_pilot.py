"""Bounded development experiment for two released stateful CLI families.

These projections are explicit task contracts, not general program equivalence.
Downloaded programs must be run by the network-isolated container entrypoint.
"""

from collections import deque
from dataclasses import dataclass
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import tempfile
import time


class BudgetExhausted(Exception):
    pass


MODES = ("breadth_first", "random_prefix", "aalpy_random_word", "candidate_state_cover")


@dataclass
class Budget:
    maximum: int
    calls: int = 0

    def take(self):
        if self.calls >= self.maximum:
            raise BudgetExhausted
        self.calls += 1


def run_command(argv, cwd, env, budget, timeout=3):
    budget.take()
    started = time.monotonic()
    result = {"argv": list(argv), "status": "OK"}
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                result["returncode"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                result.update(status="TIMEOUT", returncode=None)
        except OSError as exc:
            result.update(status="EXEC_ERROR", returncode=None, error=type(exc).__name__)
        for label, stream in (("stdout", stdout), ("stderr", stderr)):
            stream.seek(0)
            data = stream.read(65537)
            if len(data) > 65536:
                result["status"] = "OUTPUT_LIMIT"
            result[label] = data[:65536].decode("utf-8", errors="replace")
    result["seconds"] = round(time.monotonic() - started, 6)
    return result


def observe_tasks(stdout):
    value = json.loads(stdout)
    if not isinstance(value, list):
        raise ValueError("expected task list")
    fields = ("summary", "status", "notes", "project", "priority", "due")
    out = []
    for task in value:
        if not isinstance(task, dict) or type(task.get("id")) is not int:
            raise ValueError("task lacks an integer CLI identifier")
        if not all(isinstance(task.get(key), str) for key in fields):
            raise ValueError("task lacks a declared text field")
        tags = task.get("tags")
        if tags is None:
            tags = []  # Declared empty tag-set representation, not arbitrary null removal.
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError("invalid task tags")
        out.append({"id": task["id"], **{key: task[key] for key in fields}, "tags": sorted(tags)})
    return sorted(out, key=lambda row: json.dumps(row, sort_keys=True))


def observe_query(name, stdout):
    if name in ("query_open", "query_resolved"):
        return observe_tasks(stdout)
    if name == "query_tags":
        # Upstream iterates a Go map; order is not part of its tag-set interface.
        return sorted(stdout.splitlines())
    if name != "query_projects":
        raise ValueError("unknown query")
    value = json.loads(stdout)
    if not isinstance(value, list):
        raise ValueError("expected project list")
    types = {"name": str, "taskCount": int, "resolvedCount": int, "active": bool, "priority": str}
    out = []
    for project in value:
        if not isinstance(project, dict) or any(type(project.get(k)) is not t for k, t in types.items()):
            raise ValueError("invalid project fields")
        out.append({k: project[k] for k in types})
    return sorted(out, key=lambda row: json.dumps(row, sort_keys=True))


def confirm(reference_runs, candidate_runs):
    def unknown(value):
        if value is None:
            return True
        if isinstance(value, list):
            return any(unknown(v) for v in value)
        if isinstance(value, dict):
            return any(unknown(v) for v in value.values())
        return False
    if len(reference_runs) != 2 or len(candidate_runs) != 2:
        return "UNKNOWN"
    if unknown(reference_runs) or unknown(candidate_runs):
        return "UNKNOWN"
    if reference_runs[0] != reference_runs[1] or candidate_runs[0] != candidate_runs[1]:
        return "UNKNOWN"
    return ("NO_DIFFERENCE_OBSERVED" if reference_runs[0] == candidate_runs[0]
            else "CONFIRMED_DIFFERENCE")


class CliRunner:
    def __init__(self, family, program, root, budget):
        self.family, self.program, self.root, self.budget = family, program, Path(root), budget
        self.fixture = self.root.parent / "fixtures"
        self.resets = 0
        self.setup_calls = 0
        self.application_calls = 0
        self.receipts = []
        self.ready = False

    def actions(self):
        a, b, nested = (str(self.fixture / p) for p in ("alpha", "beta", "alpha/child"))
        if self.family == "zoxide":
            return {"add_alpha": ["add", a], "add_beta": ["add", b],
                    "add_nested": ["add", nested], "remove_alpha": ["remove", a],
                    "remove_beta": ["remove", b], "query_all": ["query", "--list"],
                    "query_alpha": ["query", "--list", "alpha"],
                    "query_beta": ["query", "--list", "beta"],
                    "query_child": ["query", "--list", "child"],
                    "query_exclude_alpha": ["query", "--list", "--exclude", a],
                    "query_upper": ["query", "--list", "ALPHA"]}
        return {"add_alpha": ["add", "alpha", "+work", "project:red"],
                "add_beta": ["add", "beta", "+home", "project:blue"],
                "context_work": ["context", "+work"], "context_none": ["context", "none"],
                "modify_first": ["modify", "1", "+focus", "P1"],
                "resolve_first": ["done", "1"], "start_first": ["start", "1"],
                "stop_first": ["stop", "1"], "query_open": ["show-open"],
                "query_resolved": ["show-resolved"], "query_projects": ["show-projects"],
                "query_tags": ["show-tags"]}

    def reset(self):
        self.resets += 1
        self.ready = False
        # Caller allocates root specifically to this runner; the container owns /state.
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        for path in ("alpha", "beta", "alpha/child"):
            (self.fixture / path).mkdir(parents=True, exist_ok=True)
        (self.root / "home").mkdir()
        (self.root / "db").mkdir()
        repo = self.root / "repo"
        repo.mkdir()
        self.env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": str(self.root / "home"), "TMPDIR": str(self.root),
                    "LC_ALL": "C.UTF-8", "TZ": "UTC", "TERM": "dumb", "NO_COLOR": "1",
                    "_ZO_DATA_DIR": str(self.root / "db"), "_ZO_MAXAGE": "10000",
                    "DSTASK_GIT_REPO": str(repo), "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "TwinProof Fixture",
                    "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "TwinProof Fixture",
                    "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        if self.family == "dstask":
            setup_budget = Budget(1)
            out = run_command(["git", "init", "--quiet", str(repo)], self.root, self.env, setup_budget)
            self.setup_calls += setup_budget.calls
            self.receipts.append({"kind": "setup", **out})
            if out["status"] != "OK" or out["returncode"] != 0:
                return
        self.ready = True

    def command(self, args, kind):
        out = run_command(self.program + args, self.root, self.env, self.budget)
        self.application_calls += 1
        self.receipts.append({"kind": kind, **out})
        return out

    def step(self, name):
        if not self.ready:
            return None
        action = self.command(self.actions()[name], "action")
        if action["status"] != "OK":
            return None
        commands = ([["query", "--list"]] if self.family == "zoxide"
                    else [["show-open"], ["show-resolved"], ["show-templates"]])
        state = []
        try:
            for cmd in commands:
                observation = self.command(cmd, "observer")
                if observation["status"] != "OK":
                    return None
                if self.family == "zoxide":
                    if observation["returncode"] not in (0, 1):
                        return None
                    state = observation["stdout"].splitlines()
                else:
                    if observation["returncode"] != 0:
                        return None
                    state.extend(observe_tasks(observation["stdout"]))
        except (ValueError, KeyError, TypeError):
            return None
        # Query responses are part of the observable, not just the resulting state.
        response = action["stdout"].splitlines() if self.family == "zoxide" else None
        if self.family == "dstask" and name.startswith("query_"):
            try:
                response = observe_query(name, action["stdout"])
            except (ValueError, TypeError):
                return None
        if self.family == "dstask":
            state = sorted(state, key=lambda row: json.dumps(row, sort_keys=True))
        # Mutation command prose/UUID acknowledgments are outside this declared projection.
        return {"exit": action["returncode"], "response": response if response is not None else [], "state": state}


def replay(runner, word):
    runner.reset()
    return [runner.step(action) for action in word]


def search(reference, candidate, alphabet, mode, seed, limit=192, max_depth=4):
    """Find a first discrepancy; confirmation is a separate charged phase."""
    if mode not in MODES:
        raise ValueError("unknown search mode")
    budget = reference.budget
    start = budget.calls
    old_limit = budget.maximum
    budget.maximum = min(old_limit, start + limit)
    candidate_screen_calls = 0
    attempted_words = 0
    unknown_steps = 0
    witness = None
    random.seed(seed)
    try:
        if mode == "aalpy_random_word":
            from aalpy.base import SUL
            from aalpy.oracles import RandomWordEqOracle

            class ObservedSUL(SUL):
                def pre(self):
                    nonlocal attempted_words
                    attempted_words += 1
                    reference.reset()

                def post(self):
                    pass

                def step(self, action):
                    nonlocal unknown_steps
                    value = reference.step(action)
                    unknown_steps += value is None
                    return ("UNKNOWN_REFERENCE",) if value is None else value

            class Hypothesis:
                def reset_to_initial(self):
                    candidate.reset()

                def step(self, action):
                    nonlocal unknown_steps
                    value = candidate.step(action)
                    unknown_steps += value is None
                    return ("UNKNOWN_CANDIDATE",) if value is None else value

            oracle = RandomWordEqOracle(alphabet, ObservedSUL(), num_walks=limit,
                                       min_walk_len=1, max_walk_len=max_depth, reset_after_cex=False)
            witness = oracle.find_cex(Hypothesis())
        else:
            words = itertools.chain.from_iterable(itertools.product(alphabet, repeat=n)
                                                   for n in range(1, max_depth + 1))
            if mode == "random_prefix":
                # Seeded random ordering within each length, without replacement.
                def shuffled_levels():
                    for length in range(1, max_depth + 1):
                        level = list(itertools.product(alphabet, repeat=length))
                        random.shuffle(level)
                        yield from level
                words = shuffled_levels()
            if mode == "candidate_state_cover":
                # Known state-cover idea: exploratory control, not a claimed invention.
                screen_start = budget.calls
                screen_limit = min(64, limit // 3)
                queue = deque([(action,) for action in alphabet])
                selected, states = [], set()
                while queue and budget.calls - screen_start < screen_limit:
                    word = queue.popleft()
                    per_step = 2 if candidate.family == "zoxide" else 4
                    if budget.calls - screen_start + len(word) * per_step > screen_limit:
                        break
                    outputs = replay(candidate, word)
                    selected.append(word)
                    if outputs[-1] is not None:
                        signature = json.dumps(outputs[-1]["state"], sort_keys=True)
                        if signature not in states and len(word) < max_depth:
                            states.add(signature)
                            queue.extend(word + (a,) for a in alphabet)
                candidate_screen_calls = budget.calls - screen_start
                # Favor words that extend a state-changing prefix before simple smoke actions.
                words = sorted(selected, key=lambda word: (-len(word), word))
            for word in words:
                attempted_words += 1
                reference.reset()
                candidate.reset()
                prefix = []
                for action in word:
                    prefix.append(action)
                    left, right = reference.step(action), candidate.step(action)
                    unknown_steps += left is None or right is None
                    if left is None or right is None or left != right:
                        witness = prefix
                        break
                if witness:
                    break
    except BudgetExhausted:
        pass
    finally:
        budget.maximum = old_limit
    return {"status": "CANDIDATE_WITNESS" if witness else "NO_DIFFERENCE_FOUND_WITHIN_BUDGET",
            "witness": list(witness) if witness else None, "search_calls": budget.calls - start,
            "candidate_screen_calls": candidate_screen_calls, "attempted_words": attempted_words,
            "unknown_steps": unknown_steps}


def experiment(family, reference_program, candidate_program, root, mode, seed,
               total_budget=256, search_budget=192, alphabet=None):
    """Run one method/seed/pair; no result establishes general equivalence."""
    if mode not in MODES:
        raise ValueError("unknown search mode")
    if family not in ("zoxide", "dstask"):
        raise ValueError("unknown family")
    if not (0 < search_budget <= total_budget):
        raise ValueError("invalid budget")
    started = time.monotonic()
    budget = Budget(total_budget)
    root = Path(root)
    reference = CliRunner(family, reference_program, root / "reference", budget)
    candidate = CliRunner(family, candidate_program, root / "candidate", budget)
    alphabet = list(reference.actions()) if alphabet is None else list(alphabet)
    result = search(reference, candidate, alphabet, mode, seed, limit=search_budget)
    confirmation = {"reference": [], "candidate": []}
    verdict = result["status"]
    if result["witness"]:
        try:
            for _ in range(2):
                confirmation["reference"].append(replay(reference, result["witness"]))
                confirmation["candidate"].append(replay(candidate, result["witness"]))
            verdict = confirm(confirmation["reference"], confirmation["candidate"])
        except BudgetExhausted:
            verdict = "UNKNOWN"
    setup = reference.setup_calls + candidate.setup_calls
    result.update(schema=1, family=family, mode=mode, seed=seed, verdict=verdict,
                  alphabet=alphabet, total_budget=total_budget, search_budget=search_budget,
                  application_calls=budget.calls, reference_calls=reference.application_calls,
                  candidate_calls=candidate.application_calls, setup_calls=setup,
                  total_process_calls=budget.calls + setup,
                  reference_resets=reference.resets, candidate_resets=candidate.resets,
                  confirmation_calls=budget.calls - result["search_calls"],
                  seconds=round(time.monotonic() - started, 6), confirmation=confirmation)
    return result, {"reference": reference.receipts, "candidate": candidate.receipts}

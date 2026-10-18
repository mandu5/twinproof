"""Pinned ClawForge same-implementation replay pilot; not an AI-twin benchmark.

Subprocess limits and audit hooks are defense in depth for this reviewed source
snapshot, NOT a general-purpose sandbox. Results contain digests, not task data.
"""
import argparse
import ast
import builtins
from collections import Counter
from copy import deepcopy
import datetime as dt
import hashlib
import importlib
import inspect
import io
import json
from pathlib import Path
import random
import resource
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

from twinproof.state import compare_states


ALLOWED_IMPORTS = {"copy", "typing", "datetime", "random", "string", "hashlib", "uuid",
                   "re", "time", "math", "decimal", "json", "csv", "io", "urllib.parse"}
BLOCKED_CALLS = {"open", "eval", "exec", "compile", "__import__", "input", "breakpoint"}
MAX_METHODS = 24
EPOCH = 1792281600  # Fixed experiment clock; explicit rather than wall time.


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    default=str, allow_nan=False).encode()).hexdigest()


def static_gate(code):
    problems = []
    for node in ast.walk(ast.parse(code)):
        names = []
        if isinstance(node, ast.Import):
            names = [n.name for n in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if name not in ALLOWED_IMPORTS:
                problems.append("import:" + name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
            problems.append("call:" + node.func.id)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append("dunder_attribute:" + node.attr)
    return sorted(set(problems))


def load_environment(code, name, seed, offset):
    rng = random.Random(seed)
    epoch = EPOCH + offset

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(epoch, tz)

        @classmethod
        def utcnow(cls):
            return cls.utcfromtimestamp(epoch)

        @classmethod
        def today(cls):
            return cls.now()

    class Date(dt.date):
        @classmethod
        def today(cls):
            return cls.fromtimestamp(epoch)

    class SeededRandom(random.Random):
        def __init__(self, x=None):
            super().__init__(seed if x is None else x)

    datetime_proxy = SimpleNamespace(**{key: getattr(dt, key) for key in dir(dt) if not key.startswith("_")})
    datetime_proxy.datetime, datetime_proxy.date = Clock, Date
    random_proxy = SimpleNamespace(**{key: getattr(rng, key) for key in dir(rng) if not key.startswith("_")})
    random_proxy.Random = SeededRandom
    uuid_proxy = SimpleNamespace(**{key: getattr(uuid, key) for key in dir(uuid) if not key.startswith("_")})
    uuid_proxy.uuid4 = lambda: uuid.UUID(int=rng.getrandbits(128), version=4)
    time_proxy = SimpleNamespace(**{key: getattr(time, key) for key in ("strftime", "strptime", "gmtime", "localtime")})
    time_proxy.time = time_proxy.monotonic = time_proxy.perf_counter = lambda: float(epoch)
    proxies = {"datetime": datetime_proxy, "random": random_proxy, "uuid": uuid_proxy, "time": time_proxy}

    def controlled_import(module, globals=None, locals=None, fromlist=(), level=0):
        if level or module not in ALLOWED_IMPORTS:
            raise ImportError("Unsupported import in pinned runner: " + module)
        return proxies.get(module) or builtins.__import__(module, globals, locals, fromlist, level)

    safe_builtins = {k: v for k, v in vars(builtins).items() if k not in BLOCKED_CALLS}
    safe_builtins["__import__"] = controlled_import
    scope = {"__builtins__": safe_builtins, "__name__": "twinproof_pinned_environment"}
    exec(compile(code, "<pinned-environment>", "exec"), scope)
    candidates = {key: value for key, value in scope.items() if isinstance(value, type)
                  and all(callable(getattr(value, method, None)) for method in ("_load_scenario", "get_env_state"))}
    if name in candidates:
        return candidates[name]()
    if len(candidates) != 1:
        raise ValueError("Ambiguous or missing environment class implementing the state interface")
    return next(iter(candidates.values()))()


def arguments(method, state):
    candidates = {}

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                candidates.setdefault(key, []).append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(state)
    result = {}
    for name, parameter in inspect.signature(method).parameters.items():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if name in candidates:
            result[name] = deepcopy(candidates[name][0])
        else:
            annotation = str(parameter.annotation).lower()
            if "bool" in annotation:
                result[name] = False
            elif "int" in annotation or "float" in annotation:
                result[name] = 1
            elif "list" in annotation:
                result[name] = []
            elif "dict" in annotation:
                result[name] = {}
            else:
                result[name] = "twinproof-probe"
    return result


def transition(env, method, args, kwargs):
    before = deepcopy(env.get_env_state())
    try:
        function = getattr(env, method)
        inspect.signature(function).bind(*args, **kwargs)
    except (AttributeError, TypeError, ValueError) as exc:
        return {"before": before, "result": {"dispatch_error": type(exc).__name__, "message_hash": digest(str(exc))},
                "after": deepcopy(env.get_env_state()), "category": "dispatch_error", "method_executed": False}
    try:
        result = deepcopy(function(*deepcopy(args), **deepcopy(kwargs)))
        after = deepcopy(env.get_env_state())
        category = "unchanged" if compare_states(before, after).status == "PASS" else "changed"
        if isinstance(result, dict) and ("error" in result or result.get("success") is False or result.get("status") == "error"):
            category = "returned_error"
    except Exception as exc:
        result = {"exception_type": type(exc).__name__, "message_hash": digest(str(exc))}
        after = deepcopy(env.get_env_state())
        category = "exception"
    return {"before": before, "result": result, "after": after, "category": category, "method_executed": True}


def execute(code, name, scenario, method, kwargs, seed, offset):
    env = load_environment(code, name, seed, offset)
    env._load_scenario(deepcopy(scenario))
    return transition(env, method, [], kwargs)


def literal_call(text):
    node = ast.parse(text, mode="eval").body
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id.startswith("_"):
        raise ValueError("Only a named public tool call is supported")
    if any(k.arg is None for k in node.keywords):
        raise ValueError("Expanded call arguments are unsupported")
    return node.func.id, [ast.literal_eval(x) for x in node.args], {k.arg: ast.literal_eval(k.value) for k in node.keywords}


def published_workflows(code):
    workflows, skipped = [], 0
    for node in ast.parse(code).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if not any(isinstance(x, ast.Name) and x.id == "__TEST_CASES__" for x in targets):
            continue
        try:
            cases = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            skipped += 1
            continue
        if not isinstance(cases, list):
            skipped += 1
            continue
        for case in cases:
            try:
                steps = case.get("steps", [case])
                workflow = [literal_call(step["tool_call"]) for step in steps]
                if not workflow:
                    raise ValueError("Empty workflow")
                workflows.append(workflow)
            except (KeyError, TypeError, ValueError, SyntaxError, AttributeError):
                skipped += 1
    return workflows, skipped


def receipt(name, case_id, method, args, outputs):
    left, free, coupled = outputs
    free_status = (compare_states(left, free).status if left.get("method_executed") and free.get("method_executed") else "UNKNOWN")
    coupled_status = (compare_states(left, coupled).status if left.get("method_executed") and coupled.get("method_executed") else "UNKNOWN")
    canonical_status = "UNKNOWN" if free_status == "UNKNOWN" else ("PASS" if digest(left) == digest(free) else "FAIL")
    return {"environment": name, "case_id": case_id, "method": method, "arguments_sha256": digest(args),
            "category": left["category"], "free_category": free["category"], "coupled_category": coupled["category"],
            "free_status": free_status,
            "coupled_status": coupled_status,
            "canonical_free_status": canonical_status,
            "method_executions": sum(bool(x.get("method_executed")) for x in outputs),
            "observation_sha256": [digest(x) for x in outputs]}


def run_environment(code, name, scenario):
    template = load_environment(code, name, 0, 0)
    template._load_scenario(deepcopy(scenario))
    methods = sorted(n for n, v in inspect.getmembers(template, callable)
                     if not n.startswith("_") and n not in {"get_env_state", "get_api_description"})
    cases = []
    for method in methods[:MAX_METHODS]:
        kwargs = arguments(getattr(template, method), scenario)
        outputs = [execute(code, name, scenario, method, kwargs, seed, offset)
                   for seed, offset in [(0, 0), (1, 7), (0, 0)]]
        cases.append(receipt(name, "heuristic/" + method, method, kwargs, outputs))
    workflows, skipped = published_workflows(code)
    for index, workflow in enumerate(workflows):
        instances = [load_environment(code, name, seed, offset) for seed, offset in [(0, 0), (1, 7), (0, 0)]]
        for env in instances:
            env._load_scenario({})
        for step, (method, args, kwargs) in enumerate(workflow):
            outputs = [transition(env, method, args, kwargs) for env in instances]
            cases.append(receipt(name, f"published/{index}/{step}", method, [args, kwargs], outputs))
    return {"environment": name, "status": "EXECUTED", "cases": cases,
            "public_methods": len(methods), "heuristic_methods_executed": min(MAX_METHODS, len(methods)),
            "published_workflows": len(workflows), "published_cases_unsupported": skipped}


def restrict_worker():
    for name in ALLOWED_IMPORTS:
        importlib.import_module(name)
    # strptime lazily imports modules; load it before denying file access.
    dt.datetime.strptime("2026-10-18", "%Y-%m-%d")
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))

    def audit(event, args):
        if event == "open" or event.startswith(("socket.", "subprocess.", "ctypes.", "os.")):
            raise RuntimeError("Blocked worker side effect: " + event)
    sys.addaudithook(audit)


def run(snapshot, output):
    manifest_path = Path(__file__).resolve().parents[1] / "sources/clawforge.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["files"]:
        data = (snapshot / item["path"]).read_bytes()
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Snapshot hash mismatch: " + item["path"])
    output.mkdir(parents=True, exist_ok=False)
    scenarios = {}
    with (snapshot / "ClawForge-Tool_data.jsonl").open() as stream:
        for line in stream:
            meta = json.loads(line)["meta"]
            initial = json.loads(meta["init_env"])
            for name, state in initial.items():
                scenarios.setdefault(name, state)
    reports, rows = [], []
    start = time.perf_counter()
    for item in manifest["files"]:
        if not item["path"].endswith(".py"):
            continue
        name = Path(item["path"]).stem
        code = (snapshot / item["path"]).read_text()
        reasons = static_gate(code)
        if reasons:
            report = {"environment": name, "status": "STATIC_EXCLUDED", "reasons": reasons}
        elif name not in scenarios:
            report = {"environment": name, "status": "NO_RELEASED_INITIAL_STATE"}
        else:
            try:
                proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker"],
                    input=json.dumps({"code": code, "name": name, "scenario": scenarios[name]}),
                    capture_output=True, text=True, timeout=25,
                    env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                         "PYTHONHASHSEED": "0", "TZ": "UTC", "PYTHONDONTWRITEBYTECODE": "1"})
                if proc.returncode:
                    report = {"environment": name, "status": "WORKER_ERROR", "exit_code": proc.returncode,
                              "stderr_sha256": digest(proc.stderr)}
                else:
                    report = json.loads(proc.stdout)
                    rows.extend(report.pop("cases", []))
            except subprocess.TimeoutExpired:
                report = {"environment": name, "status": "TIMEOUT"}
        reports.append(report)
    counts = Counter(r["category"] for r in rows)
    summary = {"experiment": "clawforge-same-implementation-runtime-pilot-v1",
               "source_commit": manifest["commit"], "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "environments_total": len(reports), "environment_status": dict(Counter(r["status"] for r in reports)),
               "observations": len(rows), "categories": dict(counts),
               "free_status": dict(Counter(r["free_status"] for r in rows)),
               "coupled_status": dict(Counter(r["coupled_status"] for r in rows)),
               "canonical_free_status": dict(Counter(r["canonical_free_status"] for r in rows)),
               "attempted_calls": 3 * len(rows), "method_executions": sum(r["method_executions"] for r in rows),
               "wall_seconds": round(time.perf_counter() - start, 3),
               "inference_calls": 0, "sota": False,
               "claims": ["Same source code is replayed three times; no independently generated twins.",
                          "Changing runtime can legitimately change business outcomes; differences are not false rejects.",
                          "Exceptions, returned errors, unsupported cases and exclusions are reported.",
                          "No real-defect false acceptance metric or SOTA comparison was measured.",
                          "RESTler, Keploy and independent workflow-generator baselines were not run."]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "environments.json").write_text(json.dumps(reports, indent=2) + "\n")
    (output / "cases.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    return summary


def main():
    if sys.argv[1:] == ["--worker"]:
        request = json.load(sys.stdin)
        restrict_worker()
        # Do not let debug prints in downloaded modules contaminate JSON output.
        import contextlib
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                report = run_environment(request["code"], request["name"], request["scenario"])
        except Exception as exc:
            report = {"environment": request["name"], "status": "RUNNER_ERROR",
                      "error_type": type(exc).__name__, "error": str(exc)[:300]}
        print(json.dumps(report))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.output), indent=2))


if __name__ == "__main__":
    main()

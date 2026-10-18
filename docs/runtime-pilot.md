# Independent-source runtime control pilot

Date: 2026-10-18. Source: [ClawForge/EnvCraft](https://github.com/zeng-yirong/EnvCraft)
at commit `ea401a9eeba245d35b2413bffcb0c26bd58b3f73` (Apache-2.0).
This is a **same-implementation positive control**, not a benchmark of generated
twins. It executes actual released environment methods without an LLM.

## Reproduce

Python 3.11+ on Unix, `curl`, and the installed package are required.

```sh
python3 scripts/fetch_clawforge.py
python3 scripts/run_runtime_pilot.py --snapshot .cache/clawforge --output .cache/my-runtime-pilot
```

The output directory must be new. The manifest pins 72 files (70 modules, the
released task data and license), totaling 41,322,910 bytes. Downloaded sources and
task records remain local and ignored by git. Public receipts contain only
counts, tool/case identifiers and observation digests.

The runner checks every input hash, rejects modules requiring unapproved imports,
file access, `eval` or other unsupported surfaces, and isolates eligible modules
in subprocesses with CPU/time limits and audit hooks blocking network, subprocess
launch and filesystem access. This is defense in depth for the pinned reviewed
snapshot, **not a secure sandbox for arbitrary untrusted Python**.

## Selection and controls

All 70 root tool modules were considered. Two had been read during discovery;
the remaining modules were new to this implementation. This does not establish
68 independent service families. Task states use the first released record under
the exact module name. Fifteen modules have missing or unsupported aliases in
that mapping and are excluded explicitly; seven fail the static capability gate.

Each executed module contributes up to 24 alphabetically ordered public methods,
with deterministic argument suggestions from its task state and type annotations.
Separately, the runner parses literal tool calls in released `__TEST_CASES__`
workflows and executes them sequentially from the module's default scenario.
Neither panel was selected for success or runtime sensitivity. Unsupported
workflow encodings are counted; their labels are not silently treated as passed.

Every call is executed three times: reference clock/RNG, a clock seven seconds
later with a different RNG seed, and the original shared clock/RNG. State before,
result, state after and execution category are compared. Published workflow calls
retain earlier state in that workflow. The runner does not synthesize twin code,
discover cross-service workflows or control arbitrary external dependencies.

## Measured results

| Coverage or outcome | Count |
|---|---:|
| Modules considered / executed | 70 / 48 |
| Static exclusions / unsupported initial-state mappings | 7 / 15 |
| Attempted observations / attempted dispatches / executed method calls | 1,546 / 4,638 / 4,275 |
| Heuristic single-call / published-workflow observations | 921 / 625 |
| Executed published workflows | 195 |
| Unsupported published case encodings or nonliteral blocks | 217 |
| Changed state / unchanged state | 308 / 687 |
| Returned error / method-body exception | 422 / 8 |
| Unsupported method/signature dispatches | 121 |

Execution categories are runner classifications, not hand-validated semantic
labels. For example, a returned error can still change state. Exceptions and
errors remain in the denominator, not discarded as bad tests.

| Comparator and runtime | PASS | FAIL | UNKNOWN |
|---|---:|---:|---:|
| Exact typed comparison, different runtime | 1,183 | 223 | 140 |
| Canonical JSON serialization, different runtime | 1,183 | 223 | 140 |
| Exact typed comparison, shared runtime | 1,406 | 0 | 140 |

Runtime-sensitive differences occur in 29 modules. Different times can legitimately
change expiry or other business outcomes, so the 223 differences are **not a
false-rejection score**. UNKNOWN comprises 121 unsupported dispatches (117 missing methods and four
invalid signatures) plus 19 non-JSON observations such as integer object keys; no lossy coercion is used to claim a match. Comparable coverage is
1,406/1,546 (90.94%) among executed observations, not among all possible workloads.

The final local run took 16.459 seconds wall time; a fresh repeat took 17.654
seconds. These are single-machine experiment durations, not tool latency or
throughput benchmarks. No model inference calls or GPU jobs were used. Missing
real-defect labels mean false acceptance, its uncertainty and the original
research effect-size gate cannot be computed. We do not assign a zero error rate
to those missing measurements.

## Revisions and evidence

The first run assumed filename equals class name and ran 39 modules; nine class
adapter errors were retained in the local execution ledger. Static inspection
showed differently named API classes and one facade. After regression tests, the
adapter selected the unique `_load_scenario` + `get_env_state` implementation.
All 70 modules were rerun. A second correction made the serialization baseline
abstain on non-JSON values instead of comparing their lossy string digests.
Independent AI review then found three release-blocking defects: colliding ID
tokens in the separate trace comparator, aliased before-state capture, and
unsupported dispatches incorrectly counted as executed methods and replay PASS.
Six new regressions failed first, then passed after fixes. The pilot was rerun in
full. Pre-review receipts are retained locally and are superseded by these final
numbers. None of these corrections selected favorable cases. The final suite
has 79 tests, with zero skips when pinned grader sources are present.

The final independent repeat matches the full case receipts byte for byte.
[Summary](../results/stage1/final-run/summary.json),
[all module dispositions](../results/stage1/final-run/environments.json),
[case receipts](../results/stage1/final-run/cases.jsonl),
[source pins](../sources/clawforge.json).

The exact comparator plus runtime control already closes the observed replay
gap. This supplies no advantage for a new alignment method. Real Keploy,
RESTler, Schemathesis, independent twin generation, active-probe allocation and
independent real defects were not evaluated. The [research gate remains
NO-GO](research-status.md); the result does not prove that every conformance
research direction is exhausted.

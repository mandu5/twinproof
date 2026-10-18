# TwinProof

**Catch state corruption that a plausible response can hide.**

TwinProof is a dependency-free Python CLI/library for strict JSON-state comparison,
ordered trace comparison with explicit ID creation witnesses, and reproducible
oracle audits. **No SOTA claim.** It checks supplied observations and contracts;
it does not prove program equivalence or infer user intent.

```sh
git clone https://github.com/mandu5/twinproof.git
cd twinproof
python3 -m pip install .
twinproof trace examples/trace/reference.json examples/trace/candidate.json examples/trace/contract.json
# PASS: different generated IDs, consistent references
twinproof trace examples/trace/reference.json examples/trace/corrupt.json examples/trace/contract.json
# FAIL: the later reference points to the wrong object
```

[Trace contract and limits](docs/trace-contract.md) ·
[Runtime pilot](docs/runtime-pilot.md) · [Research status](docs/research-status.md)

## Verified first result — 2026-10-18

We used the reference states to construct **957 audit cases from all 400 samples
in 167 environments** at upstream commit
`efdb7ac4421b42a6b0ca1db69441138426adfbf5`. Both official evaluation scripts show
the same state-check results under the documented offline adapter:

| Input construction | Cases | Wrong verdicts, each original grader | TwinProof | Canonical JSON baseline |
|---|---:|---:|---:|---:|
| Exact reference state | 400 | 57 false rejections | 0 | 0 |
| Reference + unexpected field | 400 | 343 false acceptances | 0 | 0 |
| Deleted object keys replaced with null | 55 | 55 false acceptances | 0 | 0 |
| First boolean replaced with 0 or 1 | 102 | 89 false acceptances | 0 | 0 |

The original grader checks only changed paths. It overlooks extra state, rejects
absent deleted keys, and splits literal dotted keys. Of the 57 rejected correct
states, 55 include deletion and the other two use literal dotted keys. Python
dictionary equality additionally conflates `True` with `1`.

**These are ground-truth-assisted oracle tests, not model predictions.** No model
accuracy, historical ranking, or research superiority has been measured. A simple
canonical JSON baseline ties TwinProof on this suite, so these results do not
establish a new verification algorithm. They concern the pinned released code;
we have not inspected unpublished author evaluation runs.

[Full results](results/2026-10-18/summary.json) ·
[Case-level evidence](results/2026-10-18/cases.jsonl) ·
[Research status](docs/research-status.md)

## Runtime control experiment

From an independently sourced ClawForge snapshot, the pilot executed **48 of 70
modules**, producing **1,546 attempted observations / 4,275 executed method calls**. There were 223
differences with different clock/RNG inputs. With shared runtime inputs, all
1,406 comparable observations matched; 140 were UNKNOWN. Seven modules were
statically excluded and 15 lacked a supported initial-state name mapping.

These are same-implementation positive controls, not AI-generated twin comparisons
or real-defect detection scores. The experiment shows no advantage over ordinary
controlled replay. The current research promotion gate is **NO-GO**; the software
remains an auditable utility. [Method, exclusions and receipts](docs/runtime-pilot.md).

## Run locally

Requires Python 3.11+; `curl` is used only by the download script. The package
runtime has no third-party dependencies. From this repository:

```sh
python3 scripts/fetch_sources.py
PYTHONPATH=src python3 -m twinproof audit \
  --snapshot .cache/envsimbench --output .cache/my-audit
```

The output directory must be new. Downloaded files are verified against the
bundled commit and SHA-256 pins and remain ignored by git. Audit execution is
offline: it runs the original graders' selected Python functions with a fixed
response at the API boundary. It does not execute dataset environment code.
SFT's optional `json_repair` path is disabled, matching its no-dependency fallback;
only state correctness is measured, not feedback matching. The adapter is for
the two reviewed source hashes, **not a sandbox for arbitrary source code**.

To compare your own states:

```sh
PYTHONPATH=src python3 -m twinproof compare expected.json observed.json
```

The result is JSON with `PASS`, `FAIL` or `UNKNOWN`, plus JSON Pointer mismatch
paths. Exit codes are 0, 1 and 2 respectively. No timestamps, identifiers or
other fields are silently ignored. Missing and null differ, array order matters,
booleans differ from numbers, and finite numbers 1 and 1.0 compare equally.
The CLI preserves decimal numeric tokens exactly rather than rounding through
binary floats. Its mismatch diagnostics also retain that numeric precision.
Invalid JSON, duplicate keys, nonfinite values and nesting beyond 128 produce
UNKNOWN. A reference state is required; this is not an oracle for intent.

Development verification (pytest must be installed):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

Pinned-grader integration tests skip if sources have not been fetched. CI fetches
them and checks the published counts. A missing download is a skipped integration
check, not a successful reproduction.

## Provenance and scope

Original benchmark: [paper](https://arxiv.org/abs/2605.07247),
[repository](https://github.com/cookieApril/EnvSimBench).
Source pins: [sources.json](src/twinproof/sources.json).
No upstream source code, dataset records or model weights are distributed here.
Redistribution rights for those materials have not been established. Local
reproduction and publication of our code are separate from external adoption.

The chosen research question is aligned with trustworthy agent reward and
verification signals. The commercial hypothesis is a conformance gate for teams
building environment twins; no customer interviews or willingness-to-pay evidence
exist yet. GitHub popularity is not a research metric or demonstrated demand.

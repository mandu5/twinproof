# Official state-alias reproduction

This experiment preserves the exploratory October 19, 2026 oracle checks and their negative planner result. It includes our runner and historical method code, derived action histories, source metadata, and receipts. Download helpers retrieve the third-party candidates and official games locally, verify pinned SHA256 hashes, and stop on upstream changes. Those downloaded sources are excluded by `.gitignore`; their separate redistribution terms remain unverified.

## Findings

Both aliases were verified by replay from the official RESET state with `arc-agi==0.9.9` and `arcengine==0.9.3`. Every supplied observation along each accepted prefix matched all 4,096 cells after reconstructing omitted actions. The saved histories are legal histories consistent with the observations; uniqueness of the authors' omitted actions is not claimed. Display `level_marks` were not treated as authoritative boundaries.

- **dc22:** 943 retained actions replayed, with five omitted completion actions and one RESET. Five requested `ACTION5` actions executed as `ACTION1`, following the released Twin adapter. Identical observation/action pairs 743/749, 927/931, and 938/941 have respectively 8, 8, and 13 different official successor cells. Both successors of each pair match the recording.
- **sp80:** 472 retained actions replayed, with five omitted `ACTION5` completions and seven RESETs. Pair 383/470 has one differing official successor cell; both successors match the recording.
- **Return loop:** from dc22 frame 743, six actions return to the identical grid, but the following `ACTION6:52,25` produces an eight-cell difference. Its full reset prefix, loop, and suffix are preserved in `dc22-reset-prefix-to-frame743.json`.
- **Negative planner result:** grid, full-state, and refined keys all find `ACTION2`, `ACTION6:52,25`, `ACTION1` to reach recorded frame 750. Each uses 17 expansions and 68 model calls; all three plans reach the exact official target. Grid records 34 unique states versus 36 for full/refined. Full and refined keys are identical here because refinement retains both mutable fields. This target demonstrates no planning or cost advantage.
- **Corrected witness:** the candidate-only frame 741 selection is not a true no-op: the official engine changes a footer pixel. Use the verified 743-to-749 return loop instead.

This is an exposed constructed target task, not a held-out experiment, original-agent reproduction, SOTA result, or game win. Official plan validation remains `NOT_FINISHED`, with five levels completed.

## Historical method boundary

`method/src/twinproof/` is the historical implementation used for these results. Its adapter predates the live core's hardening: it accepts sets, while the live adapter rejects sets and performs additional binding checks. It is preserved for reproduction and must not be presented as the latest live adapter or a security sandbox.

The bundled `world_model.py` is byte-identical to the executed historical file. The bundled `world_audit.py` contains the unchanged `bounded_search` function and necessary imports, omitting unrelated audit functions. Its whole-file hash therefore differs from the original receipt. `method-provenance.json` preserves the original, bundled, and function hashes. Runners use this bundled method unless `TWINPROOF_REPO` is explicitly set.

## Reproduce from a clean checkout

From the repository root, run the following with `uv`, `curl`, and Python 3.12 available. The reference run used Python 3.12.2. Dependencies are installed only in the experiment's virtual environment. Downloads require network access; oracle replay is offline and blocks socket connections after imports. There are no model API calls, GPU operations, or online game actions.

```sh
cd experiments/official-state-aliases
unset TWINPROOF_REPO
uv venv --python python3.12 oracle-venv
UV_CACHE_DIR="$PWD/uv-cache" uv pip install --python oracle-venv/bin/python -r oracle-requirements.lock.txt
oracle-venv/bin/python fetch_candidates.py
oracle-venv/bin/python fetch_official_references.py
MPLCONFIGDIR="$PWD/mpl-cache" oracle-venv/bin/python oracle_check.py dc22
MPLCONFIGDIR="$PWD/mpl-cache" oracle-venv/bin/python oracle_check.py sp80
oracle-venv/bin/python bounded_plan_arm.py grid
oracle-venv/bin/python bounded_plan_arm.py full
oracle-venv/bin/python bounded_plan_arm.py refined
MPLCONFIGDIR="$PWD/mpl-cache" oracle-venv/bin/python validate_plans.py
```

The download helper obtains an anonymous key only for official source GET requests; it never prints or saves the key. `oracle_check.py` has a 110-second CPU cap. Each search arm has a 90-second CPU cap, depth limit 7, and expansion limit 1,000. These are inspected-code research runners, not security sandboxes.

Fresh outputs are ignored files beside the runners. They do not replace `receipts/`. To repeat only the selected plan validation after downloading inputs, run the three `bounded_plan_arm.py` commands followed by `validate_plans.py`; the saved reset prefix reconstructs the official root without rerunning bridge discovery.

## Receipts, provenance, and cost scope

| Files | Evidence |
|---|---|
| `receipts/dc22-oracle-replay-result.json` | Final reset replay, effective actions, fallback mappings, accepted bridges; 1,143 oracle calls including discovery and checks |
| `receipts/sp80-oracle-replay-result.json` | Corresponding successful replay; 1,183 oracle calls |
| `receipts/dc22-plan-{grid,full,refined}.json` | Historical method/source hashes and search outcomes; each arm also uses 743 teacher-forced prefix calls |
| `receipts/dc22-plan-official-validation.json` | 750 oracle calls reconstruct the root; 17 branch calls validate the three plans and return loop |
| `receipts/oracle-attempt-ledger.json`, `receipts/*-v1.json`, `receipts/*-v2.json` | Preserved failed or misaligned attempts and an interrupted attempt with unknown cost |
| `receipts/dc22-oracle-level-result.json` | Intermediate conditional level initialization, superseded by full RESET verification |
| `official-source-pins.json`, `runtime-pins.json`, `oracle-requirements.lock.txt` | Source hashes and interpreter, SDK, engine, dependency versions |
| `immutable-receipt-sha256.json`, `method-provenance.json` | Original receipt and method checksums |
| `provenance/` | Original package manifest/README and integration validation |

**Aggregate exploration calls are UNKNOWN.** Earlier setup probes, entry scans, and one interrupted attempt were not fully counted. The final replay counts are not the total project cost. The selected integration rerun has its own separately recorded cost.

The integration rerun reproduced all three search outcomes and exact official target frames using the bundled historical method and verified cached inputs. It used 2,433 model calls (2,229 prefix and 204 search) and 767 oracle calls (750 prefix and 17 branch). Fresh receipts are in `provenance/integration-rerun/`; `provenance/integration-validation.json` records checks of all 12 original receipts and 31 dependency versions. Clean-checkout commands were inspected, but a new installation and network download were not repeated during integration.

The SDK's dynamically loaded game class cannot be pickled portably. Saved action histories and pinned sources reconstruct the engine states. The aliases support further tests of planner state-key sufficiency; they do not establish a method advantage. Snapshot completeness and fork independence already appear in [PCS](https://arxiv.org/abs/2607.21686), and state abstraction/refinement has substantial prior art.

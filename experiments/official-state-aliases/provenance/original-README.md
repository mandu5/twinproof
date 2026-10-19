# Official-oracle proof package — exploratory, 2026-10-19

This package contains only our runner/method code, derived action histories, metadata, and receipts. It does not redistribute the Twin-generated Python sources or official game sources. Download helpers verify their pinned SHA256 hashes and stop if upstream changes. Redistribution terms for those separately served sources remain unverified.

## Result

Both observation aliases were verified by replay from the official RESET state using arc-agi 0.9.9 and arcengine 0.9.3. Every supplied observation along each accepted prefix matched all 4096 cells after reconstructing omitted actions.

The saved history is a legal history consistent with the released observations; uniqueness of the authors' omitted actions is not claimed. Display `level_marks` were not trusted as actual level boundaries. Every accepted bridge was checked against the official engine's full resulting frame.

- **dc22:** 943 retained actions replayed, five omitted completion actions and one omitted RESET reconstructed. Five requested ACTION5 actions were executed as ACTION1, matching the released Twin adapter (`twin/cliagent/policy.py`, pinned commit, lines433–435). Recorded same-frame/action pairs743/749,927/931,938/941 have8/8/13 differing official successor cells; both members of every pair match their recorded successors.
- **sp80:** 472 retained actions replayed, five omitted ACTION5 completions and seven omitted RESETs reconstructed. The same-frame/ACTION4 pair383/470 has one differing official successor cell, with both successors matching the recording.
- **Real return loop:** from dc22 frame743, six actions return to exactly the same grid but change the successor of ACTION6:52,25 by eight cells. The full reset prefix, loop, and suffix are preserved in `dc22-reset-prefix-to-frame743.json`.
- **Negative planner result:** grid/full/refined keys all found the same three-action plan to recorded frame750: ACTION2, ACTION6:52,25, ACTION1. Each required17expansions and68model calls. All three plans reached the exact official target frame. Grid used34unique states; full/refined used36. Full/refined have identical keys on this model because the proposed refined field set contains both mutable fields. This target shows no planning or cost advantage.
- **Corrected candidate witness:** frame741's proposed selection no-op is not a no-op in the official engine: a footer pixel changes. The earlier candidate-only witness is not evidence for that specific real alias. Use the verified743→749 return loop.

This is an exposed constructed target task, not a held-out experiment, original-agent reproduction, new SOTA, or a game win. Official validation remains NOT_FINISHED with five levels completed.

## Reproduce

Run from this directory with Python3.12 available. All installations and downloaded sources stay in this directory. No inference API, GPU, online game-action endpoint, or paid operation is used. `anonkey` is obtained only for read-only official source downloads and is never printed or saved.

```sh
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

`oracle_check.py` caps its process at110CPU seconds. Each search arm caps CPU at90seconds, depth7, and1000expansions. These scripts execute inspected third-party code and are not security sandboxes. Official engine replay blocks socket connections after imports. The method implementation is included under `method/src/twinproof`; `TWINPROOF_REPO` can explicitly select another checkout, whose file hashes are recorded. `world_model.py` matches the executed file hash exactly. The bundled `world_audit.py` extracts the unchanged `bounded_search` function and omits unrelated audit functions, so its whole-file hash differs from the original receipt; `method-provenance.json` records this distinction and the function hash.

Fresh runs write results beside the runners. They do not overwrite the frozen receipts in `receipts/`. `immutable-receipt-sha256.json` records original receipt checksums.

## Evidence and cost scope

- `receipts/dc22-oracle-replay-result.json`: final full-reset alignment, exact effective history, fallback mappings, accepted missing actions,1143offline oracle calls including reconstruction search and witness checks.
- `receipts/sp80-oracle-replay-result.json`: corresponding final successful replay,1183offline oracle calls.
- `receipts/dc22-plan-{grid,full,refined}.json`: frozen method/source hashes and per-arm search results. Each arm first made743teacher-forced model calls to reconstruct its root context, in addition to68search calls.
- `receipts/dc22-plan-official-validation.json`: independent reconstruction of the official root using750oracle calls, plus17branch-validation calls. Confirms every returned plan and the return loop.
- `receipts/oracle-attempt-ledger.json`: earlier failed/misaligned attempts and one interrupted attempt. **Aggregate exploration calls are UNKNOWN**: setup probes, entry scans, and the interrupted attempt were not fully counted.1143+1183 is the final replay cost, not the total project cost.
- `receipts/*-v1.json`, `receipts/*-v2.json`: preserved failures. `dc22-oracle-level-result.json` is an intermediate conditional set-level replay, superseded by full-reset verification.
- `official-source-pins.json`, `runtime-pins.json`, `oracle-requirements.lock.txt`: source, interpreter, SDK, engine, and dependency versions.
- `receipts/twin-action-adapter-receipt.json`: primary URL and hash for the unavailable-action fallback rule.

The SDK's dynamically loaded game class could not be pickled portably. Reconstruct the engine states with the saved effective action histories and pinned sources; do not treat missing pickle output as missing reachability evidence.

The true aliases justify testing planner state-key sufficiency. They do not establish a new method's advantage. Snapshot completeness and fork independence are already covered by PCS (https://arxiv.org/abs/2607.21686), and state abstraction/refinement has extensive prior art.

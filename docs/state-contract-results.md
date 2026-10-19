# Executable-model state audit — 2026-10-19

**State failures are reproduced. Automatic key refinement has not demonstrated a planning advantage. No SOTA or TCPR-superiority claim.**

This study follows the [prospective protocol](successor-state-contract.md). It audits released generated Python models, reproduces selected observations in official engines, and tests a real released planner key. The three endpoints are separate: a trace conflict, a mutable-model-state conflict, and a harmful planner merge are not interchangeable.

## Final audited corpus

The source-bound rerun is [`corpus-03`](../results/successor/corpus-03/summary.json), with execution commit `dda03a0` from the private research checkout and full file hashes in its configuration. The published adapter/runner files have those same hashes; the private commit is not required for reproduction. All 25 published families remain in the denominator.

| Endpoint | Result |
|---|---:|
| Runtime audit completed | 9 / 25 families |
| Unsupported by the inspected Python subset | 15 / 25 |
| Generated model raised an exception | 1 / 25 |
| Counted model calls, including the error's partial cost | 14,760 |
| Branch comparisons | 1,422 |
| Shared-state / isolated-state disagreements with the isolated control | 6 / 0 |
| Fresh-prefix replay checks / disagreements | 18 / 0 |
| Counterfactual key witnesses / remaining witnessed collisions after refinement | 4 / 0 |

All four counterfactual key witnesses are from **dc22**. They are not four independent games. Seven released trace families have repeated image/action pairs with different next images, but only dc22 and sp80 exhibit the corresponding model-state witness in the supported audit. The generated g50t model raises `IndexError` during a branch probe after 1,061 calls; its failure input and phase ledger are retained.

The stricter adapter rejects sets/frozensets in global snapshot data: Python deepcopy and pickle can change their observable iteration order. This removes m0r0 and vc33 from the previously completed set. Historical `corpus-02` had 11 completed families and 16,959 calls; those figures describe its older adapter, **not** the corrected result. The prospective G0 threshold of at least ten runnable families is consequently **unmet**. We did not lower it.

Snapshot checks validate finite inspected cases. They do not prove completeness for arbitrary Python, sandbox hostile code, or prove future behavioral equivalence. The conservative exclusions, source inspection, CPU limits and macOS process restrictions are documented in the protocol.

## Independent official-engine witnesses

[`experiments/official-state-aliases`](../experiments/official-state-aliases/README.md) contains our runners, pinned downloaders, derived action histories and original receipts. Third-party generated models and official game sources must be downloaded separately.

From official RESET states, the accepted reconstruction matches every full frame along 943 retained dc22 actions and 472 retained sp80 actions. The released displays omit some level-completion actions and RESETs. The reconstruction also implements the released Twin adapter's unavailable-action fallback. It provides a legal consistent history, not proof that omitted history is unique.

Three dc22 same-image/action pairs have different official successors (8, 8 and 13 cells). A sp80 pair differs in one successor cell. A six-action dc22 return loop reaches the same 4,096-cell observation but changes the effect of a common next action. This confirms a real observation alias.

An earlier candidate-only selection “no-op” is **not** a real no-op: the official footer changes one pixel. Its negative receipt is retained. Both positive and negative validation matter.

For a constructed target at recorded dc22 frame 750, observation/full/refined keys all find the same three-action route, taking 17 expansions and 68 search model calls per arm. Each route reaches the exact target in the official engine. This is a target-reaching check, not a game win or an original-agent score. The refined key includes both mutable globals and is identical to the full key on this model.

The two final successful oracle replays consume 1,143 and 1,183 offline engine calls. Plan validation separately uses a 750-call prefix and 17 branch calls. **Total exploratory oracle cost is UNKNOWN** because earlier setup scans and an interrupted attempt were not completely counted. The successful-run counts must not be presented as total acquisition cost.

## Actual THEA planner: correctness counterexample, negative utility result

[`experiments/thea-state-keys`](../experiments/thea-state-keys/README.md) pins the released THEA bp35 engine and original `_key`/`door_clicks` function slices. The whole archived planner has a non-Python public-redaction line; we do not claim to execute the unmodified whole file. THEA's own [lessons](https://github.com/bruno353/thea/blob/b7f0ce0fa391f27b3134f875c964f14b883cfb2c/LESSONS.md#L83) already identify the omitted-door-state key defect.

Two four-click histories reachable in the released model have the same original key and differ in 173 grid cells. A common three-action continuation yields RUNNING versus GAME_OVER. Archived attempt 4 replays with 36/36 matching frames. Alternative branches in this package are learned-model results, not independent official-engine validation.

A greedy three-coordinate repair separates all eight development witnesses. On the first held-out root it misses the **only found physical continuation counterexample**. A more conservative 298-coordinate union was frozen from development before that result. It is not a repair tuned after seeing the held-out failure.

The initial 500-expansion breadth-first search hits its CPU bound after 18 completed, budget-failed arm-results. A dated amendment introduces a common goal-directed order, with 150 expansions and a four-action horizon. Twenty distinct roots from one recorded trajectory are used; these are correlated states from one game.

| Key | Targets reached | Search + route-replay engine calls |
|---|---:|---:|
| Original released key | 20 / 20 | 4,752 |
| Three-coordinate refinement | 20 / 20 | 4,815 |
| 298-coordinate union | 20 / 20 | 4,836 |
| Full grid | 20 / 20 | 4,910 |

All 80 returned paths replay to their exact targets. The shared heuristic is not admissible, so no shortest-path claim is made. The acquisition phase takes another 16,335 calls; charging it removes any apparent small online advantage over full grid. The held-out collision check separately takes 66,733 calls. The interrupted first search's unfinished call total is UNKNOWN. The original key is cheapest on the final endpoint. The saved upstream “winning” plan fails under the pinned released engine, and is not a successful-level endpoint here.

## Research decision

G0 fails under the corrected adapter; G3 fails because the proposed method has no demonstrated advantage over the strongest applicable baseline. G1 and the sampled G2 checks have useful evidence. These results support a reusable diagnostic artifact and concrete failure reproductions. They do **not** support promoting automatic key refinement above TCPR or claiming a new general state-abstraction algorithm.

[Persistent Computational State](https://arxiv.org/abs/2607.21686), [Dual-Frontier](https://arxiv.org/abs/2609.26293) and [distinguishing-continuation analyses](https://arxiv.org/abs/2406.03689) substantially constrain novelty. Snapshot isolation, suffix witnesses and greedy separating sets are prior techniques. Better packaging cannot convert the negative utility result into a scientific improvement.

## Reproduce and inspect

```sh
python3 scripts/fetch_world_models.py
python3 scripts/run_world_audit.py --output .cache/my-world-audit
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

The output directory must be new. The two experiment packages have separate pinned dependency instructions and immutable historical receipts. They require no inference API or GPU. Full test verification after the core review fixes: **149 passed** on Python 3.11.9; additional platform/independent review results are recorded separately when actually run.

The historical development, error-accounting and corrected corpus runs remain in `results/successor/`. They are repeated audits of the same corpus, not additional independent families. Expected and actual input hashes are separated on failures; missing or malformed inputs retain an ERROR row without fabricated trace counts.

## Independent review and reproduction

A fresh reviewer reproduced all four originally reported core defects before checking the fixes, reran the 149-test suite, and reconstructed the corrected corpus summary and every recorded call phase. No Critical or Important findings remained in the reviewed implementation and scoped claims.

The reviewer verified 99 pinned THEA input files and independently replayed both fixed witnesses and all 80 target rows under a process denying network and writes. All nontiming fields match; this rerun used 19,589 engine calls including setup. It called the portable runtime/worker functions against cached inputs, not the package downloader or launcher.

The official package was separately copied and rerun: all three 17-expansion/68-call searches and their exact official targets match, with the eight-cell return-loop distinction preserved. This selected integration rerun adds 2,433 model calls and 767 oracle calls. It used cached pinned dependencies/sources; it does not count as a new independent game or new method outcome.

Novelty, SOTA, TCPR superiority, universal snapshot correctness and third-party redistribution licenses were not certified by the code review. A separate [fold-context mechanism scout](../experiments/fold-context-scout/README.md) explores a different question and is explicitly not a successful replacement result.

Publication note: `results/successor/public-projections.json` maps the one path-redacted historical failure receipt to its original hash. All other corpus JSON files retain their original bytes. Console logs and downloaded third-party sources are excluded. THEA maintains its separate projection index.

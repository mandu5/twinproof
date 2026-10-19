This package reproduces a concrete state-key collision in a released THEA bp35
world model, the frozen three-coordinate repair's heldout failure, and the final
20-target comparison. The bug is reproduced; a planner benefit from the learned
keys has **not** been demonstrated.

The upstream main planner contains an invalid bare annotation at line 10. This
package does **not** execute or validate that whole planner. It extracts the exact
hash-checked `_key` (lines 136–154) and `door_clicks` (46–107) functions, and imports
the unchanged released engine and state I/O. All four search arms use that same
engine, action generator, branch states, and bounded search algorithm.

From this directory, using Python 3.11 or 3.12 on macOS or Linux:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple -r requirements.txt
.venv/bin/python verify_package.py
.venv/bin/python fetch_inputs.py --cache .cache/inputs
.venv/bin/python experiment.py witnesses --inputs .cache/inputs --output .cache/witness-replay.json
```

The copied-package check used CPython 3.11 on macOS arm64. Linux and Python 3.12
have not been independently exercised here. NumPy 1.26.4 and SciPy 1.16.2 match
the original execution host; the clean-venv check exposed the SciPy dependency,
and its initial import failure is retained in the packaging verification receipts.

The downloader verifies the pinned 27,589,165-byte archive before extracting only
96 regular files (282,192 bytes), then fetches three separately pinned helper
files. It never executes downloaded code. Full file hashes, source URLs, and
function-slice hashes are in `pins.json`; no third-party source or frames are
vendored. A local copy of the exact archive can be supplied with `--archive`.
See `NOTICE.md` for the input licensing boundary.

The worker uses the active virtual environment's Python, a fresh subprocess,
isolated Python mode, a minimal environment, a 75-second CPU cap and a 90-second
wall timeout per shard. It denies network/process operations and writes with
Python audit guards; macOS additionally uses `sandbox-exec` to deny network and
file writes. The audit hook alone is not a general adversarial-code sandbox.
No credentials, model service, paid API, GPU, or live game service is needed.
Only the downloader and dependency installation need network access.

The fixed replay makes 36 engine calls. It reconstructs both sides of each witness
from its declared initial frame and action history, checks the complete canonical
state hashes against the frozen snapshots, checks the exact original key, and
executes the common distinguishing suffix:

| Fixed witness | Original key | Three-cell repair | Shared-suffix consequence |
| --- | --- | --- | --- |
| Development witness 06 | Collides | Separates | `RUNNING` versus `GAME_OVER` |
| Holdout A witness 05 | Collides | Still collides | Avatar column 25 versus 31 |

The coordinates `(169,13), (163,7), (163,19)` and the separate 298-cell union
were frozen from development witnesses before Holdout A. The three-cell key
separated 10 of 12 heldout grid collisions but missed the only physical
continuation mismatch found there. These are model-reachable branches. They are
not independently executed live-game trajectories or independently labeled
ground-truth dynamics. Replaying the released attempt 4 matches all 36 saved
frames, which supports that trajectory only.

To rerun the existing final comparison, without selecting new cases:

```sh
for shard in 0 1 2 3; do
  .venv/bin/python experiment.py targets --inputs .cache/inputs --shard "$shard" --output ".cache/targets-$shard.json"
done
.venv/bin/python compare_targets.py .cache/targets-0.json .cache/targets-1.json .cache/targets-2.json .cache/targets-3.json
```

Every shard checks the same pinned inputs and does 69 setup engine calls. The
20 targets are deterministic distinct roots from attempt 4 prefixes 8–27, each
target four recorded actions later. The goal is exact full current map plus
avatar position, facing and gravity. The search receives the target state, not
the recorded solution route or frozen output routes. The four arms use the same
best-first priority (grid mismatch count, then avatar Manhattan distance), a
four-action horizon, 150-expansion budget, and shorter-depth reopening. Every
returned route is replayed. This heuristic does not certify shortestness.

Frozen final results:

| Key | Reached targets | Search + route-replay calls | Expansions | Sum of unique keys |
| --- | ---: | ---: | ---: | ---: |
| Original | 20/20 | 4,752 | 209 | 3,577 |
| Three cells | 20/20 | 4,815 | 212 | 3,648 |
| Union of 298 cells | 20/20 | 4,836 | 213 | 3,687 |
| Full current grid + original key | 20/20 | 4,910 | 216 | 3,786 |

All 80 routes had length four. Total setup/search/replay cost across four shards
was 19,589 engine calls, with original subprocess wall time totaling 6.53 seconds.
These are 20 correlated targets from one game, not 20 independent environments.
Unique-key counts are not measured total memory. Full-grid is a conservative
baseline for this no-undo action pool; it is not a proved sufficient state for
arbitrary histories or all possible actions. A literal state key containing undo
history was included in the earlier failed BFS experiment, and was omitted from
the prospectively amended no-undo comparison with that reason recorded.

`receipts/original/` contains 19 historical receipts: nine unchanged files and
ten public projections with personal absolute paths replaced by placeholders.
Private originals remain byte-for-byte in the original local cache. Both original
and projection hashes, the path-only redactions, and the chronology are indexed
in `receipts/provenance.json`:

1. Initial launch failure and corrected input replay.
2. Development acquisition: 8 collisions, 16,335 engine calls; both feature sets frozen.
3. Holdout A: 12 collisions, 66,733 calls; physical three-cell false negative retained.
4. Initial 500-expansion BFS: 18 completed arms all exhausted budget; the shard
   hit its CPU cap. Total unfinished-shard engine calls remain **UNKNOWN**.
5. Prospective goal-directed amendment v1 and its first-shard output.
6. Prospective v2 correction for shorter-depth reopening, followed by the final
   four shards. v1 output is retained and excluded from the v2 aggregate.
7. Fixed saved-witness replay, followed by this portability-only packaging check.

The released `level_8_winning_plan.json` also reaches `GAME_OVER` at action 25
under this engine; its failure is preserved. No repaired key is claimed SOTA,
and there is no claim of improved game wins, shortest paths, or planner utility.

The published historical receipts contain placeholders for private machine paths
and retain old runner hashes. Those hashes identify the original code, not the
portable code; neither old paths nor old commands are runtime dependencies. Portable runner
hashes are recorded in new execution receipts and `manifest.json`; portability
changes do not retroactively authenticate the old results with new code. Large
duplicate discovery logs and raw snapshot grids are excluded with original
hashes retained. `derived/witnesses.json` contains compact action histories and
canonical state hashes, so the fixed witnesses can be reconstructed from the
downloaded inputs. This minimum package replays those witnesses and final targets;
it does not rerun or re-estimate the whole original collision-discovery corpus.

The independent copied-package witness check is recorded under `verification/`.
Only fixed witnesses were replayed during packaging; final target outcomes above
are the unchanged original scientific results. `verify_package.py` checks the
file manifest and all published receipt hashes without network access. Historical
hash references inside projections continue to identify private raw files; the
provenance index maps those hashes to the published projection hashes.

# Stage 2: real released twins, no demonstrated search advantage

Status: research active; SOTA objective unmet. The development pilot completed
on two stateful CLI families and four independently generated implementations.
It reproduced concrete behavioral differences in both GPT-5.4/mini-SWE twins.
The candidate state-cover method was more expensive than ordinary controls on
these pairs. That result rejects an advantage claim for this implementation.

## Frozen execution and complete accounting

- Public experiment commit: `d73c5b5a0473ee30332ea97a4e6457d15e09881a`.
- [Linux execution, attempt 1](https://github.com/mandu5/twinproof/actions/runs/39112134988/attempts/1).
- [Independent CI checks](https://github.com/mandu5/twinproof/actions/runs/39112134930).
- [Frozen protocol](stage2-protocol.md), [source pins](../sources/programbench-pilot.json).
- Complete calibration evidence: [summary](../results/stage2/calibration/summary.json),
  [120 case receipts](../results/stage2/calibration/receipts.jsonl),
  [hash-verified raw transcripts](../results/stage2/calibration/raw.json.gz).

Attempt 1 ran **17,586 application invocations + 1,690 Git setup invocations =
19,276 measured top-level harness invocations**. Child processes internal to a
program are not counted as separate oracle interactions. Environment probes and container
build/install work are outside that interaction metric, and remain in the CI log.
Every selected program loaded. No timeout or execution error was silently excluded.
All 120 cases and their compressed raw transcripts were recovered and SHA-256 checked.

The 120 cases are 2 families × (2 generated twins + 1 reference control) ×
4 methods × 5 seeds. They are not 120 independent programs. The 40 reference-control
cases found no mismatch within their budgets; this is not a population false-positive
estimate or an equivalence proof. All 40 Gongent cases exhausted the scoped search
without a witness. That does not certify Gongent's whole program.

## Directly inspected witnesses

1. **zoxide, mini-SWE twin:** `remove <existing-directory-not-in-database>` returns
   exit 1 in the reference and exit 0 in the twin, from a fresh database, on both
   confirmation replays. The [pinned upstream remove implementation](https://github.com/ajeetdsouza/zoxide/blob/67ca1bc9592854dd4957b8b02f16292638475659/src/cmd/remove.rs)
   explicitly reports an absent database path. This affects a calling shell's
   success/failure decision.
2. **dstask, mini-SWE twin:** after adding `alpha +work project:red`, the sequence
   `show-resolved; modify 1 +focus P1` changes the reference task's priority to P1
   and adds the focus tag. The twin prints usage, returns success and leaves P2/work
   unchanged, twice. Both implementations report exit 0, so exit-only comparison
   misses the functional failure. See the AALpy seed-4 receipt and raw transcript.
3. Empty-database `modify`, `done` and `stop` also differ in exit status. These
   are repeated instances of the same interface mismatch, not separate independent
   applications or evidence of general detection accuracy.

Other projected differences need weaker interpretation. Some zoxide witnesses
concern path ranking with clock-sensitive ties; two stable repetitions do not
establish universal ranking incorrectness. An AALpy witness was UNKNOWN because
the candidate order changed across confirmations. Some dstask witnesses are an
extra blank line in an empty tag listing: a strict observable difference, but not
automatically a meaningful task-management defect. These remain in the receipts
and are not counted as independent semantic bugs.

## Method comparison

Median **total application invocations**, including discovery and two paired
confirmations, across the five declared seed labels:

| Generated twin | Shortest first | Random prefixes | AALpy random words | Candidate state cover |
| --- | ---: | ---: | ---: | ---: |
| zoxide / GPT-5.4 mini-SWE | 24 | 32 | 24 | 94 |
| dstask / GPT-5.4 mini-SWE | 56 | 32 | 24 | 152 |

The zoxide AALpy group has four confirmed differences and one UNKNOWN; its median
includes all five trials, not just successful ones. All other cells have five
projected confirmations. Different methods can find different witness classes,
so this is time-to-first-projected-difference, not same-bug detection efficiency.
Deterministic shortest-first and state-cover results repeated under five seed
labels do not provide five independent samples. No significance test is reported.

On zoxide/mini-SWE, state cover used a median 16 reference invocations versus 12
for shortest-first; on dstask it used 44 versus 28. Candidate screening therefore
did not buy a reference-call saving on the pairs where differences were found.
The complete tables include Git/setup costs and the budget-exhausted pairs.

## Claim boundary and next research gate

The old same-implementation limitation is resolved for this pilot: the generated
programs are real independent released artifacts, and functional state differences
are observable. The algorithmic advantage limitation is not resolved. These are
two development families with hand-declared CLI projections and four twins.
The full RALib, RESTler and Schemathesis pipelines have not been compared.

The original 30-family/200-transition, independent-label, held-out and strongest-
baseline gates remain in force. The next data audit must establish whether released
stateful families actually support that scope; it cannot manufacture families out
of flags, random seeds or synthetic mutations. Until a new hypothesis beats the
existing controls on genuinely independent evidence, TwinProof stays an active
exploratory research track, not a SOTA achievement or established business.

## Final corrected execution and reproduction

[Final Linux run](https://github.com/mandu5/twinproof/actions/runs/39113030027)
used public commit `ab24baac89f1936e45a8cffc9c7c7ea7e44e053f`, with all five
[review corrections](stage2-review.md). Its 120 schema-2 receipts include the
initial discovery projection and preserve observer membership. The separate
[Python 3.11/3.13 CI](https://github.com/mandu5/twinproof/actions/runs/39113029964)
passed **118 tests on each version, without skips**.

| Execution | Schema | Projected confirmations | Bounded no difference | UNKNOWN | Application / Git setup calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Calibration attempt 1 | 1 | 39 | 80 | 1 | 17,586 / 1,690 |
| Same-commit attempt 2 | 1 | 39 | 80 | 1 | 17,594 / 1,690 |
| Corrected final run | 2 | 40 | 80 | 0 | 17,586 / 1,690 |

The final extra confirmation is the clock-sensitive zoxide ranking witness that
was UNKNOWN during calibration. This variation reinforces the limited
interpretation of ranking differences. It is not an extra independently validated
functional defect. The two directly inspected exit/state examples reproduce in
the final run. The search-method medians and negative advantage conclusion stay
the same. In the final run all five zoxide AALpy cases confirmed their scoped
projection, unlike the calibration group in the earlier table description.

All **360** case transcripts across the three executions were recovered and
hash-verified: **52,766 application + 5,070 Git setup = 57,836** top-level harness
invocations. These are repeated measurements of four generated programs, not
360 independent twins. There were no recorded infrastructure/parse failures in
the final run. The final [summary](../results/stage2/final-run/summary.json),
[case receipts](../results/stage2/final-run/receipts.jsonl), and
[raw transcripts](../results/stage2/final-run/raw.json.gz) are preserved alongside
both calibrations. Repeating our CI is reproducibility evidence, not independent
third-party replication.

The [held-out audit](stage2-heldout-audit.md) found 11 additional statically
suitable stateful families. None has been run. The 30-family gate remains unmet.
The user's research objective remains active; this artifact is not its completion.

## Decision on the tested mechanism

Retire `candidate_state_cover` as the proposed research contribution, while
preserving it as a reproducible historical baseline. It spends up to 64 calls
on candidate-only state novelty before paired search and receives no discrepancy
signal during screening. Its final-state signature does not establish equal
future behavior, and distinct concrete values can increase apparent novelty
without adding a useful behavioral distinction. The observed cost disadvantage
and absence of reference-call savings do not justify consuming unseen outcomes
on a revised ordering or fingerprint.

A separate read-only AI method review reached the same recommendation; it did
not perform independent experimental replication. Keep held-out outcomes unseen
until a distinct mechanism and expected benefit are stated in advance. A next
study must include a released learning/conformance method where applicable,
such as RALib SLλ. The AALpy random-word oracle used here performs no automata
learning and cannot substitute for that comparison. All learning, screening,
reset, execution and confirmation costs must count. The project's SOTA objective
remains unmet; this is a decision to reject a tested mechanism, not a claim that
all candidate-guided search is impossible.

## Reproduce

On a Linux/amd64 machine with Docker, curl, Python 3.11+ and this repository:

```sh
python -m pip install .
python scripts/run_cli_pilot.py --family zoxide > zoxide.log
python scripts/run_cli_pilot.py --family dstask > dstask.log
cat zoxide.log dstask.log > pilot.log
python scripts/read_cli_receipts.py pilot.log --expected-cases 120 --output results/local-reproduction
```

The runner downloads pinned bytes and only then executes them inside its container.
The host does not run third-party build scripts. `--seeds 4` provides a smaller
development rerun; it changes the expected case count and is not the full protocol.

# Released CLI twins: frozen development pilot

This protocol is frozen before the first Linux execution of any selected program.
It does not replace the original research gate or establish a SOTA benchmark.

## Data and access

Two stateful CLI families, zoxide and dstask, each have two publicly released
independent Python reimplementations. Source pins, generation methods, registration
status, aggregate-outcome exposure and reference provenance are in
`sources/programbench-pilot.json`. No per-task evaluation, test cache, hidden test,
trajectory or submitted test body was read. Archive metadata and the selected
source files were downloaded to verify hashes. Only the harness and pins are
redistributed; ownership and licensing of the generated code are not assumed.

The references come from TestSuiteBench's binary release at the same upstream
commits as the ProgramBench task IDs. Identity with the canonical ProgramBench
Docker binaries is unverified. This is not an official ProgramBench score.

## Primary experiment

Run every selected reference/candidate pair and a reference/reference control.
Compare four methods: shortest-first enumeration; seeded random ordering within
each length; **AALpy 1.6.2's actual RandomWordEqOracle**; candidate state-cover
screening followed by paired replay. State-cover exploration is known prior art,
not a novel algorithm. No model is trained in the AALpy random-word comparison.

Seeds 0–4, maximum sequence length 4. Each trial allows 256 application invocations:
192 for discovery, up to 64 for two fresh paired witness replays. An invocation
includes each action and every state observer, on both implementations. Candidate
screening consumes up to 64 of the 192 discovery invocations. Git initialization
is reported separately and included in total process counts and elapsed time.
Resets, reference/candidate costs and incomplete budget-ending sequences are visible.
No excluded invocation is silently free. No claim of equal wall time or provider
billing is made. Deterministic methods repeated with five seed labels are the same
method, not five independent programs or independent statistical observations.

A stable projected mismatch reproduced twice is CONFIRMED_DIFFERENCE. Either side
being unstable, invalid, timed out, unable to initialize, or only partly confirmed
is UNKNOWN. No found witness is NO_DIFFERENCE_FOUND_WITHIN_BUDGET, never equivalence.
Controls use the same projection and methods. Inspect each actual witness against
the upstream interface before interpreting it as a program defect.

## Observation contract

The action alphabet is declared in `CliRunner.actions()` and is identical across
methods and implementations. All raw stdout/stderr/exit codes are retained.

For zoxide, record action exit status, output lines and ordered `query --list`
results after every action. Dedicated common path fixtures avoid path renaming.
The alphabet covers add/remove, queries, exclusion and case-sensitive inputs.
Stderr prose is outside this projection. Time-sensitive rank differences can
produce UNKNOWN; matching here does not validate time/rank behavior generally.

For dstask, actions cover adding, contexts, priority/tag modification, starting,
stopping, resolving and queries. The observers are show-open, show-resolved and
show-templates. Retain CLI integer ID, summary, status, notes, project, priority,
due and sorted tags. Empty null tags mean an empty tag set, by this task contract.
Ignore generated UUID and created/resolved timestamps; their correctness is not
tested. Project queries retain name, counts, active status and priority, excluding
created/resolved timestamps. Tag queries are sorted lines because upstream
iterates a Go map. List order and mutation acknowledgment prose are excluded.
Different task multiplicities remain visible; UUID identity itself is out of scope.

## Execution and evidence

Third-party code runs only in a disposable standard public GitHub Ubuntu runner's
Docker container, without network or secrets, as a non-root user, read-only root,
capabilities dropped, 256 MiB memory, 64 processes, one CPU and bounded tmpfs.
Each subprocess has a 3-second timeout. Each CI job has a 20-minute limit.
Only selected verified Python source and reference executables enter the container.
No archive build scripts execute. This isolates the host, but is not a proof against
a deliberately malicious candidate attacking the co-resident measurement process.

Pin the base image and Python dependencies, record installed Git/runtime versions.
APT Git packages are resolved at build time, a residual reproduction limitation.
Emit JSON receipts and hash-addressed compressed raw transcripts in CI logs; avoid
retained GitHub artifact storage. Preserve initial calibration failures and any
adapter changes rather than presenting an outcome-tuned rerun as preregistered.

## Interpretation

Report detection, UNKNOWN, witness length, actual reference/candidate/setup costs,
control failures and per-pair results. Two development families cannot establish
held-out generalization, a population false-positive rate, SOTA or customer demand.
Full RALib/RESTler/Schemathesis learning and differential pipelines have not been
run. A win over these four controls would still need those applicable comparisons.
If the exploratory method loses, retain that result and reject the advantage claim.

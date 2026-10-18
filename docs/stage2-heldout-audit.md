# Held-out data audit: 11 static candidates, zero new executed families

The two pinned model releases each contain 200 submission archives. The pinned
TestSuiteBench release has 197 matching reference binaries. This is artifact
availability, not 197 stateful families or 197 validated twins. Missing references
are jq, solar and samtools. See [metadata and source pins](../sources/programbench-heldout-candidates.json).

A bounded source/dependency audit inspected 43 shortlisted pairs (85 unique small
archives, approximately 5.95 MB). It did not execute programs, read evaluation
outcomes, hidden tests, trajectories, pyc or pytest-cache bodies. The parent sent
the completed pilot's outcome while this audit was running; held-out selection
used state mechanisms and runtime feasibility, not those outcomes.

Eleven additional upstream program families have evidence of application-owned
persistent state and a feasible bounded local runtime. All remain unexecuted:
handlr, hostctl, jot, bartib, calcurse, zk, cheat, direnv, ninja, pier and stgit.
Some require Bash, Git or a deterministic helper program. No new transition case
has been authored or run by this audit.

| First five candidates | Persistent state | Required scope |
| --- | --- | --- |
| handlr | MIME handler defaults and configuration | Temporary XDG directories and fixture desktop entries; avoid launching GUI applications |
| hostctl | Named host profiles and activation | Temporary hosts file; never system /etc/hosts |
| jot | Vault registry, notes and folders | Temporary HOME, vault and editor-free commands |
| bartib | Running/completed activity records | Temporary activity file; explicit treatment of clock-dependent fields |
| calcurse | Calendar events and todos | Temporary calendar directory and batch import/export operations |

The first five have Python-stdlib core scopes in both generated implementations.
Their ten source archives and five references total 16,968,265 bytes. The references
were not downloaded or executed in this audit. Each needs a frozen observation
contract, reference smoke test and isolation/reset check before inclusion.

Do not count a shared underlying SQLite engine as an independently recreated
database engine. Pueue's daemon availability remains unresolved. Atlas and DuckDB
exceed this audit's reference download bound. File transformers and related
interpreter variants were not used to fill the family count. One reviewed eva
launcher explicitly branches on PYTEST_CURRENT_TEST; it was excluded from this
shortlist. That source-specific observation says nothing about the other twins.

The supported total is two executed pilot families plus 11 static candidates.
It does not establish the original 30-family/200-transition gate. Nor is 11 a
proven corpus maximum: 148 tasks received availability checks only, and seven
shortlisted pairs were not inspected. More outcomes cannot be inferred from the
existence of archives. Source pins are published; third-party source bodies are not.

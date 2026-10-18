# Supplemental data-feasibility audit: 19 static candidates, no new execution

This extends the [initial audit](stage2-heldout-audit.md), after the negative
[Stage 2 result](stage2-results.md). It checks whether the pinned releases can
support the original research scope. It does not test an algorithm or establish
SOTA progress. The tested candidate-state-cover mechanism remains rejected.

The extension screened all 148 previously availability-only tasks, retrieved
139 pinned upstream READMEs, and inspected 24 pairs of generated source archives.
Additional payload downloads totaled **18,619,530 bytes**, below the 20,000,000-byte
cap; this excludes HTTP/TLS framing. No reference binaries or third-party programs
were executed. No hidden tests, evaluation outcomes or trajectory bodies were read.

Coverage reconciles as **2 pilot + 50 original held-out screen + 148 extension =
200 tasks**. Of the 198 non-pilot tasks, 67 source pairs have been inspected
(43 original + 24 extension); 131 pairs have not. Source inspection is exposure
to implementations: these are outcome-unseen candidates, not wholly blinded data.
Any future held-out protocol must account for that exposure.

Eight additional projects have source evidence of persistent state or an
externally driven protocol, both generated archives verified, a pinned reference
artifact listed, and an identifiable bounded isolation design:

| Project | State to test | Qualification still needed |
| --- | --- | --- |
| bore | Tunnel registration, authentication, connection lifecycle | Local-only client/server lifecycle and reference dependencies |
| entr | File-watch snapshots and child restart lifecycle | Deterministic file events and complete process cleanup |
| miniserve | Upload/remove effects on later HTTP responses | Temporary served directory and HTTP operation contract |
| xh | Persistent session headers, cookies and authentication | Local fixture server and isolated session files |
| Halite | Board state and sequential bot-turn protocol | Deterministic bots, seed control and protocol adapter |
| loop | Attempt counters, child results and stopping conditions | Deterministic child fixture and bounded process lifecycle |
| thokr | Typing progress and historical results | PTY input, clock treatment and isolated result storage |
| pipr | Pipeline editor state, history and bookmarks | PTY input and allowlisted deterministic child commands |

These eight plus the preserved initial eleven give **19 static candidates**.
They add **zero runtime-qualified families and zero executed transition cases**.
Different repositories do not by themselves establish statistical independence.
Aliases, flags, seeds, bots and language variants are not additional families.

The 148 extension decisions are 8 candidates, 13 conditional, 107 excluded by
this screen and 20 UNKNOWN. Of the 107 exclusions, 104 are metadata-only screening
decisions, not proofs of statelessness. Conditional and uninspected possibilities
remain. The audit neither establishes 30 qualified families nor proves that the
corpus cannot supply them. The 200-transition, independent-label and strongest-
baseline gates also remain unmet.

The [public metadata export](../sources/programbench-feasibility-extension.json)
contains pinned URLs, hashes, source paths and per-task decisions, with no code
or README bodies. Its SHA-256 is
`18004f7328c63d53a1f92236c1b0bc520feb9f11acd87372a855c00343d76e16`.
The private working inventory hash is
`bec654c162c757545f9f67daaa0c922c4c5af612f2e94b8dde9e3611ddf2c066`;
it is not redistributed because it includes third-party source material.
The author checked the public export's hash, unique task count, decision totals,
24 inspected-pair flags, eight positive flags and download accounting. This is an
AI-assisted static audit, not independent runtime replication.

No follow-up experiment was started. Preserve unseen outcomes until a different
mechanism with a defensible expected benefit and an actual released strong
conformance baseline has been specified.

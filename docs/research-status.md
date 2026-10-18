# Research status: no SOTA claim

2026-10-18. **Research active; SOTA objective unmet.** The software and reproducible
audits are usable OSS. The user resumed research after Stage 1's NO-GO result.
Stage 2 now measures real released twins, but the proposed search costs more than
simple controls on the development pairs. No study establishes a novel method's
superiority, customer demand or external adoption.

The Stage 0 audit found reproducible oracle defects in two released EnvSimBench
graders. Canonical JSON equality ties TwinProof on those constructed cases.
The Stage 1 same-implementation replay control found no differences among
comparable observations after sharing runtime inputs. That validates a baseline
and our experiment plumbing; it does not evaluate independently generated twins
or falsify all partially observable conformance methods.

The [Stage 2 released-twin pilot](stage2-results.md) evaluates two families and
four generated programs from two released generation configurations. Its final
run records 120 trials, with complete transcripts and reference/reference controls.
Directly inspected witnesses include a successful exit with a failed task-state
update. Candidate state-cover search is more expensive than ordinary controls;
the stronger twins have no divergence found within budget. These are scoped
observations, not whole-program equivalence or a SOTA score. The [held-out data
audit](stage2-heldout-audit.md) identified 11 additional static candidates; none
has runtime validation. The negative Stage 1 and Stage 2 findings remain in the record.

## Closest prior work

| Primary source | Established capability | Implication for TwinProof |
|---|---|---|
| [Differential Regression Testing for REST APIs, ISSTA 2020](https://patricegodefroid.github.io/public_psfiles/issta2020.pdf) | Stateful request-sequence differential testing and abstraction of nondeterministic fields | Stateful replay and noise abstraction are prior art |
| [Vive la Différence, PVLDB 2025](https://pages.cs.wisc.edu/~rgrandl/papers/p2018-zhu.pdf) | Comparing outputs and persistent database state across application versions | Full-state differential testing is prior art |
| [Keploy](https://keploy.io/docs/keploy-explained/introduction/) | Recorded traffic replay and dependency mocking | An applicable real replay tool must be evaluated before a competitive claim |
| [Schemathesis stateful testing](https://schemathesis.readthedocs.io/en/stable/explanations/stateful/) | Linked multi-operation workflows | Following a created resource through later actions is already established |

Witnessed ID bijections are a conservative engineering component, not a claimed
invention. We did not execute RESTler, Keploy or Schemathesis in this pilot; the
baseline we executed is our explicitly documented clock/RNG control plus exact
comparison. It must not be described as outperforming those systems.

## Gates still unmet

- Independently generated twins from at least two generation methods across the
  required held-out families. Stage 2 has two configurations, but only two
  development families.
- At least 30 independently validated service families with real semantic
  defects, separated by whole family. Module count is not independent-family count.
- A fair equal-budget comparison against the strongest applicable replay and
  workflow baselines, with false acceptance, false rejection and abstention.
- A primary improvement of at least five percentage points, a paired family
  confidence interval excluding zero, and false acceptance at most 1% with its
  uncertainty reported. These are decision thresholds, not observed achievements.

No point estimate, confidence interval or SOTA ranking for the missing comparison
is produced. The primary research gate remains unmet. Additional benchmark
packaging or a polished demo would not by itself change that decision.

[AI 2027](https://ai-2027.com/) and the
[AI Futures Model](https://www.aifuturesmodel.com/) motivate checking whether
verification retains value as agents improve. This is our inference from their
automation scenarios, not proof of a business opportunity. A useful next research
result would need measured residual errors under stronger agents and tools.

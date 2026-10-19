# Executable world models need a planning-state contract

Date: 2026-10-19. Status: prospective CPU study, not a SOTA claim.

## Decision and comparison with TCPR

The selected successor investigates **automatic detection and refinement of insufficient planning state in generated executable world models**. It separates two failures: hypothetical branches can contaminate mutable runtime state, and even correctly isolated branches can be incorrectly merged by an observation-only search key. The first mechanism is established prior art; the second is the empirical and algorithmic target here. Working implementation remains in TwinProof; no new project is advertised as validated yet.

The existing TCPR study provides a more mature empirical and theoretical comparison bar. This successor must contribute actual external generated-program failures, a useful intervention, comparison against correct full-state execution, and reproducible outcome evidence. A few local examples do not yet exceed that research maturity. Unpublished TCPR measurements are not redistributed in this package.

Alternative audited: estimand-preserving ML leakage interventions. Delimited release, causal information-flow experiments, test-label randomization, and hyperfuzzing already cover its generic primitives. The ASE22 external 100-notebook artifact has missing data and compatibility problems; only a small immediate CPU subset was identified. It is deferred, not disproved.

## Closest work and claim boundary

- [Twin](https://arxiv.org/html/2608.14490v1) already replays and repairs executable models. Its [repository](https://github.com/Alexyskoutnev/TWIN-ARC-AGI-3) documents order-sensitive evaluation and corrects its unseen-transition result. We are auditing its released models, not reproducing its original agent score.
- [Persistent Computational State](https://arxiv.org/html/2607.21686v1) already treats complete snapshots, independent forks, measured state discovery, and restoration. Snapshotting and identifying necessary state are **not our invention**. Full isolated state is a mandatory strong baseline.
- [Dual-Frontier](https://arxiv.org/html/2609.26293v1) already treats decision-specific world-model verification and failure attribution. A generic trust gate is not a successor contribution.
- Automata distinguishing suffixes, bisimulation, abstraction refinement, information flow and program slicing are foundations. No novel general theorem is claimed. Novelty of their application and combination here remains to be established with the actual results.
- [Vafa et al., NeurIPS 2024](https://arxiv.org/abs/2406.03689) already use distinguishing continuations to assess learned world-model abstractions. [THEA's bp35 report](https://github.com/bruno353/thea/blob/b7f0ce0fa391f27b3134f875c964f14b883cfb2c/LESSONS.md#L83) already identifies a real planner key omitting door configuration. Neither failure discovery nor suffix testing is claimed as novel here; automatic operational repair is the target.

AI-2027 and AI Futures motivate a scenario in which generation becomes cheaper than validation; these are forecasts, not evidence of demand or technical novelty.

## Hypothesis

An observation-only API `step(grid, action)` is insufficient when its generated implementation retains hidden computational state. A source-aware wrapper can (1) isolate that state and (2) use executable distinguishing suffixes to refine a search key only when observationally equal states have different futures. Compared with raw shared execution it should remove interference; compared with observation-only duplicate pruning it should retain necessary distinctions; compared with a full-state key it may avoid irrelevant distinctions. The last advantage is an empirical hypothesis, not assumed.

The algorithm must preserve cross-root aliases. Unsupported effects, mutable defaults, external resources or nondeterminism cause explicit unsupported status or conservative fallback. No sampled test is promoted into a universal equivalence certificate.

## Corpus and exposure

Candidate sources and observed histories come from `https://arc-agi-3-twin.vercel.app/showcase.json` and `games/{id}.json` (25 game families). Store content hashes and fetch dates; do not redistribute third-party source until license scope is clear. The reference simulator is optional independent validation, obtained through the documented ARC SDK. Showcase success scores are stale metadata and must not be used as our performance endpoint.

Development: dc22, sp80, ft09, cd82. Their code and metadata have been inspected; dc22/sp80 have known mutable globals. Other 21 families are outcome-unseen at this protocol's creation, but source metadata has been inspected. Any scout execution is explicitly exploratory. Missing logs, unavailable imports and non-runnable models stay in the 25-family denominator. Reconstructed logs are not silently substituted for missing original artifacts.

## Frozen first experiment

1. Decode all published observed frames and actions with strict validation; count repeated `(grid, action)` inputs with different observed successors. This is an empirical lower bound on deterministic observation-only one-step error **on these traces**, not generalization error or model quality.
2. Load supported models in bounded child processes with a minimal environment and controlled working directory. Inspect imports/effects before execution. Capture full Python data globals as a single object graph. This is an audited subset, not an arbitrary-code security sandbox.
3. Teacher-forced replay supplies each published observed input in chronological order. Snapshot the model before each call. Report next-frame accuracy separately from snapshot consistency; level-transition effects and terminal frames remain explicit.
4. From each stored context, compare isolated prediction with prediction after a deterministic branch excursion. All methods see the same inputs/actions. Shared execution, restart+prefix replay, and full snapshots are controls. Count construction, replay, audit and evaluation calls separately.
5. For same-grid contexts, search one-action and observed two-action suffixes for different predictions under full isolation. Store both histories, snapshot hashes, suffix, output hashes and actual bytes locally. Infer a minimal separating subset of differing global fields only over witnessed conflicts; check it on held-out suffixes/contexts. A full-state fallback protects uncovered cases. Distinguish witnessed incompatibility from absence of a witness.
6. Test search-key utility on bounded reachability tasks sampled from authentic model continuations. Use identical isolated execution and action sets for observation, full-state, and refined keys. Report failed, budget-exhausted and unsupported searches; target-reaching inside a learned model is **not actual game completion**.

Initial bounds: at most 25 models, 90 seconds per model for the first replay pass; suffix depth at most 2; per-family witness search budget 2,000 model calls after replay. All real observed trace conflicts may be enumerated without model calls. Any extended bound is a dated development amendment before its outcome is used.

## Decision gates

- G0: reproducible loading/decoding and honest denominator, with at least 10 runnable external families for a cross-family study.
- G1: distinguish real trace aliasing, model-state aliasing, and branch interference; never infer one from another.
- G2: isolated execution agrees with fresh replay on every tested supported case, including negative controls; failures invalidate wrapper claims.
- G3: show an improvement over the strongest applicable baseline on a frozen endpoint with all construction costs counted. Matching a correct full-state baseline is useful correctness evidence, not SOTA.
- G4: fresh review plus independent rerun of raw receipts. Family counts, not thousands of correlated branches, determine breadth.

Only a broader held-out study, defensible novelty and matched published competitors can support a SOTA claim. Failure of one pilot prompts a documented diagnostic/algorithm revision, not a fabricated success or a silent endpoint change.

## Execution clarification before main outcomes

The first implemented audit learns separating global fields from the entire released observation transcript, then freezes them before counterfactual branch checks. This is an offline-history-to-new-branches diagnostic, not a chronological held-out trace test. The first replay checks reconstruct prefixes ending at indices min(50,n-1) and min(150,n-1); their calls are counted. Excursions use sixteen uniformly spaced context indices plus witness contexts, the current action and the eight most frequent recorded action strings. The independent game engine is being checked separately. Generated Python is run in a minimal-environment child, with a 90-second wall/CPU bound; on macOS the process also denies network and writes outside its scratch/results directories. This does not constitute a secure arbitrary-code service.

An added observation-only planner on Twin's released model is a **constructed stress test** because its original planner was not included in those JSONs. THEA's released key is a separate, stronger real-planner endpoint. Third-party source decoding and unsuccessful loads remain visible. No cost-free acquisition or source-level proof is inferred from finite tests.

## Review-driven implementation amendment

The independent review demonstrated that ordinary dunder globals, data-bound built-in methods, mutable GenericAlias arguments and replaced code bindings can evade naive snapshot root selection. These are captured or rejected explicitly. Sets/frozensets in global data are now rejected because deepcopy/pickle can change observable iteration order. This is a conservative coverage reduction, not evidence that excluded candidates are incorrect. The corrected `corpus-03` rerun has nine completed families, below G0's unchanged ten-family threshold. The pre-correction runs remain available, bound to their own source hashes.

Malformed/missing or pin-mismatched source artifacts retain failed-family rows. Expected and actual byte hashes are separate, and no trace count is inferred from bytes that failed the source pin. The final report is [state-contract-results.md](state-contract-results.md).

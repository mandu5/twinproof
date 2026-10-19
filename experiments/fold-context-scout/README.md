# Fold-relative label dependencies: mechanism scout

**A new question to qualify, not a demonstrated successor to TCPR or a SOTA result.**

This small CPU experiment asks whether row-wise self-exclusion is an adequate
proxy for outer-fold label isolation. It is not: globally precomputed out-of-fold
(OOF) features can exclude every row's own label while feeding outer-test labels
into the outer-training computation. Conversely, an encoder fitted only on an
outer-training set may use those training labels without accessing outer-test
labels, even when it lacks internal cross-fitting and is prone to overfitting.

This distinction follows established cross-validation and information-flow
principles. It is not a newly discovered leakage mechanism. The research question
is whether a practical **fold-relative dependency analysis with executable
counterexamples** can diagnose these compositions precisely, including valid
nested procedures, in existing generated and human-written ML programs.

## Executed result

The protocol was frozen before execution. Ten synthetic datasets, five outer
folds and three explicitly constructed pipelines give 150 fold-arm cases. The
predictive pipeline is TargetEncoder + Ridge, using scikit-learn 1.7.2. We perturb
only held-out labels and compare predictions while keeping training labels,
features, splits, seeds and hyperparameters fixed. Evaluation scores are not used
as a leakage oracle.

| Composition | Outer dependency flagged | Predictions changed | Row-wise self-label feature path |
|---|---:|---:|---:|
| Inner cross-fitting inside each outer training fold | 0/50 | 0/50 | 0/50 |
| Global OOF features before outer cross-validation | 50/50 | 50/50 | 0/50 |
| Train-only encoding without internal cross-fitting | 0/50 | 0/50 | 50/50 |

The maximum observed prediction change in the global-OOF arm is 1.0588327035;
both outer-safe controls are exactly invariant in these executions. These are
correlated folds of ten own datasets and three hand-specified program patterns,
not 150 independently sourced programs. Absence of observed changes alone is not
a universal noninterference proof.

`receipt-instrumented.json` is the current runner's result. Instrumentation counts
1,300 actual encoder estimation batches and 300 Ridge fits, including original
and intervened executions, in about 2.43 seconds on the recorded local runtime.
`receipt.json` preserves the earlier equivalent run, whose 6/1 batch counts were
derived from the inspected implementation rather than instrumented. Its runner
is retained as `provenance/initial-run.py`. Counting both runs gives 2,600 encoder
batches and 600 Ridge fits; independent review also re-executed the case logic.
Reported wall times describe individual runs, not all research effort.

The dependency sets are explicitly propagated through trusted TargetEncoder and
Ridge compositions. They overapproximate influence; an intersecting dependency
set is a potential path until the intervention witnesses an effect. **This code
does not automatically instrument arbitrary notebooks.** It excludes
label-dependent splits, group/time validity, hyperparameter selection, unknown
operators, side effects and adversarial code. The global-OOF arm is a deliberate
miscomposition, not a bug in scikit-learn.

## Reproduction

```sh
python3 -m venv .cache/fold-scout-venv
.cache/fold-scout-venv/bin/pip install -r experiments/fold-context-scout/requirements.txt
.cache/fold-scout-venv/bin/python experiments/fold-context-scout/run.py --output .cache/fold-scout-rerun.json
```

The output path must be new. The script needs no downloaded dataset, inference
API or GPU. Each receipt records the protocol, runner and encoder source hashes.

## Prior art and admission bar

- [Scikit-learn's official example](https://scikit-learn.org/1.7/auto_examples/preprocessing/plot_target_encoder_cross_val.html) explains internal cross-fitting and correct pipeline use. The scout adapts the general example design, not its published performance result.
- [NBLyzer's 2025 paper](https://caterinaurban.github.io/pdf/scp2025.pdf) already develops dependency-based leakage analysis with sound abstract semantics. The available old repository must not be silently treated as the paper's updated implementation.
- [ArgusEyes](https://stefan-grafberger.com/arguseyes-dbspektrum.pdf) already uses relational provenance to screen ML pipelines.
- [FSE 2026](https://conf.researchr.org/details/fse-2026/fse-2026-research-papers/177/Improving-Data-Leakage-Detection-in-Machine-Learning-Notebooks-through-Static-Slicing) combines provenance-aware slices with LLM prompts; that combination is not a new proposal here.
- [A Grammar of Machine Learning Workflows](https://arxiv.org/abs/2603.10742) and [temporal noninterference](https://arxiv.org/abs/2607.04958) already cover important typed workflow and formal leakage guarantees.

No published detector was run on the 150 cases. An additional **simple graph
reachability baseline with the same explicit dependency information ties all
150 verdicts**, with zero disagreements (`graph-baseline-receipt.json`). This
rejects novelty or superiority for the set-union calculation itself. Reproduce
with `python3 experiments/fold-context-scout/graph_baseline.py --output .cache/graph-rerun.json`.

There are zero external programs executed in this mechanism scout. A pinned
ASE 2022 archive census reads 100 notebooks: 99 decode and one is malformed.
Seven contain a `KFold` name mention, but none names TargetEncoder, stacking,
calibration or cross_val_predict. This is a string census, not resolved call
coverage or proof of absence; data availability and suitability remain UNKNOWN.
The archive SHA256 and per-notebook hashes are in `external-source-census.json`.

The next admission test must establish a new, useful
abstraction over existing dependency analyses; execute version-matched baselines;
and evaluate external compositions with safe nested-CV controls and UNKNOWN
outcomes for unsupported effects. If a published analysis already handles this
precisely, this remains an engineering extension, not the sought research result.

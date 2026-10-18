# What this experiment can and cannot contribute

Checked 2026-10-18. TwinProof is investigating conformance of generated program
twins. It has not established a new learning algorithm or SOTA result.

| Primary source | Existing capability | Consequence for TwinProof |
| --- | --- | --- |
| [AALpy learning-based testing](https://github.com/DES-Lab/AALpy/wiki/Learning-Based-Testing-with-AALpy) | Learn multiple systems and compare models, or use one learned system to test another | Learning a candidate to test a reference is prior art; our random-word run is not a full comparison with AALpy learning |
| [SL-lambda, JAR 2026](https://link.springer.com/article/10.1007/s10817-026-09758-9) | Scalable register-automata learning using counterexample analysis and restricted suffixes; implemented in RALib | Fresh identifiers, useful suffixes and active learning are not new; a learning claim needs a real RALib comparison |
| [Tomte fresh outputs, ICTAC 2015](https://sws.cs.ru.nl/publications/papers/fvaan/TomteFresh/) | Learning with fresh outputs and counterexample-driven abstraction | Renaming nondeterministic IDs alone is not a new result |
| [RESTler differential regression, ISSTA 2020](https://software-lab.org/publications/issta2020_restapis.pdf) | Stateful differential API testing with abstraction of unstable values | Stateful replay and ignoring declared unstable fields are established mechanisms |
| [Schemathesis stateful testing](https://schemathesis.readthedocs.io/en/stable/explanations/stateful/) | Chaining producer/consumer operations from API schemas and links | An OpenAPI product should compare this directly; CLI-only experiments cannot claim to beat it |
| [CodeT, ICLR 2023](https://openreview.net/pdf?id=ktrw68Cmu9c) | Joint use of generated programs and generated tests for selection | Cross-candidate agreement is not a standalone novelty claim |
| [ProgramBench](https://programbench.com/) and [submission registry](https://github.com/ProgramBench/submissions) | Reimplementation tasks and released generated programs | Supplies real independent twins; two selected families remain development data |
| [TestSuiteBench](https://github.com/eth-sri/testsuitebench) | Test-suite evaluation against real applications and program variants | Supplies pinned reference executables here; we are not running its official mutation/test-suite benchmark |

The SL-lambda paper explicitly identifies more efficient counterexample discovery
as future work. That is a plausible research opening, not evidence that this
state-cover control solves it. Its published evaluation includes real-protocol
models and distinguishes learning cost from equivalence-query testing. A future
claim must preserve that distinction and count all resets and oracle interactions.

## Future direction and business hypothesis

[AI 2027](https://ai-2027.com/) is a scenario with uncertainty, not an observed
schedule or proof that software can already be copied perfectly. The authors now
point readers to their evolving forecasts. Their [August 2026 model update](https://blog.aifutures.org/p/q25-2026-timelines-update-uplift)
adds coding-uplift and revenue extrapolations and states that forecasts are
conditional on progress being as fast as technically feasible. Neither source
validates TwinProof or demonstrates paying demand.

Our inference is that cheaper code generation makes auditable behavior checks
useful across legacy rewrites, agent training environments and replacement tools.
The possible product is a reproducible failure witness and scoped conformance
report for a customer-authorized replacement. A generic reverse-engineering wrapper
is vulnerable to model improvements and already faces capable open tools.

The defensible asset would have to be independently labeled real discrepancies,
reliable adapters and measured savings against existing testing tools. These are
still being tested. No revenue, customer interview, external adoption, GitHub
trending status, strongest-baseline win or SOTA is claimed. Technical progress
and market validation are separate gates.

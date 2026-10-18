# Independent AI review and one verified correction pass

A fresh GPT-6-astra reviewer inspected `8e0f39d..db90f56`, the actual transcripts,
source, protocol and tests. It ran 112 tests and independently checked all 120
calibration transcript hashes and the 19,276 recorded application/setup process
counts. This is an AI review, not human peer review or independent experiment
replication. Its initial verdict was **not ready to merge**.

| Finding | Initial grade | Author disposition | Regression |
| --- | --- | --- | --- |
| Initial discovery excluded from stability checks | Important | Fixed; discovery must equal both new runs | changing discovery and UNKNOWN discovery tests |
| Task query membership lost by flattening observers | Important | Fixed; state keyed by observer | task moved between open/template views |
| Deep JSON escapes as RecursionError | Important | Fixed; parsing failure recorded as UNKNOWN | nested JSON followed by a valid step |
| Successful parent can leave background child | Important | Fixed; group cleanup and UNKNOWN | child attempts a delayed file write |
| Invalid UTF-8 bytes silently replaced | Minor | Regraded Important and fixed: can collapse distinct outputs into false equality | distinct invalid bytes retained and UNKNOWN |

All six regression tests failed before implementation. Each fix was verified and
the whole 118-test suite passed. The reviewer found no affected existing confirmed
calibration case for the discovery-instability defect. No second reviewer was used;
fixes are verified by the author's regressions and final Linux rerun.

## Recorded rulings and limits

- Continue the existing isolated research branch without another design approval:
  the user explicitly resumed and delegated execution. Cost if wrong is scope
  drift; no paid inference/GPU or unrelated project execution is authorized here.
- Regrade invalid UTF-8 as Important because byte replacement can hide a real
  observable difference. Cost is stricter UNKNOWN handling for invalid text.
- Deliberate attacks against the co-resident measurement process remain outside
  scope. Host isolation is provided; adversarial measurement integrity is not.
- Exhaustive TAR/PAX decompression denial-of-service and kernel/container escape
  resistance were not established. Do not interpret allowlist tests as such proof.
- Identity with canonical ProgramBench Docker binaries remains unverified; the
  reference release has the matching task ID/upstream revision, not proven byte identity.
- Clock-sensitive zoxide rankings are observations, not universally validated bugs.
- UUID/timestamp correctness, mutation prose and excluded list ordering remain
  outside the declared task projection; false acceptance there is unmeasured.
- SOTA, strongest-baseline superiority, held-out generalization and population
  error rates remain unestablished; the research objective stays active and unmet.
- The reviewer did not independently rerun the released programs. Repeated CI
  execution by the author is reproducibility evidence, not independent replication.

No remaining Minor findings were deferred from this review.

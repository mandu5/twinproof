# Stage 1 independent AI review and author verification

2026-10-18. A fresh-context AI reviewer inspected the whole Stage 1 change,
reproduced failures, ran the suite and checked the public-file allowlist. This is
not human review, peer review or independent academic validation.

| Finding | Author fix and verification |
|---|---|
| P1: normalized ID arrays/keys could collide with ordinary candidate JSON | Every JSON node and key now has an unambiguous tagged representation. Separate value/key collision regressions failed first and now pass. |
| P2: live-reference state getters could mutate recorded before-state | Before, after and return values are deep-copied at capture. A live-getter regression failed first and now passes. |
| P2: nonexistent methods and invalid signatures counted as executed calls and replay PASS | Signature binding happens before dispatch; unsupported cases remain in the denominator as UNKNOWN. Attempted dispatches and actual method executions are reported separately. Three related regressions failed first and now pass. |

The reviewer initially found the release **not ready**. All three findings were
fixed in one author verification pass; there was no second independent review of
those fixes. The final local suite passes **79 tests, zero skips**. The complete
runtime pilot was regenerated, and a fresh repeat produced byte-identical case
receipts (SHA-256 `dd69191dffa01505c938d0b6857f58d3246119616b4188b8279f29c08b889df4`).

The reviewer declined to judge remote delivery, SOTA/novelty, real-defect accuracy,
literature completeness, and arbitrary-code sandbox security. Remote delivery is
verified separately after publication. The other items remain unclaimed; the
runner is only for the pinned reviewed snapshot and the research promotion gate
is NO-GO. No minor findings were deferred.

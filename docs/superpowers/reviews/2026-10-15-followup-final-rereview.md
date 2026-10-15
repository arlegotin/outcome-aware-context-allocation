# Final scoped re-review

Reviewed `final-fix-report.md` and the complete `review-5c295b3..6885a33.diff`, limited to I1, the required source-version/reproduction qualification, and breakage introduced by this fix. Code/tests are at `c1c1720`; the subsequent `6885a33` changes documentation/provenance only. This is the single requested scoped re-review, not another broad review.

## Strengths and dispositions

**I1 — ADDRESSED.** `runtime.py:586` records reader acquisition before invoking the constructor. The finalizer at `runtime.py:619` checks registered worker identity/quiescence even when assignment never completed. Live or unknown workers set `cleanup_error`, so `runtime.py:631` preserves null exact stop and upper bound. The existing resume guard and immutable reconciliation retain that uncertainty after the worker exits. A registered worker successfully stopped during startup still permits an exact failed-session envelope.

The new parameterized regression in `tests/test_followup_recovery.py:237` exercises a real registered child and a constructor that raises before returning a backend. It checks unresolved totals, absence of paid jobs/warm-ups, rejection of another acquisition while the child lives, unchanged original receipts, and unknown exact stop after reconciliation. Its successful-cleanup control checks that honest exact accounting remains available. This directly covers the previously missing integration path and preserves the existing failed-close handling.

**Source-version/reproduction qualification — RESOLVED.** README, publication scope and the follow-up report distinguish measured `9ddc4ae`/867 tests/fresh-process rescoring from later `c1c1720`/869 tests. Raw authentication explicitly requires the recorded source at the original bound paths plus private assets. Hardened source intentionally fails v2's mutable-source binding; the separate archival hash audit is not represented as raw-score reproduction. No snapshot or manifest rebinding is claimed.

## Evidence inspected

- The retained native log ends with **869 passed in 114.66 seconds**; its receipt records zero skips, exit 0, and the same `c1c1720` source before/after. No source/test changes exist between that commit and `6885a33`.
- Read-only hash checks matched the new public report, test log/receipt, and retained archive-audit receipt to their public provenance fields.
- Comparing the public summary directly with `5c295b3` confirms every original top-level study value is unchanged except the report hash; the only added top-level value is `post_study_hardening`.
- Inspected root's preservation receipt: all 1,303 v1 and 4,431 v2 files remain unchanged, as do the original 22/26 source bindings. The implementation report and linked audit retain the archived 37-file snapshot/Git checks separately from the intentional current-source mismatch.
- The reported focused sequence is one failing live-child regression plus one passing clean control before the fix, followed by 67 focused passes. No tests, inference, Gold/scoring commands or archive-producing commands were run in this review.

## Issues

**Critical:** None.

**Important:** None remaining in the reviewed scope.

**Minor:** None requiring changes.

No new actionable breakage was found in the fix.

## Declined to judge

- Unrelated runtime paths, broader scientific conclusions, historical reuse ancestry, real sleep/wake behavior, cross-platform behavior, and future reader/controller experiments: already covered or explicitly deferred in `final-review.md`; outside this single scoped re-review and not reopened.
- Automatic recovery when a native reader fails before registering a verifiable identity: the fix deliberately preserves uncertainty and blocks unsafe resume; guaranteed recovery is not claimed or required to resolve I1.
- Independent re-execution of tests, raw scoring, inference or the full retained-file crawl: prohibited repetition for this review; inspected the existing evidence and performed only narrow read-only diff/hash checks.

## Assessment

**Spec-compliance verdict: APPROVED for the final fix and required documentation qualification.**

**Code-quality verdict: APPROVED for the reviewed scope.**

**Ready to publish: Yes, with the existing limitations retained.** I1 and the required reproduction integration are resolved. The prior broad review's supported scientific assessment and explicit deferred limitations remain in force; this approval adds no new scientific outcomes or runtime-performance claims.

> Historical broad review before the fix. Its single Important finding was resolved by the [scoped re-review](2026-10-15-followup-final-rereview.md).

# Final whole-branch review

Reviewed base `427053d` through head `5c295b3` (eight commits), including the full follow-up runtime/planner/scorer/analysis integration, public report, aggregate provenance, README and publication changes. Read the prospective spec/plan, implementation and native-repair reports, scoped review dispositions, and progress-ledger rulings. Review was read-only except for this requested report. No model calls, preparation, scorer commands, new tests, suite reruns, private-ledger mutation, Git mutation or reviewer delegation occurred.

## Strengths

- The study preserves the prospectively fixed 64/32-reserved/128 cohorts, distinguishes eight executed calibration questions from the 32 reserved, and accounts for all 688 assigned generations. The archived v1 failure is separate: 304 terminals, zero question calls and zero question tokens, with headroom deferred rather than relabeled complete.
- Source snapshots and immutable closures provide unusually concrete evidence. Read-only checks verified both versions' 37 source bindings against their recorded Git commits, every file in the retained stage closures, all three v2 public summaries against archived scorer summaries, the public report hash, and the full-suite log hash. V2 has 48/256/384 terminal records and exactly 688 question calls. Archived headroom score rows independently yield joint/answer ceilings of 12/78.
- Continuous parent deadlines check time after wake/message receipt, keep blocking IPC serialization/receive off the deadline thread, and retain partial outputs on timeout. Warm service includes fresh retrieval and payload persistence; enclosing engine costs are distinguished from overlapping components and from excluded engineering/verification/review costs.
- The native SQLite repair is narrow and supported by real producer/SQLite/ranking integration coverage with protected-content, metadata, directory-listing and network denials. The experiment's new index explicitly requires the producer's nested empty reuse metadata, avoiding the disclosed historical ancestry defect.
- Scoring requires complete stage closure, preserves assigned failure denominators, recomputes immutable results, and separates privileged Gold access from serving. The headroom attestation avoids exposing scorer stores to the native worker.
- Public conclusions are appropriately limited: strict benchmark agreement remains primary, three measured actions are not the all-budget optimum, the clairvoyant chooser knows outcomes and realized latencies, and no learned-policy superiority, quality-preservation or production-economics claim is made. The eight-case review is explicitly enriched, post-hoc and agent-assisted. Its saved blind-review hash matches the unblinding receipt; no primary scores changed.

## Issues

### Critical

None found.

### Important

**I1 — Reader-construction cleanup failure can still publish an exact resident-session endpoint.**

- **Locations:** `src/outcome_poc/followup/runtime.py:586`, `runtime.py:610`, `runtime.py:619`; producer path `src/outcome_poc/followup/supervisor.py:199` and `supervisor.py:227`.
- **Trigger and behavior:** `backend = ContinuousBackend(factory)` only assigns `backend` after construction returns. During construction, `_start()` may time out or fail and then `_terminate('startup_failure')` may itself fail, including its explicit still-alive-worker path. The constructor raises, leaving `run_stage`'s local `backend` as `None`. Its finalizer therefore skips `backend.close()`, leaves `cleanup_error=None`, and writes `timing_status='exact'` with a finite stop and upper bound despite unsuccessful worker cleanup. The retained supervisor object/lifecycle is also not handed back to the stage caller.
- **Why it matters:** `session_accounting`/`report` trusts that exact receipt and may report complete, finite physical costs while the owned reader has not been shown quiescent. The later resume guard does check live workers, but once a worker eventually disappears it accepts the existing finite receipt without correcting its prematurely claimed endpoint. This is the constructor counterpart of the failed-close defect already repaired in the reviewed finalizer.
- **Fix:** Carry construction cleanup/quiescence state to the session owner (or verify owned-worker quiescence before publishing an exact final receipt). When cleanup cannot establish a stop, preserve null exact stop/upper bound and reconcile later without rewriting the original record. Add a focused authored constructor-failure regression that creates a registered owned child, raises before returning the backend, verifies unresolved cost reporting/live-worker resume rejection, and confirms later reconciliation retains an unknown exact stop. Also retain the clean-startup-failure control so ordinary failures with successful cleanup need not lose exact accounting.
- **Evidence/impact boundary:** This finding follows directly from the exception/assignment/finalizer control flow; no new fault test was run during this review. The archived v2 sessions all have successful construction/execution/shutdown receipts, and no recorded v1/v2 session took this constructor-failure path. It does **not** invalidate the published measured results or their cost totals.

### Minor

None requiring changes.

## Recommendations and integration requirements

Resolve I1 before claiming general runtime failure-accounting readiness. Preserve both frozen experiments: do not patch their snapshots, manifests, receipts, scores or source identities. A subsequent runtime fix must be a separately committed source version.

Because each plan binds both its archived snapshot and absolute mutable-working-tree source files, any such fix will intentionally make current-HEAD `verify`/`score`/`report` reject v2's `9ddc4ae` source binding. Update the public reproduction instructions and provenance/disposition accordingly: authenticate v2 with its recorded `9ddc4ae` source at the bound paths plus retained private assets, or use a clearly separate read-only archival hash audit. Do not present verification performed before a later source fix as verification of the hardened HEAD against v2. The source snapshot/Git identity checks remain valid evidence of the measured version.

The recorded native suite has 867 passes, zero skips, and a successful receipt at `9ddc4ae`; its log and receipt were inspected, not rerun. The existing tests meaningfully cover native isolation, denied-parent SQLite traversal, complete-stage scoring, real spawned IPC failures, interrupted sessions and failed close. The untested cross-component constructor/finalizer path is the material remaining gap.

## Declined to judge

- Repair of the historical reused-index ancestry consumers: explicitly parked by the prior final disposition; this experiment neither changes nor relies on them. Their Important residual status remains disclosed, not resolved by this review.
- Real system sleep/wake behavior and production timing stationarity: no deliberate sleep experiment or production sample exists; reviewed continuous-clock/deadline code, fault-test evidence and observed diagnostic timing health only. The report states that limit.
- Independent factual truth or semantic recategorization of the eight citation cases: outside this review's evidence mandate; checked the blinded-before-labels receipt, aggregate categories, qualifications and unchanged scores, without treating agent judgments as truth certification.
- Quality of a future learned router, all ten budgets, a different reader/prompt, and strong tuned-baseline competitiveness: intentionally unexecuted follow-on work; no corresponding claim is made here.
- Complete adaptation cost, engineering/agent cost and deployment break-even: not measured by this follow-up; reviewed the recorded disjoint engine envelopes and explicit exclusions, not an invented total.
- Adversarial unknown external Gold copies and arbitrary concurrent hostile filesystem rewriting: the stated isolation model uses bound known stores/aliases plus import guards, not a universal positive read allowlist or cryptographic defense against a malicious operator.
- Cross-platform execution of the native follow-up suite: the experiment and validation target native macOS; no Linux/Windows or outer-sandbox test result is claimed by this review.
- Fresh reproduction of inference or official evaluator execution: expressly disallowed for this review and unnecessary for its artifact checks; rely on the retained fresh-process rescoring evidence, evaluator provenance and reviewed scorer logic, with the public limitations retained.

## Assessment

**Spec-compliance verdict: Changes required for the runtime's failure-cost contract (I1); completed-study selection, execution, analysis and reporting otherwise conform.**

**Code-quality verdict: Changes required (one Important finding, no Critical findings).**

**Ready to merge/publish? With fixes and the source-version reproduction qualification above.** The completed scientific result and aggregate public claims are supported by the retained artifacts, and I1 is outside the observed execution paths. The whole branch should not receive unqualified runtime approval until constructor failures preserve the same uncertainty already required for failed shutdowns.

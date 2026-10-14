# Confirmation cost forecast audit

This is a read-only development forecast, not an implementation, sample-size choice, method change, or authority to freeze. Snapshot time: 2026-10-14T20:57:27.991871+00:00. The fixed deadline remains 2026-10-15T12:12:52 UTC. Remaining time at this snapshot: 15.257 hours; after the required minimum two-hour reporting/recovery reserve, 13.257 hours remain for **all** unfinished implementation, review, calibration, indexing, execution and closure/scoring work. Finish experimental execution by 2026-10-15T10:12:52 UTC or earlier to preserve that reserve. Task14 coding/review and Task13 calibration/freeze are still real work with unmeasured durations; their time is not assumed to be zero. No new charging gate or question applies.

The complete required family roster is eleven representatives, the explicit fixed-ten anchor and the random control. Shuffled remains included as a diagnostic; it cannot become B*. A* is PRE-OUTCOME-GBM:17:numeric and B* is PROXY-LABEL:14:numeric. Two paired repetitions require **four additional direct pipeline executions per query**, A1/B1/A2/B2, even if their deterministic answer actions already exist in the representative collection. Repetitions are not additional unique tasks and never deduplicate against each other or source actions.

| Family | Selected configuration | Budgets used on TUNE128 | Ten decisions | Saved warm mean seconds |
|---|---|---|---:|---:|
| ADAPTIVE-k-published | `ADAPTIVE-k-published-B5` | 6, 7, 8, 9, 10 | varies | 2.3837 |
| ADAPTIVE-k-tuned | `ADAPTIVE-k-tuned-B1` | 2, 3, 4, 5, 6, 7, 8, 9 | varies | 1.4376 |
| FIXED | `FIXED-9` | 9 | varies | 2.8851 |
| LLM-SUFFICIENCY | `LLM-SUFFICIENCY` | 2, 10 | 11/128 | 1.8506 |
| POST-OUTCOME | `POST-OUTCOME:20:numeric` | 2, 10 | 26/128 | 1.7445 |
| PRE-LINEAR | `PRE-LINEAR-100:20:numeric` | 2, 10 | 8/128 | 1.2986 |
| PRE-OUTCOME-GBM | `PRE-OUTCOME-GBM:17:numeric` | 2, 10 | 25/128 | 1.4931 |
| PRE-RF | `PRE-RF:18:numeric` | 2, 10 | 16/128 | 1.3898 |
| PROXY-LABEL | `PROXY-LABEL:14:numeric` | 2, 10 | 8/128 | 1.2599 |
| QUERY-ONLY | `QUERY-ONLY:20:numeric` | 2, 10 | 12/128 | 1.3050 |
| SHUFFLED-LABEL-GBM | `SHUFFLED-LABEL-GBM:20:numeric` | 2, 10 | 24/128 | 1.5288 |

Fixed-ten's saved warm mean is 3.0674 seconds. Random mixture uses the selected candidate's **fit** escalation probability 0.19921875, not its tuning routing rate. Its exact canonical SHA-256 [271828, task_id, "random-mixture"] rule selects ten on 27 of the 128 development IDs; that development count is descriptive and does not replace the frozen probability. The random control's reconstructed saved-source mean is 1.5254 seconds. No protected IDs, sample, outcomes, documents or annotations were accessed for this forecast.

## Complete call accounting and warm-cost forecast

Joining only development task IDs, selected action budgets and operational event durations gives the following physical collection options. All include the anchor, eleven families, shuffled, random, and **four** direct selected-pair executions. These are schedule/accounting options to resolve before freeze, not permission to omit methods.

| Collection/accounting option | Mean generation calls per query | Saved warm seconds per query |
|---|---:|---:|
| Maximal exact answer-action aliases, draft/full aliases, one paid judge, plus four direct runs | 9.4453125 | 16.0422 |
| Same answer-action pool, but reserve a separately executed actual no-reuse POST pipeline | 10.6484375 | 17.7867 |
| Execute every family separately, plus random, anchor and four direct runs | 18.203125 | 28.6754 |

The answer-budget union is 3 budgets on 3 development tasks, 4 on 65 tasks, and 5 on 60 tasks: 569 distinct answer calls over 128 queries, mean 4.4453125. It includes fixed-two for POST draft availability and fixed-ten for the anchor, plus selected Adaptive-k and fixed-nine actions. A single extra paid sufficiency judge per query yields 697 pooled calls, mean 5.4453125, before the four direct runs. All two/ten learned, shuffled and random answers already belong to that union. The selected actual POST escalates on 26/128 development tasks; a separate POST pipeline adds 128 paid drafts and 26 paid full answers, mean 1.203125 calls per query. It uses cache_mode=none: no prefix reuse is assumed.

The strongest alias option requires prospective verification of identical full action/request signatures and intact source receipts, including the installed template, model/config, evidence ordering, caps, role and cache semantics. Shared output acquisition must still attribute each policy's actual paid draft/judge/routing costs; physical collection sharing cannot make POST's draft free in serving-cost comparisons. Cross-method action aliases are distinct from numerical KV reuse. If that sharing proof is unavailable, the second or third forecast is appropriate. Direct A*/B* runs always execute fresh complete pipelines with retrieval/routing/prompt/generation/payload timing.

The direct-pair contribution uses 2 × (1.4930571 + 1.2599284) = **5.5059709 seconds/query**, reconstructed from saved development action/routing receipts; it is not newly measured paired A*/B* timing. Representative pooled estimates sum the saved complete fixed-action serving costs, paid judge preparation/generation/parse, and measured selected-policy routing/payload work. The separate-POST estimate additionally pays the entire selected actual POST serving cost, conservatively retaining its draft even though fixed-two is already collected. Tiny duplicated fixed routing/payload charges make these acquisition estimates slightly conservative. Nested generation intervals are never added again to an enclosing serving total.

Actual TUNE native envelope was 3,436.0863 seconds for 1,552 pipeline jobs and 1,811 generation calls; complete serving time was 3,330.7854 seconds. Their ratio is 1.0316144. Applying the existing 1.5 planning margin and that measured envelope factor to the separate-POST and fully separate means gives about **27.5–44.4 seconds/query**. A rounded provisional complete-roster allowance is therefore **28–45 seconds/query**, plus separately budgeted indexing, calibration, source binding/review, scoring/closure and any declared diagnostic slice. If exact maximal aliases are verified, its corresponding lower planning allowance is about 24.8 seconds/query; do not silently take that saving as guaranteed.

Thus a planning formula is T_remaining_work(n) = T_Task13 + T_Task14_implementation_review + T_index_setup + n × (28–45 seconds) + T_named_diagnostics + T_scoring_closure, with at least 7,200 additional seconds reserved for reporting/recovery. All non-query terms remain unmeasured here. This range is a workload allowance, **not** a statistical upper confidence bound or a deadline guarantee. TUNE128 routing, output lengths and hardware state need not match later execution. Do not choose n solely from the fastest endpoint or drop mandatory families to fit a desired n. The old pilot's two-arm-only envelopes explicitly excluded anchors/representatives and cannot stand in for this complete roster.

## POST sensitivity and evidence qualifications

Actual selected POST warm mean is **1.7444730 seconds/query**. Its separate optimistic clean-prefill sensitivity is **1.2846030 seconds/query**, a reduction of 0.4598700 seconds/query. That sensitivity removes all measured clean full-call prefill while retaining the paid draft and other work; it is **unexecuted**, not a measured optimized pipeline or a physical schedule saving. Task11's predeclared numerical parity check failed on two real cases despite greedy-output parity. Do not substitute this bound for actual no-reuse POST in the execution forecast or selected B*. Any mechanism/superiority interpretation must retain the sensitivity qualification.

Tuning costs are development paid-action reconstructions with measured per-request routing/payload replacement, not fresh selected-policy measurements. Sixteen direct reconstruction checks covered only four development tasks and PRE-OUTCOME-GBM:11, PRE-RF:11, POST-OUTCOME:11 and published Adaptive-k. They do **not** directly validate the chosen A*:17 / B*:14 pair. Direct/reconstructed cost ratios ranged 0.8080–1.2092; aggregate direct/reconstructed time was 0.9113, with saved output/status parity. Historical successful ancillary paid receipts were retrospectively sealed: original v1 closures did not bind every ancillary file at completion. Present bytes passed content checks, but historical completion-time byte identity is not proved. Task14 must use the final forward paid-receipt closure format.

The outer native launch wall duration is null because the orchestrator stopped after native exit; the 3,436-second self-measured native envelope is available. Do not relabel it as complete editing/preflight/recovery elapsed time. The prior accounting profile's 3.996-second validation/lookup timing excludes gold/document scoring and cannot replace actual scoring allowance.

## Named diagnostics: declare their scope before freeze

| Diagnostic | Scope choices and cost consequence |
|---|---|
| Shuffled-label GBM | Mandatory full representative/control coverage; included above. Fit permutation already fixed; no retraining from confirmation outcomes. |
| Two/ten random mixture | Mandatory frozen control; included above. Existing two/ten signatures normally add no generation to the pool; still record decisions, logical costs and distinct diagnostic identity. |
| A/A aliases | Predeclare use of the actual repeated same-arm runs for alias/output/timing checks, or additional independently scheduled direct aliases on a fixed development/diagnostic slice. An additional fresh A/A pair adds two full pipeline calls per slice task. Never claim replay aliases measure timing noise. |
| Always-abstain | Zero model calls when declared as an explicit diagnostic-only policy; retain its assigned denominator and payload/overhead. Never hide action zero inside the core two/ten policy. |
| No-context | Explicit opt-in diagnostic slice or declared full scope; each diagnostic task adds one paid action-zero Reader call and its normal pipeline work. Do not reuse it as a core action. No new timing was collected here. |
| Clairvoyant action oracle | Declare whether its action set is two/ten, the collected union, or all ten budgets. Two/ten needs no extra generation once both actions exist; oracle decisions remain scorer-only after closed execution and never route serving. All-k requires the missing budgets: mean 5.5546875 extra fixed actions/query relative to this development union. Their cost must be added. All-k fixed budgets alone cost a saved mean 19.6350 seconds/query. |
| Stress/transfer/other named checks | Separate prospectively bounded diagnostic slice or explicit unexecuted status. No silent deletion, post-outcome slice choice, or pooling of synthetic stress outcomes with natural prevalence. |

## What Task13 still needs on development

1. **Longest prompt and forced 256-output capacity/timeout.** Saved TUNE operational events reach 2,993 prompt tokens, with three calls reaching the 256-output cap and a largest measured generation interval of 14.5083 seconds. These natural capped outputs do not establish a deliberately forced longest-prompt/max-output calibration. Use development or synthetic length-matched input for at least the structural 4,396-token full-ten size, allowing the qualified runtime-order check; never generate actual protected questions before freeze. Cover representative answer/judge paths, retain the 8,192/256 caps unless a prospectively justified compatible change is made, and record peak resources plus real operational conditions. Task13's timeout rule is twice the largest measured request time **after** this calibration; 29.0166 seconds from existing data alone is not a final timeout decision. Judges currently use their distinct 16-token cap.
2. **Actual selected A*/B* paired repeats and order/drift.** Prospectively choose a small development set by structural length strata, then run the frozen selected thresholds with at least two fresh paired repetitions, reproducible randomized A/B order, warm-up separated from steady timing, and blocks spaced enough to observe order/thermal drift. Retain per-request complete latency, output/token/status parity and real resource/power observations. Do not retune thresholds or diagnostic scopes from protected outcomes.
3. **Noise covariance and stationarity evidence.** Prior pilot receipts contain 16 same-action two/ten pairs, all token-parity checks passing, median max/min latency ratio 1.0723 and maximum 1.1778. They support a margin, not a current paired A*/B* covariance matrix or proof of stationarity. Task8 native A/A was synthetic plumbing; Task11 repeated the same four POST/sufficiency cases, not the selected pair. Estimate paired arm covariance in seconds squared within development length strata and inspect order/block trends. Supply evidence-backed stationarity/determinism flags; leave unverified flags null. If considering the predeclared one-repeat fallback, its conservative covariance matrices and provenance must be frozen; two actual paired repetitions remain preferred.
4. **Complete forecast, precision and recovery rehearsal.** Measure a mini-block of the actual final dependency schedule, including judge/POST costs and forward receipts, to settle alias versus separate execution. Budget sample-only indexing/setup and actual Task14 coding/review time, cold/reload costs, closure/scoring and final reporting reserve. Validate interrupted fixture resume with the same source/config/signatures. Repetitions do not improve the number of independent successful questions; freeze the success/LOO/quality/stationarity criteria and choose n once before protected access. No forecast here authorizes an outcome-dependent extension or change of methods.

## Source identity and audit boundary

The public selection was compacted during this scout. Calculations were repeated against its stable private pointer, not a stale in-memory public table. Authoritative inputs used for the final calculations:

- `artifacts/provenance/task12-selection.json`: SHA-256 `00712e0262f86fc040331521677a2f383d289d0d1300e9edf91193916f569ace`, 223,825 bytes.
- `artifacts/runs/task12-tune128-retry/selection.json`: SHA-256 `e5f640c6f8a1292089df633e20611f50a074a3b2ade80714334a416414005ee9`, 60,933,330 bytes; matches the public pointer. Per-task arrays were joined internally for action/cost aggregates and were not dumped into the report.
- `artifacts/runs/task12-tune128-retry/schedule.json`: SHA-256 `641c75ddfddd758ce8ae1451d22c8f7af27de00aa083571842c52ff6d6bd472d`.
- `artifacts/runs/task12-tune128-retry/native-summary.json`: SHA-256 `4df352fafff465ec088e6761993cd5270d0ee2b1f1e44fb61744394424688aa6`.

Only annotation-free development selection/cost fields, schedule metadata, per-job `events.jsonl` timing/token-count fields, and existing operational reports/briefs were consumed. No `predictions.jsonl`, paid raw results, question/evidence text, gold stores, raw datasets, protected IDs/outcomes or scoring files were read. No model/tokenizer/embedding initialization, generation, indexing, sampling, git mutation, package/asset change or power setting change occurred. This scout writes only this report. The final Task12 report and final source-bound Task13/14 protocol remain authoritative if later hashes/settings change.

inconclusive

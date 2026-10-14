# Execution checkpoint

Recorded 2026-10-14T21:00:44.135241+00:00. This is an in-progress recovery checkpoint; the final deliverable remains `artifacts/final_report.md`.

We are testing whether a cheap controller can decide how much evidence an AI needs before it answers. The proposed controller learns from actual correct and incorrect answers. The main question is whether that training earns its cost compared with simpler rules.

The practice comparison is complete on 128 development questions. The chosen outcome-trained controller achieved 10 strict answer-and-citation successes, versus 11 for the chosen simpler support-coverage proxy. Their estimated serving seconds per strict success were 19.11 and 14.66 respectively. These are tuning observations with sparse successes, not an untouched-test finding. The proxy, ridge, question-only and random-forest representatives all beat the proposed controller on the tuning efficiency objective. A small 128-versus-256 training check showed no stable progress, so no larger training collection is justified now.

All 246 configurations and losing or ineligible rows remain saved. A fresh reviewer verified the table arithmetic, common eligibility/selection rules, model bindings and original paid costs. The reviewer found two problems in the new forward receipt-locking code: it could accept a receipt already missing before closure, and re-closing could overwrite the hashes that detected corruption. Fix round1 is complete and approved before any protected generation; 570 tests passed. These reproduced flaws did not change the saved numeric costs or selected configurations. Original historical v1 closures and explicitly retrospective auxiliary-receipt seals remain preserved; no historical completion-time hash guarantee is invented.

Reviewed implementation otherwise covers pinned local assets, annotation-separated data, deterministic retrieval, strict answer/citation scoring, cost/recovery accounting, observable features, learned/simple controls, and paid draft/sufficiency controls. The machine is an M3 Max with 36 GiB RAM, native Python3.12.9 and macOS26.7.1. Exact dependencies, asset/source/split manifests and native receipts are retained. A01 qualifies the archived author-origin HotpotQA snapshot. No protected sample or model output exists yet; the protected finite population contains 7,344 questions.

Practice acquisition completed 1,552 jobs and 1,811 paid model calls in a self-measured 3,436.09-second native envelope. All five network/gold isolation probes passed on the corrected retry. One prior preflight failed before any model generation and is retained. Native source b5d479c and later analysis source33280ba are separately bound. The paused outer orchestrator was terminated only after native completion to enforce the receipt-sealing-before-Gold boundary; its complete unpersisted elapsed cost remains unknown.

The paid post-answer comparison uses actual no-reuse execution. Prefix reuse matched exact greedy tokens but failed the declared log-probability tolerance on two development cases. An optimistic clean-prefill cost bound removes the candidate's apparent advantage over that comparator; superiority to an optimized post-answer system remains unresolved.

A read-only capacity audit found all 7,344 canonical full-ten prompts fit the initial 8,192-total/256-output capacity. This is not proof for every possible ranking; runtime checks remain required. A development-only forecast provisionally allows 28–45 seconds per test question for the complete method roster and four fresh direct paired executions, plus calibration, indexing, source review, scoring and at least two hours for reporting/recovery. No test sample size is selected yet. Task13 read-only preparation is complete and the closure fix has passed its scoped review. Implementation of calibration and protocol freeze is next.

Charging is left to the user as instructed; there is no charger-related prerequisite or discretionary battery stop. Actual resource conditions and infrastructure failures remain recorded normally. The original 24-hour deadline remains 2026-10-15T12:12:52UTC.

Remaining work: freeze methods, capacity/timeout, sample and complete schedule; review the final execution/scoring source; execute and close the untouched paired comparison; analyze uncertainty and required attribution checks; reproduce and write the final report. Any incomplete assigned run remains incomplete. No improvement, preserved quality, web-search saving or commercial benefit has been established.

inconclusive

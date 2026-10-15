# Evidence-first reader validation

> Execute inline using superpowers:executing-plans and test-driven-development. The user's WP0–WP6 specification and renewed instruction to proceed govern this continuation.

Goal: test the single allowed authored evidence-first prompt on the untouched 64-question validation pool, then obey the frozen admission result.

Architecture: extend only the new reader_recovery adapter with explicit protocol/condition dispatch. Reuse its continuous supervisor, isolation, request transaction, closure and actual scorer. Preserve diagnostic snapshots and historical global prompts. One local 4B model, same ten original paragraphs, same decoder and caps, no cache or retries.

Ruling: the earlier report deferred any prompt test until human adjudication. The specification requires reporting unresolved semantic validity and retaining strict scores; it does not prohibit a new strict-benchmark experiment. The user's renewed instruction authorizes proceeding. Human certification and semantic endpoint changes remain unavailable. The many answer-correct/citation-wrong outputs and blind bridge-omission observations support testing citation generation. The absent sentence-only improvement still rules out the paid selector here. Cost if wrong: a fully accounted 128-call negative screen; no routing/final sample is spent.

Ruling: the old 19:30 window is an immutable execution record. This separately identified continuation uses a 21:00 UTC administrative cap after renewed authorization, with the same memory reserve. It is not an invented deployment requirement.

Protocol: reader-evidence-first-v1. Use exactly the prior 64 validation IDs, no resampling, 128 assigned calls. Keep the prior 32 exposed and future 128 excluded. Pair baseline and candidate within questions; prespecified blocks of eight questions have four of each first condition, hash-randomized question order. One greedy repetition, no semantic retries, no added decoding budget. Examples are invented bridge/comparison facts, never benchmark-derived. Citations precede answer in the same accepted JSON schema.

Admission: existing four simultaneous zero-margin quality guards versus unchanged-ten (also the selected comparator), plus strictly positive strict-EM lower bound from that family, complete closure, valid identities, and no new invalid-output/failure count relative to baseline. Report actual time/quality tradeoff; no efficiency claim. A 64-question bounded screen targets a large capability change; enumerate detectable rescue/harm thresholds before outcomes, disclose sparse precision and do not promise power for small effects. If not admitted, conclude this candidate failed/inconclusive; do not launch WP4/WP5 or buy more labels. If admitted, freeze the next headroom/learnability design before collecting any new outcomes. Operational success remains unassessable.

Tasks:

- [x] Test prompt dispatch, baseline byte parity, authored examples and unknown-condition rejection; observe RED then implement.
- [x] Test exact balanced assignment, source/condition identity and reservation handoff; implement new protocol preparation without Gold projections.
- [x] Extend shared transaction/closure/scoring tests to the new two-condition natural-only protocol; test admission cannot be won by identical/all-zero outcomes.
- [x] Freeze source and run full native suite:1117 passed, zero skips,317.66s; independent technical/usefulness/stress review completed before assigned generations.
- [x] Prepare/index/preflight the fresh root, forecast all prompt lengths and execution resource use, run all128 calls, close before Gold, score twice in fresh processes.
- [x] Apply the frozen gate: strict endpoint positive, answer preservation unresolved, full admission false. No WP4/WP5 launch or final-pool use. Retain complete evidence and report separately from reader_recovery_v1.
- [x] Seal future reservations, verify1119 native tests with zero skips and retain private byte-verified archives. Deliver on a local branch while preserving historical main.

Review fix ledger:

- Forecast tokenization must match actual generation (`add_special_tokens=False`): RED/GREEN tokenization regression and full suite passed.
- Forecast coverage, pre-answer continuous-domain timing and each paid prompt/token identity must bind before Gold: RED/GREEN authored transaction regression and full suite passed.
- Ruling: strict-quality admission does not establish acceptable cost. The broad reader-improvement claim stays false; report strict-benchmark quality separately and leave cost acceptability unknown. Cost if wrong: a slower candidate could be mislabeled useful; separate flags prevent that claim.
- Every actual paid entry, including warmup after model acquisition, now has a retained reserve check: RED/GREEN wrapper regression and full suite passed.
- Per-request resource/deadline admission now lies inside the new validation request interval; authored callback timestamps verify that nesting.
- Ruling: the live-checkout denial also denies an inherited working directory. Keep the failed native preflight and invoke from the fresh allowed root; the second actual native probe passed17 file denials and network denial. This is an explicit invocation constraint, not a relaxed sandbox.
- Deferred minor: the outer launcher journals its completed envelope after child return. Outer death can leave that envelope unknown; no full-cost or partial-schedule efficiency claim is allowed then. Actual completion must be verified before reporting.
- Deferred minor: CLI top-level description retains the recovery-v1 wording; `prepare-validation --help` explicitly identifies the new protocol stage. No source is changed after freezing to polish this description.

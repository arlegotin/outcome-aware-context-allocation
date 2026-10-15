# Reader recovery v1

This is a new bounded research diagnosis, separate from the preserved allocation, citation and 14B studies. `config.json` is an execution record with a finite October 15 window, not a ready-to-run template for future work. Operational requirements were requested; none were supplied. No operational-success claim is authorized by this design.

Before any assigned generation, reserve 32 fresh diagnosis, 64 independent validation and 128 evaluation IDs. The latter 128 are a reservation pool, not a powered or frozen final assignment. Exclude original448, followup224, citation320 and reader-study128 reservations, including unexecuted questions and duplicate-group closure. Every new reservation stays excluded from future independent work. Retain `cohorts.json` even if setup or inference fails.

Run the unchanged 4B reader on all32 questions at natural2,5,10 and two explicitly Gold-assisted diagnostic views: complete support documents and annotated support sentences. No Gold answer reaches generation. Sentence views retain complete original Documents as identity/membership objects and render only selected original indices. Natural and oracle groups have separate processes; natural runs first. Profiles deny raw/Gold/history, the other group's outputs, and explicitly supplied earlier setup roots. No final/validation task text is exported to serving.

Use one greedy repetition, unchanged model/template/settings, no cache, repair or semantic retry. Strict joint EM remains answer EM times exact support-set EM subject to output/evidence validity. Report answer/support diagnostics, all failures, Q, mean T and R. Zero successes produce null R with `zero_successes`. Request T starts at adapter entry and ends after durable payload **and receipt** publication; the measuring record's own publication is post-response telemetry. Initial/final synchronization, retrieval, evidence reads, rendering, generation, parsing and durable output are inside T. Continuous parent supervision is authoritative; worker active timing is diagnostic. Enclosing sessions include setup/warmup/cleanup and must not be added again to their nested service/lifecycle intervals.

The 32-question diagnosis is exploratory. Four prespecified contrasts (sentences−documents, documents−natural10, natural10−natural2, natural5−natural10) report strict and answer harm/rescue bounds with tail alpha .0125. These are diagnostic intervals, not a simultaneous certification across all eight contrasts, reader admission, efficiency or quality preservation. Low precision remains visible. The quality-only union and empirical clairvoyant time/strict-quality frontier are diagnostics; their answer guard is not automatically satisfied.

Maximum future candidate budget is one evidence-first prompt and, conditionally, one paid selector/answer configuration. Neither is admitted or automatically launched here. Require localization/capability evidence and representative blind rubric review first, then a separate frozen independent validation protocol with useful supported-answer improvement and honest cost/quality uncertainty. Do not expand allocation labels on this diagnosis. Allocation learning and final comparison retain the user's full comparator, interval, zero-margin guard and accounting requirements.

The implemented new CLI is `python -m outcome_poc.reader_recovery`:

```sh
python -m outcome_poc.reader_recovery --help
python -m outcome_poc.reader_recovery prepare --help
python -m outcome_poc.reader_recovery run --help
```

Stages are `prepare --config PATH --root NEW_ROOT`, `index --root ROOT`, `verify --root ROOT`, `run --root ROOT --group natural|oracle`, and `score --root ROOT`. Native execution uses the frozen source snapshot and actual macOS denial probes in coordinator and child. Scoring requires the entire160-job assignment and both exact session closures before Gold opens. It recomputes in each invocation and rejects source drift. There is no generic confirmation launcher or automatic interrupted-group resume. A partial group remains unscored with its work retained.

`prepare --selection-from PRIOR_ROOT` is only a software-setup handoff: it requires identical pre-outcome cohorts/config and no assigned jobs in the prior root. It cannot resample or adopt observed answers. Add `--deny-root PRIOR_ROOT` for **every** earlier annotation-bearing setup, including other software-only attempts. The prior roots, indexes and costs remain immutable. This flag is isolation metadata, not permission to ignore old work.

Native controlled suspension is unperformed unless separately authorized. Unit sleep/crash/reboot simulations and a passing suite do not establish useful quality, native suspend behavior or an efficiency advantage. Public benchmark pretraining contamination and annotation ambiguity remain unresolved.

## Completed diagnosis and reproduction

All160 assigned calls closed on32 fresh questions. Natural2/5/10 had0/1/0 strict successes and19/20/22 answer successes. Both Gold-assisted views had3 strict successes. No candidate reader or new gate was admitted. See the [report](../../docs/experiments/2026-10-15-reader-recovery.md), [numeric results](evidence/results.json) and [required human adjudication](annotation-review.md). The64 validation and128 evaluation reservations remain untouched.

The actual final preparation used the same frozen config and cohorts after three software-only setup attempts, and denied all previous roots:

```sh
# Historical execution record; roots already exist and must never be overwritten.
python -m outcome_poc.reader_recovery prepare \
  --config experiments/reader-recovery-v1/config.json \
  --root /private/tmp/oaca-reader-recovery-v1-attempt4 \
  --selection-from /private/tmp/oaca-reader-recovery-v1-attempt3 \
  --deny-root /private/tmp/oaca-reader-recovery-v1 \
  --deny-root /private/tmp/oaca-reader-recovery-v1-attempt2 \
  --deny-root /private/tmp/oaca-reader-recovery-v1-attempt3
```

Actual index, natural, oracle and score syntax was verified and executed against that root. Serving/scoring used its frozen `source/src`, with the retained native Python3.12 environment. The original environment's editable install points at the historical checkout: explicitly setting `PYTHONPATH` is necessary when using it for the new code. Current source additionally authenticates the index directly before Gold; measured source remains immutable and had an explicit retained pre-scoring index admission. These are separate source identities.

The read-only public-safe aggregate builder has no scientific dependencies. Its actual command is:

```sh
python3 experiments/reader-recovery-v1/summarize_evidence.py \
  --root /private/tmp/oaca-reader-recovery-v1 \
  --root /private/tmp/oaca-reader-recovery-v1-attempt2 \
  --root /private/tmp/oaca-reader-recovery-v1-attempt3 \
  --root /private/tmp/oaca-reader-recovery-v1-attempt4 \
  --audit-dir /private/tmp/oaca-recovery-evidence \
  --worktree /Users/artemlegotin/.codex-s/worktrees/a840/outcome-aware-context-allocation \
  --output-dir experiments/reader-recovery-v1/evidence
```

It requires a **new** output directory. For another verification use a different fresh destination, then compare numeric results and authenticated input identities. The manifest timestamp and its own output hash naturally differ. This command independently verifies scored aggregates and all four observed setup-cost inventories; it does not reopen Gold or replace the two fresh actual Scorer passes. Complete project/engineering cost remains unknown. Private scratch evidence must be archived for later authentication and must not be uploaded with this aggregate bundle.

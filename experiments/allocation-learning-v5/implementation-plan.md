# V5 implementation plan

Spec: the user WP0–WP6 contract and protocol.md in this directory.
Global constraints: isolated worktree only; retained history/roots untouched;
no v5 benchmark generation before exact-source smoke/precision/source freeze;
no Gold in serving; model recipe fixed; complete time/call/resource caps.

## Task 1: held-out evaluation

Implement NEW src/outcome_poc/heldout.py and tests/test_heldout.py only, plus a
private-ready CLI tool tools/evaluate_routing_signal.py. Read protocol.md first.
Provide evaluate(rows, training_gold, fit_ids, holdout_ids, output_dir, *,
fit_sizes=(128,256,512), seed=20261018) with genuinely disjoint duplicate groups,
fit-only four-fold inner selection, quantile-level threshold rules, original
fit_gates (including standardized ridge and proxy/shuffled/query/RF), actual
ThresholdPolicy and select_configuration. Source PairedActionRows/Gold are
privileged offline inputs; never imported by serving. All train/inner/holdout
memberships must be recorded; holdout outcomes cannot affect any selected rule,
model/preprocessing parameters, fit sizes or B. Export private manifests and
held-out per-question decisions; public summary must exclude IDs/text/choices.
Use same holdout256 for all fixed prefix sizes; do not touch train.learning_curve.
Inner numeric model cost uses observed action T +.02; endpoint/fixed modes have
zero planning overhead. Final held-out policy cost uses observed complete action
T plus measured individual .choose (conservative includes original fixed routing).
Calibrate random action rate on fit only, deterministic question-hash decisions.
The largest-fit continuation screen and all omitted comparisons match protocol.
Include meaningful tests demonstrating holdout-label perturbation leaves
selection/model state unchanged, duplicate-group exclusion, no zero-success R,
and a real held-out fixture distinct from resubstitution. Small explicit test
estimator overrides are allowed only in tests for speed, never research code.
Do not run native inference, read actual trial Gold, alter other source files,
commit parent changes or spawn agents. Send report to /private/tmp/oaca-v5-heldout-report.md.

## Task 2: acquisition integration

Root implements NEW explicit schema5 allocation-routing-signal-v5 preparation,
schedules fit512/learning_holdout256, exact-source authored smoke2, caps/index
proof, actual fit_extension stage authorization and frozen actual runner.
Authenticate reader admission plus complete v4 screen and fresh score audit.
Carry all mandatory prior roots/Gold parents/audits forward. Preserve v1–v4
semantics and source seals. Native resource cap must be verified by frozen scorer
and external before-Gold gate. Source/assignment/privacy/unsupported-ID negatives
and full suite before smoke. Precision scenarios before outcomes.

## Task 3: execute and conclude

Review both tasks, freeze source/config/cohorts/schedule/precision and budget,
run exact-source smoke, then complete1536 assigned fresh calls and warmup.
Verify closure/caps before Gold, score and independently rescore read-only.
Apply preplanned held-out evaluator once; retain unfavorable results and costs.
Stop or proceed to a separately specified tuning/final protocol only as gated.
Publish allowed aggregates and provenance, archive restricted evidence, preserve
original clean checkout and commit a reviewable local research branch.

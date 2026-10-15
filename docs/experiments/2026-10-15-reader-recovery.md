# Reader recovery v1: citation and target validity before more routing labels

Continuation: the user subsequently authorized proceeding with one unchanged-strict reader test. The separate [64-question evidence-first validation](2026-10-15-evidence-first-validation.md) is now complete. Its strict endpoint improved, but full admission failed on the answer guard. This report retains the earlier diagnosis, source and decisions as they stood before that continuation.

The new diagnosis completed all **160 assigned calls on 32 fresh questions**. The unchanged reader answered many questions correctly but rarely supplied the exact reference evidence. Natural two/ten each had zero strict successes; five had one. Gold-assisted support documents and support sentences each had three. No reader improvement, outcome-trained allocation advantage or operational success is demonstrated.

The project now has a tested recursive index-lineage correction, a separately frozen native diagnostic path and an authenticated fresh recomputation of the historical A03 scores. Those are measurement and software results. They do not turn the research thesis into a positive finding.

## Contract and prospective design

The user supplied no service quality floor, worthwhile saving, deployment volume/horizon or operational workload after being asked. These remain **unknown**, not convenient numerical targets. Work continued as benchmark research. The 19:30 UTC execution cutoff was a finite local research cap, not a deployment requirement or performance target. No new reader/model selection was performed.

The [frozen config](../../experiments/reader-recovery-v1/config.json) registered 32 diagnosis questions, 64 untouched validation reservations and 128 untouched evaluation reservations before assigned outcomes. The 128 are a reserved pool, not a powered final schedule. Candidate caps were one evidence-first prompt and, conditionally, one paid selector/answer reader. Diagnosis alone cannot admit a reader. A later validation protocol would need its own fixed effects/precision, resource forecast, full assignment and admission rule before outcomes.

Reservation reconstruction used actual prepared membership and all historical preparation/study manifests. The original448, followup224, citation320 and reader128 families are disjoint and total1,120 IDs, including unexecuted reservations. Normalized duplicate-group closure and official development exclusion left **88,459 eligible training questions**. The new 32/64/128 reservations were selected once with the recorded PCG64 seed20261015. Three subsequent software-only setup handoffs preserved identical cohorts and made zero assigned generations. All224 new IDs remain reserved. Public benchmark pretraining contamination remains unresolved.

The five arms were natural2, natural5, natural10, complete known-support documents and annotated support sentences. Five was prespecified as a diagnostic intermediate budget; it is not a development-selected final comparator. All arms use the unchanged Qwen3-4B-Instruct-2507 MLX4-bit reader, greedy settings, original tokenizer/template, CPU float32 normalized BGE retrieval and complete original paragraphs for natural serving. No semantic retry, cache, output repair, prefix reuse, enlarged token limit or new model was used.

Oracle projections expose source text and annotated sentence IDs, **never reference answers**. Complete original Documents remain the identity/membership objects; shortened views retain original sentence indices and full-ranking D aliases. The natural process cannot read projections or oracle outputs. The later oracle process cannot read natural outputs. Actual OS profiles deny raw/Gold/historical/live-source paths, prior setup roots and network access in both coordinator and model child. The 64/128 future task texts were never exported to serving.

## New observations under one shared protocol

Every cell below has denominator32, including abstentions and invalid citations. These are the same questions across arms, not160 independent questions. Strict success S is official-compatible answer EM times exact support-set EM, with valid output/evidence membership. E is answer EM. Q=sum(S)/n; R=sum(T)/sum(S).

| Arm | Strict S /32 | Answer E /32 | Q | Mean T (s) | p95 T (s) | R (s/strict success) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Natural2 | 0 | 19 | 0% | 0.8703 | 1.2486 | Unavailable: zero successes |
| Natural5 | 1 | 20 | 3.125% | 1.4241 | 1.7768 | 45.5726 |
| Natural10 | 0 | 22 | 0% | 2.4820 | 3.0968 | Unavailable: zero successes |
| Known-support documents, Gold-assisted | 3 | 25 | 9.375% | 0.9457 | 1.2809 | 10.0878 |
| Annotated support sentences, Gold-assisted | 3 | 23 | 9.375% | 0.7769 | 1.1821 | 8.2874 |

Ratios with one or three successes are descriptive only; no eligible primary ratio interval or efficiency claim is supplied. Oracle timing benefits from privileged evidence selection and shorter inputs. It is not a deployable allocation method. Natural groups ran before oracle groups with separate resident sessions; hashed job order within each group does not remove between-group load/thermal/time confounding.

| Arm | Support EM /32 | Mean support precision | Mean support recall | Mean support F1 | Answer-correct but not strict |
| --- | ---: | ---: | ---: | ---: | ---: |
| Natural2 | 3 | .7344 | .3906 | .4927 | 19 |
| Natural5 | 4 | .6844 | .4167 | .4948 | 19 |
| Natural10 | 3 | .6823 | .4349 | .5073 | 22 |
| Support documents | 6 | .9844 | .5599 | .6885 | 22 |
| Support sentences | 6 | .8750 | .4974 | .6104 | 20 |

All160 generations stopped normally within the existing token limits; longest input2931 tokens and longest output128, against caps8192/256. There were143 `ok`,12 `abstain` and5 `invalid_citation` results. Natural2 had6 abstentions; natural5 had4; natural10 had1 abstention and2 invalid citations; support documents had none; support sentences had1 abstention and3 invalid citations. No timeout, infrastructure error, overflow or truncation occurred in this assignment. Failures' work and denominators remain included.

One natural-ten invalid citation was a malformed citation object; another addressed an index outside the original document. Three sentence-arm outputs cited original indices absent from the displayed view. The renderer retained the original indices and aliases. These are observed output violations, not evidence that reindexing or accepting malformed evidence would fix the reader. There were no generic JSON parse-error statuses to justify syntactic constrained decoding, and no truncation evidence to justify raising output limits.

The diagnostic intervals were fixed before outcomes: four contrasts, strict and answer harm/rescue bounds, tail alpha .0125 per diagnostic calculation, finite-population N88459. They are exploratory individual bounds, **not simultaneous certification across eight contrasts**. The underlying library's `preserved` field is not a new preservation claim.

| Contrast A−B | Strict difference | Strict diagnostic interval | Answer difference | Answer diagnostic interval |
| --- | ---: | --- | ---: | --- |
| Sentences−documents | 0 | [−.1830, .1830] | −.0625 | [−.2307, .1226] |
| Documents−natural10 | .09375 | [−.1128, .2738] | .09375 | [−.1128, .2738] |
| Natural10−natural2 | 0 | [−.1279, .1279] | .09375 | [−.1549, .3138] |
| Natural5−natural10 | .03125 | [−.1276, .1834] | −.0625 | [−.2307, .1226] |

The sentence arm rescued one document-arm strict failure and harmed one success. It rescued no answer-EM failures and harmed two. Sentence localization alone therefore did not demonstrate improvement. This is a small diagnostic, not evidence that localization never matters. The document/sentence oracle contrasts change multiple properties and cannot isolate a single cause.

Correct answers with wrong or incomplete citations are a distinct observed task failure. High reference precision but lower recall in the document arm is consistent with citation omission. It does not establish causal dominance, semantic truth or that all reference sets are adequate. Even clean annotated sentences gave only3 strict successes, so an automatic paid selector is not justified by this result.

## Blind rubric review and unresolved target validity

An auxiliary Codex agent reviewed eight hash-selected outputs from seven questions without method, reference answer, strict score or sampling stratum. Four outputs came from the7 strict successes and four from153 failures. The disclosed expansion weights are1.75 and38.25. Evidence length may reveal the projection type, and repeated questions prevent an independent eight-question interpretation. No population semantic-quality estimate is made.

The reviewer judged seven answers supported by the displayed text and three cited subsets sufficient. Five outputs were tagged as missing a bridge, one as answer-unsupported and two as ambiguous; tags overlap. These are LLM rubric judgments, **not human adjudication or truth certification**.

Two strict-success outputs on the same question were flagged as missing the relation connecting the named characters to the relevant book. One was the complete annotated-sentences view, with every shown sentence cited. Conversely, one strict failure was judged adequately supported but did not match the reference answer string. These flags show why both agreement and semantic evidence need inspection; they do not authorize correcting Gold, substituting a semantic endpoint or treating an LLM review as independent validation.

The [required human review](../../experiments/reader-recovery-v1/annotation-review.md) specifies the exact next adjudication. A private108,060-byte packet contains all eight displayed views, outputs, original ten-document packets and reference annotations, with the sampling key. Its identity is in the evidence manifest. Humans have not performed this review.

Reader candidate selection is therefore **deferred**. An authored evidence-first prompt remains a plausible next bounded intervention if the target and citation bottleneck survive adjudication. It has not been implemented or tested here. The failed one-sentence CHAIN intervention and rejected14B screening candidate were not rerun. No new semantic metric, supervised adapter, larger-model screen or stochastic decoding experiment was introduced.

## Allocation implications and conditional phases

The actual two/ten strict table is32 both-fail, zero two-only, zero ten-only, zero both-success. The unchanged `oracle.headroom` and `oracle_frontier` consequently produce zero strict union headroom. All measured two-paragraph requests were cheaper, so the zero-overhead clairvoyant equal-strict frontier chooses two with27.8483 total seconds and **unavailable R**. That is not a useful zero-quality winner. The frontier does not enforce answer preservation; natural ten has four answer rescues and one harm relative to two.

Low quality headroom does not rule out equal-quality cost savings in general. Here no strict successes or nonzero strict-difference labels exist between the two actions in this sample, the answer guard is unresolved and no absolute operational floor is supplied. There is no evidence to pay for more allocation labels, tune metadata features or train a new outcome gate yet. This is a conditional stop, not proof that pre-answer allocation or outcome supervision cannot work with a capable reader and useful actions.

WP3 reader improvement, WP4 learnability/cost modeling and WP5 final comparison remain **unperformed**. No gate was admitted. The 64/128 pools remain untouched. In particular, there is no new comparison against proxy-label routing, published/tuned Adaptive-k, development-selected intermediate budget, rate-matched random, ridge/query-only/shuffled-label controls or paid post-answer/sufficiency methods. They remain required before their corresponding allocation claims. The incomplete historical full-family run cannot stand in for them.

Any future positive efficiency claim still requires an eligible, prospectively valid interval for R_A−R_B entirely below zero. Savings without measured quality loss additionally require the existing simultaneous zero-margin joint/answer guards against the development-selected comparator and fixed-ten, plus declared failure/latency requirements. A nonsignificant loss is not preservation; the30-success eligibility threshold is not a power calculation. Final n and repetitions must be forecast from suitable development rates and effect/precision requirements before final outcomes. No operational-success claim is possible without actual service requirements and workload evidence.

## Measurement, provenance and observed costs

HEAD was clean `ae1706bb1739c1c0a4e724b33feaa8b01289d292`; the original checkout remains unchanged. New work lives in an isolated native worktree. Actual inference used a frozen dirty source snapshot, not a claim that HEAD alone identifies the implementation:

| Identity | Value |
| --- | --- |
| Actual assigned run | `/private/tmp/oaca-reader-recovery-v1-attempt4` |
| Plan content hash | `90c8f71bcc4deaafb78d57641b73c75306d99faa05f6d8fb810b1f1e04ac1e1d` |
| Measured source inventory hash | `4d358b77276a53abb651c4d2ca88d5dc36074e1717198c9328639ac0f134fd8f` |
| Score file SHA256 | `b45987dd3973f43dbb58696aeedd0526b99bde7752621d0a342aedd0d572bbb4` |
| Lock SHA256 | `e1bd09c1dc51f39bd53e62df6ce79eb2d726b26fa30d486ac3d584f297c2d8c8` |
| Qwen4B revision | `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b` |
| Qwen4B snapshot hash | `ecf7edd130ec9663e80927112f50d4aab12143a43c4a1f4c532f99d0379e1660` |
| BGE revision | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| BGE snapshot hash | `0883c9ca2b589beb4d2ad6150d9c96e7c9400d2f1eadf29ad9542af82601f54a` |

Apple M3 Max, macOS26.7.1 arm64, native Python3.12.9 and36 GiB physical RAM were recorded. The retained environment's51 installed lock entries matched exactly; `pip check` passed. A new venv and dependency reinstall were not performed. Actual reader/encoder asset files were authenticated against retained immutable manifests, not resolved from mutable main. The14B manifest revision was separately inspected but the model was not used. Tokenizer/template assets, every module, config, projection, assignment, per-call prompt/template hash, attempt and closure are bound in the private records; the aggregate evidence manifest exposes hashes without restricted content.

The new adapter explicitly uses `mach_continuous_time`, pinned boot identity, the continuous supervisor and parent/child interval checks. Request T starts at adapter entry before validation/directory creation/initial synchronization and ends after durable terminal payload **and receipt** publication. It includes retrieval, view read, rendering, generation, parsing and final synchronization. The timing-record write itself is post-response instrumentation. Legacy worker active telemetry is diagnostic; it is not subtracted from continuous stamps. The largest observed request continuous/active difference was4.5 microseconds. Native controlled suspension was **not performed**; this agreement does not validate suspend behavior.

Both resident sessions closed with identified workers, quiescence and exact accounting before Gold was opened. Explicit `verify_index` plus full-assignment admission was retained before scoring. Each fresh scorer process recomputed all160 rows with the actual `Scorer`; score, summary and closure bytes matched. Independent aggregate sums were then checked against the exact assignment. After the run, a new pre-Gold index guard was added directly to `closed_records`, with a failing-then-passing real-order fixture. The measured snapshot remains unchanged and reproduction uses it. The current source and measured source are identified separately; no historical seal was rebound.

| Disjoint observed envelope | Seconds |
| --- | ---: |
| All four index setups, including encoder acquisition | 37.1153 |
| Both native launchers, including resident startup/warmup/cleanup | 232.8600 |
| Two fresh scoring attempts | 1.4253 |
| Native preflight probes | .2442 |
| Sum of these observed disjoint intervals | 271.6448 |

The earlier index envelopes were9.3826,9.4153 and8.7465 seconds; the final one was9.5709. They are all retained, not discarded as setup noise. Resident sessions231.4716 seconds and service207.9689 seconds are **nested** inside launcher envelopes and are not added again. Model loads, two actual known-answer warmups and cleanup remain in the session records. General preparation, implementation, repeated tests, review and historical/project adaptation costs are not completely measured; total project cost and incremental adaptation cost remain **unknown**. No break-even is reported. A valid future break-even divides attributable incremental adaptation seconds by positive mean per-query saving, not by a difference in seconds-per-success.

The conservative, overlapping RSS-plus-MLX working-set bound peaked at6,011,342,980 bytes. This is a bound, not disjoint physical-memory accounting. The limit was30,923,764,531 bytes, preserving7,730,941,133 bytes (20% physical RAM, greater than4 GiB). All160 request memory gates passed. Existing system swap was about10.45 GB and did not increase in the recorded group ranges; this is not evidence of a swap-free machine or an operational latency guarantee. Per-arm p99/max and resource ranges remain in the numeric results.

## Historical evidence authentication, kept separate

Read-only `reproduce --scores-only` from the unchanged original checkout independently rescored all3,360 A03 jobs over480 questions. The stored score and analysis digests matched the fresh actual Scorer/analyzer output. This upgrades the accessible A03 aggregates from merely inherited public numbers to authenticated retained scoring evidence in this session. It **does not validate historical wall time**.

| Historical A03 method | Strict /480 | Answer /480 |
| --- | ---: | ---: |
| Outcome GBM | 14 | 150 |
| Coverage proxy | 17 | 155 |
| Fixed ten | 11 | 173 |
| Fixed two | 16 | 143 |
| Rate-matched random | 16 | 149 |

A/B repetitions do not increase n. The original8,640-job assignment remains incomplete at6,510 and the attempted reproduction kept Gold closed. The latest reader-study development closure was verified read-only, not independently rescored here. Its measured source `e5ced9a...` and publication-test repair `1be34ab...` remain different evidence identities. Fresh32-question counts are neither a before/after reader improvement nor comparable estimates on the old480-question population. No revised reader was admitted, so no valid before/after reader-improvement table exists.

## Software checks and the three final reviews

The full supported native suite passed **1,109 tests, zero skips, in322.27 seconds**. It runs the original tests plus real-producer lineage, original-index projection, actual transaction/closure/scoring and authenticated external-evaluator parity tests. The verification log and exact test/source inventories are bound in the [evidence manifest](../../experiments/reader-recovery-v1/evidence/evidence-manifest.json). The [review disposition](../superpowers/reviews/2026-10-15-reader-recovery-review.md) records scope and limits. Seven parity cases execute the pinned official evaluator's actual entrypoint with authenticated bytes; stdlib JSON supplies its optional `ujson` import. These are mathematical software probes, not reader-quality validation. The historical evaluator-provenance constant still describes its old source-derived checks; the new external execution has its own log/source identity rather than a rewritten historical field.

An initial outer-sandbox suite could not access native boot identity. Native execution outside that enclosing restriction was required. Intermediate development runs also caught an authored fixture-directory defect and source edits made while source-binding fixtures were active. The directory was fixed and final verification ran against stable source; failures were retained in private logs, not relabeled as passes.

Three reviews were distinct: (1) independent path/lineage/contract review, (2) a usefulness counterexample review that assumed all code passed, and (3) root failure-stress review against actual regressions and native execution. They found and corrected bypasses, incomplete telemetry/assignment binding, a masked index-check fixture and reporting-cost omissions. [The review record](../superpowers/reviews/2026-10-15-reader-recovery-review.md) distinguishes executed checks from conceptual scenarios. Repeated reviews do not add empirical questions.

## Reproduction and publication

[CLI/design instructions](../../experiments/reader-recovery-v1/README.md), [numeric results](../../experiments/reader-recovery-v1/evidence/results.json), [evidence manifest](../../experiments/reader-recovery-v1/evidence/evidence-manifest.json) and its [closure](../../experiments/reader-recovery-v1/evidence/closed.json) are public-safe aggregates and hashes. Raw benchmark text, Gold, predictions, model files, reserved IDs and qualitative packets remain private. A4,594,278-byte ignored private archive retains all1,579 new setup/run/audit files; every archived file was compared with its source. Its append-only [retention receipt](../../experiments/reader-recovery-v1/evidence/retention.json) binds the archive and public closure. Original model/raw/Gold assets remain in historical storage and are not copied into the archive. A clone alone cannot reproduce absent assets. Restore original bound paths only if absent; never overwrite an existing sealed root.

Verified commands on the retained machine (the fixed window is a past execution record; do not rerun it as a future protocol):

```sh
RECOVERY_WORKTREE=/Users/artemlegotin/.codex-s/worktrees/a840/outcome-aware-context-allocation
RECOVERY_HISTORY=/Users/artemlegotin/Documents/git_alter/outcome-aware-context-allocation
RECOVERY_PY="$RECOVERY_HISTORY/.venv/bin/python"
RECOVERY_ROOT=/private/tmp/oaca-reader-recovery-v1-attempt4

PYTHONPATH="$RECOVERY_WORKTREE/src" "$RECOVERY_PY" -m outcome_poc.reader_recovery --help
PYTHONPATH="$RECOVERY_WORKTREE/src" "$RECOVERY_PY" -m outcome_poc.reader_recovery prepare --help
PYTHONPATH="$RECOVERY_WORKTREE/src" "$RECOVERY_PY" -m outcome_poc.reader_recovery run --help

# After complete closure, from the actual frozen source in fresh processes:
PYTHONPATH="$RECOVERY_ROOT/source/src" "$RECOVERY_PY" \
  -m outcome_poc.reader_recovery score --root "$RECOVERY_ROOT"

# Actual historical read-only scorer reproduction from the original source:
cd "$RECOVERY_HISTORY"
"$RECOVERY_PY" -m outcome_poc reproduce --scores-only \
  --protocol artifacts/protocol-task17-timing/protocol.json \
  --output /private/tmp/oaca-recovery-evidence/historical-a03-reproduction.json

# Native full suite; authenticate this external source before executing it:
cd "$RECOVERY_WORKTREE"
HOTPOT_EVALUATOR_PATH=/private/tmp/oaca-recovery-evidence/hotpot_evaluate_v1.py \
  PYTHONPATH="$RECOVERY_WORKTREE/src" PYTHONDONTWRITEBYTECODE=1 \
  "$RECOVERY_PY" -m pytest -q -p no:cacheprovider \
  --basetemp=/private/tmp/oaca-final-verified
```

The stdlib-only [aggregate verifier](../../experiments/reader-recovery-v1/summarize_evidence.py) was run with all four setup roots. It reads scored rows and independently checks assignment/count/ratio sums, cost-envelope disjointness and authored warmup answers; it is not another Gold scorer. See its implemented `--help` and the experiment README for the exact command.

## Applicable primary references

The [pinned official HotpotQA evaluator](https://github.com/hotpotqa/hotpot/blob/fa3a36370899e1d85822de61e58c85ea19993154/hotpot_evaluate_v1.py) defines the reference metrics; this repository deliberately adds output/evidence validity. [Adaptive-k v3](https://arxiv.org/html/2506.08479v3) remains a required largest-gap/buffer-five/top90% comparator, not evidence that our outcome controller won. [Sufficient Context v3](https://arxiv.org/html/2411.06037v3) motivates separating available evidence from reader correctness. [ALCE](https://aclanthology.org/2023.emnlp-main.398/) and [fine-grained citation rewards](https://aclanthology.org/2024.acl-long.161/) motivate inspecting citation capability; neither validates a substitute semantic endpoint here.

[RASER v1](https://arxiv.org/html/2606.02488v1) uses a paid first answer, whose features/cost cannot be given to a pre-answer policy for free. [DynaKRAG v2](https://arxiv.org/html/2607.06507v2) distinguishes evidence-oriented and outcome supervision for sequential actions; it does not justify rewriting this two-action study. [Apple's continuous-time documentation](https://developer.apple.com/documentation/kernel/1646199-mach_continuous_time) supports the sleep-inclusive clock choice, while native controlled suspend remains untested. The [Qwen4B](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) and [Qwen14B](https://huggingface.co/Qwen/Qwen3-14B) cards describe different model lineages; their sampling advice is not evidence that greedy decoding caused the failed14B screen. No cited paper's headline improvement is claimed as this repository's result.

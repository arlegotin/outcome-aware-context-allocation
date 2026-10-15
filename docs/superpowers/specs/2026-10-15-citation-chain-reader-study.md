# Complete citation chains with one reader call

Status: prospective study; no new study outputs have been generated.

## Question and value

Can one explicit instruction help the existing reader cite the complete evidence chain, without a second model call? The previous fresh headroom study produced only 8 strict successes in 128 full-context answers, despite 69 correct answer strings. Its small qualitative review suggested missing intermediate relations. That is a reason to test a reader improvement, not evidence that this instruction works.

A useful reader improvement would make subsequent context-allocation labels less sparse. This study does not train a controller, establish routing learnability, prove customer value, or replace the original strict metric. A negative or inconclusive result ends this candidate at the declared sample sizes.

## Frozen treatment

Compare two explicit conditions:

- `baseline`: the byte-identical `generation.ANSWER_SYSTEM` and original rendering.
- `chain`: that exact string, one newline, then exactly:

```text
Include the supplied sentences that establish every link from the entities or conditions in the question to the answer, including intermediate entity links and the final answer relation.
```

Keep the concise answer, two-key JSON schema, abstention behavior, full-ranking aliases, original sentence indices and strict parser unchanged. No minimum citation/document count, additional reasoning output, answer repair, judge, semantic retry, or prompt search. Render through a local message adapter delegating once to the real tokenizer; never mutate globals, the resident tokenizer, or rendered prompt text. Baseline parity must be byte-exact. Freeze full system strings and final prompt identities.

Use the existing pinned Qwen3-4B-Instruct-2507 4-bit reader revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`; greedy decoding; context8192, output256, prefill512, generation deadline120 seconds. Use the existing pinned BGE-small CPU float32 normalized384-dimensional encoder, original paragraph windows/ranking and all original reader semantics. Bind actual asset files from `artifacts/provenance/asset-manifest.json`. No new packages, downloads, model changes, paid APIs or inference network.

## Fresh data and sampling

Use prepared official-training representatives, never official-development tasks. Bind the existing preparation manifest and the metadata inventory in `configs/followup-reader-headroom.json`, plus all prior follow-up cohort reservations. Exclude the full original448, prior224 (including24 never executed calibration reservations), all official-development7344, and their normalized-question duplicate groups/aliases to a fixed point. No prior results or Gold enter selection. Metadata reconnaissance found88907 eligible representatives; compact canonical sorted-ID-array SHA256 `7cd2dc2fee7388fef8cc5badd9c64317a91550b6badc0abf394ca99dd98e18a7`. Fail rather than silently select from a changed inventory; record a prospective amendment if reconciliation is needed.

Sort eligible IDs lexicographically. Use `numpy.random.Generator(numpy.random.PCG64(20261015)).permutation(len(ids))`. First64 are diagnosis; next256 are comparison, with disjoint normalized groups. Freeze all320 reservations, the eligible population, generator/version and the complete schedule before new labels are read. The comparison is an SRS-without-replacement design from the remaining88843-question finite eligible population, conditional on diagnosis reservation. This is a seeded pseudorandom operational implementation, not proof of future-workload independence. Shared titles/entities and pretraining contamination remain possible.

After selection is immutable, a separate privileged preparation step may read Gold and emit diagnosis-only support-document IDs, never answers or sentence labels. Comparison question/evidence text and all comparison Gold are excluded from diagnosis review and serving until comparison admission. The serving store has annotation-free tasks/documents; only diagnosis tasks carry the explicitly diagnostic document-ID projection. No gold-aware truncation, reordering or retrieval injection in natural budgets.

## Roster and fixed admission

| Stage | Questions | Cells | Assigned generations |
| --- | ---: | --- | ---: |
| Diagnosis |64|baseline/chain × natural2/natural10/support-documents|384|
| Comparison, if admitted |256|baseline/chain × natural2/natural10|1024|
| Total |320| |1408|

Support-documents uses complete original paragraphs containing annotated support and is diagnosis-only, annotation-assisted, and not deployable. Natural arms always use identical shared ranking and evidence for both prompts. Within each question, hash-randomize cell order using canonical `[20261015,"citation-chain-v1",stage,task_id,condition,arm]`, with stable ID ties; question order follows the frozen sample. Job IDs bind all factors, source/assets/settings, execution mode and repetition0. One call per cell, no answer cache or cross-question/prompt KV reuse. One authored, unscored original-prompt warmup per resident session is separately charged. No additional calibration cohort is needed for this efficacy study; prior timing stability is motivation, not a new timing guarantee.

Close all384 diagnosis jobs before scoring. Admit comparison only if execution is complete and healthy, chain has strictly more joint-EM successes at natural10, and chain has no lower observed answer-EM count at either natural budget. Record an immutable admission receipt with the exact closed-score/summary hashes and decision. This is a development screen, not significance, quality preservation or proof that a failed screen excludes a modest effect. If not admitted, preserve all1024 comparison jobs as deferred and end this candidate. Do not alter the prompt, metric, sample or threshold to rescue it. If admitted, execute the entire1024-cell comparison without interim efficacy peeking or sample extension.

Healthy means every assigned cell has one paid invocation and a validated terminal receipt; no `infra_error`, `timeout` or `context_overflow`; all sessions have verified quiescence and exact endpoints; source/assets/probes/resource gates hold. Parse failures, invalid citations, abstentions and output-cap `budget_exhausted` remain semantic failures and do not disqualify an otherwise healthy comparison. Timing drift is reported and limits cost interpretation; it does not change quality scores or the admission count rule.

An assigned infrastructure/timeout/context-overflow failure ends this candidate's stage permanently, retaining the incomplete schedule and all costs; do not execute its remaining cells or score it as complete. A clean intentional boundary pause, or startup failure before any assigned observation starts, may resume only untouched scheduled jobs after verified quiescence and unchanged bindings. Completed jobs are checksum-verified and skipped. An interrupted started job terminalizes as infrastructure failure and ends the stage. This deliberately conservative policy may sacrifice an otherwise recoverable experiment; it prevents selective retries or an improvised missingness rule.

## Measurement and isolation

Add a separate `src/outcome_poc/citation_study/` package and new ignored run root. Do not change any existing source, frozen config, result, snapshot, manifest or original report. Reuse the hardened continuous supervisor, parser, index helpers, native sandbox and generic transaction/session accounting through explicit versioned compatibility dependencies. Make a fresh index with no ancestry/reuse.

Freeze source commit, source snapshot and working-source identities, inputs, config, prompt registry, seeds, schedule, assets, clock/boot and denial probes. The native launcher must run the sealed source. Both coordinator and spawned model worker deny imports of old and new annotation/scorer modules; native Seatbelt denies network, raw/Gold, comparison inputs before admission, historical artifacts and score stores. Actual nonempty denial probes must succeed before paid work. Keep literal ancestor metadata grants needed by SQLite, without granting directory listing/content. New `__main__` and package imports stay annotation-free. Privileged preparation/scoring run separately.

Authoritative service time includes sleep and starts before fresh query encoding/ranking; it stops after generation, parsing and required payload persistence. Telemetry publication is separate. Use `mach_continuous_time` through existing helpers and synchronize before/after work. The120-second deadline bounds generation transport/device work, not the complete query or session. Record continuous/active drift, order, resource samples, tokens, calls, errors, complete raw predictions and hashes privately. Timing instability prevents an efficiency conclusion; it does not erase valid quality outcomes. No deliberate sleep test or production stationarity claim is implied.

Preserve existing constructor-failure quiescence handling: live or unknown workers block resume even if the local backend assignment failed. Uncertain session endpoints remain null with bounds, including after later quiescence reconciliation. Preserve partial tokens, paid intents, interrupted attempts and all terminal failures. Do not semantically retry. Retrieval failure records a zero-call observation and aborts the stage; timeouts/cleanup failures retain paid outputs and halt an unusable worker. A partial schedule cannot be scored as a smaller complete sample. Validate every assigned factor and receipt before immutable closure and before opening Gold.

## Analysis

Use the unchanged official HotpotQA scoring behavior. Primary comparison efficacy endpoint: paired joint-EM difference `chain − baseline` at natural10. All256 assigned questions remain in the denominator; invalid/abstain/overflow/timeout/infrastructure semantic outcomes score zero. Report the paired four-cell counts, net percentage-point change and two-sided95% finite-population bounds. Use `statistics.paired_quality_bounds` with tail alpha0.0125: four one-sided hypergeometric bounds combined by union bound. Report this conservative interval as such. The finite population is88843, revalidated from preparation. No unpaired interval or degenerate zero-harm bootstrap.

Report natural2 and all diagnosis results as secondary/diagnostic. For the two answer-EM guards (natural2 and natural10), report simultaneous95% paired bounds using tail alpha0.00625 (eight one-sided count bounds). No quality-loss margin is invented. A nonnegative point estimate or nonsignificant loss does not establish preservation. Any positive primary finding must disclose answer-risk bounds, costs and failures. No score override from qualitative review.

For each condition/arm report joint/answer/support EM and F1, support precision/recall, failures/abstentions/truncation, prompt/output tokens, generation calls, mean/p50/p95 continuous warm seconds, paired time changes and seconds per strict success. Ratios use all work divided by all strict successes; zero successes is null with a reason, rendered∞. With one timing repetition and likely sparse success, cost ratios are descriptive: do not claim confirmed efficiency, calibrated safety, or quality-preserving superiority. No ratio Gaussian interval without the original30-success and timing/influence prerequisites, which this design does not promise.

Report engine cost as the sum of disjoint preparation, index setup, resident sessions and scoring envelopes; nested job/warmup/load/lifecycle/resource intervals are diagnostics, not extra summed cost. Keep engine cost separate from unmeasured engineering time, prior asset acquisition, review and full deployment adaptation/break-even.

Independent comparison supporting a positive strict effect earns a local reader finding and a separately frozen allocation-headroom study. A point estimate alone, extra support recall, an oracle-only gain or a failed/uncertain primary interval does not establish routing value. A failed diagnosis ends this candidate without spending the comparison calls. An inconclusive comparison ends at256. No automatic larger model, extra variants or expansion until favorable.

## Deliverables and acceptance

Create prospective spec/plan, tested additive software/config, immutable private manifests/ledgers and aggregate public report `docs/experiments/2026-10-15-citation-chain-reader-study.md` plus machine-readable provenance. List executed/deferred work, actual hardware/assets/source, complete denominators, admission, all cells, uncertainty, failures/costs and the next evidence-triggered step. Recompute closed scores in a fresh process; verify historical byte preservation. Update reader-facing README only from measured results, using the requested writing skill. Keep raw benchmark/model/Gold/prediction material private. Review, commit and push meaningful stages to the already-public current main branch. The prior24-hour cap is removed; do not inherit it. No charger/battery checks or permanent power changes.

# One citation-chain reminder: a mixed development result

The reminder increased exact answer-plus-citation successes with ten paragraphs from **4 to 6 out of 64**, while correct answer strings fell from **43 to 42**. It failed the prospectively frozen development screen. The 256-question independent comparison remains deferred, with none of its 1024 scheduled generations executed. This is neither a confirmed improvement nor evidence of a population-level quality loss.

The [spec](../superpowers/specs/2026-10-15-citation-chain-reader-study.md), [plan](../superpowers/plans/2026-10-15-citation-chain-reader-study.md), [software review](../superpowers/reviews/2026-10-15-citation-chain-software-review.md) and [aggregate provenance](../../artifacts/provenance/citation-chain-reader-study-summary.json) preserve the design, implementation and evidence. The original PoC and prior reader/headroom study remain unchanged.

## What was tested

The previous study found correct answer text alongside incomplete citations. This study tested one cheap intervention: append exactly one sentence to the existing system message:

> Include the supplied sentences that establish every link from the entities or conditions in the question to the answer, including intermediate entity links and the final answer relation.

Everything else stayed fixed: the same local reader, greedy decoding, evidence ranking, original sentence indices, JSON contract and strict parser. There was one answer call per cell, no repair or judge call, no forced citation count, and no answer-cache reuse. Baseline rendering was byte-identical to the original. Strict success means the reference answer **and exactly the reference supporting sentences**; it measures benchmark agreement, not certified truth or proof that the model used its citations.

All 384 assigned diagnosis calls completed on 64 fresh official-training questions: two prompt conditions times natural budgets 2/10 and a diagnosis-only known-support-document control. The control supplies whole annotated supporting documents; it is not deployable retrieval or a truth upper bound. One authored warmup was separately charged. No new controller, label expansion, pooled transfer, second model or dataset was run. There was no new qualitative adjudication or score override.

## Selection and stopping

Preparation reconciled 88,907 eligible training representatives after excluding the original 448 reservations, all 224 prior follow-up reservations (including 24 never executed), all 7,344 official-development representatives, and normalized duplicate aliases/groups. The excluded-ID fixed point contained 8,016 IDs. The sorted eligible-ID hash matched the prospectively specified `7cd2dc2fee7388fef8cc5badd9c64317a91550b6badc0abf394ca99dd98e18a7`.

NumPy PCG64 seed 20261015 permuted sorted eligible IDs; the first 64 became diagnosis and the next 256 the reserved comparison. All 320 reservations, prompt strings and the 1,408-cell schedule were frozen before new Gold projection. Comparison would target the remaining 88,843-question finite population, conditional on diagnosis reservation. Shared entities/titles and possible pretraining contamination remain; these are fresh experimental questions, not demonstrably unseen facts.

The frozen admission rule required healthy complete execution, strictly more natural 10 joint successes, and no lower observed answer count at either natural budget. Execution was healthy and strict successes increased. At ten paragraphs, answer EM fell by one, so admission returned **defer**. No rule, prompt, metric, seed or sample was changed to rescue it. The conservative screen can reject a modest useful effect; it is not a significance test or quality-preservation certificate. Reserved comparison questions remain excluded from future reuse even though no comparison answers were generated.

## All assigned diagnosis results

Every row uses all 64 questions. Counts in the two quality columns are successes. “Non-ok” includes abstention, parsing/citation errors and output-cap failures; a validly formatted wrong answer can still have status `ok`. Full benchmark task failure is 64 minus joint successes. Prompt/output tokens and calls are totals. Costs are descriptive warm service measurements, including retrieval, rendering, generation, parsing and required payload persistence.

| Prompt | Evidence | n | Joint EM count | Answer EM count | Support F1 | Mean / p95 seconds | Seconds / joint success | Prompt / output tokens | Calls | Non-ok |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline |2|64|1|29|0.4634|1.092 /1.548|69.89|27,303 /2,255|64|8/64|
| Chain |2|64|4|30|0.5014|1.167 /1.698|18.68|29,223 /2,431|64|7/64|
| Baseline |10|64|4|43|0.5510|3.006 /4.372|48.10|105,324 /3,295|64|2/64|
| Chain |10|64|6|42|0.5278|3.075 /4.393|32.80|107,244 /3,440|64|4/64|
| Baseline |Support documents|64|1|42|0.6060|1.112 /1.636|71.15|26,320 /2,426|64|3/64|
| Chain |Support documents|64|5|44|0.6121|1.128 /1.514|14.44|28,240 /2,367|64|4/64|

There were 19 abstentions, 5 parse errors, 2 invalid-citation outputs and 2 output-cap failures across 384 observations. No assigned infrastructure error, timeout or context overflow occurred. These are observations on the same 64 questions, not 384 independent tasks. No train/adaptation seconds are allocated to individual rows: no controller was trained, and shared setup/session work remains separately reported.

The added sentence cost 30 input tokens per call. Paired mean service changes were +0.0753 seconds at two paragraphs, +0.0694 at ten, and +0.0165 in the support-document control. Lower observed seconds/success ratios are sensitive to a handful of strict successes. There is one timing repetition per cell, no confirmatory efficiency interval and no demonstrated amortization or deployment break-even.

## Pairing and uncertainty

All results below are **development diagnostics**. The independent primary comparison was not run. Intervals use the frozen finite-population method on N = 88,907: conservative hypergeometric harm/rescue bounds combined by a union bound. Joint intervals use four tails at 0.0125; natural answer guards use eight tails at 0.00625 for simultaneous 95% coverage. They are not independent-proportion intervals or claims about future customer traffic.

| Metric / evidence | Both succeed | Baseline only (harm) | Chain only (rescue) | Neither | Change, percentage points | Conservative interval, percentage points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Joint /2|1|0|3|60|+4.69|[−5.86,+14.43]|
| Joint /10|4|0|2|58|+3.13|[−6.35,+12.09]|
| Answer /2|29|0|1|34|+1.56|[−7.61,+10.68]|
| Answer /10|41|2|1|20|−1.56|[−13.30,+10.50]|
| Joint /support documents|1|0|4|59|+6.25|[−5.21,+16.64]|

Zero observed joint harms does not mean zero harm risk: the natural 10 one-sided harm-count upper bound is 6.61% at the specified tail level. The intervals do not establish either efficacy or preservation. The single net answer loss is a stopping-rule observation, not proof of a real degradation.

A post-score allocation diagnostic also remains sparse. For baseline, two/ten joint outcomes were both 1, two-only 0, ten-only 3, neither 60. For chain they were both 4, two-only 0, ten-only 2, neither 58. Thus the chain reader produced only 2 nonzero outcome-difference labels out of 64; a chooser knowing future outcomes could get 6 successes, equal to fixed-ten quality on this sample. That diagnostic says nothing about whether a deployable controller can identify those two tasks or save enough time. It supplies no cost frontier or learned-router result.

## Execution, cost and provenance

The measured source is `14544f6a6c1c88ce67d647fc616faaf8aef3b6c4`; plan hash `640aa00bfd6b850c168e4e0441027ac10efa3f46e6601b49b927a535fca30a6d`. Hardware: Apple M3 Max, 36 GiB RAM, macOS 26.7.1, native Python 3.12.9. No package upgrades, downloads or paid services were used. The old 24-hour cap did not apply.

Reader: `mlx-community/Qwen3-4B-Instruct-2507-4bit`, revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`; context 8192/output 256/prefill 512/greedy/generation deadline 120 seconds. Encoder: `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, CPU float32 normalized 384-dimensional vectors. Exact asset snapshot hashes/licenses are in aggregate provenance and [third-party notices](../../THIRD_PARTY_NOTICES.md): Apache-2.0 reader provenance, MIT encoder, HotpotQA/processed Wikipedia CC BY-SA 4.0. No raw data/models are redistributed here.

Serving ran from sealed source under native network/raw/Gold/score-store denials, with comparison stores and derived indexes additionally denied during diagnosis. Both coordinator and spawned reader had annotation import guards. Actual kernel probes preceded paid work. The diagnosis index was fresh with no embedding reuse. Ranking/evidence identities matched across prompt conditions, and every assigned cell retained its own real call and receipt. All session endpoints were exact and quiescent; no recovery attempts or task replacements were needed.

The continuous clock includes sleep. Maximum absolute continuous/active drift was 8.875 microseconds; the descriptive drift flag was false. Prompt-pair order was baseline-first 98 and chain-first 94. These checks do not establish thermal or production stationarity. The 120-second deadline bounded generation transport/device work, not the whole query or session.

| Disjoint measured engine envelope | Seconds |
| --- | ---: |
| Preparation |21.264806|
| Diagnosis index setup, including encoder acquisition |13.921338|
| Resident serving session, including load/warmup/cleanup |692.668840|
| Two scoring processes, including validation |30.462317|
| **Total recorded engine envelopes** |**758.317299**|

Job service, warmup, model lifecycle and resource intervals are nested; they are not added again. The total excludes engineering, software tests, prior assets, launcher/preflight outside recorded envelopes, admission, standalone verification, reporting, review and deployment adaptation. It is not complete experiment compute or a customer cost estimate.

348 resource samples recorded peak MLX 3,354,815,568 bytes, parent RSS 460,718,080 and child RSS 1,640,742,912. Unified-memory/RSS counters overlap and are not summed. System-wide swap was already 6,534,922,240 bytes at the first sample and stayed constant across these samples; sampling does not rule out changes between samples.

Fresh-process rescoring reproduced all four score/summary/closure files byte-for-byte. Frozen verification passed. A separate audit checked 5,834 historical source/config/test/run files before inference; final preservation evidence accompanies publication. Raw questions, Gold, predictions, resources and detailed process records remain private. The public summary contains aggregates and hashes only.

Final software verification passed 899 tests with no skips at test-only commit `4eaf940`. All measured source/config modules remain identical to `14544f6`; the later fixture change generated no new scientific observations. Software correctness checks do not establish a quality or efficiency finding.

## Reproduction and next decision

A public clone can run the authored software tests. Authenticating this real run requires the retained private run root `artifacts/runs/citation-chain-reader-v1`, prepared inputs/metadata and pinned assets at their bound paths. Use the recorded source commit or its exact sealed source; never rewrite bindings to accommodate later code changes.

```sh
.venv/bin/python3.12 -m outcome_poc.citation_study verify --root artifacts/runs/citation-chain-reader-v1
.venv/bin/python3.12 -m outcome_poc.citation_study score --root artifacts/runs/citation-chain-reader-v1 --stage diagnosis
.venv/bin/python3.12 -m outcome_poc.citation_study report --root artifacts/runs/citation-chain-reader-v1
```

Scoring appends its new attempt cost while reproducing unchanged score bytes. Do not start comparison after the defer decision or delete failures to resume a terminal stage. Historical configs depend on retained research inputs; they are not an instruction to overwrite existing evidence.

The one-sentence candidate has not earned a larger controller study. A useful continuation requires a better-supported reader/measurement design, followed by fresh allocation labels and strong tuned comparators with charged overhead. This result does not settle all citation approaches or the broader allocation idea. It does remove the justification for treating this reminder as a validated fix or collecting more outcome labels under it now.

**inconclusive**

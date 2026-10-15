# Reader diagnosis and context-allocation headroom

**The fresh study found real reading costs and allocation headroom, alongside a low ceiling for strict benchmark success.** On 128 questions, fixed budgets of two, five and ten paragraphs achieved 5, 7 and 8 exact answer-plus-citation successes. A perfect chooser could reach 12. Giving the reader the known supporting documents in a separate 64-question diagnosis still yielded only 3 strict successes. The next useful experiment is reader/citation and metric-suitability work; more controller training is premature.

This follow-up asks whether the frozen reader can answer with exact supporting citations when the relevant documents are available, and how much a perfect choice among evidence budgets could improve its results. It follows the [original inconclusive experiment](../../artifacts/final_report.md). It does not retrain a controller or change the original results.

## Design and scope

The user removed the original 24-hour cap for this continuation. The [prospective specification](../superpowers/specs/2026-10-15-reader-headroom-followup.md) fixes fresh development questions, settings and stage admission. These are development diagnostics, with no confirmatory superiority or quality-preservation claim.

From 89,131 eligible official-training representative questions, the deterministic selection reserved 64 for diagnosis, 32 for calibration and 128 for headroom. It excluded the original pilot/fit/tuning union of 448 questions, all 7,344 official-development representatives, and normalized duplicate overlaps. Question freshness does not guarantee title/entity separation or absence from model pretraining.

Calibration uses eight of its 32 reserved questions, selected by candidate-text length before outcomes, with two repetitions of each budget. Diagnosis uses all 64 assigned questions at budgets 2, 5 and 10, plus a support-document control. Headroom assigns 128 different questions at budgets 2, 5 and 10. That is 688 assigned generations on 200 unique questions; 224 questions were reserved, and 24 calibration reservations are deliberately unexecuted. Repetitions do not create additional independent questions.

`ORACLE-SUPPORT-DOCS` supplies whole original documents containing the reference supporting facts. A preparation process projects document IDs only. It supplies neither reference answers nor supporting sentence labels to serving. This is an annotation-assisted diagnostic, not a deployable retrieval method. Natural budgets and the control preserve the common full ranking's document aliases and original sentence indices.

Strict success remains HotpotQA joint exact match: reference-answer agreement and exactly the reference supporting-sentence set. Answer exact match is diagnostic. Correct text with different supporting citations can reflect incomplete reasoning, citation selection errors or annotation limitations; it cannot automatically be counted as a cosmetic failure.

## Frozen system

- Reader: `mlx-community/Qwen3-4B-Instruct-2507-4bit`, revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`.
- Encoder: `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, CPU float32 normalized cosine.
- Original prompt/parser, greedy decoding, context 8,192 tokens, output cap 256, prefill steps 512, timeout 120 seconds. No prompt tuning, model change, semantic retries or controller training.
- Hardware: native Apple M3 Max, 36 GiB RAM, macOS 26.7.1, Python 3.12.9 and the existing hash-locked environment.
- A small new index contains 2,224 selected documents. No embeddings or index ancestry are reused. The known historical reuse-consumer defect remains unfixed and outside this execution path.
- Serving runs in a native macOS sandbox denied network, raw/Gold and historical outcome stores; scoring is a separate command after each stage closes.

Authoritative elapsed times and deadlines use Darwin `mach_continuous_time`, which includes sleep. Warm service includes fresh query encoding/ranking, evidence reads, generation, parsing and prediction-payload persistence. Model/encoder loading, one authored warm-up per resident session, index construction, scoring and enclosing session costs are recorded separately. Nested intervals are never added to their enclosing intervals. Legacy active-clock component telemetry is diagnostic only.

## Infrastructure amendment

The first versioned attempt, source `a8b4b5c`, failed before any question reached the reader. All 48 calibration and 256 diagnosis records have zero generation calls and zero prompt/output tokens, with `OperationalError: unable to open database file`. Two separate authored warm-ups succeeded. All 384 headroom assignments were explicitly deferred. These 304 infrastructure terminals are retained; they are not evidence of a reader or allocation failure.

The native sandbox allowed database bytes but denied metadata access to the literal ancestor directories that SQLite uses to resolve its path. Repair `9ddc4ae` permits metadata on those specific ancestors while retaining directory-listing, protected-file content/metadata and network denials. A new native regression exercises the actual index producer, SQLite and ranking under the denied-parent topology. A retrieval failure now retains the first terminal record and aborts instead of consuming the whole stage.

After independent review and 867 passing tests, the repaired attempt froze the exact same cohorts, selected task/document/support-ID bytes and reader/encoder settings in a new root. No question outcome from the failed attempt could influence selection. Both attempts remain separate; no record was overwritten or rebound. Its original source snapshot is retained. The failed attempt's mutable-working-tree source check deliberately ceases to match after the repair; its archived before-repair audit and original snapshot establish its identity.

The failed attempt's recorded disjoint preparation/index/resident-session/scoring envelopes total 93.246 seconds. Debugging and software-test time are additional engineering work, not hidden service savings.

## Calibration

All 48 requests completed without infrastructure, parser or citation-ID errors. All 24 repeated prompt-token, output-token and raw-output pairs matched. The maximum repeated-time ratio was 1.0613 and the median was 1.0162. No request exceeded the prespecified continuous-versus-active clock drift threshold of 0.25 seconds.

Mean warm service times were 0.894 seconds for two paragraphs, 1.417 for five and 2.468 for ten. These eight length-stratified questions establish local timing behavior, not population quality or efficiency. Strict successes across the 16 observations per arm were 0, 2 and 0 respectively; identical repetitions mean those are not 16 independent questions.

## Reader diagnosis: 64 questions

All 256 assigned requests have terminal records. There were no infrastructure failures, timeouts or context overflows. Every arm retains the same 64-question denominator.

| Evidence | Answer EM | Joint EM | Support F1 | Mean / p95 seconds | Seconds per strict success | Invalid outputs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 paragraphs | 27 / 64 | 1 / 64 | 0.543 | 1.193 / 1.817 | 76.337 | 2 / 64 |
| 5 paragraphs | 35 / 64 | 3 / 64 | 0.606 | 1.918 / 2.674 | 40.911 | 0 / 64 |
| 10 paragraphs | 34 / 64 | 1 / 64 | 0.597 | 3.199 / 4.551 | 204.734 | 0 / 64 |
| Reference-support documents (diagnostic) | 37 / 64 | 3 / 64 | 0.645 | 1.234 / 2.014 | 26.334 | 4 / 64 |

Two paragraphs contained all reference-support document titles on 43/64 questions, five on 58/64 and ten on all 64. The support-document control also contained them on all 64, yet achieved only 3 strict successes. This shows low benchmark-supported reader/citation performance in this setting; it does not establish which answers were true or make reference annotations exhaustive.

Among valid outputs with a correct reference answer, supporting citations missed the exact reference set on 26/64, 32/64, 33/64 and 33/64 questions for two, five, ten and the diagnostic control respectively. One further correct answer in the control had an invalid output. The ten-paragraph arm had one output-cap failure. These failures remain unchanged in the primary counts.

A clairvoyant choice among the three natural budgets reaches 4 strict successes, versus 3 for fixed-five. Its answer-only ceiling is 41, versus 35 for fixed-five. Perfect budget selection therefore cannot fix most diagnosis failures under the strict target. The support-document control is not included in that frontier.

Calibration, resource checks and diagnosis timing health passed. Because the diagnosis had nonzero strict successes, the prospectively specified sensitivity gate admitted the entire unchanged 128-question headroom stage. This gate establishes that the endpoint can register successes; it is not a significance, utility or quality-preservation test.

## Supplementary citation review

A post-hoc, enriched review selected eight of the 33 valid, answer-correct but exact-support-wrong outputs in the support-document control. Cases were hash-ordered with a declared seed before their text was reviewed. An agent reviewer first saw the question, supplied evidence, answer and citations without reference labels; its report was saved and hashed before references were supplied.

The observed set differences were six proper subsets of the reference citations and two sentence substitutions. After comparing references, the reviewer judged that six actual citation sets omitted a relation needed to connect the question to the answer. Two were plausible alternative relevant sentence choices, one conditional on document context. A missing-relation case also exposed a possible shorter alternative chain, but the model had not cited it.

These are qualitative agent judgments about eight selected disagreements, not independent truth verification, prevalence estimates or evidence that every benchmark discrepancy is substantive. They support checking citation-chain completeness while retaining annotation/context ambiguity. No primary score changed. Private question, answer, passage and reference text remain unpublished.

## Headroom: 128 different questions

All 384 requests completed and were scored after closure. There were no infrastructure failures, timeouts, context overflows or output-cap failures. Abstentions and invalid outputs remain in every 128-question denominator.

| Fixed budget | Answer EM | Joint EM | Support F1 | Mean / p95 seconds | Seconds per strict success | Invalid outputs | Abstentions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 57 / 128 | 5 / 128 | 0.522 | 1.004 / 1.456 | 25.701 | 0 / 128 | 17 / 128 |
| 5 | 65 / 128 | 7 / 128 | 0.537 | 1.670 / 2.466 | 30.540 | 7 / 128 | 8 / 128 |
| 10 | 69 / 128 | 8 / 128 | 0.565 | 2.780 / 3.990 | 44.484 | 4 / 128 | 4 / 128 |

More context changed which questions succeeded. Between two and ten paragraphs, 3 questions succeeded at both budgets, 2 only at two, 5 only at ten, and 118 at neither. Escalating everyone therefore rescued 5 strict successes and harmed 2, for a net gain of 3. The paired table does not assume that more context helps monotonically.

A clairvoyant choice among two and ten reaches 10 strict successes. Adding five as a third action increases that ceiling to 12/128 (9.375%), versus 8/128 (6.25%) for the highest-quality measured fixed arm. That is 4 additional strict successes, or 3.125 percentage points. These are empirical ceilings on this sample, not an achievable controller result or an estimate for future workloads. Budgets one, three, four and six through nine were not tested here.

The cost frontier starts at each question's cheapest measured action. It then buys the least costly success-increasing switches. The strict frontier runs from 4 successes at 127.129 total seconds to 12 at 132.574 seconds, or 11.048 seconds per strict success at that final point. Fixed-ten takes 355.869 seconds for 8 successes; fixed-two takes 128.506 seconds for 5. This shows idealized cost/quality headroom. The chooser knows future success **and** realized latency and pays no prediction error or routing overhead. It is not a serving baseline. The strict frontier does not impose the separate answer-EM guardrail; the answer-only frontier uses different choices.

The answer-only ceiling is 78/128, versus 69/128 for fixed-ten. That diagnostic does not replace joint EM. There is room to allocate context more effectively, but strict successes and two/ten outcome-difference labels remain sparse: only 7/128 questions have a nonzero strict outcome difference. This experiment has not shown that pre-answer features can identify them.

| Stage / budget | Prompt tokens | Output tokens | Assigned generation calls |
| --- | ---: | ---: | ---: |
| calibration / 2 | 6,302 | 564 | 16 |
| calibration / 5 | 12,100 | 684 | 16 |
| calibration / 10 | 26,426 | 636 | 16 |
| diagnosis / 2 | 26,324 | 2,498 | 64 |
| diagnosis / 5 | 54,927 | 2,999 | 64 |
| diagnosis / 10 | 109,025 | 3,293 | 64 |
| diagnosis / ORACLE-SUPPORT-DOCS | 26,112 | 2,702 | 64 |
| headroom / 2 | 51,860 | 4,533 | 128 |
| headroom / 5 | 109,279 | 5,591 | 128 |
| headroom / 10 | 218,972 | 5,767 | 128 |

## Timing, resources and recorded costs

All three stages passed the prospective drift/instability checks. This supports descriptive comparisons of these warm executions. It does not establish production stationarity, a learned-policy improvement or behavior across a real sleep/wake cycle. Continuous-clock and queued-deadline fault tests cover the clock/supervisor contract; no deliberate system-sleep experiment was run.

Each stage used one resident session and one separately recorded authored warm-up. The repaired run made 688 assigned question generations plus 3 warm-ups. Including the invalid first attempt, there were 5 authored warm-ups; the failed attempt made no question generations.

| Recorded disjoint envelope | Seconds |
| --- | ---: |
| Preparation | 22.201 |
| New index setup | 34.861 |
| Three resident serving sessions | 1293.650 |
| Initial scoring and fresh-process score reproduction | 36.793 |
| Sum of these measured envelopes | 1387.504 |

Service latency, model/encoder loading and warm-up are nested inside the resident-session envelopes and are not added again. The 93.246-second failed attempt is separate. These are recorded engine envelopes, not the complete cost of engineering, launcher/verification/report commands, qualitative agent review or obtaining the previously pinned assets. There is no trained deployment policy, adaptation-cost amortization or measured break-even query count in this follow-up.

Across the three serving stages, peak sampled MLX allocation was 3,367,285,216 bytes. The largest separately sampled parent RSS was 733,609,984 bytes and aggregate child RSS was 2,968,600,576 bytes; they occurred in different stages and overlap unified-memory accounting, so they must not be summed as a physical peak. System swap-in-use was 6,618,808,320 bytes at every sampled point in the three stages, including their first/last samples. This was existing system swap, not measured project-created swap. Sampling was every two seconds and cannot exclude shorter transients or activity between samples.

## Provenance and reproduction

The measured v2 study used source `9ddc4ae0b50aebf115ccf2679d39d1bf296ba0fb`; plan hash is `c105dfabbdb0611832e55444fc340b201b063986792b338746ea606e42f9bf65`. Its new physical index manifest hash is `70cf7f872d58bafb2ce1141d0881c5b49fcfdd7ac8cd17dfa2372dc7f600e3f2`. Both versioned attempts retain their source snapshots, and all 37 bound source files in each snapshot match its recorded Git commit. The original protocols' 22 and 26 source bindings and protocol-file hashes remain unchanged.

That measured source passed **867 tests with zero skips** in 118.86 seconds on native macOS, including actual sandbox/SQLite ranking, isolation and interrupted-session checks. At the same source version, all three stages were rescored in separate fresh processes; all nine score/summary/closure files matched byte-for-byte. Verification checked frozen source, inputs/assets, index, jobs and stage closures. The [aggregate receipt](../../artifacts/provenance/followup-reader-headroom-summary.json) contains counts, tables, frontiers, hashes, resource observations and verification evidence without benchmark text.

To authenticate the raw v2 results, use a checkout of the recorded `9ddc4ae` source at the original absolute paths bound by its plan, with the retained private data, assets and closed run present. From that checkout, the relevant commands are:

```sh
.venv/bin/python3.12 -B -m outcome_poc.followup verify --root artifacts/runs/followup-reader-headroom-v2
.venv/bin/python3.12 -B -m outcome_poc.followup score --root artifacts/runs/followup-reader-headroom-v2 --stage calibration
.venv/bin/python3.12 -B -m outcome_poc.followup score --root artifacts/runs/followup-reader-headroom-v2 --stage diagnosis
.venv/bin/python3.12 -B -m outcome_poc.followup score --root artifacts/runs/followup-reader-headroom-v2 --stage headroom
.venv/bin/python3.12 -B -m outcome_poc.followup report --root artifacts/runs/followup-reader-headroom-v2
```

Verification deliberately rejects mismatched source or inputs. The later hardened source intentionally fails v2's mutable-working-tree source binding; neither the archived snapshots nor the plan have been rebound. As a separate read-only archive check, the retained inventories and recorded Git commits can authenticate file hashes and source snapshots without executing inference or scoring. Such an audit does not reproduce raw scores. After hardening, that audit matched all 1,303 v1 and 4,431 v2 inventoried files and both sets of 37 source snapshots against their recorded commits.

Post-study software hardening at `c1c1720264eb0b537645cad6db25ad7be618e58c` fixes uncertain cost accounting when reader construction fails and leaves an owned worker alive. No recorded v1/v2 session took that failure path. This version was not used for the measured study or its rescoring; its separate native suite passed **869 tests with zero skips** in 114.66 seconds. Its test receipt and archive-audit hashes are recorded separately under `post_study_hardening` in the aggregate provenance. These software checks add no measured study outcomes or engine costs.

Repeated scoring adds a separate measured scoring-attempt cost, while immutable score outputs must remain identical. A public clone does not contain the private run, benchmark stores, historical exclusion metadata or model weights. It can run authored software tests and inspect the aggregates. The commands above authenticate the retained study; they are not a turnkey public rerun or authority to overwrite historical outputs. New studies need fresh roots, manifests and an independently frozen protocol.

## Decision and next experiment

The first two continuation stages are complete. Longer runtime has produced a clearer diagnosis, not a demonstrated controller improvement. Reading fewer paragraphs saves real warm service time, and perfect budget choices leave empirical cost/quality headroom. Reliable selection from observable features, quality preservation against strong tuned baselines and adaptation economics remain unproven.

Pause controller-label expansion. If continuing, freeze a separate reader/citation and metric-suitability study on fresh development questions. Compare specific changes against the current reader contract, inspect complete citation chains and annotation alternatives, and charge every extra selection or verification call. A reader, prompt, precision or metric change requires new paired outcomes; the historical controller labels cannot silently carry over.

Only after that stage produces an informative, useful success signal should the project collect more outcome labels and compare the learned gate against all fixed budgets, Adaptive-k, proxy/query/linear/tree controls and a fully charged post-answer gate. Freeze a new untouched confirmation after tuning; establish both quality guardrails and full costs before making an efficiency claim. Provider/customer workloads and willingness to pay remain separate dependencies.

No new controller, all-k baseline competition, confirmatory comparison, pooled-corpus transfer or precision/model upgrade was executed here. The qualitative review is supplementary and preserves every primary failure. The original report and its invalid speed endpoints remain unchanged.

**Outcome classification: inconclusive. Recommended continuation: reader/citation and metric-suitability study before more controller training.**

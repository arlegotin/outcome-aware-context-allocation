# The larger reader failed its development screen

The pinned, explicitly nonthinking 14B reader did not earn the independent comparison. On the same 16 reused development questions with ten retrieved paragraphs, it produced **8 reference-matching answers and 1 exact answer-plus-support success**, versus **10 and 2** for the 4B control. Both admission conditions failed. The run was operationally healthy and complete; the failure is the frozen empirical screen, not an infrastructure block.

All **96 assigned calls and two separate authored warmups completed**. The 128 fresh questions remain reserved, their 512 comparison calls unexecuted. No confirmation index was built, no new controller was fitted, and no alternative prompt/model search followed this result. The original [allocation findings](../../artifacts/final_report.md) remain unchanged.

This is a small, reused development set. It neither establishes general inferiority of the larger reader nor confirms quality preservation, useful allocation labels or savings. Switching to this larger reader configuration was not enough to clear the next gate.

## Question and frozen design

The original allocation experiment had sparse strict successes and little useful two/ten outcome signal. A citation reminder failed its separate screen. The next bounded question was whether a different reader profile could improve that foundation before spending more compute on outcome labels.

The [design](../superpowers/specs/2026-10-15-reader-quality-comparison-design.md) and [plan](../superpowers/plans/2026-10-15-reader-quality-comparison.md) were committed before actual preparation or generation. The sole candidate first passed its [authored feasibility check](2026-10-15-reader-capability-preflight.md). This study then reran both readers afresh, avoiding historical answer or embedding reuse.

| Factor | Frozen value |
| --- | --- |
| Control | `qwen4b-instruct`: Qwen3-4B-Instruct-2507 MLX 4-bit, revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b` |
| Candidate | `qwen14b-nonthinking`: Qwen3-14B MLX 4-bit, revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`, explicit `enable_thinking=False` |
| Common work | Original answer/citation system prompt, installed template once, greedy, context8192/output256/prefill512, continuous startup/request timeout120 seconds |
| Retrieval | BGE-small-en-v1.5 at `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, CPU float32 normalized; new shared stage index; fresh query encoding/ranking every call |
| Development | 16 IDs selected by the prespecified namespace hash from the prior citation diagnosis64, without correctness/support-rank filtering; arms2,10,known-support-documents |
| Confirmation | Uniform without replacement PCG64(271829) sample128 from N=88,587 eligible training representatives; reserved before development outcomes |
| Execution | 14B block then4B block, frozen by content hash; one resident reader, one repetition per cell; no answer/prefix cache, repair or semantic retry |

These are different April hybrid and July Instruct model lineages, not a controlled intervention on parameter count alone. The known-support-document arm is explicitly Gold-assisted diagnosis: the reader receives complete original documents selected by projected IDs, not reference answers or sentence labels. It cannot override the natural-evidence admission rule.

The pool retained all original 448, followup 224 and citation 320 reservations, including unexecuted questions, and duplicate-group closure. The fresh sorted-ID hash matched `340ac60b947956a03da43fa0a3bead3d1ceb60d39d648f658404bc8262f9fdc0`. Official development questions remained excluded. The reused 16 were already excluded from this population; N was not reduced again. All new 128 reservations must remain excluded from future fresh experiments, even though unexecuted.

Admission required complete healthy execution, strictly more natural-ten joint exact matches for14B, and no lower answer exact-match counts at either natural budget. This is a conservative selection screen, not a noninferiority certificate. Strict success is official-compatible HotpotQA answer EM multiplied by exact support-set EM. It measures reference agreement, not truth certification or evidence use. The 16 questions are reused official-training records; development is their role in this study, not the official HotpotQA development split. Public benchmark pretraining contamination and incomplete support annotations remain possible.

## All assigned results

Every row has all16 assigned questions. Parse failures and abstentions remain in the denominator; no semantic result was retried or removed.

| Reader / evidence | Answer EM | Joint EM | Support F1 | Abstentions | Parse errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4B / two | 6/16 | 1/16 | .452 | 2 | 1 |
| 14B / two | 6/16 | 2/16 | .506 | 3 | 0 |
| 4B / ten | 10/16 | 2/16 | .540 | 0 | 0 |
| 14B / ten | 8/16 | 1/16 | .636 | 1 | 0 |
| 4B / known support documents | 9/16 | 1/16 | .617 | 1 | 1 |
| 14B / known support documents | 10/16 | 3/16 | .715 | 1 | 0 |

Across 96 calls there were 86 `ok`,8 abstentions and2 parse errors, with zero timeouts, overflows, truncated outputs, infrastructure failures or unreceipted attempts. An `ok` output is structurally valid, not necessarily correct. Answer F1, support EM/precision/recall and joint F1 are retained in the [machine-readable summary](../../artifacts/provenance/reader-quality-comparison-summary.json).

At natural ten, 14B rescued one strict success and lost two relative to4B; neither reader succeeded on 13 questions. Answer-only comparison rescued one and lost three, with seven correct under both. Natural-two answer counts tied, but there were two rescues and two harms: equal totals do not mean identical behavior. With known support documents,14B rescued three strict successes and lost one. That mixed diagnostic result does not rescue the failed natural-ten screen.

Within 14B, two versus ten had zero shared strict successes, two two-only successes, one ten-only success and 13 failures under both. A chooser with both future outcomes could reach 3/16, versus 2/16 for the better observed fixed arm. The corresponding 4B union was 2/16, with one shared and one ten-only success. These tiny, clairvoyant development frontiers are not deployable controllers; three nonzero14B outcome differences do not establish learnable or economical allocation.

The independent primary comparison was **not executed**. There is no confirmatory population interval. This report uses observed development counts only; it does not present zero-width census calculations over these 16 as production uncertainty or claim that a nonsignificant difference preserves quality. The frozen128-question protocol and its finite-population quality bounds remain unperformed.

## Costs and resources

Timings start before query encoding and include ranking, evidence reads, rendering, generation, parsing and payload persistence. Accelerator synchronization and continuous/active clocks were recorded. These are descriptive observations from sequential reader blocks, one repetition and a system with existing swap; no efficiency interval, stationarity or production-latency claim follows.

| Reader / evidence | Mean / p95 seconds | Seconds / strict success | Prompt / output tokens | Calls | Failure rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4B / two | 1.051 / 1.529 | 16.822 | 6,583 / 653 | 16 | 3/16 |
| 14B / two | 3.362 / 4.437 | 26.896 | 6,647 / 835 | 16 | 3/16 |
| 4B / ten | 2.980 / 4.981 | 23.840 | 25,100 / 1,127 | 16 | 0/16 |
| 14B / ten | 7.870 / 9.918 | 125.926 | 25,164 / 995 | 16 | 1/16 |
| 4B / known support documents | 1.060 / 1.562 | 16.959 | 6,270 / 673 | 16 | 2/16 |
| 14B / known support documents | 3.380 / 4.380 | 18.026 | 6,334 / 882 | 16 | 1/16 |

Failure rate in this table means a non-`ok` output status (abstention or parse error); benchmark failure is instead one minus joint EM. Ratios charge every assigned failure and divide total seconds by total strict successes. They are finite descriptive ratios here, not supported efficiency comparisons. No action result was replayed to reconstruct service cost. Reader training was zero; no router was trained. Shared preparation took 33.850 seconds, fresh index setup 6.431, and the two resident-session envelopes 258.509 seconds (14B) and 95.217 (4B). Those envelopes already include acquisition, warmup, service, gates and cleanup. Two scoring attempts, including fresh-process reproduction, took 23.967 seconds. The sum of these disjoint recorded intervals was 417.974 seconds. Nested job/warmup/lifecycle times are not added again. Launcher overhead, verify-only reruns, publication, engineering, tests/review and upstream pretraining are outside that sum; it is not complete project compute.

The two authored warmups added 174/41 prompt/output tokens for14B and 170/29 for4B, separately from the table. Assets were already local: no new download. Gate1 separately discloses pinned acquisition bytes and its incomplete full-download timing. No deployment adaptation break-even is established because no saving or admitted policy was demonstrated.

The machine was the same native Apple M3 Max, 36 GiB, macOS 26.7.1, Python 3.12.9. MLX 0.32.3 / MLX-LM 0.32.0, Transformers 5.19.0, NumPy 2.5.4 and the unchanged hashed lock were recorded. All package versions and asset snapshot hashes are in the aggregate summary. Qwen retains Apache 2.0 provenance and BGE MIT; original conversion history limits and dataset terms remain in [third-party notices](../../THIRD_PARTY_NOTICES.md).

| Reader | Peak MLX bytes | Sampled parent / child RSS bytes | Minimum system available bytes | Global swap start → stop bytes |
| --- | ---: | ---: | ---: | ---: |
| 14B | 9,126,748,248 | 694,779,904 / 2,343,354,368 | 5,993,922,560 | 12,454,789,120 → 12,438,011,904 |
| 4B | 3,186,056,364 | 604,291,072 / 2,843,230,208 | 9,768,534,016 | 12,438,011,904 → 12,438,339,584 |

RSS and MLX can overlap; do not add these peaks as physical memory. Global swap is a system observation, not uniquely attributable project allocation. All 100 resource boundaries per reader passed the unchanged conservative project gate. Both coordinator and worker proved 69 actual file denials plus network/import/source-origin checks before acquisition. They denied raw/Gold/history, mutable source and confirmation inputs/index. Both workers closed with known quiescence; there were no failed startup sessions or operational repairs in the actual experiment. The temporary idle-sleep assertion ended with the command; no system/power settings changed.

## Reproduction and decision

Measured source: `e5ced9a9c906517fa0f5107b1c2b5ff8c3beb1e1`; tested source: `0e90291`, with 1,064 tests and zero skips. Reader source and configuration stayed unchanged. A publication-only test fixture was subsequently repaired to remove its private-archive dependency; the full suite at `1be34ab` again passed 1,064 tests with zero skips, and all 30 preparation-file checks passed with private paths hidden. [Software review](../superpowers/reviews/2026-10-15-reader-quality-software-review.md) records the crash-window defect fixed before real execution.

The run's plan hash is `d59dce9dd50e14532b94d50280ea85fe9e816dae205854d5287141057051fc52`. The public summary binds plan, assets, sample/schedule, index, prediction closure, score closure and admission decision by bytes/SHA256. Raw tasks/Gold/predictions/model assets and detailed process files remain private under the [publication scope](../PUBLICATION.md). A clean clone can inspect findings and run authored checks; exact raw authentication requires the retained archive at its bound paths.

With those prerequisites present, the standalone CLI supports `prepare`, `index`, `verify`, `run`, `score`, `admit` and `report`. Reinvoking `run --root artifacts/runs/reader-quality-comparison-v1 --stage development` was verify-only: all 765 retained file identities matched, with zero additional launches/generations. Fresh-process scoring reproduced scores, summary and seal byte-for-byte. Its additional attempt time stayed in the ledger; only that ledger and the derived aggregate report changed. Confirmation remains reserved/unexecuted; never run mutable preparation over this root.

Stop this reader candidate and additional allocation-label collection under this protocol. It did not earn the larger test, much less controller training. Further work would need a separately justified reader/workload or validated measurement change and a fresh protocol. More model size, more labels and a more favorable diagnostic row are not evidence of savings. The original controller's value remains unestablished.

inconclusive

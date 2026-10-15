# Evidence-first validation: a strict-quality gain, incomplete reader admission

The single authored evidence-first candidate produced **19 strict successes versus 6** and **44 matching answers versus 33** on the same 64 reserved validation questions. Mean complete warm request time rose from 2.592 to 2.720 seconds, about4.94%. All 128 assigned calls completed. Two fresh actual Scorer processes produced identical score, summary and closure bytes.

The prespecified strict-quality interval is above zero. The simultaneous answer-EM guard is not: its lower bound is−5.77 percentage points. Consequently the **full frozen admission gate fails**. This is positive evidence for the registered strict endpoint, with answer preservation inconclusive. It is neither an admitted useful reader nor an outcome-trained allocation or operational win. The sample, prompt and interval method were not changed to improve the conclusion.

## What changed and what was held common

The user renewed authorization to proceed after the initial diagnosis. The new [protocol config](../../experiments/reader-evidence-first-v1/config.json) and [implementation plan](../superpowers/plans/2026-10-15-evidence-first-validation.md) were frozen before validation outcomes. They allow exactly one one-pass prompt with authored bridge/comparison examples. No reference answer, fit label or validation example was copied into those demonstrations.

The [new prompt module](../../src/outcome_poc/reader_recovery/prompts.py) uses an invented ship/navigator/badge bridge and invented opening dates for a comparison. It asks for original-index citations first, then the concise answer, in the same accepted JSON schema. This differs from the failed historical intervention that appended CHAIN_SENTENCE. Historical prompt constants and parser behavior are unchanged.

Both arms use the same unchanged 4B model/tokenizer/template revision, greedy decoder, ten natural original paragraphs, CPU BGE retrieval, original D aliases and indices, token limits8192/256, one resident model, no cache or semantic retry and one generation per assigned call. One authored warmup is separate and costed inside the resident envelope. There is no paid selector, draft, post-answer judge or model swap. This comparison therefore does not establish an advantage from avoiding such calls.

The 64 validation IDs were reserved before the earlier32-question diagnosis and used exactly once here. The prior 32 remain exposed, and the final 128 remain untouched. Conditional finite-population N is88,427 after excluding the exposed 32 from the prior 88,459 eligible questions. Hash-randomized question order pairs conditions; each eight-question block has four of each first condition. The 128 calls are64 independent question units, not128 questions.

All 128 prompts were rendered/tokenized before assigned generation. Forecasts use the real backend's `add_special_tokens=False`, original aliases/indices and installed template, with maximum input 2803 tokens. Every paid prompt hash and input-token count matched its forecast; complete forecast coverage and pre-answer continuous timestamps were checked before Gold. Longest generated output was199 tokens. All 128 generations stopped normally; no timeout, infrastructure error, overflow or truncation occurred.

## Before/after under the shared protocol

S is answer EM times exact supporting-sentence-set EM, subject to valid output and supplied-evidence membership. E is answer EM. Q=sum(S)/n; R=sum(T)/sum(S). Every arm's denominator is64, including invalid outputs and abstention.

| Reader condition | Strict S /64 | Answer E /64 | Q | Mean T (s) | p95 T (s) | R (s/strict success) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unchanged baseline, natural ten | 6 | 33 | 9.375% | 2.5919 | 3.6393 | 27.6474 |
| Authored evidence-first, natural ten | 19 | 44 | 29.6875% | 2.7200 | 3.5978 | 9.1620 |

R values are descriptive. Both strict-success counts are below the existing30-success ratio-interval gate, and one greedy timing repetition provides no independently estimated final timing-noise model. There is **no eligible efficiency interval or efficiency finding**. A lower point R is not a validated savings claim. The candidate's mean request latency is higher, despite its lower point seconds per success.

| Diagnostic | Baseline | Evidence-first |
| --- | ---: | ---: |
| Answer F1 | .6195 | .7424 |
| Exact supporting set /64 | 11 | 26 |
| Support precision | .7779 | .8174 |
| Support recall | .5435 | .6404 |
| Support F1 | .5930 | .6879 |
| Correct answer without strict success | 27 | 25 |
| Missing reference supports, total | 78 | 64 |
| Excess reference citations, total | 31 | 28 |
| Input tokens, total | 105972 | 121844 |
| Output tokens, total | 3195 | 2274 |

The candidate adds exactly248 input tokens per question and produces fewer output tokens on this sample. These tokens and all rendering/parsing work are included. Missing/excess reference citations are overlap observations, not causal proof or a semantic support judgment.

Baseline statuses were 62 `ok`,1 `invalid_citation`,1 `parse_error`; candidate statuses were 62 `ok`,1 `invalid_citation`,1 `abstain`. No failed output was repaired or retried, and all its work remains included. The candidate's invalid/runtime-failure count1 did not exceed the control's2; this part of the gate passed.

## Frozen interval and admission result

The prospective rule uses the repository's existing four simultaneous zero-margin quality guards: strict and answer EM against unchanged-ten as the selected comparator and against fixed-ten. Those comparator aliases are identical here and remain conservatively duplicated. Each rescue/harm tail uses .003125. A strictly positive strict lower bound, all four preservation guards, valid full closure and no larger invalid/runtime-failure count were required. No noninferiority margin was invented.

| Candidate−baseline endpoint | Rescue | Harm | Difference | Prespecified simultaneous-family interval |
| --- | ---: | ---: | ---: | --- |
| Strict joint EM | 13 | 0 | +.203125 | [.0009386, .3699096] |
| Answer EM | 13 | 2 | +.171875 | [−.0576747, .3686204] |

The strict table is6 both-success,13 candidate-only,0 control-only,45 both-fail. The answer table is31 both-success,13 candidate-only,2 control-only,18 both-fail. Strict rescue and answer rescue need not concern the same questions.

Before outcomes, exact threshold enumeration showed that64 questions require at least13 rescues with zero harms for a positive lower bound,16 with one harm and19 with two harms. These are precision illustrations, not power calculations. The strict endpoint reaches its bound; the answer endpoint does not. A positive point answer difference does not establish preservation. The answer interval is also not evidence of a demonstrated loss.

The frozen summary's `admitted` and qualified `strict_benchmark_quality_improvement` flags are false because they represent the **entire admission rule**. The separately reported registered strict endpoint has a positive lower bound. Both facts are retained; no flag or gate was rebound after seeing outcomes. Broad reader-improvement, allocation-improvement and operational-usefulness claim flags remain false. Cost acceptability is unknown because actual requirements were not supplied.

## Evidence support and remaining semantic uncertainty

A new auxiliary agent reviewed eight hash-selected outputs from eight questions, blind to condition, reference and strict score. Four came from 25 strict successes across both arms and four from 103 failures. Expansion weights are6.25 and25.75. After unblinding, seven selected outputs were candidate and one baseline, so this is not a balanced semantic method comparison.

The reviewer judged four answers supported by their displayed packet, three cited subsets sufficient and all eight citation memberships valid. Overlapping tags were two missing bridges, five missing final relations, one excess citation, four unsupported answers and three ambiguities. Three cases had no tagged problem. These are auxiliary LLM rubric observations, not independent human truth certification or a replacement benchmark endpoint. Unsupported means the supplied text did not establish the complete answer, not that an answer is factually false.

Three sampled strict-success outputs were judged adequately supported; one strict-success output was flagged as lacking support even in the full ten-document view. That flag needs human adjudication. No Gold or score was corrected. Together with the prior diagnosis's annotation flags, it prevents calling exact-set agreement a semantic certificate. Question/citation generation can still fail despite matching a reference.

The measured support-EM/F1 and answer improvements are consistent with a useful citation-generation intervention, but do not isolate examples, ordering, instructions, compact JSON or answer reasoning as the cause. There was one complete bundled candidate, not an ablation. Public benchmark contamination remains unresolved. The representative-review rubric and private adjudication packets remain available; human review has not occurred.

## Accounting and measurement

Actual inference used frozen plan `2c130a656badd6f8c696f1e05b171cf33b8cb57d027ab5754a465ff68af733cf` and source inventory `2c8c94a030b1e8799fe402b784f86b0cbe442eef6f534a982cebd1bd86f24088`, based on `ae1706bb1739c1c0a4e724b33feaa8b01289d292` plus the bound dirty source. Score-file SHA256 is `ed1544b85b4b99c57b27036ed8e2b06974ce20c325284880e296d3bda7d8304c`. Model/encoder revisions and actual file identities are unchanged from the [initial recovery report](2026-10-15-reader-recovery.md) and reauthenticated during preparation. No mutable main revision was resolved.

Native Apple M3 Max/macOS26.7.1 arm64/Python3.12.9 and the unchanged lock were used. The pre-inference full native suite passed 1117 tests, zero skips,317.66 seconds, with authenticated external official-evaluator parity. Frozen source was compared bytewise with the tested live source before generation and had no drift. After collection, a separate preparation-only reservation guard was added and tested; its delivered source is identified separately. The measured snapshot and both scorer outputs remain immutable.

Continuous parent supervision, boot identity, synchronized model calls and owned-worker quiescence were reused. Request T includes resource/deadline admission, retrieval, rendering, generation, parsing, synchronization and durable terminal **and receipt** publication. Its measuring-record publication is later instrumentation. Model acquisition, authored warmup, all prompt forecasts, per-request admission/paid checks and cleanup remain in enclosing resident/launcher costs; nested intervals are never added twice. Legacy active telemetry is diagnostic, not authoritative.

| Observed disjoint envelope | Seconds |
| --- | ---: |
| Preparation after fresh-root creation | 10.3248 |
| Fresh no-reuse index plus encoder acquisition | 13.4592 |
| Native launcher including resident session | 352.9799 |
| Two fresh scoring attempts | 1.4725 |
| Both preflight attempts, including failure | .1431 |
| Sum of these observed intervals | 378.3796 |

Resident 352.0808 and service 339.9621 seconds are nested inside the launcher. Their difference includes loading, warmup, forecast/setup and cleanup. The earlier diagnosis's271.6448 observed seconds remain separately retained; these disjoint research envelopes total 650.0244 seconds. This is **not total project cost**: general setup before recorded envelopes, implementation, tests, reviews and historical adaptation remain unknown. All failed preflight work is retained. Attributable incremental adaptation cost and any break-even remain unavailable. No seconds-per-success difference is used as an amortization denominator.

All 257 request/paid memory-admission gates passed, with a maximum observed conservative overlapping RSS-plus-MLX bound 6,716,761,796 bytes against 30,923,764,531, preserving a7,730,941,133-byte project reserve. RSS and MLX are not claimed to be disjoint physical memory. Of435 resource samples,3 background samples were unavailable during zombie-PID enumeration races. They remain missing, not zero. Thus the observed maximum is not a continuously certified peak. Available system swap observations ranged9,402,580,992–9,410,969,600 bytes; this was not a swap-free machine.

The first preflight failed before any model call because the live-checkout denial also denied the inherited working directory. The unchanged profile passed 17 file-denial probes and network denial when invoked from the allowed fresh root; the actual run used that working directory. Both coordinator and model child enforced isolation. Both failures and the invocation constraint are documented rather than weakening the profile.

No controlled native suspension or actual reboot experiment was performed. Simulated clock/deadline/crash tests do not establish native suspend behavior. The outer launcher writes its complete envelope after subprocess return; an outer death could leave that cost unknown. This run returned successfully with complete receipts, lifecycle and quiescence; no incomplete schedule was scored.

## Completion, conditional stop and retained pools

WP0/WP1 safeguards and the WP2 diagnosis are delivered, and WP3's single justified evidence-first candidate has now completed independent validation. The candidate shows a registered strict-endpoint gain but does not clear the complete admission rule. It remains an experimental condition, not the silently promoted default reader.

WP4 learning/cost modeling and WP5 final allocation comparison are **not launched**, as required after failed admission. No new two/ten outcome-label acquisition, controller selection or final-data tuning occurred. The full comparator requirements—including proxy supervision, fixed intermediate, published/tuned Adaptive-k, rate-matched random, ridge/query-only/shuffled-label controls and paid post-answer alternatives for avoidance claims—remain necessary for any later allocation claim. Reader improvement alone would not establish router value.

The new [reservation catalog](../../experiments/reservation-manifests.json) records hashes/counts and private paths for all 224 new IDs, including the unexecuted final 128. Delivered preparation rejects completed protocol IDs before creating a root; missing/tampered private reservation metadata fails closed. Future independently named protocols must carry those IDs through duplicate-group closure. This guard was added after outcomes strictly for future preparation; it changes no measured prompt, metric, assignment, interval or result.

The next decisive work is human evidence/annotation adjudication and, if warranted, a separately planned independent validation of the **unchanged** candidate with suitable precision and resources. This is not permission to keep adding observations until the current guard passes. The existing64 result stays final and its gate stays failed. A final allocation sample cannot be spent as more reader development. There is no automatic two-stage selector, larger-model retry or semantic-metric rescue.

## Artifacts and verification

[Commands and design](../../experiments/reader-evidence-first-v1/README.md), [aggregate results](../../experiments/reader-evidence-first-v1/evidence/results.json), [evidence manifest](../../experiments/reader-evidence-first-v1/evidence/evidence-manifest.json) and [closure](../../experiments/reader-evidence-first-v1/evidence/closed.json) bind all assignments, attempts, source, lock/environment, data/reservation metadata, assets, authored prompts, clocks, stage closure and scoring/report identities. Raw task text, Gold, predictions, private review packets and model files are not published. The [retention receipt](../../experiments/reader-evidence-first-v1/evidence/retention.json) binds a private2,845,371-byte archive; all1095 archived files were compared with their sources. Both old and new archives remain ignored/local. Original raw/Gold/model assets remain in historical storage.

Both actual scorer passes ran in fresh processes from the frozen source; score/summary/closure bytes matched. The standalone [aggregate verifier](../../experiments/reader-evidence-first-v1/summarize_evidence.py) independently checks every assigned row, Q/T/R sums and question-level rescues/harms. Its JSONL reader preserves Unicode line-separator characters inside valid strings. Monitoring nulls remain unavailable. These reporting safeguards were checked on the actual data and do not alter scores.

The [three-part review](../superpowers/reviews/2026-10-15-evidence-first-review.md) separates executable contracts, usefulness counterexamples and failure stress, with executed versus conceptual evidence. Review and software-test counts do not add empirical questions. This is a useful new reader result under a strict benchmark endpoint, with the original allocation thesis still unproven.

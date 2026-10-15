# Reader diagnosis and context-allocation headroom

This is a new development experiment after the published, inconclusive study. The user authorized continuation without the original 24-hour cap. Work stays on the current branch, with meaningful commits and subagents. The original protocols, source bindings, ledgers and report remain unchanged.

## Question and scope

Before buying more outcome labels, establish whether the frozen reader can answer with correct sentence citations when the relevant documents are available, and whether selecting evidence budgets has useful quality/cost headroom. This stage produces diagnostic evidence, not a new algorithm, a quality-preservation certificate or a provider benchmark.

Use the existing pinned Qwen3-4B-Instruct-2507 4-bit reader, BGE-small CPU encoder, answer prompt, greedy decoding, 8,192-token capacity, 256 output tokens, 512-token prefill steps, and 120-second generation timeout. No model upgrade, prompt tuning, new learned controller, paid API or inference network access belongs in this experiment. A diagnosed reader limitation can justify a separately designed next experiment; it cannot silently change this one.

## Fresh questions and stages

Use official-training representative questions whose prepared split is `fit_extension`. Exclude the complete old pilot64, fit256 and tune128 union, all official-development questions and normalized duplicates (NFC, casefold, whitespace collapse). Bind the prepared metadata and exclusion inventories. Sort eligible IDs by `(sha256(canonical_json([20261015,"fresh-development-reader-headroom-v1",task_id])),task_id)`.

Freeze the first 64 as diagnosis, the next 32 as calibration and the next 128 as headroom before reading any new annotations or outcomes. Preserve question-level freshness qualifications: document/entity overlap and pretraining contamination remain possible. No task replacement or outcome-based sample extension.

1. Calibration: select eight of the 32 by total candidate character-length order at evenly spaced integer positions including both extremes. For each, execute budgets 2, 5 and 10 twice in deterministic randomized blocks (48 paid generations). Record warm-up/model-load observations separately. These outcomes cannot alter the frozen reader or primary scoring. Calibration is a resource/timing check, not an independent quality claim.
2. Diagnosis: all 64 questions, budgets 2, 5 and 10, plus `ORACLE-SUPPORT-DOCS` (256 paid generations). The latter selects whole original paragraphs containing annotated support, in shared retrieval-rank order, with original document/sentence identities. It is an annotation-assisted diagnostic, never a deployable baseline or controller feature. A privileged preparation process may project only task ID and support document IDs; no answer or sentence-support labels enter serving. Missing/ambiguous support-document mappings fail preparation rather than being guessed.
3. Headroom: all 128 questions, budgets 2, 5 and 10 (384 paid generations). Proceed after the diagnosis is closed and the operational check passes; if the reader/metric is uninformative, preserve the complete diagnosis and explicitly defer this stage with a rationale. No automatic larger model or label collection. Three budgets do not stand for the best of all ten budgets; later competitiveness still requires the original strong baseline roster.

Use prospectively hash-randomized arm order within a question block and deterministic question order. No significance peeking or timing-based task substitutions. The headroom stage is development evidence, not untouched confirmation after tuning on the diagnosis.

## Runtime and integrity

Add a standalone `python -m outcome_poc.followup` interface and new modules; do not edit any historical frozen source. Use a fresh, fail-if-exists run root. Bind exact settings, assets, source/import closure, selected tasks/documents, schedule and support projection. Do not route through the expired historical execution window. Record the new execution as uncapped by that window.

Use Darwin `mach_continuous_time` converted with integer `mach_timebase_info` for all authoritative enclosing timings and supervisor deadlines. It includes system sleep. Record active-clock and UTC observations only as diagnostics, plus boot identity; refuse cross-boot resumption. The unchanged reader/retriever may retain active-clock internals, but those are not continuous components and must never be summed into the new service endpoint. A persistent spawned reader worker remains warm. Enforce continuous deadlines for startup, synchronization and generation using short polls and a deadline check after every message/wake. A result first observed past its deadline is a timeout. Preserve partial outputs and all attempts; do not retry semantic failures.

Warm service starts before query encoding/ranking and ends after generation, parsing and required prediction-payload serialization. Synchronize the accelerator around measured work. A separate timing envelope stores the stop timestamp after payload persistence; timing telemetry follows the stop. Charge retrieval separately on every fixed-arm call; no answer replay or cross-question cache. Record model/encoder loading, indexing, warm-up, scoring, telemetry and failures separately. Never add overlapping parent and child intervals. Retain RSS, MLX peak and swap observations without pretending their sum is disjoint physical memory.

Build a small new index for selected documents with **no index reuse** in a new parent directory/attempt ledger. Verify the producer's actual nested `offline.reuse_sources` exists and is empty, the completion receipt and payload hashes match, and bind the new continuous build envelope. This experiment deliberately does not fix or rely on the historical reused-index ancestry consumers; that existing limitation remains disclosed.

Serving must be a separate local process denied network and all raw/Gold stores (including aliases and historical Gold projections). Give it only selected annotation-free tasks/documents, the support-ID diagnostic projection, assets and the frozen plan. Probe actual OS denials before generation. Keep raw question text, answers and outputs in ignored local artifacts. Compare frozen input/source identities before and after execution. Atomic per-job payload and receipt plus append-only attempts must support interruption without dropping failed work or reusing a mismatched completion. Partial schedules stay incomplete and are not relabeled smaller completed studies.

## Analysis and decisions

Score only closed stage predictions in a separate Gold-enabled command, using the existing official-equivalent answer/support/joint metrics and strict parser semantics. Every assigned terminal prediction, including errors and abstentions, stays in the denominator. Report answer EM, support EM/F1, joint EM, invalid/empty/truncated outputs, tokens, calls, mean/p50/p95 service times, harm/rescue cells and sleep/drift observations. Preserve primary failures; diagnostic annotation review cannot override scores.

For diagnosis, compare the oracle-support-doc control with natural budgets and separately count correct-answer/wrong-support cases. Do not infer that every such case is merely cosmetic: missing a relation can be a real failure. Summaries should distinguish observed categories from unsupported causal explanations.

For headroom, display all three fixed policies and an explicitly clairvoyant empirical frontier. Start at each question's cheapest measured action; consider actions that improve binary success at the smallest incremental cost. The oracle pays measured action costs but has perfect future knowledge and no routing error/overhead. Report both strict joint and answer-only diagnostic frontiers, with no switch in primary metric. Give costs per supported success as sum(time)/sum(success), null plus reason when denominator is zero. No production uncertainty or superiority claim arises from this selected development experiment. Timing instability or sleep makes cost comparisons unresolved even though elapsed work remains visible.

Leave a public, aggregate-only follow-up report with executed/unexecuted stages, exact settings and hashes, complete denominators, headroom, measured costs/limitations, and a next-step decision: reader/prompt study, stronger allocation test, or stop this reader/action/workload direction. Update public-facing entry points only with measured evidence, keeping the original report intact.

Apple clock contract: https://developer.apple.com/documentation/kernel/1646199-mach_continuous_time and https://github.com/apple/darwin-xnu/blob/main/osfmk/mach/mach_time.h. The local symbol and timebase have been probed; sleep/wake timing validity still needs measured health checks.

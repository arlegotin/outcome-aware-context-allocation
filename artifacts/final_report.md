# Outcome-aware context allocation — final report

The fixed main comparison, fresh scoring reproduction, conditional replay, complete failure taxonomy, eight-case diagnostic and pooled-transfer diagnostic are complete. The original full-family assignment remains incomplete and unscored. Whole-branch review: qualified approval; final scoped check/status/archive closure pending.

The experiment has **not established an advantage from training the controller on reader outcomes**. On the same 480 questions, the outcome-trained controller achieved 14 strict successes versus 17 for the proxy-label controller. These sparse outcomes do not support the prespecified primary interval. Neither quality preservation nor a supported quality loss is established by the four simultaneous guards. Both native runs also lost host-suspension time from their clocks, so no wall-time efficiency or break-even claim is valid.

The timing failure is environmental evidence about measurement validity, not evidence that the routing mechanism cannot work. The quality results and diagnostics still indicate what needs attention before buying more outcome labels.

## What was tested and what completed

A cheap controller chooses **two or ten already-retrieved paragraphs** before a local reader answers. The strict target requires both an exact answer and exact annotated supporting citations. Answer-only accuracy is a diagnostic. This is a packet-based HotpotQA distractor experiment, not open-web search.

A* is the frozen outcome-trained GBM (`PRE-OUTCOME-GBM:17:numeric`, threshold 0.0339522174316994). B* is the frozen proxy-label model (`PROXY-LABEL:14:numeric`, threshold 0.801315057689046). Both are cheap learned controllers. Proxy training uses annotated support coverage without requiring paired reader outcomes; common outcome-based tuning still costs. FIT256 and TUNE128 preceded the protected sample. All [246 tuning configurations across 11 families](provenance/task16-development/20261015T015117851969Z/tuning-configurations.json) remain visible; the richer outcome-label strategy was already unproven against the selected proxy in development.

| Collection | Assignment | Actual terminal work | Scientific use |
| --- | --- | --- | --- |
| Original full-family run | 480 questions; 8,640 jobs | Stopped at 6,510 jobs under outcome-blind A04 | Incomplete and unscored; no subset or original family-quality table |
| Separate A03 run | The same 480 questions from N=7,344; 3,360 jobs | All 3,360 jobs closed | Full descriptive quality for A/B, FIXED10, FIXED2 and random; invalid wall timing |

A04 advanced the original operational cutoff from 06:12:52 to 04:30 UTC to preserve the one fixed-size A03 attempt. It did not change either scientific protocol or repair either clock. Original stop was 04:30:00.253260 UTC; A03's last job was 06:59:20.490028 UTC. No third timing attempt, sample enlargement or policy retuning occurred. The six [Rulings and their supersession](provenance/task16-final/rulings-phase2b.json) preserve that history.

A03 used two fresh repetitions per selected A/B method; other methods ran once. Repetitions remain within each question and do not increase n. All repeated same-arm outputs agreed. Native closure retained 3,360 attempts and matching paid start/finish pairs; network attempts were zero and all six OS-denial probes passed. The original assignment remains 480 even though collection stopped.

## Quality, failures and timing limitations

Every row below has the same 480-question denominator. Non-ok counts include abstention, invalid citation, parse failure and budget exhaustion; they are not removed from quality denominators. A/B job-status totals include both repetitions.

| Method | Strict successes / 480 | Answer-only successes / 480 | Non-ok jobs / assigned jobs |
| --- | --- | --- | --- |
| Outcome GBM A* | 14 | 150 | 142 / 960 |
| Proxy-label B* | 17 | 155 | 134 / 960 |
| FIXED10 | 11 | 173 | 38 / 480 |
| FIXED2 | 16 | 143 | 75 / 480 |
| Random mixture | 16 | 149 | 68 / 480 |

The [complete baseline table](baseline-table.csv) also retains support F1, exact repetition/denominator conventions, active-clock latency and tokens, interval availability, and unavailable per-method adaptation costs. Blank adaptation values mean unknown, not zero.

The approved [failure taxonomy](provenance/task16-final/a03-failure-analysis.json) covers every lost job: 3,255 of 3,360. On the first repetition per method, A/B/FIXED10/FIXED2/random lose 466/463/469/464/464 questions. Observed tags overlap; all causal attribution remains unknown, with no inferred retrieval-versus-reasoning split. The [complete local private failure ledger](runs/task16-failure-analysis/all-lost-jobs.jsonl) retains every lost job without changing scores.

The four exact simultaneous guards compare A minus the named comparator. Intervals are percentage points; each tail uses α=0.05/16 with the frozen finite-population calculation.

| Guard | Harm / rescue | Difference | Simultaneous interval |
| --- | --- | --- | --- |
| Strict success vs B* | 4 / 1 | −0.625 | [−2.655, +1.443] |
| Answer-only vs B* | 14 / 9 | −1.042 | [−4.943, +2.900] |
| Strict success vs FIXED10 | 2 / 5 | +0.625 | [−1.743, +2.955] |
| Answer-only vs FIXED10 | 48 / 25 | −4.792 | [−11.234, +1.770] |

All four intervals cross zero. Failure and valid wall-latency nonregression are not established. Nonsignificant loss is not quality preservation.

The primary approximate ratio interval is **unavailable**: A/B have only 14/17 strict successes, below the frozen minimum of 30. Stationarity and influence assessments remain `null`; determinism is `true`. Wall-time validity is independently `false` for both runs. During A03, recorded UTC intervals near 1,000.69 and 996.53 seconds corresponded to only 60.03 and 60.02 performance-clock seconds. Later awake operation or a user's awake promise cannot repair those missing intervals. Transient process candidates matched pytest-related argument strings, but their ownership and workload intensity are unknown; they are not proof of heavy test contention.

For audit only, the following are **active-clock diagnostics, not wall-time performance estimates**. Mean and p95 use within-question averages for A/B. `R = sum(T) / sum(strict success)`; zero success would render infinity/unavailable, never zero. Paid token totals include every repetition.

| Method | Active mean, s | Active p95, s | Active R, s/success | Prompt / output tokens | Paid calls |
| --- | --- | --- | --- | --- | --- |
| A* | 1.913 | 5.137 | 65.590 | 713,234 / 38,822 | 960 |
| B* | 1.583 | 3.236 | 44.688 | 544,716 / 38,014 | 960 |
| FIXED10 | 3.676 | 6.806 | 160.401 | 817,280 / 25,049 | 480 |
| FIXED2 | 1.313 | 2.259 | 39.382 | 204,378 / 17,848 | 480 |
| Random | 1.748 | 4.226 | 52.427 | 321,753 / 19,013 | 480 |

No valid deployment saving is inferred from these numbers. Break-even is withheld because wall timing is invalid and complete method adaptation costs are unknown. Its intended denominator is actual per-query `T_B − T_A`, not a difference in seconds per success. A nonpositive valid saving would imply infinite break-even.

## What the diagnostics show

The prespecified FIXED2/FIXED10 quality oracle has only **20/480 strict successes**, versus 16 for the better fixed budget: four extra successes even with perfect knowledge of both outcomes. The strict four-cell counts are 460 both-fail, 9 small-only, 4 full-only and 7 both-success. That is little observed room for this strict two-budget target.

Answer-only outcomes show more heterogeneity: 32 small-only and 62 full-only cases, with an oracle of 205 versus FIXED10's 173. More context is not monotonically better. This does not establish that the pre-read features predict the useful action, and it does not authorize changing the primary metric after seeing results. FIT256 supplied only 16 nonzero strict outcome-difference labels. The combination of a sparse training target and sparse protected strict successes limits how informative this run can be. [Exact headroom diagnostic](provenance/task16-final/a03-two-budget-quality-headroom.json).

The implemented conditional action-replay analysis completed all 480 traces without errors. Its 1,920 selected A/B direct checks were compatible. Other policy results below reconstruct quality from admitted observed actions; they are **not fresh complete family executions**. Full direct runtime is unavailable for every replay row, so there are no family R values or superiority claims.

| Frozen replay policy | Strict / answer successes | Questions choosing ten |
| --- | --- | --- |
| Linear | 16 / 143 | 23 |
| Outcome GBM | 14 / 150 | 116 |
| Random forest | 14 / 145 | 39 |
| Proxy-label | 17 / 155 | 55 |
| Query-only | 16 / 143 | 27 |
| Shuffled-label GBM | 15 / 148 | 69 |

POST and LLM-family direct protected comparisons are unavailable because the original full-family collection is incomplete. Development POST actually used cache mode `none`; the optimistic prefix-reuse bound was not an executed optimized comparator. Implemented recipes are not evidence of executed comparisons. [Task18 operation report](provenance/task18-a03-operations/report.md).

A fresh agent reviewed eight preselected answer-correct/support-nonexact outputs before seeing their key or Gold. Notes were sealed first, then only those eight Gold records were decoded for adjudication. The diagnosis found four wrong/missing relational-citation cases, two plausibly sufficient but nonexact reference sets, one qualified alternative direct route, and one ambiguous question. One citation-gap case also raised a reference-set concern. These are enriched, agent-assisted interpretations—not population prevalence, a human study, certified truth or corrected labels. All eight primary scores remain unchanged. [Aggregate and evidence hashes](provenance/task16-final/blinded-disagreement-adjudication.json).

Taken together, these observations support diagnosing citation/reader reliability and validating an informative strict target in a **fresh independent protocol before costly label expansion**. They do not establish that richer outcome labels add routing value, and they do not justify a post-test metric switch or rescue run.

## Transfer status, resources and cost boundaries

The prospectively sealed pooled-transfer diagnostic completed all **96 jobs across 32 queries**, then scored only after closure. Its corpus contains 70,092 documents and 70,233 windows: 61,353 newly encoded and 8,880 reused. The same preselected 32 queries are nested within the main 480, so this is exploratory transfer evidence, not an independent sample or a repair of the primary result.

| Pooled method | Strict / 32 | Answer-only / 32 | Non-ok / 32 | Questions choosing ten |
| --- | --- | --- | --- | --- |
| A* | 4 | 9 | 6 | 4 |
| B* | 3 | 8 | 6 | 4 |
| FIXED10 | 2 | 9 | 4 | 32 |

A/B each had 26 ok, five abstentions and one invalid citation; FIXED10 had 28 ok and four abstentions. Within pooled retrieval A rescued one strict case against B and harmed none. On those same 32 questions, packet-to-pooled strict successes changed A 2→4, B 3→3 and FIXED10 1→2. These tiny descriptive shifts establish neither superiority nor quality preservation. Title overlap/fact-title coverage@10 was 0.796875. A separate original-reference content-hash document-ID diagnostic also measured 0.796875, with all 32 mappings unique and none ambiguous; all three methods' top-ten ID sequences agreed on every query. Neither metric certifies semantic truth or sentence-support recall. [Transfer aggregate and limits](provenance/task15-transfer-diagnostics/public-summary.json).

MuSiQue, protected stress/no-context and title-disjoint generalization results are unexecuted. No cross-dataset or open-web claim follows.

The native reuse-provenance defect affects **both the protected-index seal** (`protected.py:292`) **and pooled-index seal** (`transfer_runtime.py:225`): both read top-level `reuse_sources`, while real producer manifests store `offline.reuse_sources`. Their native ancestry inventories are incomplete. The retained [external reconciliation](provenance/task15-transfer-reuse-reconciliation/public-safe-receipt.json) and [pre/post guard plan](provenance/task15-transfer-reuse-reconciliation/generation-inventory-guard-plan.json) cover four direct parents plus one ancestor, including the shared protected index. This qualifies the retained lineage; it does not fix either native consumer or certify its fields as complete. Current vector/score bindings, source and manifests remain as recorded; full cost and adaptation remain unknown. Before another experiment relies on native lineage, correct both consumers in separately versioned source with fail-closed recursive identities and real-producer synthetic integration checks. Do not patch or rebind this experiment. The separate document-ID diagnostic does not change native scores.

The transfer manifest's **file SHA256** is `75ebb9d431a5c62a8bacdb3f8dd89fe8d56824f2cb47e51483b57d67b5c996f5`; its distinct **internal manifest_hash** is `c81c662a7540b4119d65989f8f31471bfd0924f8c38f8c50758767a46fdf7e74`. A mistaken identifier in an initial preflight did not alter/reseal/rebind the manifest. The failed attempt remains accounted. [Identity clarification](provenance/task15-manifest-identity-clarification.json).

Execution used an Apple M3 Max with 36 GiB RAM, macOS 26.7.1 and native Python 3.12.9, a pinned 4-bit Qwen3-4B-Instruct-2507 reader and BGE-small-en-v1.5 embeddings. A03 sampled peak process-tree RSS was 3,121,856,512 bytes and MLX peak 3,367,284,112 bytes. Their overlapping conservative bound, 6,489,140,624 bytes, was below the 30,923,764,531-byte limit. This sum is not a disjoint physical-memory estimate. [Pinned assets/licenses](provenance/asset-manifest.json), [environment](provenance/environment.json), [split audit](provenance/wp1-data.json).

| Recorded interval | Seconds | Boundary and counting rule |
| --- | --- | --- |
| Original outer active envelope | 15,400.918 | Invalid as wall time; contains setup/index/partial jobs; no interior added again |
| A03 outer active envelope | 6,656.832 | Invalid as wall time; contains setup and complete jobs; distinct execution identity |
| Initial A03 scoring command | 51.226 | Separate offline wrapper; its 6.987-second scorer interior is nested |
| Fresh A03 reproduction command | 51.062 | Separate offline wrapper; inner analysis is nested |
| Task18 action replay | 72.215 | Parent includes 70.639-second adapter; not their sum |
| Blind-packet preparation | 1.067 | Separate preparation before blinded review; distinct from postseal agent elapsed |
| Complete A03 failure taxonomy | 0.529 | Separate offline parent interval; no Gold read or reader calls |
| Pooled count attempts | 5.645 failed + 89.828 completed | Separate attempts; worker intervals nested; imports outside measured bounds remain unknown |
| Prospective transfer preparation | 22.858 | Separate native preparation; original sealed manifest retained |
| Pooled full pilot | 875.066 external / 874.832 native | External wrapper counted once; native parent, worker and index are nested |
| Reuse reconciliation | 0.521 | Additional external read-only provenance analysis |
| Pooled generation | 179.531 external / 179.169 native | External wrapper counted once; native interval nested |
| Transfer terminal metadata verification | 0.288 | Separate successful verification; failed verifier/authorizer costs remain unknown |
| Pooled scoring / reference-ID diagnosis | 4.748 / 4.648 | Separate wrappers; native scoring-attempt interval nested within scorer |
| Eight-case postseal stage | 215.634 | UTC interval includes agent reading/reasoning; not local active compute or known financial cost |

The initial [physical inventory](provenance/task16-final/initial-physical-costs.json) has a **partial source-qualified mixed active/historical subtotal** of 28,786.080 seconds before later diagnostics/report work. The [final synthesis inventory](provenance/task16-final/final-physical-costs.json) records 30,086.361 seconds after separately measured transfer/scoring/diagnostic additions, with 12 unknown roots. Later report, archive and review overhead is retained separately; it is not silently zero-filled. Neither subtotal is total project wall time or comprehensive compute. Full project cost and per-method adaptation remain `null`. Unknown historical setup/editing/outer work, the failed root manifest probe and incomplete allocations are not zero-filled. Shared index/vector construction is deduplicated by its original physical identity; independent original/A03 setup and job IDs are namespaced. Proxy adaptation does not inherit paired-reader-label requirements merely because the joint experiment paid them. Pretrained assets, shared setup, common tuning and method-specific adaptation remain distinct.

Dataset provenance is the pinned, unaltered Internet Archive replay authorized by A01, with its recorded license and integrity qualifications; equality to currently inaccessible author-origin bytes is not independently certified. Development v1 ancillary-receipt seals were retrospective, not historical completion-time attestations. Annotation agreement is not truth certification; public pretraining contamination, the core packet workload and small pooled slice, one reader and one machine limit interpretation.

## Reproduction, evidence and next steps

A03 initial scoring used frozen code; fresh-process reproduction reran `Scorer.score` on all closed predictions and the exact assigned Gold, then matched every canonical score and immutable base analysis. It did not return cached `score_run` results. Original reproduction returned unavailable with `gold_opened=false`. [Final technical appendix](task16-final-technical/report.md), [original incomplete appendix](task16-original-initial/report.md), [machine quality summary](provenance/task16-final/a03-initial-quality-summary.json).

For retained artifacts, a fresh reproduction writes a **new receipt outside the frozen runs**:

```sh
.venv/bin/python3.12 -m outcome_poc reproduce --scores-only \
  --protocol artifacts/protocol-task17-timing/protocol.json \
  --output artifacts/runs/reproduction-check/a03-receipt.json
```

It requires retained private datasets, assets and closed run files; sanitized tracked metadata alone is insufficient. Do not rerun mutable setup/index stages over these retained artifacts: the A03 binding includes the shared index-attempt ledger. A new experiment requires fresh roots/configuration and a new protocol. A fresh clone supplies source and sanitized metadata, not the private raw evidence; acquiring and preparing its data is a separate new-run workflow. Immutable assets may be shared read-only when safe.

The latest source verification remains **802 native Python 3.12.9 tests, zero skips**, with clean dependencies and no frozen-source mismatch. Documentation and data assembly do not trigger an automatic broad rerun. [Verification receipt](provenance/task18-full-suite.json).

The [machine summary](summary.json), [remaining-risk ledger](remaining-risks.json), complete CSV and technical appendix agree with this conclusion. Exact process records remain private; the [pre-final process archive](provenance/process-archive/2026-10-14/20261015T081649298357Z/README.md) retains public hashes and all six Rulings. Historical scratch references map to byte-verified archive copies without rewriting scientific inputs. Whole-branch review: qualified approval; final scoped check/status/archive closure pending.

The next useful experiment should first diagnose citation/reader reliability and establish an informative strict learning target on fresh data, then preregister its controller comparison and measure complete wall time on an awake, controlled host. No post-test relabeling, threshold retuning or extra rescue run is warranted by these results.

inconclusive

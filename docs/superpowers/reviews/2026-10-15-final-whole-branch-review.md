# Final whole-branch review

Review range: `cc1b992` → `851846579aad8f384d409de7e53b31c296b4e9c5`.
Reviewer: fresh independent final-review agent, using the specified senior-reviewer rubric.
Package: `.superpowers/sdd/2026-10-14-outcome-aware-context-allocation/review-cc1b992..8518465.diff` (7,232,105 bytes; 27 current source-module sections).

## Scope and evidence

This is the single final whole-branch review. I reviewed in passes: binding requirements and final claims; serving/data/policy/scoring/closure integration; replay/transfer/provenance/accounting; and verification/reproduction/handoff. I used the supplied diff package's file map and inspected the implementation at the exact requested HEAD. This is a risk-focused whole-branch review, not a claim that every line of the 108,159-line package or every retained raw record was independently re-audited.

I read the implementation specification, implementation-plan requirements and terminal status, `research_poc_plan.md`, README, final report, machine-summary structure and claim/result/cost fields, baseline CSV, and remaining-risk ledger. Source inspection covered the data conversion/split logic; annotation-free runtime projections; retrieval/window/reuse production; features/policy permissions; training/model admission and tuning selection; protocol freeze/schedule/source binding; serving, paid receipts, recovery and closed accounting; protected closure/scoring/statistics; report/reproduction; conditional action replay; transfer admission/execution/scoring; and diagnostic scope. I inspected selected tests for exact finite-population bounds, Gold separation, paid-receipt corruption, reproduction and transfer, and the test coverage inventory for recovery, timeout, scoring, reporting and replay.

Read-only verification performed during this review:

- Both `git diff --quiet f12491c6f684250fa2b9ea0df10b6b46368042fd 851846579aad8f384d409de7e53b31c296b4e9c5 -- src tests tools pyproject.toml requirements.lock` and the corresponding working-tree comparison returned 0. The existing full-suite log ends `802 passed in 213.44s`; its native execution receipt records exit 0. Thus its code/test/dependency evidence applies to this HEAD. I did not rerun that suite.
- Rehashed the explicitly bound source inventories in the original and A03 protocols: all 22 and 26 files, respectively, matched. This was a source-identity check, not a new full asset/protocol/scientific audit.
- Cross-checked the public method rows and CSV: five rows, each with 480 assigned questions; selected arms have 960 jobs each, other arms 480 each. Public counts/statuses agree with the readable report. The summary has four quality guards, null primary CI, unknown stationarity/influence flags, invalid wall timing, and all four positive/preservation/loss claims false.
- Inspected the fresh A03 reproduction receipt and its implementation: `reproduce` calls `Scorer.score` for each prediction, then `analyze_run`, and compares canonical digests; it does not rely on the cached `score_run` return. The receipt reports all 3,360 jobs reproduced. This review did not rescore them again.
- Verified the reconciliation sidecar's SHA256 against its public receipt; inspected its executed source, six source nodes (new pooled index plus five historical sources), four direct parents, guard plan, preflight and terminal-verification receipts. The documented generation guards check 34 strict files, three source hashes, and the preserved 388-byte stage-cost prefix with complete appended-parent reconciliation. I inspected these recorded checks rather than rerunning the entire index inventory.
- Confirmed the public physical subtotal is 30,086.36062842137 seconds with 12 unknown roots and null full total. The reused 175.59180962399114 historical seconds are reference-only, not a new pooled charge.

No test suite, scientific generation, index build, model load, download, Gold decoding, original partial semantic-output inspection, or source/HEAD/index mutation was performed. Only this review file was written. The three untracked provenance files present at review start were left untouched.

## Strengths

1. **The final conclusion follows the admissible evidence.** `artifacts/final_report.md:5` and the machine summary say inconclusive. Sparse strict successes (14/17), four intervals crossing zero, and independently invalid wall clocks are all explicit. The report does not turn nonsignificance into preservation or active-clock ratios into efficiency. Original 6,510/8,640 partial work stays incomplete and unscored; A03 repetitions remain within the same 480 questions.
2. **Closure and recovery are substantive, not just output-file existence checks.** `src/outcome_poc/runner.py:548`, `:720`, and `:1132` bind full assigned job sets, attempts, paid start/partial/finish receipts, terminal predictions and shared costs. Uncertified process death blocks inference; observed failed attempts and worker reloads remain charged. `src/outcome_poc/scoring.py:184` and `src/outcome_poc/report.py:249` require complete admission before Gold use.
3. **The scientific boundaries are represented in code.** Serving task/document schemas exclude annotations; learned pre-answer policies reject paid drafts; POST and sufficiency explicitly require paid inputs. Source-bound protocols preserve selected models, methods, sample and schedule. Strong baseline selection retains all eleven development families, uses the common fixed-ten quality filter and allows the proxy model to win. No favorable reselection appears in the final analysis.
4. **Statistics and reproduction are appropriately conservative.** Exact hypergeometric harm/rescue bounds use the declared `.05/16` tail allocation; timing repeats are averaged within questions and covariance is retained. Zero/sparse success and unresolved validity cannot yield a valid primary claim. The exhaustive small-population test checks coverage independently of the bound implementation. Fresh scoring reproduction is implemented and has actual execution evidence.
5. **Attribution and costs are bounded honestly.** The action adapter refuses incomplete original outcomes and missing POST/LLM information, checks action/request/output/token compatibility, and leaves absent representative runtime null. The complete failure taxonomy retains unknown causes. The eight-case review is clearly agent-assisted enriched diagnosis; pooled32 is nested exploratory evidence. Cost inventories distinguish reused origins, nested intervals, separate runs and unknown totals instead of inventing an adaptation or break-even result.
6. **The recorded provenance workaround is specific and reviewable.** The sidecar traverses the real producer schema, validates source payload/ledger/encoder/convention links and preserves frozen native bytes. Its protected-index node also connects the shared lineage used by the main runs. The public report expressly says native metadata was not repaired.

## Issues

### Critical — must fix

None found within the reviewed scope. In particular, I found no new basis to retract the descriptive quality counts or the final inconclusive conclusion.

### Important — should fix

**I1. Native reuse provenance remains silently empty for real producer manifests; this also affects the protected-index seal. Known residual defect, not a newly discovered failure of the completed reconciliation.**

- Locations: `src/outcome_poc/transfer_runtime.py:225` and `src/outcome_poc/protected.py:292`; producer schema at `src/outcome_poc/retrieval.py:434` and `:438`.
- Trigger: an index built by the real `build_index` uses one or more reuse sources. The producer stores these in `offline.reuse_sources`, but both consumers read top-level `reuse_sources` with an empty-list default.
- Effect: native `reused_physical_sources` and related source-hash inventories omit the reused ancestry. Native consumers alone therefore cannot substantiate complete historical lineage/cost ownership, and a future run can repeat this omission without an error. This is an engineering/spec-conformance defect even though final index payload hashes still bind the vectors actually used; it is not evidence that those vectors or current scores are wrong.
- Current-run mitigation: the external sidecar and pre/post guards cover four direct parents plus one ancestor, including `data/index/protected`; preserve the original source/manifests; and do not recharge historical work. The final report, README and risk ledger disclose the limitation. The final physical total and adaptation remain unknown. On that evidence, I accept the workaround for this retained, qualified result. I do **not** certify the native fields as complete or the defect as fixed.
- Remedy: before relying on native lineage in a new experiment, correct both consumers in separately versioned source to traverse the actual nested schema, fail closed on malformed/missing declared reuse, preserve original physical identities and recursive ancestry, and add a synthetic integration test using manifests produced by the real index builder. Do not patch or rebind the frozen experiment to make old fields appear complete. No present-run source mutation or additional scientific execution is required to close this handoff honestly.

### Minor — nice to have

**M1. The safe fresh-run instructions stop before a concrete configuration example.**

- Locations: `README.md:44`–`:46`, `configs/base.json:2`, and the historical path settings in `configs/development.json`.
- Trigger: a new maintainer follows the fresh-checkout setup and then tries to start a new experiment.
- Effect: the README correctly requires new roots, but does not enumerate the configuration fields/ledgers that must move together or give a minimal isolated example. The supplied configurations point at historical roots; a user must reconstruct the new-run path setup from source and the long plan. This does not impair the clearly documented retained-evidence scoring command, and the README explicitly warns against running mutable setup over frozen artifacts.
- Remedy: add a short, nonexecuting example or linked checklist covering fresh provenance, prepared data, indexes and their attempt-ledger parents, development run/training roots, protocol and confirmation roots, and a new deadline. State that historical configs are execution records, not a fresh-run launcher. This is a documentation improvement, not authorization for another experiment.

## Qualified experimental limitations, not additional implementation findings

- Both wall-time endpoints are invalid. The selected primary ratio CI is separately unavailable because strict successes are below 30. A result cannot be promoted by a timing repair, more questions, an extra repetition or another timing attempt.
- The original full-family assignment did not complete. Conditional six-family replay cannot supply missing protected direct POST/LLM results or full representative runtime; optimized POST parity was not established.
- Full project cost and per-method adaptation are unknown. A partial mixed active/historical subtotal is not elapsed project time or a complete compute bill.
- A01 archive-source equivalence to a current author copy is unverified; retrospective development seals have limited historical guarantees. Single reader/machine, public contamination, annotation limitations and packet/limited-transfer scope remain.
- The full lost-job taxonomy is an observed classification, not a causal diagnosis. The eight-case interpretation and nested pooled32 results do not estimate population prevalence, certify truth or independently confirm a benefit.

These limitations materially restrict readiness and claims; they are not dismissed merely because they are disclosed. The spec expressly permits an inconclusive handoff, and the public claims stay within these restrictions.

## Declined to judge

- **Quality of the incomplete original run:** excluded by the explicit no-partial-semantic-access/no-subset-scoring requirement; I did not inspect or infer it.
- **Independent scientific rerun of A03, transfer or all raw ledger entries:** excluded by the review boundary. I assessed source, retained receipts and aggregate consistency, not a second experiment or rescoring pass.
- **Semantic truth of all annotations, eight adjudications or transfer citations:** requires independent substantive adjudication beyond this code/integration review. Existing scores remain annotation agreement, not truth certificates.
- **Current-origin dataset equivalence, contamination and the contemporary research/novelty landscape:** not established by local hashes or this code review; the inherited research ledger is disclosed as such and no new external research was undertaken.
- **Valid wall-time efficiency, complete financial/compute cost and deployment break-even:** unavailable under the recorded clock failures and unknown cost roots; I decline to estimate missing quantities from active timers.
- **Production service readiness, cross-platform support, open-web/cross-dataset performance, customer value or legal/patent conclusions:** outside this local PoC's delivered scope and unsupported by these experiments.

No other considered behavior was silently set aside as outside the spec.

## Recommendations and assessment

Preserve the scientific inputs, original incomplete assignment and raw failures. Complete the coordinator-owned final review/status incorporation and exact post-review process archive; the public “review pending” text at this reviewed HEAD is intentional and is not a finding. Record I1 as a residual with its external mitigation, and address the native traversal only in source for a future separately frozen experiment. M1 can be addressed with a small documentation-only change if useful.

**Spec verdict:** Qualified pass for the specification's permitted inconclusive final handoff. The original full-family execution, valid timing objective and complete adaptation accounting are not complete and must remain so labeled. The A03 comparison, fresh scoring reproduction and bounded explanatory diagnostics have the required reported evidence; I1 is an explicit native-provenance deviation with a reviewed external qualification.

**Code-quality verdict:** Acceptable for preserving and reproducing this local result, with the important known native lineage defect and one minor fresh-run documentation improvement. The existing 802-test evidence applies to unchanged source. No newly identified implementation blocker warrants changing frozen source or rerunning scientific work.

**Ready to merge/hand off? Yes — for the bounded local inconclusive research handoff, with I1 explicitly retained and the coordinator's already planned archive/status closure.** This is not approval to claim an efficiency win, complete native provenance, a self-contained public dataset release or production readiness. No push, merge or publication action is requested or authorized by this review.

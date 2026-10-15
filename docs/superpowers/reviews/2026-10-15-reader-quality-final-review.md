# Final whole-branch reader-quality review

Reviewed base `0dcdd4654cab45aabedd16175c3129443a4a4ddc` through head `5762f51`. This is the one final whole-branch review, applying the Senior Code Reviewer rubric, binding design, implementation plan, ledger, Task 1 review, Task 2 review and its scoped RQR-001 fix review. The ledger contains one prospective startup-only Ruling and no parked/minor findings. RQR-001 is addressed in the reviewed head.

## Strengths

- Preparation preserves the full historical reservation union and duplicate closure, freezes the 16/128 samples before support projection, and gives each reader an explicitly bound profile and leaf while sharing fresh stage inputs/index (`src/outcome_poc/reader_study/preparation.py`, `study.py`). Confirmation admission precedes access to its inputs; its future index has a real denial sentinel.
- Runtime composes existing job transactions and lifecycle primitives rather than replacing the historical runner. It binds native worker identity and reader configuration before acquisition, retains partial constructor state, verifies both leaves before resumption, and holds launch ownership through log closure. The fixed acquisition-to-identity crash window now permanently refuses unknown ownership (`runtime.py:283`). Authored native tests exercise actual sandbox/spawn, reader-profile rejection and concurrent launch ownership.
- Scoring keeps every assigned reader/arm cell, validates closed predictions before Gold, preserves invalid outcomes as joint failures, seals source/Gold/output identities, and correctly orients paired contrasts as 14B minus 4B (`scoring.py`). Independent confirmation uses the frozen finite population and tail constants; timing remains descriptive.
- The report and public aggregate honestly publish a failed, operationally healthy screen. Natural-ten joint counts are 1 versus 2 and answer counts 8 versus 10; two-paragraph answers tie at 6. Known-support-document improvements do not override admission. All 128 confirmation questions remain reserved and all 512 calls remain unexecuted. The reused development sample is not presented as fresh confirmation; public results omit the private development census intervals and make no preservation, efficiency, controller or business claim.
- Cost reporting distinguishes disjoint preparation/index/session/scoring envelopes from nested diagnostics, keeps both scoring attempts, and states omissions from total project compute. Both model lineages, resource observations, strict-reference scoring limits and the unavailable clairvoyant chooser are disclosed.

## Issues

### Critical

None found.

### Important

**RQF-001 — New authored configuration test requires the private experiment archive.**

- **Location:** `tests/test_reader_study_preparation.py:149` (production validation call at line 152); dependency: `src/outcome_poc/reader_study/preparation.py:32`, particularly its file-presence loop at line 41.
- **Problem:** `test_production_config_and_mandatory_metadata_cannot_be_weakened` calls `validate_metadata_inventory(config)` on the real production configuration without supplying authored files. That validator requires every named original/followup/citation metadata path to exist beneath ignored `artifacts/runs/`. Those files are intentionally absent from a public clone. The initial happy-path validation therefore raises before the test reaches its assertions.
- **Impact:** The new test fails in the documented clean-clone software-check workflow and contradicts the plan's authored-fixture requirement. The 1,064-pass result accurately describes the retained research checkout, but its private files mask this new test dependency. This is a publication/test-portability issue; it does not invalidate the measured screen or require additional model calls.
- **Evidence:** `.gitignore:17` excludes `artifacts/runs/`; `git ls-files` returned no tracked entry for the first required original schedule or citation cohorts. A focused, read-only invocation of this exact test, masking only `Path.is_file()` for `artifacts/runs/` as it would be in a clean clone, failed with `FileNotFoundError: artifacts/runs/confirmation/schedule.json`. The reproduction accessed no historical metadata contents. `tests/conftest.py` contains no fixture or collection hook that supplies these paths.
- **Fix:** Supply authored temporary placeholder files at the required relative paths (with the test operating in a temporary working directory), or inject a narrow authored filesystem view. Retain validation of the exact production path inventory and add an absent-required-file assertion. Do not require the private archive or skip the test. Keep scientific source and retained run bindings unchanged; validate the affected test under a filesystem view without historical runs.

### Minor

None recorded.

## Verification and scope

- Read the supplied whole-branch package in bounded segments. Initial combined responses truncated some already supplied prose; recovered the omitted beginning and reviewed all changed implementation/test sections. No broad dependency rereview or model execution was performed.
- Read all four task/ledger records and the software-verification, prepared-audit, verify-only, reproduction and final aggregate evidence. Accepted the recorded full-suite result of 1,064 passed, zero skipped, 319.49 seconds at `0e90291`; independently verified its log SHA256 and all 140 recorded source/test/config/lock identities against the current files. No suite rerun was needed.
- Independently checked all 13 public evidence byte/SHA256 references and all 671 files bound by the actual development closure: zero mismatches. Files with benchmark content were streamed only into hashes; their contents were not inspected or interpreted.
- Compared public cell aggregates, physical totals, session aggregates and decision fields with the private aggregate: all matched. Confirmed schedule metadata has 96 observations/16 tasks and 512 observations/128 tasks in the frozen reader-block order. Confirmed no confirmation index build, admission file, paid assigned call or warmup; its real denial sentinel remains present.
- Read native session/resource/probe metadata: one exact successful session per reader, 100 passed resource boundaries per reader, and both coordinator/worker receipts reporting 69 file denials plus network/source-origin checks. Independently recomputed recorded resource peaks; they match the public summary. No failed startup exception was used in this actual run.
- The one additional behavior check was the narrowly scoped clean-clone test reproduction described in RQF-001. No source, config, scientific result, git index, branch or HEAD mutation occurred. Only this review report was written.

## Declined to judge — explicit root disposition required

1. **Independent semantic rescoring and model-byte authentication:** task/document/question/Gold/prompt/output contents and model bytes were expressly outside reviewer access. I checked source, authored behavior, aggregate consistency and run-file hashes, relying on the root's recorded preparation/rescoring audit for actual semantic execution. No contradiction was found.
2. **Actual confirmation quality or resource behavior:** the failed frozen admission correctly prevents execution; there is no empirical confirmation result to assess. The 128/512 reservation remains intact, and authored confirmation software coverage was reviewed.
3. **Absence of pretraining contamination, exhaustive annotations or real-world answer truth:** this review cannot establish those properties. The sample is reused official-training material, not official HotpotQA development or contamination-free data. The report limits conclusions to strict reference agreement and this reader-profile screen; the linked prior reports explicitly retain pretraining and annotation ambiguity. I found no claim requiring those unestablished properties, and did not initiate new research or experiments.
4. **Repair of known historical index-reuse consumers:** unchanged historical source/results are expressly preserved, and this study uses fresh shared indexes. The existing README disclosure remains; repairing those consumers would be a separate versioned task.
5. **Final private archive copy/hash verification and remote publication:** these are root-owned completion actions after this review. I cannot certify an archive or push that has not yet occurred; the current evidence package itself was checked as above.

## Assessment

**Ready to publish: With fixes.** Resolve RQF-001 and verify that the affected test passes without private historical files, then perform the planned scoped rereview and root archive/publication closure. The runtime implementation, retained evidence and narrow negative scientific claim otherwise align with the frozen design; no further candidate search or inference is warranted by this review.

## Final fix and root closure

RQF-001 was addressed in `1be34ab` with an authored temporary metadata fixture and missing-file assertion. The scoped independent rereview approved the fix with no new breakage. Thirty affected-file tests passed with private paths absent/unreadable. The final full suite passed 1,064 tests, zero skipped, in 326.02 seconds; all 140 tested file identities stayed unchanged afterward. Production scientific source, configuration and retained results stayed unchanged from the measured protocol.

The declined review items retain their stated limits: root pinned-asset/native checks and exact rescoring supply execution evidence, without an independent truth/model-byte certification; confirmation remains deliberately unexecuted; contamination and annotation completeness remain unestablished; disclosed historical index consumers are unchanged and unused. Root verifies the exact process archive and normal remote push separately. No additional experiment, candidate search or semantic retry was introduced.

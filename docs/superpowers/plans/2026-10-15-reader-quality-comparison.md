# Reader Quality Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether the resource-qualified 14B reader supplies better strict answer-and-support outcomes before acquiring more allocation labels.

**Architecture:** Add `outcome_poc.reader_study`. A sealed outer protocol owns two scientific stages, each with one shared fresh index and two single-reader transaction leaves. Reuse the existing citation job transaction and generic lifecycle/supervisor/closure primitives; own factor-aware preparation, validation, orchestration and scoring. Never call historical study orchestrators or modify old modules.

**Tech Stack:** Existing Python 3.12, NumPy, CPU Sentence Transformers, MLX/MLX-LM and pytest; no dependency changes.

**Spec:** `docs/superpowers/specs/2026-10-15-reader-quality-comparison-design.md`.

## Global Constraints

- Current main; user authorizes execution, subagents, meaningful commits and publication. Preserve every pre-existing source/config/scientific result. New modules only under `src/outcome_poc/reader_study/`, new config/tests/run roots. No battery polling, power changes, paid APIs or remote compute.
- Reader IDs `qwen4b-instruct` (revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`) and `qwen14b-nonthinking` (revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`). New reader uses the approved ProfileFactory with explicit nonthinking; old reader uses NativeReaderFactory. Assets are already local and pinned.
- Original ANSWER_SYSTEM, baseline prompt only, installed template once, greedy, context8192/output256/prefill512/startup and request continuous timeout120 seconds. No caches, repairs, semantic retries, KV quantization or sliding truncation. CPU float32 normalized BGE revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
- Scientific stages `development` and `confirmation`; internal legacy leaf slot `diagnosis`. Every job, receipt-derived score and row carries explicit `reader_id` and `scientific_stage`. One resident reader at a time. One repetition; timings descriptive only.
- Development16 reused citation-diagnosis questions, selected by SHA256 bytes of UTF8 `reader-quality-v1:development:` + task ID, tie ID; three arms `2`, `10`, `support-documents`:96 assigned calls. Confirmation128 fresh questions, two natural arms:512 assigned calls, only after admission. All reservations freeze before benchmark generation.
- Eligible confirmation population88587, sorted-ID canonical hash `340ac60b947956a03da43fa0a3bead3d1ceb60d39d648f658404bc8262f9fdc0`; PCG64 seed271829 on sorted IDs. Preserve all original448, followup224, citation320 reservations and duplicate closure. N=88587, no additional subtraction for reused16.
- Both coordinator and child enforce sealed source origins and actual raw/Gold/prepared/history/network/import denials before acquisition; development additionally denies confirmation inputs and future index. Use actual-file probes, including an authored sentinel in the future confirmation index directory.
- Single writer through launch logs and closure, durable started/partial/terminal transactions and session costs; unknown quiescence or paid fatal/interruption permanently blocks the stage. Never shrink incomplete denominators. Completed observations never regenerate. Existing conservative resource gates remain unchanged; separate memory/swap diagnostics.
- Root alone prepares actual cohorts, indexes and runs models after software reviews. Workers/reviewers use authored fixtures only. Raw task/Gold/prediction/model/process records stay ignored; only aggregates and hashes are published.

## Review Focus

- Correct-looking outcomes from a swapped reader leaf: factor/request/model/template/decoding identity must all agree (Task1 binding tests and Task2 request-swap tests).
- Outer-root read exceptions accidentally allow confirmation evidence in development: actual input and index sentinel probes must fail in both native processes before fake acquisition (Task2 native test).
- Partial work hidden by clean restart or finalization races: inherited writer ownership, failed constructor identity, paid interruption and closed verify-only rerun must retain costs and refuse unsafe resume (Task2 lifecycle tests).
- Prior unexecuted reservations reused or duplicate representative relabeled: exact mandatory metadata union and normalized-group closure, plus deterministic authored eligibility fixture (Task1 cohort tests).
- Factor loss or incomplete-case scoring manufactures a win: missing/extra/duplicate cells, invalid citations, altered closure/Gold/scorer identity and asymmetric reader failures must fail or count zero as specified (Task2 scoring tests).

## Files and interfaces

- `configs/reader-quality-comparison.json`: exact reader registry, common settings, upstream metadata and asset paths, cohort/statistical/admission constants.
- `reader_study/study.py`: annotation-free constants, cohort/schedule pure functions, outer/leaf/stage verification and immutable file identities. Serving verification reads current stage only.
- `reader_study/preparation.py`: privileged metadata audit, selected input/support projection, sealed source/protocol, fresh per-stage index.
- `reader_study/runtime.py`: native launcher/factory, one-stage coordinator, per-reader resident sessions and closure, admission validation. Reuse primitives rather than copying historical run_stage.
- `reader_study/scoring.py`: privileged factor-aware deterministic scoring, admission and report assembly from closed predictions.
- `reader_study/__main__.py`: lazy dispatcher separating privileged preparation/scoring imports from `_serve`.
- `tests/test_reader_study_{study,preparation,runtime,native,scoring}.py`: authored behavior fixtures, no real benchmark/model bytes.

### Task 1: Freeze two-reader cohorts, factor bindings and fresh stage inputs

**Files:** Create config, `reader_study/{__init__,__main__,study,preparation}.py`, `tests/test_reader_study_{study,preparation}.py`.

**Interfaces:**
- `study.plan_cohorts(tasks: list[dict], old_ids: set[str], membership: list[dict], citation: dict, *, development_n=16, confirmation_n=128) -> dict`. Reuse normalized group logic while selecting the named development subset and independent fresh permutation; pure fixtures may use smaller counts without weakening production configuration checks.
- `study.make_schedule(cohorts: dict, bindings_hash: str) -> list[dict]`: reader block and cell hash order from the spec, explicit factors in content-addressed jobs, `stage='diagnosis'`, `prompt_condition='baseline'`, scientific stage separate. Each leaf schedule is the exact subset of this outer roster; no reader IDs as prompt conditions.
- `study.verify(root: Path, *, privileged=False, stage=None) -> dict`; `study.verify_stage(root: Path, stage: str, plan=None) -> dict`; `study.leaf_root(root: Path, stage: str, reader_id: str) -> Path`; `study.verify_leaf(root: Path, stage: str, reader_id: str, plan=None) -> dict`. Outer source snapshot, common/reader registry, input identities and leaf bindings are immutable. `stage=None` verifies common protocol only; no confirmation inputs opened during development. Confirmation verification requires the Task2 admission validator unless privileged preparation explicitly performs inventory-only validation.
- `preparation.prepare(root: Path, config_path: Path) -> dict`; `preparation.index(root: Path, stage: str) -> dict`. CLI `prepare --root ... --config ...`, `index --root ... --stage development|confirmation`, `verify --root ... [--stage ...]`.
- Leaf plans supply existing transaction-required fields (single assets.reader, freeze.settings.reader/decoding/bindings/boot, source origin binding, schedule hash and legacy diagnosis input files); leaf job hashes bind outer source/cohorts/reader and scientific stage. Model profile settings remain compatible with existing GenerationRequest decoding contract. Outer reader profile hash additionally binds forced nonthinking.
- Reuse `followup.study.build_new_index/verify_index` at a shared stage setup path, never historical native embedding-reuse consumers. Task2 receives the exact index seal/path in the stage envelope. Confirmation index is unavailable until admission; its future sentinel is sealed separately from eventual index files.

- [ ] Write failing authored tests for deterministic16-of64 and128 fresh selection (smaller pure fixtures allowed), all historical reservation union including deferred/unexecuted IDs, duplicate group closure/minimum representatives, wrong production population/hash/config and missing metadata path rejection.
- [ ] Write failing factor/plan tests:96/512 production factorial counts, order stable under input enumeration changes, reader swap changes job identity, natural matched evidence inputs equal, baseline prompt registry exact, wrong source/assets/profile/cohort/schedule/leaf stage rejected, verification of development never touches confirmation inputs, frozen support projection cannot influence selection.
- [ ] Run new files with `.venv/bin/python -m pytest tests/test_reader_study_study.py tests/test_reader_study_preparation.py -q`, save intended failure evidence.
- [ ] Implement these interfaces with ordinary immutable JSON/JSONL. Verify metadata against prepared manifest/fingerprint and mandatory original22 + both followup + citation cohort files. Freeze settings/cohorts/inputs/schedule before projecting development support documents. Use corrected reader-probe denial-location projection, current source snapshot, asset verification and boot/environment identities. No Gold in leaf natural inputs, no benchmark work in tests. Keep leaf source origins anchored to outer source without duplicating model/index bytes; declare exact bindings for Task2 in report.
- [ ] Run new tests and imported preparation/index/asset behavior tests that cover changed contracts. Self-review, commit `Freeze paired reader study and independent confirmation reservations`, report commands/results and interface details.

### Task 2: Execute, close and score explicit reader factors safely

**Files:** Create `reader_study/{runtime,scoring}.py`, extend only new `__main__.py` as needed; create `tests/test_reader_study_{runtime,native,scoring}.py`. Modify only new Task1 files if integration requires it.

**Interfaces:**
- `runtime.launch(root: Path, stage: str) -> dict`; `runtime.run_stage(root: Path, stage: str, *, backend_factory=None, encoder_factory=None, max_jobs=None) -> dict`; `runtime.validate_closed_stage(root: Path, stage: str) -> dict`; `runtime.validate_admission(root: Path, plan=None) -> dict`. Injected factories/max_jobs are authored tests/clean boundary pauses only; CLI always derives exact native factories.
- Reuse `citation_study.runtime.execute_job/completion/recover_or_refuse`; `followup.runtime.close_stage/reconcile_sessions/session_accounting/stage_lock/warmup`; ContinuousBackend and retained failed-constructor object; reader-probe isolation/availability monitor/gate and launch-lock helpers where compatible. Own a minimal isolated factory binding selected leaf to outer source and reader, publishing unchanged generic worker identity plus probe receipts before acquisition.
- Preserve exact natural ranking/evidence parity in outer closure. Validate all leaf receipts against explicit reader/stage/asset/profile. Outer closure seals all stage inputs/index, ranking identities, leaf closures and terminal cells. Scoring starts only after both leaves close and no extra/missing cells exist.
- `scoring.score_stage(root: Path, stage: str) -> list[dict]`; `scoring.admit(root: Path) -> dict`; `scoring.report(root: Path) -> dict`. CLI `run`, `score`, `admit`, `report` plus internal `_serve`. Score seal binds Gold/scorer/source/closure; exact fresh-process rerun is verify-only and byte-reproducible.
- Admission: complete healthy96 cells, 14B natural10 joint count strictly greater than4B, answer counts nonlower at2/10. No support-document score in admission. Failed/aborted stage cannot admit. Confirmation requires immutable admission tied to exact development closure/score seal and frozen rule.
- Confirmation primary paired joint-EM natural10 with N88587, hypergeometric four tails alpha0.0125. Simultaneous answer2/10 guards eight tails alpha0.00625. Preserve all failures; harm/rescue orientation14B minus4B; one repetition/descriptive times only, no efficiency superiority interval. Two/ten oracle union/discordance descriptive. Undefined ratios null+reason, not JSON Infinity.

- [ ] Write failing authored execution fixtures covering both reader identities/requests, unknown/extra/missing cells, context/output/truncation/parser errors, paid interruption/no semantic retry, completed resume verification, constructor failure cleanup/quiescence and inherited launch-lock concurrency. Use imported helper fixtures where sufficient, but prove this adapter invokes them.
- [ ] Write failing native fixture with real Seatbelt/spawn and authored factory: actual raw/Gold/history/current checkout/confirmation inputs and index sentinel/network/annotation imports denied in coordinator and worker before acquisition. Reader-specific factory/profile tampering and unknown process identity fail closed. No real models/data in tests.
- [ ] Write failing scoring/admission fixtures with asymmetric reader successes/failures, invalid citations, paired orientation, nonzero zero-harm bound, correct finite census behavior, all assigned denominators/costs, missing stage/forged admission refusal, changed prediction/Gold/scorer/source rejection and fresh-process score reproduction.
- [ ] Run targeted new tests; record intended red evidence. Implement thin orchestration and factor-aware scoring with official metric math unchanged. Hold outer writer lock through launch log closure; one reader/session at a time. Resource gates before/after acquisition/warmup and each assigned attempt, all lifecycle/paid progress retained. No aliasing of reader identity, full historical-run copy, global monkeypatch or new dependency.
- [ ] Run new tests and relevant imported transaction/supervisor/native/resource/scoring tests. Run full suite once after targeted tests and source settle; no real inference concurrently. Self-review, commit `Run and score isolated paired reader capability study`, report exact evidence. Root then executes under task-scoped approval.

## Root execution, publication and completion

After both task reviews pass, root verifies historical file preservation and commits the final prospective software/protocol. Prepare a new ignored root `artifacts/runs/reader-quality-comparison-v1`, inspect bindings and dry schedule, then index development and execute96 calls under native isolation. A temporary caffeinate assertion is allowed. Score only closed results; apply the frozen admission exactly. If it fails, publish the negative development screen and leave confirmation128/512 unexecuted/reserved. If it passes, build the fresh confirmation index and execute all512 with no interim scoring. Do not change source/profiles/rules after development results; a verified operational startup repair must retain failed session records and invalidate no scientific settings.

Verify closed reruns are no-generation and fresh-process rescoring reproduces bytes. Audit complete assigned denominators, historical file identities and separate resource/cold/session/adaptation accounting. Public report describes execution versus unperformed work, both reader lineages, limitations, failure rates, outcome cells and appropriate finite-population uncertainty. Preserve the original final report and use a new dated experiment report + public aggregate provenance; update README in the requested voice.

One fresh whole-branch reviewer receives all task/parked/deferred records and measured aggregate evidence. At most one final fix wave and one scoped rereview. Archive exact private workspace, verify copies/hashes, publish sanitized closure and all ordered Rulings/cost-if-wrong. Commit and push current main under standing authorization. End with an honest outcome category and concrete next-step decision; no allocation/provider/customer claim is earned solely by a better reader.

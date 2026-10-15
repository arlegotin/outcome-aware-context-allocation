# Citation-chain Reader Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Test one frozen citation-chain instruction with the existing reader on fresh, paired questions.

**Architecture:** An additive study package freezes selection, two explicit prompt conditions and a factorial schedule. A native isolated adapter reuses the hardened continuous reader/accounting primitives; a separate privileged scorer consumes only closed stages. Historical source and results remain unchanged.

**Tech Stack:** Existing pinned Python3.12/MLX-LM/Sentence Transformers/NumPy/SciPy and standard library. No dependency changes.

**Spec:** `docs/superpowers/specs/2026-10-15-citation-chain-reader-study.md`

## Global Constraints

- Work on current main with meaningful commits; do not change any existing source, frozen config, result, snapshot, manifest or original report.
- New source lives in `src/outcome_poc/citation_study/`; new tests use `tests/test_citation_*.py`; new config is `configs/citation-chain-reader-study.json`.
- Baseline is byte-identical ANSWER_SYSTEM; chain appends one newline and the exact sentence in the spec. No other reader/parser/evidence changes, repairs, minimum citation counts or semantic retries.
- Reader revision50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b: context8192/output256/prefill512/generation deadline120s/greedy. Existing pinned BGE-small CPUfloat32 normalized384-dimensional encoder.
- No new packages/downloads/model changes/paid APIs/inference network. Native interpreter `.venv/bin/python3.12`.
- Fresh cohorts diagnosis64/comparison256 from88907 eligible training representatives; NumPy Generator(PCG64(20261015)) permutation of sorted IDs. Comparison population88843. Exclude all prior448+224 reservations, officialdev7344 and normalized duplicate groups.
- Diagnosis baseline/chain ×2/10/support-documents =384 assigned calls. Comparison baseline/chain ×2/10 =1024 calls, only if the exact diagnosis admission rule passes. One authored baseline warmup per resident session is extra.
- Admission health: all assigned cells calls1; no infra_error/timeout/context_overflow; exact quiescent session endpoints and valid source/assets/probes/resource gates. Semantic failures remain counted. Any assigned infrastructure failure permanently aborts that stage; only clean pauses or pre-observation startup failures may resume untouched jobs under identical bindings.
- Authoritative time includes sleep; no inherited24-hour cap, battery checks or permanent power changes. Fresh indexes without reuse. Keep failed/partial work and uncertain worker cost bounds.
- Gold/import/network isolation applies to coordinator and spawned worker. Native new-entry probes and closure-before-Gold are mandatory. Comparison inputs are denied during diagnosis.
- Primary efficacy: natural10 paired joint-EM difference, conservative95% finite-population interval with four tails at0.0125. Two answer guards use eight tails at0.00625. Costs descriptive; no unsupported preservation/efficiency/business claim.
- Root owns real preparation/generation/Gold/scoring/reporting after software review. Builders use authored fixtures only and do not dispatch subagents.

## Review Focus

- Prompt condition altered without changing a job ID/receipt must fail verification (Task1/2).
- A nominally fresh normalized-question alias of a prior reservation must remain excluded (Task1).
- Diagnosis child opening comparison inputs or the new scorer must be denied, including in a spawned worker (Task2).
- Constructor failure before backend assignment with a live/unknown worker must block exact closure and resume (Task2).
- Missing cells, semantic failures or zero successes must stay in the assigned denominator and cannot produce a favorable complete-case ratio (Task2).

## File responsibilities

New `prompts.py` owns immutable condition strings and local rendering. `study.py` owns annotation-free selection, schedule and binding verification; `preparation.py` owns privileged projection/store creation and fresh indexing. `compat.py` names/version-checks reused private runtime dependencies. `runtime.py` owns new factors, native entry/session driver and closure. `scoring.py` owns privileged closed-stage scoring/admission; `analysis.py` owns aggregate paired comparisons and report data. `__main__.py` lazily dispatches CLI commands; `__init__.py` is annotation-free. Keep files focused; do not copy the entire prior runtime.

---

### Task 1: Freeze fresh cohorts and explicit prompt conditions

**Files:** Create `src/outcome_poc/citation_study/{__init__,prompts,study,preparation}.py`, `configs/citation-chain-reader-study.json`, `tests/test_citation_prompts.py`, `tests/test_citation_study.py`.

**Interfaces:** Consume unchanged `generation.render_prompt`, `ANSWER_SYSTEM`, `prompt_identity`; `followup.study` identity/publication/index/projection primitives; `data_runtime` stores and pinned assets. Produce `prompts.CONDITIONS`, `render_condition(question, evidence, aliases, tokenizer, condition) -> str`; `study.plan_cohorts(tasks, old_ids, membership, *, diagnosis_n=64, comparison_n=256) -> dict`; `study.make_schedule(cohorts, bindings_hash) -> list[dict]`; `study.selected_jobs(root, stage) -> list[dict]`; `study.verify(root, *, privileged=False) -> dict`; `preparation.prepare(root, config_path) -> dict`; `preparation.index(root, stage) -> dict`. Document exact persisted plan fields for Task2. Production config validation enforces spec constants; small authored fixture helpers may accept explicit counts without weakening production validation.

- [x] Write tests `test_baseline_rendering_is_byte_identical`, `test_chain_changes_only_system_once`, `test_old_duplicate_alias_excluded`, `test_exact_pcg64_selection_and_factor_roster`, `test_prompt_or_schedule_tampering_rejected`. Assert original system plus exact newline/sentence, unchanged user/evidence content, one template invocation, all unique384/1024 factor identities and hash changes on condition/source/settings changes.
- [x] Run focused tests and record genuine RED failures before source implementation.
- [x] Implement explicit prompt adapter/registry, metadata-only eligibility validation (including the old22 metadata paths plus all prior224 cohort reservations), PCG64 selection, sample hashes, deterministic question/cell order and source/assets/config/input bindings. Freeze cohort/schedule/prompt selection before privileged projection. For small fixtures compare exact NumPy permutation; production must require eligible count/hash from spec and valid prepared membership/manifests. Bind real model decoding settings, not a disconnected fixed hash.
- [x] Implement separate stage task/document stores and fresh per-stage indexes with no reuse, so diagnosis sandbox can deny the entire comparison input directory. Shared source documents may naturally occur in both cohorts; no claim of title/entity disjointness. Freeze copied input bytes and source snapshot; verification on serving must not open denied Gold/historical metadata. Privileged verification separately checks original Gold/input bindings. New support projection contains only diagnosis task/support-document IDs. Do not invoke old hardcoded cohort planner, prepare or verify.
- [x] Run focused tests and the existing suite once before commit; report exact commands/output. Do not run real preparation/index/inference or open prospective Gold. Commit the new planner/prompt/config/tests and write the persistent task report, including source/run schema handoff and concerns.

### Task 2: Run and score the isolated paired reader study

**Files:** Create `src/outcome_poc/citation_study/{compat,runtime,scoring,analysis,__main__}.py`, `tests/test_citation_runtime.py`, `tests/test_citation_analysis.py`, `tests/test_citation_native.py`. Task1 new files may be amended for concrete integration needs; existing historical source stays unchanged.

**Interfaces:** Consume Task1 plan/schedule/store fields and `render_condition`; reuse hardened `followup.supervisor.ContinuousBackend`, continuous clock, generic transaction/completion/session/reconciliation/monitor/sandbox helpers through explicit versioned compat. Produce CLI `python -m outcome_poc.citation_study prepare|index|verify|run|score|admit|report --root PATH` with `--stage diagnosis|comparison` where relevant and `--config` for prepare. `run` launches a sealed native `_serve` entry. Privileged scoring is lazy and denied by both serving guards. `runtime.validate_closed_stage(root, stage, *, privileged=True)` checks every assigned cell and immutable inventory before Gold. `analysis.summarize(rows, stage, population_N) -> dict` exposes deterministic aggregate data; `scoring.admit(root) -> dict` publishes comparison decision/admission receipts.

- [x] Write authored fixture tests for factor-bound generation/receipts, unchanged parser and paired evidence/aliases, tampering/corrupt resume rejection, actual new-entry kernel/raw/Gold/network/comparison denial, spawned new-scorer import denial, paid partial/timeout/cleanup handling, interrupted job terminalization, constructor failure with registered live/unknown worker and no exact endpoint, complete-schedule closure-before-Gold, and finite-population/zero-success/all-query analysis. Cover cases by adapting reusable old authored fixtures rather than redownloading models.
- [x] Run focused tests to demonstrate RED failures. Implement a small versioned adapter using pinned owned private helpers where needed; no global monkeypatch and no whole-runtime copy. Keep old shapes required by `completion`, `_commit`, session accounting and worker quiescence reconciliation. Explicitly validate condition/arm against frozen prompt registry and schedule, retain all startup/warmup/paid/payload/receipt/resource records and authoritative continuous times.
- [x] Implement native launch from source snapshot, extended import guard before model loading in coordinator AND spawn factory, exact denial probes and boot binding, read-only metadata traversal for SQLite, fresh query retrieval per cell, one original authored warmup/session and unmodified strict parsing. No prompt cache. Deny comparison stage inputs in diagnosis. Gate comparison on immutable externally generated admission attestation referencing closed diagnosis scores; serving cannot open score files. Refuse live/unknown worker resume; preserve uncertain session upper/lower bounds without later relabeling exact. Retrieval failure logs zero-call and aborts, cleanup failures retain paid terminal work then abort.
- [x] Implement complete immutable closure and separate official scoring. Admission is complete/healthy384 diagnosis observations, strictly greater chain natural10 joint count and nonlower chain answer count at both natural budgets. Report comparison deferred if false, never silently shrink or run it anyway. Score reproduction must verify closed bytes and produce identical rows/aggregate bytes without changing closure or historical files.
- [x] Implement paired aggregate analysis using exact spec tail alpha/population conventions, factor counts, primary/secondary distinctions, true all-query ratios with null reason/∞ display, descriptive costs/tokens/failures, continuous-active drift/order checks, nested versus disjoint engine envelopes and no preservation/business inference. CLI report writes private aggregate JSON suitable for root public synthesis, including missing/deferred stage status. Require complete cells and at least one call for healthy admission; zero-call infrastructure failures cannot pass.
- [x] Run focused adapter/native tests (escalated when macOS sandbox/process requires it), an authored interrupted/resumed closed workflow and the full suite once before commit. No real model/new Gold/data execution. Commit implementation/tests and persistent report with RED/GREEN evidence and exact commands. Task review must approve before root freezes real inputs.
- [ ] Root executes additive preparation/index/diagnosis, monitors operational status only, closes and scores all384 observations, then records exact admission. If passed, execute all1024 comparison observations without peeking; otherwise preserve as deferred. Record all attempts/envelopes and use temporary caffeinate only if useful.
- [ ] Root recomputes closed scores in a fresh process, verifies source/assets/old source and result inventories, and writes `docs/experiments/2026-10-15-citation-chain-reader-study.md` plus `artifacts/provenance/citation-chain-reader-study-summary.json`. Use the requested writing skill for measured README updates; no raw question/answer/Gold/prediction publication. Commit results separately. One broad final review and at most one final fix wave/scoped rereview, then archive current workspace, verify and push current public main.

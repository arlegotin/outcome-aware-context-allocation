# Reader Headroom Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Diagnose the reader and measure honest context-allocation headroom on fresh development questions.

**Architecture:** A separate follow-up package binds new data, assets and jobs while reusing the historical reader semantics. A continuous-clock supervisor bounds a persistent worker; a separate scorer consumes only closed stage outputs. Old frozen modules and results remain byte-identical.

**Tech Stack:** Existing pinned Python 3.12, MLX-LM, Sentence Transformers, NumPy/SciPy, standard-library JSON/dataclasses/ctypes/multiprocessing.

**Spec:** `docs/superpowers/specs/2026-10-15-reader-headroom-followup.md`

## Global Constraints

- Work on current main with meaningful commits and no changes to historical frozen files/outputs.
- No dependency upgrades, new model, prompt change, controller training, paid API or inference network.
- Native interpreter is `.venv/bin/python3.12`; use new ignored run roots.
- Authoritative timings/deadlines include sleep; unchanged active-clock submeasurements remain diagnostic only.
- New index has no reuse; no silent reliance on historical ancestry consumers.
- Fresh cohorts are diagnosis64/calibration32/headroom128 with fixed budgets 2/5/10 and diagnosis-only support-document oracle.
- New experiment has no inherited 24-hour deadline. Failures stay visible, no task replacement, no semantic retries.

## Review Focus

- Sleep between poll/result receipt must expire the request even if a result is queued (Task 1).
- Worker death, partial progress or cleanup failure must preserve paid work and stop/recover explicitly (Task 1).
- Stale source, input, closure or completed-job bytes must fail before reuse/scoring (Task 2).
- A valid-looking unassigned task or oracle projection carrying answer/Gold fields must be rejected (Task 2).
- Zero-success and incomplete schedules must never produce favorable zero ratios or complete-case summaries (Task 2).

---

### Task 1: Continuous warm-reader supervision

**Files:** Create `src/outcome_poc/followup/__init__.py`, `clock.py`, `supervisor.py`; test `tests/test_followup_clock.py`, `tests/test_followup_supervisor.py`.

**Interfaces:** Consume existing `generation.NativeReaderFactory`, `_reader_worker` and schema `ReaderResult`/`GenerationRequest`. Produce `continuous_ns() -> int`, `clock_identity() -> dict`, `boot_identity() -> str`, and `ContinuousBackend(factory, *, startup_timeout=120., clock=continuous_ns)` exposing tokenizer/generate/synchronize/close, worker PID, lifecycle and resource properties matching the existing supervisor's caller-facing shape. No prefix reuse needed; explicitly reject it.

- [ ] Write failing tests for timebase integer conversion, unavailable clock fail-closed, fake advancing continuous clock across sleep, result observed after deadline, bounded startup/sync, partial output on timeout and worker death. Use authored fakes and one real spawned fixture worker, no model downloads.
- [ ] Run the new tests to verify genuine failures before code.
- [ ] Implement the minimal standalone continuous supervisor using the existing worker protocol; enforce deadlines before and after each poll/receive with bounded polls. Record lifecycle times solely in the new clock domain, preserve partial generation counts and expose old internal timing telemetry as diagnostic only.
- [ ] Verify focused tests and original supervised-reader tests. Commit only the new files/tests and write a task report with command results and concerns.

### Task 2: Frozen development study, isolated execution and report

**Files:** Create focused modules under `src/outcome_poc/followup/` (`__main__.py`, `study.py`, `runtime.py`, `analysis.py` and a separate Gold-enabled `scoring.py` as appropriate), `configs/followup-reader-headroom.json`, `tests/test_followup_study.py`, `tests/test_followup_analysis.py`, `tests/test_followup_runtime.py`; final aggregate report `docs/experiments/2026-10-15-reader-headroom-followup.md`.

**Interfaces:** Consume Task 1 clock/supervisor, historical `DocumentStore`, `EncoderBackend`, `build_index`, `Retrieval`, prompt/parser helpers, schema validation and scoring math. Produce CLI `prepare`, `index`, `run --stage calibration|diagnosis|headroom`, `score --stage ...`, `report`, `verify`; all accept a new run root. Separate annotation-enabled dispatch from serving imports.

- [ ] Write failing tests for exact fresh cohort/exclusion ordering, immutable manifests/source hashes, strict oracle projection schema, no-reuse completion binding, complete-schedule closure, all-query zero-success metrics, corrupted receipt/resume rejection, Gold-import isolation and actual native sandbox denial. Synthetic fixtures must exercise the same production planner/run/score logic.
- [ ] Implement fixed settings from the spec, separate privileged support-ID projection and annotation-free tasks/documents, source/settings/input bindings and job IDs/repetitions. The known metadata-only reconnaissance is in ignored `artifacts/runs/followup-recon/{data,runtime}.md`; it is guidance, not an input outcome table.
- [ ] Implement new-root no-reuse index construction with continuous setup envelope; strictly require nested no-reuse manifest, physical receipt and payload identities. Do not edit old ancestry source.
- [ ] Implement a native serving launcher with network/raw/Gold denials and denial probes; persistent resident reader/encoder, synchronized continuous service intervals, payload-first/receipt-second commits, retained attempts, startup/shutdown/setup resources, deterministic within-question randomized arms and cross-boot fail-closed resume. Deny serving imports of new or old scorer.
- [ ] Implement separate closed-stage scoring and aggregate analysis. Budgets 2/5/10 share the full ranking and original prompt identities. Oracle whole-support docs are diagnostic only. Report incomplete stages without scoring a favorable subset, true sum-time/sum-success ratios and a clairvoyant three-action cost frontier. Include timing-health diagnostics; no quality preservation or new speed claim from unstable timings.
- [ ] Run focused tests and a synthetic interrupted/resumed workflow; commit implementation before native data generation. Task review must approve before real experiments.
- [ ] Root executes preparation/index/calibration/diagnosis; inspect only operational status until each stage closes. Score diagnosis, make the spec's explicit headroom admission/defer decision, then run/score the entire128 stage when informative. Preserve all688 planned generation identities; never relabel deferred work executed.
- [ ] Write aggregate-only report and machine-readable summary from closed records, rerun scoring in a fresh process, verify source/input/old protocol hashes and appropriate integration tests. Commit report separately from implementation.

The root owns native execution and final interpretation; the Task 2 implementer implements/tests but must not generate real study outputs or open real Gold before root freezes the run.

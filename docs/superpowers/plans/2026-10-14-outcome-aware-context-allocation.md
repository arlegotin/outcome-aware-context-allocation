# Outcome-aware Context Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute a reproducible local test of whether a cheap outcome-trained, pre-answer two/ten-paragraph controller earns its overhead against strong tuned comparators.

**Architecture:** An ordinary Python CLI prepares physically separated task/document/gold stores, ranks evidence with a shared encoder, and runs one frozen reader. Serving modules are independent of scoring; immutable manifests and an append-only cost/attempt ledger support development replay and fresh protected paired executions. A separate scorer, finite-population analysis and report generator produce a bounded positive, tradeoff, negative, inconclusive or blocked result.

**Tech Stack:** Native Python 3.11/3.12, MLX/MLX-LM, CPU float32 Sentence Transformers/PyTorch, NumPy/SciPy/scikit-learn, psutil, pytest, huggingface-hub, setuptools, standard-library JSON/SQLite.

**Spec:** [2026-10-14-outcome-aware-context-allocation-design.md](../specs/2026-10-14-outcome-aware-context-allocation-design.md). Read both documents before executing. Initially delivered as spec and plan only. The user subsequently authorized execution with subagents and meaningful commits on the current branch; completed task steps are checked only after verification and review.

## Global Constraints

- Work and meaningful commits stay on this branch (`main`); do not create a worktree or replacement branch.
- The executor records a UTC project-start/deadline before the first implementation/setup action; the 24-hour window includes setup and reporting, and elapsed work is never reset at a restart, handoff or protocol freeze.
- Primary candidate: `PRE-OUTCOME-GBM`, with actions exactly `{2,10}` on valid ten-paragraph HotpotQA distractor packets.
- Reader: `mlx-community/Qwen3-4B-Instruct-2507-4bit`, with original provenance `Qwen/Qwen3-4B-Instruct-2507`.
- Encoder: `BAAI/bge-small-en-v1.5`, 384 dimensions, normalized cosine similarity on CPU float32.
- Start smoke tests at 8,192 total tokens and 256 new tokens, one sequence, greedy decoding, installed chat template, no speculative decoding or thinking additions.
- Leave the greater of 4 GiB or 20% of physical RAM outside the measured project working set.
- No rotating/truncated KV cache, KV quantization, privileged memory-limit changes or hidden model substitution in the primary system.
- Only preparation/scoring/training commands may read gold. Serving commands expose no gold-file argument, scorer import or annotation-bearing record.
- Split seed `20261014`, estimator seed `1729`, sampling/bootstrap seed `271828`; hashes use the spec's canonical UTF-8 JSON serialization.
- All failed work stays in its numerator and assigned tasks stay in quality denominators. Zero successes yields infinity, serialized as `null` with `reason="zero_successes"`; never emit JSON Infinity/NaN.
- Direct `A*`/`B*` runs execute the whole pipeline with no answer-cache hits. Timing repetitions are not additional tasks.
- No protected generation before final protocol freeze; no protected retuning, repeated significance checks or post-outcome sample extension.
- Every experimental report ends with exactly one of: **qualified positive**, **efficiency/quality tradeoff**, **no advantage over existing methods**, **evidence against the tested mechanism**, **inconclusive**, **blocked by prerequisites**.
- Public assets may be downloaded for execution, but data/model text, credentials and caches are not committed or published by default. No paid API or remote GPU.

## Review Focus

1. Torn completion writes and corrupt replay payloads must preserve paid attempts and prevent silent skipping; tests belong to Tasks 1 and 8.
2. A protected duplicate question with a different source ID must remove the matching training group, while later pilot/fit extensions remain disjoint; tests belong to Task 3.
3. A single overlong sentence, repeated title, encoder-truncated query or tied score must preserve original citation identity and deterministic ranking; tests belong to Tasks 3 and 4.
4. A timed-out semantic failure or malformed paid draft must keep its costs and assigned denominator; tests belong to Tasks 5, 8 and 11.
5. A near-census with zero harms or unstable timing/output must not produce a false zero-risk/zero-uncertainty quality claim; tests belong to Tasks 6 and 14.

## File Map and Execution Order

| Files | Responsibility | Owner task |
| --- | --- | --- |
| `pyproject.toml`, `.gitignore`, `src/outcome_poc/__init__.py`, `__main__.py`, `schemas.py`, `storage.py` | Packaging, lazy dispatch, typed validated records, atomic/hash/ledger primitives | 1 |
| `configs/base.json`, `environment.py`, `assets.py`, `requirements.lock` | Start/deadline, discovery, pinned downloads, compatible lock | 2 |
| `generation.py` | Native reader adapter, exact renderer/parser, worker deadline support | 2, 5, 8 |
| `data.py` | Validation, conversion, duplicate removal, split/corpus manifests | 3 |
| `retrieval.py` | Native encoder, token windows, index and deterministic rankings | 2, 4 |
| `scoring.py` | Separate official metric implementation and closed-run scoring | 5, 14 |
| `statistics.py` | Finite-population bounds, ratio/timing variance and guards | 6 |
| `features.py`, `policies.py` | Observable vectors and prespecified action decisions | 7, 11 |
| `timing.py`, `runner.py` | Warm boundary, component events, direct/replay execution and recovery | 8, 13 |
| `oracle.py`, `pilot.py`, `configs/development.json` | Headroom/format/cost/capacity gate | 9 |
| `train.py`, `select.py` | Paired fit collection, local learners and common tuning selection | 10, 12 |
| `protocol.py`, `configs/frozen.json` | Freeze, sampling, schedules and consistency enforcement | 13 |
| `robustness.py` | Frozen attribution, pooled transfer and boundary diagnostics | 15 |
| `report.py`, `README.md`, `research_poc_plan.md` | Honest blocked/partial/final handoff and fresh reproduction | 2, 16 |

This is one coupled experiment, not several independent products. Tasks 1–2 establish the critical asset/reader path before broad work. Tasks 3–8 establish the trustworthy harness. Task 9 determines whether expensive training is warranted; Tasks 10–15 are conditional on its gate and remaining time. Reporting in Task 16 is required even if an earlier gate blocks. Do not claim the unexecuted suffix of the plan is complete when reporting a valid early-stop outcome.

Read the spec's builder decisions as exact defaults. Measured values remain runtime gates rather than guesses. Each task owns its named interfaces; when a later task extends a file, preserve earlier signatures or record and update all consumers in the same commit.

## Task 1: Establish Validated Records, Durable Storage and the CLI

**Files:** Create `pyproject.toml`, `.gitignore`, `src/outcome_poc/{__init__,__main__,schemas,storage}.py`, `tests/{conftest,test_schemas,test_storage,test_cli}.py`.

**Interfaces:** Produces spec dataclasses `Task`, `Document`, `RankedDocument`, `Decision`, `GenerationRequest`, `ReaderResult`, `PaidDraft`, `Prediction`, `CostEvent`, `ScoredTask`, `PairedActionRow`, `GoldRecord`; ordinary dictionaries represent manifests/configs. `Document` has `doc_id: str`, `title: str`, `sentences: list[str]`, `character_count: int`. `Decision.threshold_mode` permits null only for non-threshold policies, with a null threshold; learned modes remain strictly validated. `GenerationRequest` carries model/prompt/decoding hashes, role, context/output limits, timeout and cache mode. `ReaderResult` carries raw/parsed output, status, token counts, token IDs and stop reason. `validate_record(record: object) -> None`; `canonical_bytes(value: object) -> bytes`; `content_hash(value: object) -> str`; `atomic_json(path: Path, value: object) -> str`; `append_jsonl(path: Path, value: object) -> None`; `read_jsonl(path: Path) -> Iterator[dict]`. Storage validation rejects nonfinite numbers before writing.

- [x] **Step 1: Record the execution clock and bootstrap only the test environment.** Use a discovered native `python3.11` or `python3.12`; create `.venv`, install pytest/setuptools, and record the original UTC start/deadline in `artifacts/provenance/execution-window.json` before installation. Refuse reset of an existing start. If no supported interpreter is available, record `BLOCKED_DEPENDENCY` and proceed to the documentation/report branch of Task 16. Do not present the planning shell's Python 3.14.6 as the chosen execution interpreter.
- [x] **Step 2: Write failing primitive tests.** Pin canonical serialization and invalid float/bool cases; use a subprocess killed before atomic replace to prove the old file survives and an incomplete attempt remains visible.

```python
def test_canonical_bytes_and_finite_validation():
    assert canonical_bytes({"b": 2, "a": "é"}) == b'{"a":"\xc3\xa9","b":2}'
    with pytest.raises(ValueError):
        canonical_bytes({"time": float("inf")})
```

Also assert runtime `validate_record` rejects a citation index `True`, negative elapsed time and an unknown status; `atomic_json`'s returned digest matches the persisted bytes; JSONL truncation is reported, not silently omitted. `python -m outcome_poc --help` must list the proposed commands without importing MLX or scoring.
- [x] **Step 3: Run the red tests.** `python -m pytest tests/test_schemas.py tests/test_storage.py tests/test_cli.py -q`; expect collection/import failure for the not-yet-created package. This first red run may use `PYTHONPATH=src`; install the editable package once `pyproject.toml` exists.
- [x] **Step 4: Implement the primitives and lazy dispatcher.** Use setuptools package discovery under `src`, explicit validators and `os.replace`/fsync writes. Define CLI commands now but dispatch unimplemented ones to a clear unavailable-stage error; later tasks replace each handler. Ignore `.venv`, caches, raw/prepared/gold/index data, downloaded models and generated runs; do not hide the eventual lock or intentionally retained sanitized manifests/reports. Add invented fixture data and injectable clocks/backends to `conftest.py` only as later consumers need them.
- [x] **Step 5: Verify packaging and tests.** `python -m pip install -e .`; rerun Step 3; `python -m outcome_poc --help`; all pass without native model imports.
- [x] **Step 6: Commit.** `git add pyproject.toml .gitignore src/outcome_poc tests`; `git commit -m "feat: establish validated records and durable experiment storage"`.

## Task 2: Pass the Native Asset and Inference Prerequisite Gate (WP0)

**Files:** Create `configs/base.json`, `src/outcome_poc/{environment,assets}.py`, `requirements.lock`, `tests/{test_environment,test_assets,test_smoke}.py`; create initial reader/encoder adapters in `generation.py`/`retrieval.py`; extend `__main__.py`, `README.md`, `research_poc_plan.md`.

**Interfaces:** Consumes storage/records. Produces `discover(output_dir: Path) -> dict`; `resolve_assets(config: dict, cache_dir: Path) -> dict`; `verify_assets(manifest: dict) -> None`; `smoke(config: dict, assets: dict) -> dict`; `ReaderBackend.load(snapshot: Path, config: dict) -> None`, `.generate(prompt: str, request: GenerationRequest) -> ReaderResult`, `.synchronize() -> None`; `EncoderBackend.encode(texts: list[str]) -> np.ndarray` (normalized float32 rows, CPU, 384 columns). Later tasks consume these adapters, never Hub repository names as implicit download paths during serving.

- [x] **Step 1: Write failing asset/discovery tests.** Stub the Hub metadata client; ensure a commit revision is resolved before download, changed asset bytes fail verification, a missing license blocks the asset and inference receives only local paths. Denied `sysctl` leaves `physical_memory_bytes=null` with an error and fails the resource gate; it must not substitute a guessed M3 Max configuration. A known finite 384-vector passes; 383 dimensions or NaN fails.
- [x] **Step 2: Run the red tests.** `python -m pytest tests/test_environment.py tests/test_assets.py tests/test_smoke.py -q`; expect missing adapters/handlers or failed assertions.
- [x] **Step 3: Implement discovery, pinned downloads and smoke.** Acquire HotpotQA through author links, record redirect/final URL, size/SHA-256 and provenance; obtain reader and encoder Hub commit IDs and safe snapshots. Resolve a mutually compatible native environment and inspect installed generation/synchronization/cache signatures. Save wheel names/hashes, versions, original/conversion licenses, cold-load time and smoke memory/token telemetry. Run `pip check`, generate actual hashed `requirements.lock`, and keep `pip-freeze.txt` separately. No trust-remote-code/external pickle/script path. Record both permitted and failed discovery attempts. Extend README with actual setup steps and mark unimplemented commands; research handoff retains the supplied brief's attribution/access limits without claiming full paper reproduction.
- [x] **Step 4: Pass deterministic tests and a real offline smoke.** Run Step 2; `python -m outcome_poc discover --config configs/base.json`; `assets --config configs/base.json`; `smoke --config configs/base.json`. The smoke must load the exact revision, emit a valid short citation JSON example twice, compare generated token IDs, verify local-only inference, and log encoder dimension, synchronization, resident/peak bytes and swap. Record network-disabled test mechanism. Pretrained card/API existence alone does not pass.
- [x] **Step 5: Persist gate state and a provisional report.** Write WP0 status, artifacts/hashes and next command. On an indispensable failure write a prerequisite-blocked provisional report and do not continue to data collection. Choose precise package/backend repair on development rather than silently replacing the model.
- [x] **Step 6: Commit verified code and resolved lock.** `git add configs/base.json src/outcome_poc tests README.md research_poc_plan.md requirements.lock`; `git commit -m "feat: verify pinned assets and native reader prerequisites"`. Exclude raw/model/cache files.

## Task 3: Prepare Annotation-Separated Data and Deterministic Splits (WP1)

**Files:** Create `src/outcome_poc/data.py`, `tests/{test_data,test_splits,test_no_gold_access}.py`; extend `__main__.py`.

**Interfaces:** `prepare(train_path: Path, dev_path: Path, output_dir: Path, split_seed: int = 20261014) -> dict`; `normalize_question(question: str) -> str`; `audit_data(prepared_dir: Path) -> dict`; `DocumentStore(path: Path).get(doc_id: str) -> Document`; `load_tasks(path: Path, split: str) -> list[Task]`. Produces protected population, development reservation and exclusion manifests. Fixtures `raw_hotpot`, `documents10` and `task10` use invented questions/text only.

- [x] **Step 1: Write failing conversion/split tests.** Test content-ID stability when raw order changes; different text with the same title differs; support sentence indices survive conversion. Reject malformed records, duplicate IDs, duplicate packet content and ambiguous support titles with reasons. A development duplicate with another ID removes its training group. NFC/case/whitespace equivalent questions group together. Assert pilot reserves 64, tune next 128, fit next 256; extending pilot from 32 to 64 and fit from 256 to 512 never overlaps tune/protected.
- [x] **Step 2: Run red.** `python -m pytest tests/test_data.py tests/test_splits.py tests/test_no_gold_access.py -q`; missing preparation or isolation behavior fails.
- [x] **Step 3: Implement conversion, explicit rejection rules and bounded storage.** Write task/document/gold stores separately, sorted/canonical manifests and duplicate membership ledger. Hash canonical `[title, sentences]`; partition by canonical `[20261014, group_key]` hash then group-key tie-break. Represent duplicates with minimum task ID. Measure conversion RSS/bytes before reader loading; use bounded parsing if required and lock any added parser. Record actual protected `N` and train/protected overlap. Runtime dataclasses exclude answer/support/task-type fields.
- [x] **Step 4: Verify synthetic invariants and raw data audit.** Run Step 2; `python -m outcome_poc prepare --config configs/base.json`; `audit-data --config configs/base.json`. Check zero exact-question overlap after training removal and that rejected IDs were recorded before any model outcomes. `test_no_gold_access` must inspect serving modules' import closure and monkeypatch file access to deny gold paths; extend it as modules arrive.
- [x] **Step 5: Commit.** `git add src/outcome_poc/data.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: separate annotations and freeze deterministic data partitions"`.

## Task 4: Build Reproducible Token Windows and Shared Ranking (WP1)

**Files:** Extend `src/outcome_poc/retrieval.py`; create `tests/{test_ranking,test_windows,test_index}.py`.

**Interfaces:** `embedding_windows(document: Document, tokenizer: object, max_tokens: int = 480) -> list[dict]`; `build_index(documents: Iterable[Document], encoder: EncoderBackend, output_dir: Path) -> dict`; `Retrieval(index_dir: Path, documents: DocumentStore, encoder: EncoderBackend).rank(question: str, candidate_ids: list[str]) -> list[RankedDocument]`. Window dictionaries carry token spans/original sentence IDs and vector offsets. Index manifest includes encoder revision/dimension, mapping/digests and offline costs.

- [x] **Step 1: Write failing windows/ranking tests.** Use an injected deterministic tokenizer/encoder. A single >480-token sentence splits into compliant title-inclusive windows while every window retains its original sentence index. Whole sentences pack consecutively; no document instruction prefix is introduced. Query prefix matches the spec exactly. Equal float32 scores sort by content hash independent of candidate order; paragraph scoring uses maximum window cosine. A long query's truncation is explicit and logged, and unindexable title overhead errors visibly.
- [x] **Step 2: Run red.** `python -m pytest tests/test_windows.py tests/test_ranking.py tests/test_index.py -q`.
- [x] **Step 3: Implement float32 memmap/index metadata and ranking.** Deduplicate paragraphs once; use CPU encoder batches selected by measured memory. Never return windowed/truncated evidence to the reader. Persist metadata character counts as `len(title)+sum(len(sentence))`. Record offline indexing seconds/bytes independently; query encoding/lookup/dots/aggregation/sort return component timings to later accounting. Record exact query truncation/tokenizer convention in index manifest.
- [x] **Step 4: Verify real development indexing and order invariance.** Run Step 2; `python -m outcome_poc index --config configs/base.json --split pilot`. Repeat rank on shuffled candidate IDs and compare scores/ranks exactly. Verify only scheduled pilot documents were embedded and each window vector has 384 finite normalized float32 components. Gold metadata must not enter any query path.
- [x] **Step 5: Commit.** `git add src/outcome_poc/retrieval.py tests`; `git commit -m "feat: add deterministic paragraph indexing and ranking"`.

## Task 5: Enforce Reader Output and Official Scoring (WP2)

**Files:** Extend `generation.py`; create `src/outcome_poc/scoring.py`, `tests/{test_prompt,test_parsing,test_scoring}.py`; extend isolation tests/CLI.

**Interfaces:** `render_prompt(question: str, evidence: list[Document], aliases: dict[str,str], tokenizer: object, role: str = 'answer') -> str`; `parse_answer(raw: str, evidence: list[Document], aliases: dict[str,str], truncated: bool = False) -> ReaderResult`; `Reader.answer(...) -> ReaderResult` as in the spec; `normalize_answer(text: str) -> str`; `score_answer(prediction: str, gold: str) -> dict`; `score_support(predicted: set[tuple[str,int]], gold: set[tuple[str,int]]) -> dict`; `Scorer.score(...) -> ScoredTask` as specified. Metric dictionaries include EM/F1/precision/recall.

- [x] **Step 1: Write failing prompt/parser/metric fixtures.** Golden prompt contains the exact system text and aliases based on full ranking; selecting a budget never renumbers sentences. Accept one JSON/unlabeled fence, reject multiple objects/prose/duplicate keys/extra fields/bool or unknown indices/truncation; empty answer abstains; duplicate citations do not inflate support recall. Invalid citations with a correct answer score zero primary success and retain answer-only diagnostics.

```python
def test_official_joint_f1_is_not_mean_of_f1s():
    answer = score_answer("red blue", "red green")
    support = score_support({("A", 0)}, {("A", 0), ("B", 0)})
    p = answer["precision"] * support["precision"]
    r = answer["recall"] * support["recall"]
    assert joint_f1(answer, support) == pytest.approx(2 * p * r / (p + r))
    assert joint_f1(answer, support) != pytest.approx((answer["f1"] + support["f1"]) / 2)
```

Define `joint_f1(answer: dict, support: dict) -> float` in `scoring.py`. Include normalized `yes/no/noanswer` mismatch, empty support sets and repeated answer-token fixtures; a forced-correct/forced-wrong pair changes the success count by exactly one.
- [x] **Step 2: Run red.** `python -m pytest tests/test_prompt.py tests/test_parsing.py tests/test_scoring.py tests/test_no_gold_access.py -q`.
- [x] **Step 3: Implement renderer/parser/scorer and pinned parity fixtures.** Retrieve the official evaluator at a resolved repository commit, save source digest/provenance, and compare fixture mathematical outputs in a scorer-only test. Avoid runtime dependency on the evaluator's optional imports or external pickle use. `Scorer` maps hashes through original documents to title/index sets. Distinguish prompt/output truncation from valid EOS; reserve output capacity before generation. No free repair generation.
- [x] **Step 4: Verify fixtures and one development generation.** Run Step 2, parity fixtures and a local pilot-input reader call. Gold is read only afterward by the separate scorer. Validate complete import closure and denied-gold runtime test.
- [x] **Step 5: Commit.** `git add src/outcome_poc/generation.py src/outcome_poc/scoring.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: enforce citation contract and official HotpotQA scoring"`.

## Task 6: Implement Conservative Finite-Population Analysis (WP2)

**Files:** Create `src/outcome_poc/statistics.py`, `tests/test_statistics.py`.

**Interfaces:** `efficiency(times: np.ndarray, successes: np.ndarray) -> dict`; `finite_population_upper(x: int, n: int, N: int, alpha: float = .05) -> float`; `finite_population_lower(...) -> float`; `paired_quality_bounds(a: np.ndarray, b: np.ndarray, N: int, tail_alpha: float) -> dict`; `compare_primary(times_a: np.ndarray, times_b: np.ndarray, success_a: np.ndarray, success_b: np.ndarray, N: int) -> dict`. Times have shape `(n,repetitions)`, successes shape `(n,)`; compare returns effect/CI/variance components/sensitivity/status, not nonstandard floats. `quality_guards(rows: list[dict], N: int) -> list[dict]` implements the fixed four-guard family.

- [x] **Step 1: Write failing statistical tests.** Ratio is sum time/sum success, not mean per-query ratios; zero successes returns null/reason. Census binary bounds equal counts exactly; invalid input raises. Zero observed harm in a subsample has positive upper bound; enumerate small finite populations to verify one-sided coverage. Test swapped arms, covariance-preserving paired timing variance and positive timing variance at census.

```python
def test_zero_harm_is_not_zero_population_risk():
    assert finite_population_upper(0, 10, 100, .05) > 0
    assert finite_population_upper(4, 20, 20, .05) == 4 / 20
    assert finite_population_lower(4, 20, 20, .05) == 4 / 20
```

Tests also require no Gaussian ratio CI below 30 successes, full leave-one-out diagnostics, no double-counted timing noise, four quality guards with each count tail `.05/16`, sparse discordance handling and explicit invalidity for supplied unstable-timing/nondeterministic-output flags.
- [x] **Step 2: Run red.** `python -m pytest tests/test_statistics.py -q`.
- [x] **Step 3: Implement spec equations and validation.** Use `scipy.stats.hypergeom.cdf` binary search, sample variance `ddof=1`, normal critical value `1.959963984540054` and paired-repetition covariance. Validate `n<=N`, complete arrays, finite positive times and minimum repetitions or frozen conservative fallback. Quality preservation uses the exact count-bound family; regular paired variance remains diagnostic. Mark sign-sensitive/insufficient-success comparisons inconclusive. Expose timing-stationarity flags as recorded input, never infer a valid run merely from a numerical interval.
- [x] **Step 4: Pass the statistical suite.** Run Step 2. Compare constructed rescue-minus-harm identity and A/A exact zero effect; separately verify A/A timing uncertainty can remain positive. Retain small-population coverage outputs as test evidence, not a general formal proof.
- [x] **Step 5: Commit.** `git add src/outcome_poc/statistics.py tests/test_statistics.py`; `git commit -m "feat: add finite-population effects and timing uncertainty"`.

## Task 7: Implement Observable Features and Cheap Policy Limits (WP2)

**Files:** Create `src/outcome_poc/{features,policies}.py`, `tests/{test_features,test_policy_limits}.py`; extend gold-isolation tests.

**Interfaces:** `build_features(question: str, ranked: list[RankedDocument]) -> np.ndarray` (42 values); `feature_schema() -> dict`; `FixedPolicy(k: int).choose(...) -> Decision`; `AdaptiveKPolicy(buffer: int).choose(...) -> Decision`; `ThresholdPolicy(model: object, config: dict).choose(...) -> Decision`; `training_thresholds(predictions: np.ndarray) -> list[dict]`. Each policy has `policy_id: str`; pre policies reject a non-null paid draft.

- [x] **Step 1: Write failing feature/boundary tests.** Pin all 42 positions with known scores/counts, ordered one-hot precedence, population SD, float64 entropy, nine real-real gaps and short-packet padding/masks. Zero packets yield exhausted budget before model prediction. Near-flat/tied scores select the first largest permitted gap. For ten documents `ceil(.9*m)=9` searches eight gaps; buffer zero gives `j+1`, never zero.

```python
def test_learned_threshold_endpoints_are_fixed_actions(task10, ranked10, stub_regressor):
    for mode, expected in [("always_ten", 10), ("always_two", 2)]:
        config = {"threshold_mode": mode, "threshold": None}
        policy = ThresholdPolicy(stub_regressor, config)
        assert policy.choose(task10.question, ranked10).action_k == expected
```

Also assert schema mismatch/nonfinite features cause logged full fallback or exhausted cap, never gold lookup; requested/effective short-packet budgets are visible; quantiles use `method='linear'` from training predictions only; endpoint serialization contains no Infinity.
- [x] **Step 2: Run red.** `python -m pytest tests/test_features.py tests/test_policy_limits.py tests/test_no_gold_access.py -q`.
- [x] **Step 3: Implement formulas and policy configs.** Preserve question-only seven-value slice; implement `{2,10}` clipping/threshold semantics and caller-cap wrapper. The published Adaptive-k buffer 5 and tuned buffer variants get separate stable config IDs. Measure policy/feature overhead through the later serving ledger.
- [x] **Step 4: Pass tests and aliases.** Run Step 2 and score endpoints against fixed-action fixture predictions. Identical questions/rank metadata must yield identical decisions without reader calls.
- [x] **Step 5: Commit.** `git add src/outcome_poc/features.py src/outcome_poc/policies.py tests`; `git commit -m "feat: implement observable allocation features and policy boundaries"`.

## Task 8: Charge Complete Serving Work and Recover Interrupted Jobs (WP2)

**Files:** Create `src/outcome_poc/{timing,runner}.py`, `tests/{test_cost_ledger,test_resume,test_timeout,test_harness}.py`; extend `generation.py`, CLI and isolation tests.

**Interfaces:** `serve(task: Task, policy: object, runtime: object, job: dict) -> Prediction`; runtime owns shared retrieval/document store/reader/backend synchronization and injected clock. `action_signature(task: Task, config: dict, evidence_ids: list[str], role: str, cache_mode: str) -> str`; `job_id(signature: str, mode: str, repetition_id: int) -> str`; `execute_job(job: dict, runtime: object, run_dir: Path) -> Prediction`; `close_run(run_dir: Path, expected_jobs: list[dict]) -> dict`; `validate_harness() -> dict`. Runtime objects have no gold reference. Reader worker lifecycle lives in `generation.py` and exposes cooperative/forced timeout records.

- [x] **Step 1: Write failing fake-clock/fake-reader tests.** Set known component times and assert warm service includes retrieval, routing, evidence/prompt, all paid calls, parsing and payload serialization exactly once. Timing ledger append occurs afterward and is recorded separately. Two post calls have two events but retrieval only once. Replayed action charges original cost; direct mode never reuses answers. Job signatures change with prompt/backend/cache mode; repetition IDs yield distinct jobs.
- [x] **Step 2: Add recovery/timeout red cases and run them.** `python -m pytest tests/test_cost_ledger.py tests/test_resume.py tests/test_timeout.py tests/test_harness.py tests/test_no_gold_access.py -q`. Kill a fixture worker mid-write, resume it and compare assigned denominator with uninterrupted execution. Corrupt completion checksum must block skipping. Timeout preserves partial output/elapsed event and counts zero success; semantic parse failure gets no retry; infrastructure rerun links attempts and retains total experiment cost. A stalled worker is killed/reloaded without an invisible second answer.
- [x] **Step 3: Implement warm timing, supervisor and durable transactions.** Synchronize immediately before/after service timing. Atomic prediction/completion payloads and append-only attempts/errors/events use Task 1 primitives. Separate component sums from enclosing latency. Close markers contain hashes/counts only when scheduled terminal records are present; unresolved infrastructure errors remain invalid/incomplete even if terminal. Operate at question/generation boundaries and derive RNG/order from job identity.
- [x] **Step 4: Pass tests and validate the real harness gate.** Run Step 2; `python -m outcome_poc validate-harness --config configs/base.json`. Include A/A, correct/wrong, malformed citation, timeout, threshold alias and statistics checks; use only a few development real calls. Confirm gold files are inaccessible to serving and every paid generation has an event.
- [x] **Step 5: Commit.** `git add src/outcome_poc/timing.py src/outcome_poc/runner.py src/outcome_poc/generation.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: account for complete serving and durable job recovery"`.

## Task 9: Measure Reader Suitability, Headroom and Runtime (WP3)

**Files:** Create `src/outcome_poc/{oracle,pilot}.py`, `configs/development.json`, `tests/{test_oracle,test_pilot}.py`.

**Interfaces:** `oracle_frontier(rows: list[PairedActionRow]) -> list[dict]`; `headroom(rows: list[PairedActionRow]) -> dict`; `run_pilot(config: dict, runtime: object) -> dict`; `capacity_forecast(observations: list[dict], remaining_seconds: float) -> dict`. Produces `pilot_costs.json`, `headroom.csv`, `reader_failures.jsonl`, `capacity_forecast.json` and WP3 gate state.

- [x] **Step 1: Write failing oracle/pilot tests.** Construct all four small/full success cells and assert counts sum to assigned `n`, net difference equals rescue-minus-harm and maximum quality uses `max(S2,S10)`. Oracle starts with cheaper actions and sorts only success-improving switches by incremental time/task ID. Non-monotone outcomes must not be coerced into “ten is better.” A zero-discordance tiny pilot reports insufficient evidence rather than universal impossibility.
- [x] **Step 2: Run red.** `python -m pytest tests/test_oracle.py tests/test_pilot.py -q`.
- [x] **Step 3: Implement disjoint pilot and resource forecast.** Execute two/ten for first 32 reserved pilot tasks, no-context diagnostic and a hash-selected small all-k slice; extend to 64 only for stated instability. Warm execution shapes/short-median-long strata and retain warm-ups; collect valid citation rate, all metrics, token lengths, timings, RSS/MLX/swap and output determinism. Forecast conservative job time from observed prefill/decode/components, not GPU FLOPS. Compare oracle frontier to fixed budgets and plausible measured gate overhead.
- [x] **Step 4: Pass tests and run pilot.** Step 2, then `python -m outcome_poc pilot --config configs/development.json`. Separate serving from scorer invocation. Resolve prompt/citation/capacity problems on development with amendments and invalidation of old dependent outputs. If strict joint EM is uninformative, report reader/metric limitation; changing primary metric requires a new untouched protocol. Do not inspect protected outcomes.
- [x] **Step 5: Record the continue/stop decision and commit.** Gate permits Task 10 only with informative headroom and feasible resources; otherwise perform Task 16 with evidence and explicit unexecuted tasks. `git add src/outcome_poc/oracle.py src/outcome_poc/pilot.py configs/development.json tests`; `git commit -m "feat: measure allocation headroom and local execution capacity"`.

## Task 10: Collect Paired Fit Outcomes and Train Prespecified Learners (WP4)

**Files:** Create `src/outcome_poc/train.py`, `tests/{test_training,test_learning_curve}.py`; extend CLI and policies.

**Interfaces:** `collect_pairs(tasks: list[Task], runtime: object, config: dict) -> list[PairedActionRow]`; `fit_gates(rows: list[PairedActionRow], training_gold: dict[str,GoldRecord], output_dir: Path) -> dict`; `load_gate(manifest: dict) -> object`; `learning_curve(nested_rows: list[list[PairedActionRow]]) -> list[dict]`. `load_gate` accepts only locally created, checksummed artifacts; fit functions receive explicit training gold only for proxy labels. Gate manifest contains feature hash, fit IDs, parameters, target definition, clipping, thresholds and training time/bytes.

- [x] **Step 1: Write failing fit/leakage tests.** Verify target values include `-1,0,+1`, failed semantic actions remain zero and missing infrastructure blocks training. GBM constructor matches all spec values; RF has 300 trees/leaf 8/full features/seed 1729; ridge standardization uses fit-only population statistics and zero SD becomes one. Query-only receives seven features. Proxy labels use missing gold support from top two on fit only. Permutation preserves the target distribution and never touches tune/protected labels.
- [x] **Step 2: Run red.** `python -m pytest tests/test_training.py tests/test_learning_curve.py tests/test_no_gold_access.py -q`.
- [x] **Step 3: Implement paired collection and local fits.** Generate two actions for 256 fit tasks under the frozen development reader config, with identical action-signature deduplication only in development. Score in a separate closed run, then join observable rows with scored outcomes by task ID. Train GBM, ridge grid, RF, query-only, proxy and shuffled GBM; prepare post fit features from existing paid drafts. Save local artifacts/manifests and all acquisition/training costs. Lock estimator defaults in config for reproducibility.
- [x] **Step 4: Pass tests and index/collect/fit.** Run Step 2; `python -m outcome_poc index --split fit --config configs/development.json`; `python -m outcome_poc collect --split fit --config configs/development.json`; `python -m outcome_poc fit --config configs/development.json`. Add learning-curve nested doubling only if fit-only/development evidence and remaining-time forecast justify it; index each newly scheduled extension before its collection. Tune set stays disjoint and is never merged into fit. All training predictions/quantiles come from actual fit rows.
- [x] **Step 5: Commit.** `git add src/outcome_poc/train.py src/outcome_poc/policies.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: train outcome and proxy allocation controls"`.

## Task 11: Implement Paid Draft/Judge Controls and Prefix-Reuse Bounds (WP4)

**Files:** Extend `generation.py`, `features.py`, `policies.py`, `runner.py`; create `tests/{test_post_outcome,test_sufficiency,test_prefix_cache}.py`.

**Interfaces:** `post_features(question: str, ranked: list[RankedDocument], draft: PaidDraft) -> np.ndarray` (46 values); `PostOutcomePolicy.choose(...) -> Decision`; `SufficiencyPolicy.choose(...) -> Decision` consumes a paid judge result through the runtime, not gold. `common_prefix_length(a: list[int], b: list[int]) -> int`; `Reader.answer_with_prefix(..., prefix_cache: object) -> ReaderResult`; `optimistic_post_cost(events: list[CostEvent], reusable_prefill_seconds: float) -> dict`.

- [ ] **Step 1: Write failing paid-control tests.** Missing draft event ID is rejected; post features are exactly the four observable appendages specified. Invalid retained drafts remain failures. Sufficiency uses exact prompt/16-token cap/top-two format; malformed or truncated judge escalates; every judge/final call is charged. A full answer can reuse only common prompt tokens and never generated draft tokens. Inputs mutated after draft must not reuse stale cache.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_post_outcome.py tests/test_sufficiency.py tests/test_prefix_cache.py tests/test_cost_ledger.py -q`.
- [ ] **Step 3: Implement post/judge paths and development cache parity.** Retrieve once, pay draft, gate, possible full generation; share the same final reader contract. Clone common-prefix cache before draft continuation and prove parity with no-reuse on development inputs, including first divergent token and cache-boundary cases. If installed backend cannot faithfully support reuse, log the limitation and optimistic lower cost bound that subtracts all reusable prefill work; do not claim candidate superiority where this bound removes the margin. Prefix-mode outputs/signatures remain distinct observations.
- [ ] **Step 4: Pass suites and real cache/judge checks.** Run Step 2; compare token IDs and scores for a hash-selected development parity block; preserve raw events/resources and both cache modes. Check reconstructed post time has retrieval once and draft decoding even under the optimistic bound. Cost uncertainty and unresolved parity are gate facts, not a “baseline loses” result.
- [ ] **Step 5: Commit.** `git add src/outcome_poc/generation.py src/outcome_poc/features.py src/outcome_poc/policies.py src/outcome_poc/runner.py tests`; `git commit -m "feat: add charged post-answer and sufficiency comparators"`.

## Task 12: Tune Every Family and Select A*/B* Without Test Access (WP4)

**Files:** Create `src/outcome_poc/select.py`, `tests/test_selection.py`; extend CLI/train/runner.

**Interfaces:** `configuration_metrics(predictions: list[Prediction], scores: list[ScoredTask], events: list[CostEvent]) -> dict`; `select_configuration(config_rows: list[dict], anchor: dict) -> dict`; `tune(config: dict, runtime: object) -> dict`. Output complete tuning table, all family representatives, candidate `A*`, noncandidate `B*`, published Adaptive-k reference, thresholds/action rates and comparator optimization caveats.

- [ ] **Step 1: Write failing selection tests.** Empirical joint/answer EM both meet fixed-ten anchor before eligibility. Selection sorts by `R`, negative joint EM, mean time then config ID; zero-success ratios sort as infinite. Always-ten endpoints alias exactly. A high-efficiency quality-losing config remains visible/ineligible, and a superior simple/RF/post config can be chosen as `B*`. No protected IDs are accepted in tuning tables.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_selection.py tests/test_policy_limits.py tests/test_cost_ledger.py -q`.
- [ ] **Step 3: Implement all-k tuning and common family optimization.** On 128 tune tasks execute `k=1,...,10` and sufficiency jobs; share development action outputs across equivalent policies but charge their own routing and paid components. Evaluate all ridge alpha/thresholds, GBM/RF/query/proxy/post thresholds, published/tuned Adaptive-k and fixed budgets. Select A*/B* before protected sampling. Store every config, losing row, cost source and family eligibility; final fixed-ten anchor remains explicit even when selected fixed budget differs.
- [ ] **Step 4: Pass tests, index tuning documents and tune.** Run Step 2; `python -m outcome_poc index --split tune --config configs/development.json`; `python -m outcome_poc tune --config configs/development.json`. If the candidate is always-ten or another policy wins, preserve that result. The intended competitive experiment does not silently omit an unfinished mandatory family; finish it, reduce feasible `n` before freeze, or report a limited/incomplete stage. No feature search triggered by protected results.
- [ ] **Step 5: Commit.** `git add src/outcome_poc/select.py src/outcome_poc/train.py src/outcome_poc/runner.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: select allocation policies with common quality and cost rules"`.

## Task 13: Freeze Limits, Sample and Complete Job Schedule (WP5)

**Files:** Create `src/outcome_poc/protocol.py`, `configs/frozen.json`, `tests/{test_protocol,test_schedule}.py`; extend CLI/runner.

**Interfaces:** `freeze_methods(development: dict, selection: dict, capacity: dict) -> dict`; `sample_protected(population_ids: list[str], n: int, seed: int = 271828) -> list[str]`; `plan_jobs(methods: dict, sampled_tasks: list[Task]) -> list[dict]`; `freeze(config: dict) -> dict`; `bind_source(protocol: dict, commit: str) -> dict`; `verify_protocol(protocol_path: Path) -> dict`; `plan(protocol: dict, dry_run: bool = True) -> dict`. Final protocol hashes method specification, population/sample, schedule, reader/prompt/config/source commit and dependency/assets/scorer/schema identities. `bind_source` works only before any protected generation and preserves method/sample/schedule digests exactly; it updates the source/file hashes and audit record, then rebuilds the final protocol hash.

- [ ] **Step 1: Write failing protocol/schedule tests.** Protected generation before freeze raises; unresolved fields/hash changes/nonfinite configs are rejected. The methods file is written before sampling; PCG64 chooses uniformly without replacement from sorted IDs. Direct repetitions are not deduplicated against development or each other. Each question has every required representative plus direct selected pair and fixed-ten anchor. Post/judge expansion counts all unique paid calls. Same-policy aliases can reuse deterministic outcomes for scores, but direct A/A timing jobs remain distinct. Binding source preserves methods/sample/schedule digests and is rejected after even one protected generation attempt; a changed frozen runtime file blocks verification, while a new reporting-only file does not.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_protocol.py tests/test_schedule.py tests/test_resume.py -q`.
- [ ] **Step 3: Measure final limits and implement freeze.** On development, cover longest frozen prompt and forced maximum output; timeout is twice largest measured request time. Choose paired repetitions (minimum two unless predeclared conservative fallback), stationarity diagnostics, token caps, `n` from actual remaining time, required roster and reporting/recovery allowance. Forecast precision/success count and job bytes; freeze `.05` primary interval and four exact quality guards. Write methods, then sample/schedule, then final hash. Freeze run order derived deterministically per question/repetition. No source changes that alter method meaning after recording commit without a new protocol.
- [ ] **Step 4: Pass tests, dry-run and interruption rehearsal.** `python -m outcome_poc freeze --config configs/frozen.json`; `python -m outcome_poc plan --protocol artifacts/protocol.json --dry-run`. Confirm source/assets/settings hashes, expected all-query denominator, feasible complete job count and report reserve. Rehearse resume with a small fixture protocol; inspect only operational metadata. A low-powered run may be declared a bounded diagnostic before outcomes, not promised preservation.
- [ ] **Step 5: Commit implementation; then regenerate source-bound protocol if needed.** `git add src/outcome_poc/protocol.py src/outcome_poc/runner.py src/outcome_poc/__main__.py configs/frozen.json tests`; `git commit -m "feat: freeze confirmation protocol and paired execution schedule"`. Bind the final immutable execution protocol to this committed source without introducing a commit-hash cycle; protocol artifacts are separately hashed and need not be tracked in the same source commit.

## Task 14: Execute the Protected Pair and Score Only Closed Runs (WP6)

**Files:** Extend `runner.py`, `scoring.py`, `statistics.py`, CLI; create `tests/{test_protected_run,test_closed_scoring}.py`.

**Interfaces:** `run(protocol: dict, runtime: object) -> dict` produces immutable closure/predictions/events/resources/errors; `score_run(protocol: dict, run_dir: Path, gold_path: Path) -> list[ScoredTask]` is scorer-only; `analyze_run(protocol: dict, scored_rows: list[ScoredTask], events: list[CostEvent]) -> dict` consumes Task 6 statistics. Monitoring emits counts/health, not protected metrics before closure.

- [ ] **Step 1: Write failing end-to-end fixture tests.** Full assigned sample includes parse errors/timeouts/failures; no complete-case intersection changes denominators. Unclosed/mismatched protocol or missing infrastructure records block complete primary analysis. A/B order is randomized but reproducible; actual calls occur for every direct repetition. If repeated token IDs/outcomes differ or paired costs change with thermal/order blocks, analysis is flagged invalid/inconclusive instead of silently pooling.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_protected_run.py tests/test_closed_scoring.py tests/test_no_gold_access.py tests/test_statistics.py -q`.
- [ ] **Step 3: Implement protocol-verified execution and separate scoring.** Keep weights/index resident; index sampled protected documents from the already selected schedule only. Resume identical jobs/attempts without tuning. Persist all errors, partial attempts and system states. Close with complete schedule/hash checks; only then permit scorer gold access. Average repetitions within unique tasks, preserve raw times/paired covariance and generate harm/rescue/quality bounds. A deadline-expired incomplete run remains incomplete rather than selecting fast completed queries as a new sample.
- [ ] **Step 4: Pass all fixtures.** Run Step 2 plus `python -m pytest -q`. Verify that fixture runs have not created protected benchmark outputs and that all serving/scoring/statistical implementation changes are ready to commit.
- [ ] **Step 5: Commit protected-run enforcement and bind its source.** `git add src/outcome_poc/runner.py src/outcome_poc/scoring.py src/outcome_poc/statistics.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: enforce frozen paired execution and closed-run scoring"`. Re-score saved development predictions with the final scorer; require unchanged metrics/targets/selected A*/B*, update scorer provenance and invalidate/rebuild any affected scored cache records. A mathematical change requires an amendment and repeat of dependent fit/tune/freeze work before test access. Call `bind_source` through `python -m outcome_poc freeze --config configs/frozen.json --bind-source-only` to bind this commit without resampling, retuning or changing limits. Verify preserved method/sample/schedule digests and final protocol hash. This operation is forbidden once any protected attempt exists.
- [ ] **Step 6: Execute only the newly verified final protocol.** `python -m outcome_poc run --protocol artifacts/protocol.json`; after closure, `python -m outcome_poc score --protocol artifacts/protocol.json`. Do not show interim significance or extend `n`. Compare frozen A*/B* and fixed-ten; all-family superiority is unavailable without a prespecified simultaneous family. Validate minimum-success/influence/stationarity gates before interpreting ratio CI. No further frozen runtime/scorer file edits are permitted during Tasks 15–16.

## Task 15: Challenge Label Attribution, Accounting and Packet Transfer (WP7)

**Files:** Create `src/outcome_poc/robustness.py`, `tests/{test_ablations,test_transfer,test_stress}.py`; extend only the lazy CLI's robustness dispatch and report inputs. Do not change frozen retrieval/runtime files; implement pooled-corpus access in `robustness.py` through the existing encoder/index interfaces.

**Interfaces:** `ablate(protocol: dict, scored_rows: list[ScoredTask], events: list[CostEvent]) -> dict`; `pooled_corpus_manifest(development_tasks: list[Task], protected_population: list[Task]) -> dict`; `transfer(protocol: dict, corpus: dict, query_ids: list[str], runtime: object) -> dict`; `stress_cases(tasks: list[Task], documents: DocumentStore, spec: dict) -> list[dict]`. Failure review records evidence/tags/blind-selection identity and never overwrites scores.

- [ ] **Step 1: Write failing attribution/transfer tests.** Real/proxy/query-only/shuffled/random representatives stay frozen; ablation results cannot select a new A*/B*. Direct/replayed comparisons detect an omitted draft/query/parse component. Pooled search sees a deduplicated union of selected development documents and the entire declared protected population, without candidate restrictions or gold association/injection. Transfer query IDs are selected independently of support ranks/outcomes and gate remains unchanged. Pooled embedding/index costs are new explicit costs.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_ablations.py tests/test_transfer.py tests/test_stress.py -q`.
- [ ] **Step 3: Implement priority attribution and optional frozen transfer.** Finish outcome/proxy/query-only/ridge/RF/post/shuffle/random comparisons and reconstructed/direct accounting first. Add pooled memmap CPU retrieval and report actual window/vector count, full retrieval latency and support recall@10 in the scorer. Budget-pilot before scheduling new generations. Optional support removal, labeled contradiction/prompt-injection, title-disjoint and blinded annotation review use declared diagnostic copies; never modify natural primary scores or invoke external-action tools. Record MuSiQue/precision/retriever changes as unexecuted or new protocols.
- [ ] **Step 4: Verify and run within remaining budget.** Step 2; `python -m outcome_poc ablate --protocol artifacts/protocol.json`; if forecast fits, `python -m outcome_poc transfer --protocol artifacts/protocol.json`. If transfer does not run, retain packet-only claim and list the missing test. Review explanations need evidence; use unknown where causal attribution is uncertain.
- [ ] **Step 5: Commit.** `git add src/outcome_poc/robustness.py src/outcome_poc/__main__.py tests`; `git commit -m "feat: add frozen attribution and pooled-corpus transfer checks"`. Preserve the primary source binding; any genuinely required change to frozen runtime is a separate amended experiment, not a patch to protected observations.

## Task 16: Reproduce and Deliver an Honest Final Report (WP8)

**Files:** Create `src/outcome_poc/report.py`, `tests/{test_report,test_reproduce}.py`; update `README.md`, `research_poc_plan.md`, CLI; generate `artifacts/final_report.md`, `artifacts/summary.json`, tables and remaining-risk ledger.

**Interfaces:** `reproduce(protocol: dict | None, run_dir: Path | None, scores_only: bool = True) -> dict`; `report(state: dict, output_path: Path) -> dict`; `classify_outcome(evidence: dict) -> str`. Must support prerequisite-blocked and development-only states with no fabricated protocol/test results. Report state includes executed/unexecuted WP status, all manifests/provenance/tuning/closed-run analysis and caveats.

- [ ] **Step 1: Write failing report/decision tests.** Zero-success `R` renders infinity/undefined, never zero. All method rows retain assigned `n` and failures; adaptation is distinct from pretrained assets and experiment costs. A lower ratio without quality-guard clearance cannot say quality preserved. Incomplete primary work classifies inconclusive; absent indispensable assets classify blocked by prerequisites; a tuned simpler winner is retained. Positive claims name actually evaluated comparators and tested scope.
- [ ] **Step 2: Run red.** `python -m pytest tests/test_report.py tests/test_reproduce.py -q`.
- [ ] **Step 3: Implement full and early-stop reports.** Include scope, actual hardware/package/assets/licenses/hashes, populations/exclusions/overlap, every frozen configuration, full tuning/quality/cost/failure/latency/token/memory tables, approximate primary CI and exact harm/rescue guards, adaptation/break-even, direct/replay/cache caveats, attribution/transfer, unexecuted tests and all amendments. No unsupported novelty/open-web/business statements. Reader/annotation/contamination/timing/generalization limitations stay explicit. End with one allowed verdict; standalone machine-readable summary must agree. A provisional blocked report can run without MLX installed.
- [ ] **Step 4: Pass report tests and reproduce from raw inputs in a fresh process.** `python -m pytest -q`; `python -m outcome_poc reproduce --scores-only --protocol artifacts/protocol.json`; `python -m outcome_poc report --protocol artifacts/protocol.json`. If early stopped before protocol, `report --state artifacts/provenance/experiment-state.json` must work. Recompute hashes/denominators/statistics and compare deterministic score digests. For a performance claim, run a fresh-process small direct timing block and inspect stationarity/order sensitivity. Run `python -m pip check` and `git diff --check`; no extra broad repeat tests once required checks pass unless new changes/failures justify them.
- [ ] **Step 5: Commit source/docs and selected sanitized report/provenance.** `git add src/outcome_poc/report.py src/outcome_poc/__main__.py tests README.md research_poc_plan.md`; `git commit -m "feat: reproduce results and report bounded experimental conclusions"`. Explicitly stage final report/summary and sanitized manifests if intended for the repository; retain raw predictions locally without exposing dataset text/secrets. Verify branch is still `main`, commits are meaningful and working tree has no accidental tracked assets. Do not push or publish as part of local handoff.

## Gate Checklist and Requirement Coverage

| Spec section / brief WP | Owning tasks | Concrete evidence |
| --- | --- | --- |
| 1–3: scope, objective, verdicts | 9, 12, 14, 16 | Headroom gate, preselected comparator, full-denominator ratio and qualified conclusion |
| 4 / WP0: prerequisites/assets/hardware | 1–2, 9, 13 | UTC clock, native supported lock, real offline smoke, memory/capacity/timeout measurements |
| 5 / WP2: boundaries/records/storage | 1, 3, 5, 8 | Lazy serving closure, denied gold reads, canonical validation, interrupted-run recovery |
| 6 / WP1: data/splits | 3, 13 | Validation/exclusions, exact-question isolation, fixed population then uniform sample |
| 7 / WP1–2: retrieval/reader/parser | 2, 4–5, 8 | Window/ranking fixtures, prompt/alias fixtures, official scorer parity, explicit failures |
| 8–9 / WP4: features/learners/baselines | 7, 10–12 | 42/46-value schemas, exact models, all-k/Adaptive-k/query/proxy/RF/post/judge roster |
| 10 / WP2,6: metrics/records/resume | 1, 5, 8, 14 | Complete terminal ledgers, checksum/idempotence, scorer separation |
| 11 / WP3–6: accounting/economics | 2, 8–9, 11, 13–16 | Native synchronization, direct/replay parity, charged drafts/judges, cache bound, break-even |
| 12 / WP5–6: inference/statistics | 6, 13–14 | Immutable protocol/schedule, exact quality bounds, timing variance, stationarity/LOO gates |
| 13 / WP0–8: command/gate workflow | 1–16 | Implemented CLI handlers, structured stage status, preserved deadline and staged exits |
| 14 / WP3,7: oracle/attribution/transfer | 9, 15 | Oracle frontier, label/feature/control checks, pooled corpus or disclosed omission |
| 15 / WP8: acceptance/report | 16 | Fresh reproduction, required tables/provenance/raw failures, final verdict |
| 16: research provenance/limits | 2, 16 | Source/asset attribution, inherited versus fresh evidence, no unsupported novelty claim |

Before implementation, review this spec/plan together and preserve the user's chosen execution method. If no method has been chosen, recommend native inline execution for this single tightly coupled 16-task harness, with independent reviews at scientific gates; subagent execution is available through its named skill if the user chooses it. This documentation handoff does not execute either method.

During execution, an early gate failure still requires the honest Task 16 handoff. It does not make conditional unfinished software tasks complete. A reproducible negative result or an explicit prerequisite block is an acceptable research outcome; a predetermined win is not.

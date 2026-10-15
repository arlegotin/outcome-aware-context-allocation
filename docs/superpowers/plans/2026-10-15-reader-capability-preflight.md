# Reader Capability Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether one pinned, explicitly nonthinking 14B reader can execute the authored workload safely and reproducibly before building a benchmark comparison.

**Architecture:** Add a standalone `outcome_poc.reader_probe` package. Compose existing asset validation, native reader, continuous supervisor, clocks, resource checks and Seatbelt helpers; never modify historical modules. A sealed source/config/assets plan owns three authored calls and durable session/call receipts.

**Tech Stack:** Existing native Python 3.12, MLX/MLX-LM, Hugging Face Hub, psutil and pytest; no dependency changes.

**Spec:** `docs/superpowers/specs/2026-10-15-reader-capability-design.md`, Gate 1 only.

## Global Constraints

- Work on current `main`; meaningful commits; no worktree, package upgrades, paid service or remote compute.
- Preserve every existing source/config/result file. New code lives in `src/outcome_poc/reader_probe/`; downloaded assets and runs remain ignored.
- Sole candidate `mlx-community/Qwen3-14B-4bit` revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`; original provenance `Qwen/Qwen3-14B` revision `40c069824f4251a91eefaf281ebe4c544efd3e18`; original historical conversion commit unknown.
- Existing ANSWER_SYSTEM/parser; explicit `enable_thinking=False`; greedy, context 8192, output 256, prefill 512, continuous startup/request deadline 120 seconds, no KV quantization/truncation or caches.
- Reuse unchanged `followup.runtime.resource_check`, `ResourceMonitor`, `stage_lock`, `probe_denials`, `sandbox_profile`, `followup.supervisor.ContinuousBackend`, `generation.NativeReaderFactory`, asset verification and official parser.
- Native inference denies network, Gold/raw/prepared/index/historical outcomes and annotation imports in coordinator and worker before acquisition; only sealed source may supply project imports.
- No benchmark text, Gold, task selection or model inference in implementer/reviewer tests. Root owns downloads and real runs after task approval.
- No process kills except owned supervised workers; no system/power changes or battery polling.

## Review Focus

- Pickled/spawned tokenizer facade must retain forced nonthinking and not recurse on attribute lookup (Task 1 pickle fixture).
- Snapshot metadata may lie about filenames, shard membership or file identity; verify exact safe inventory and LFS/Git blob hashes (Task 1 corrupt/inventory fixtures).
- Native launcher and spawned worker can otherwise import checkout code or inspect outcomes before a factory runs; test real kernel/import probes before an acquisition marker (Task 2 native authored fixture).
- Constructor, timeout, cleanup or coordinator interruption can leave an owned process or paid work unrecorded; test durable failed sessions, unknown quiescence and no retry (Task 2 lifecycle fixtures).
- Reinvocation must verify closed receipts and never regenerate or accept altered output/source/profile/settings (Task 2 closure/tamper/resume fixtures).

## File responsibilities

- `configs/reader-capability-preflight.json`: public immutable asset inventory/settings.
- `reader_probe/profile.py`: validated reader settings, tokenizer facade, picklable native factory.
- `reader_probe/assets.py`: pinned acquisition, exact safe inventory and provenance manifest.
- `reader_probe/study.py`: authored prompts, plan preparation/verification and closed receipts.
- `reader_probe/runtime.py`: guarded native coordinator/factory, session ownership, calls and resources.
- `reader_probe/__main__.py`: standalone `assets`, `prepare`, `verify`, `run`, internal `_serve` dispatcher.
- `tests/test_reader_probe_{profile,assets,study,runtime,native}.py`: authored behavior fixtures.

### Task 1: Pin the reader profile and verify acquired assets

**Files:** Create `configs/reader-capability-preflight.json`, `src/outcome_poc/reader_probe/{__init__,__main__,profile,assets}.py`, `tests/test_reader_probe_profile.py`, `tests/test_reader_probe_assets.py`.

**Interfaces:**
- Consumes existing `generation.NativeReaderFactory(snapshot, config)`, `assets.verify_assets(manifest)` and standard canonical hashing.
- Produces `profile.load_config(path: Path) -> dict`, `profile.NonThinkingTokenizer(tokenizer)`, `profile.ProfileFactory(snapshot: Path, config: dict)` (picklable callable returning an existing ReaderBackend with only its own tokenizer wrapped).
- Produces `assets.acquire(config_path: Path, asset_root: Path, manifest_path: Path) -> dict` and `assets.verify_manifest(manifest: dict, config: dict) -> None`. No model/MLX import during acquisition/verification.
- CLI: `python -m outcome_poc.reader_probe assets --config configs/reader-capability-preflight.json --asset-root models/pinned/reader-capability14b --manifest artifacts/runs/reader-capability-preflight-v1/assets.json`.

- [x] Write failing authored tests: exact profile values; reject wrong pin/mode/caps; facade always forwards `enable_thinking=False`, rejects explicit true and survives pickle; factory forwards loaded identity and changes no global/asset. Asset fixtures reject unsafe/extra/missing files, wrong revision/metadata identity/license, altered shard byte/hash, index names not matching verified shards, and external symlinks; valid tiny authored safetensors-named fixture passes without loading a model.
- [x] Run `.venv/bin/python -m pytest tests/test_reader_probe_profile.py tests/test_reader_probe_assets.py -q`, record intended missing-implementation failures.
- [x] Implement the declared interfaces. Include the exact safe conversion file inventory from the already-inspected `artifacts/runs/strong-reader-recon/mlx14b-file-manifest.json` in public config, with size, Git blob ID and LFS SHA256 where supplied. Include original README/config/LICENSE identities from pinned original metadata; no tokenizers/weights from original. Verify non-LFS Git blob SHA1 as `sha1(b'blob '+str(size).encode()+b'\0'+bytes)` and all LFS SHA256. Independently compute SHA256/bytes for every acquired file and retain the existing compatible reader asset entry (`kind=model`, status/license/repo/revision/local_path/files/snapshot_hash). Preserve acquisition timing/bytes and pinned source URLs. An immutable completed manifest is verified and reused, not overwritten. No downloads in tests, no remote code, scripts or pickle checkpoints. Use existing Hub snapshot API with an explicit filename allowlist.
- [x] Run the two test files plus existing asset/reader tests that directly exercise imported interfaces. Report clean TDD evidence and self-review, then commit `Add pinned nonthinking 14B reader profile and asset verification`.

### Task 2: Seal and execute the three-call native preflight

**Files:** Create `src/outcome_poc/reader_probe/{study,runtime}.py`; extend only the new `reader_probe/__main__.py`; create `tests/test_reader_probe_{study,runtime,native}.py`.

**Interfaces:**
- Consumes Task 1 profile/config/asset interfaces and unchanged supervisor/resource/clock/parser/native sandbox helpers.
- Produces `study.prepare(root: Path, config_path: Path, assets_path: Path) -> dict`, `study.verify(root: Path) -> dict`, `runtime.launch(root: Path) -> dict`, `runtime.run(root: Path, *, backend_factory=None) -> dict`, internal CLI `_serve`. Injected factories are tests only; native CLI always derives Task 1 factory from sealed verified assets.
- CLI `prepare --root ... --config ... --assets ...`, `verify --root ...`, `run --root ...`; `run` launches `/usr/bin/sandbox-exec` with sealed snapshot source, never imports annotation code. Native process and spawned factory verify origins, plan/boot, settings/profile identity and real file/network/import denials before acquisition.

- [x] Write failing authored plan tests: seals reject changed config/assets/lock/source/profile; long prompt uses actual tokenizer counts and full original sentences to reach 7800–7936 with total <=8192; exactly three distinct call IDs bind repetition/role/settings; same first two prompt IDs; all fixed calls/receipts included in successful closure. Model files stay outside source snapshot and historical paths remain unchanged.
- [x] Write failing lifecycle/native tests: actual authored spawn + Seatbelt denies file/network/import access in both processes before acquisition marker; unexpected checkout imports fail; malformed/truncated output fails without retry; startup/timeout/cleanup/resource failures retained; constructor failure with owned worker or unknown quiescence cannot masquerade as clean close; started interrupted call blocks clean resume, completed calls never regenerate; altered closed payload/profile/source fails verification; all failure work stays visible. Use existing supervisor fixtures/helpers when they cover unchanged lifecycle internals; tests must prove the new adapter actually invokes them.
- [x] Run the new targeted tests and record missing implementation failures.
- [x] Implement prepare/verify with immutable per-file identity inventory, config/lock/source/asset/profile/boot hashes and copied `src/outcome_poc` sealed snapshot. Generate denials for whole `data/{raw,prepared,gold,index}`, actual raw locations discovered from asset-registry data-kind metadata (including this checkout's `models/pinned/data`), historical run tree (new run exempted by existing helper), existing outcome/analysis paths; seal the metadata projection and explicitly probe actual raw and Gold files when present, never rely on missing-file exceptions. Include module guards for `outcome_poc.data`, `outcome_poc.scoring`, historical followup/citation preparation/scoring, and future `outcome_poc.reader_study.preparation`/`.scoring`. Do not deny the profile/asset-verification modules needed for model load.
- [x] Implement durable locked sessions using continuous clock + active clock + boot/process creation identity. Start session before model acquisition; use the existing ContinuousBackend, retain constructor object on failure so owned-worker cleanup/lifecycle can be inspected. Reuse ResourceMonitor and unchanged resource_check at each specified boundary; add system available memory as a separate diagnostic, never a new gate. Stop on missing mandatory RSS/MLX counters after acquisition. Finalization always attempts owned worker cleanup, proves quiescence and records terminal session state/lifecycle/cost bounds. Do not claim exact endpoints if recovery can only bound them.
- [x] Implement three authored calls. Short evidence: title `Authored reader probe`, original sentence index 0, text `The access code for the violet cabinet is LARK-27.`, question `What is the access code for the violet cabinet?`; require normalized answer `LARK-27` and exact supplied citation. Repeat byte-identically. Long call retains that sentence first and appends deterministic numbered irrelevant sentences (builder chooses fixed harmless content), selecting whole sentences by actual rendered token count to satisfy 7800–7936. Bind every exact prompt/token list/request before its paid call; persist incremental output and terminal ReaderResult, parse against supplied evidence, no retries. A closed pass requires three valid calls, equal repeated output tokens/payload, long coverage, passing gates/probes and quiescence; otherwise emit explicit blocked/failed/incomplete result. Successful repeated `run` is verify-only. A failed or interrupted paid call makes that root permanently non-admissible; do not silently continue in a new root. A wholly pre-paid startup failure may resume only with retained session and proven worker quiescence.
- [x] Run new targeted tests and relevant existing supervisor/isolation/asset tests once. Self-review and commit `Add sealed native reader feasibility preflight`. Root then executes acquisition/prepare/run and verifies raw artifacts before any downstream benchmark work. Do not build Gate 2 here.

## Root execution and handoff

After Task 1's review passes, root may download the single pinned candidate in parallel with Task 2 implementation: acquisition writes only the new ignored asset/run paths and uses the approved verifier. Model loading waits for both task-scoped reviews. Root then prepares a fresh run and executes once under the native sandbox. Preserve historical file hashes before/after. Record actual asset bytes, hardware/versions, continuous/active durations, calls/results/token counts, separate memory peaks/swap/availability, gates/probes, lifecycle and exact outcome. A blocked preflight gets a public aggregate report and no benchmark claims. A pass earns Gate 2's separately committed plan before any benchmark generation; the original design remains authoritative.

Run an appropriate full suite once after new source passes targeted checks. A fresh final whole-branch reviewer checks the implementation and measured aggregate evidence, with at most one final fix wave and one scoped re-review. Public docs include executed/unexecuted scope, public evidence hashes and no raw predictions/task text. Update README using `write-like-me` only for reader-facing prose. Archive the private plan workspace after review, publish sanitized archive hashes/rulings, commit and push main under standing authorization.

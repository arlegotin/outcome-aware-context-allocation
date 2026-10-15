# Task 17 handoff — MANIFESTS VERIFIED, NATIVE EXECUTION HELD

## Latest handoff: successful manifest-only attempt 2

After root's scoped approval and explicit renewed release, the reviewed writer succeeded at unchanged coordinator HEAD `869b701f4d3d0c23a02a3fe36be66af298d924c4`. New protocol: `ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07`, at `artifacts/protocol-task17-timing/protocol.json`. The canonical source binding hash is `02a4e334af73c6802f441a54bc84ab8578758da1cf80c68799bf1b9a682c11ed` over 26 files.

Existing `verify_protocol` and `plan(dry_run=True)` passed. Exact original sample bytes, 480 questions/N=7344, all 3,360 retained schedule rows and 1,920 direct primary jobs were verified. Only the three declared methods fields differ. Original four manifests and all 22 frozen source files remain byte-identical. Original index source `index-attempt:927ba64d93084cd2a6d43ead0b85ee54` remains owned by original protocol `415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100` and `artifacts/runs/confirmation`, with no new indexing cost claimed.

All attempt-2 receipts and full hash/settings/index-ownership report are preserved outside scratch at `artifacts/runs/operational-planning/task17-preparation-attempts/attempt-0002/`. Full report: `report.md`; report SHA256: `0c717fef137ad9c7e5249cb506eb46c39c56a3af4ab726ac20237d3aeb1b5c91`; receipt hashes: `receipt-sha256.json`.

- Writer/identity guards: 02:13:08.944674–02:13:29.424858 UTC; 20.480114 wall / 20.480051584 performance-clock seconds.
- Independent verification: 02:14:40.144523–02:14:45.322061 UTC; 5.177387 wall / 5.177372792 performance-clock seconds.
- Attempt-2 measured phase sum: 25.657501 wall / 25.657424376 performance-clock seconds. UTC envelope including inspection/communication interval: 96.377387 seconds, not an additive cost.
- Including the retained failed attempt once: 32.149756 wall / 32.149662584 performance-clock seconds of measured local preparation phases.

The dry-run's inherited original-plan `feasible=True` is explicitly non-certifying for this new roster and current wall budget. Root's measured-budget/awake/original-closure authorization remains separate. The new native run directory and index realization do not exist. No model loading, index construction, generation, Gold/scoring/prediction/raw outcome access or source/config/test/git mutation occurred. New manifest files are untracked; no publication or commit was attempted.

## Fix round 1 source handoff history: shared output-container compatibility

Recorded UTC: `2026-10-15T02:09:05+00:00`. Fix commit: `1ad111e8055aa022787dc1e7a548d497f676a693`, based on coordinator HEAD `27b61596c0b61c49b3493d0a8b99bf9b73f3fad1`. Only the new writer and its tests changed: 47 insertions, 6 deletions. No config/amendment/frozen-core/primary-input changes.

**Root cause and ruling:** The live parent uses `artifacts/` as its broad output container. Treating that entire directory as an exclusive root incorrectly rejected the reviewed fresh descendants. The writer now protects the four original scientific files and every original source/artifact binding individually, while retaining exclusive protection of the original run and index roots. Existing or partial destinations, resolved aliases and mutually nested new roots remain rejected. This is the root-authorized actual-container contract correction, not a new output-path workaround.

The real-producer synthetic fixture now covers `output_dir=artifacts`, `run_dir=artifacts/runs/confirmation`, an original bound model artifact under the shared container, and the two approved new descendant paths. Its end-to-end success test verifies original bytes, selected settings, parent/index/source bindings and all 3,360 jobs. Nine negative cases cover original run root/child, index child, scientific/source/artifact file descendants, an artifact ancestor, original-container ancestor and mutually nested new roots.

Verification:

- RED: `.venv/bin/python3.12 -m pytest 'tests/test_task17_manifest.py::test_preserves_sample_bytes_settings_and_exact_seven_job_schedule[shared]' -q` → **1 failed in 2.99s**, the same overlap `ValueError` as the live failure, at 02:04 UTC; `task-17-fix1-red.log`.
- Layout GREEN: shared-container success plus nine negative cases → **10 passed in 43.22s**; `task-17-fix1-layout.log`.
- Final focused command: `.venv/bin/python3.12 -m pytest tests/test_task17_manifest.py tests/test_protocol.py -q` → **57 passed in 177.18s**, exit0. Started 02:05:39 UTC; completion observed before 02:08:57 UTC; `task-17-fix1-focused.log`.
- Diff whitespace checks pass; diff against 27b6159 for frozen `src/outcome_poc`, configs, lockfile, original calibration/native tools is empty. Commit range contains exactly the two new Task17 file modifications. An unrelated root-owned checkpoint edit was left unstaged and untouched.
- Root's pre-fix integration evidence was 762 passed/0 skips in 183.50s plus clean dependency checks and 22 exact frozen hashes. The full suite was **not rerun after this narrow fix**, per root's explicit instruction; current evidence is the 57 focused tests.

**Failed physical preparation remains accounted:** Copied the five original failed-attempt receipts/report byte for byte into ignored `artifacts/runs/operational-planning/task17-preparation-attempts/attempt-0001/`, with `copy-sha256.json`. Both source and preserved copies were rechecked unchanged. This is duplicate evidence of the same physical attempt, not a second cost. Retain 6.492255 wall seconds / 6.492238208 performance-clock seconds from 02:00:55.000805–02:01:01.493212 UTC. The result receipt SHA256 is `d6c4f4ee9412099ef361b7c2a9fbc09f10cbdba5d25fff1416e0b5f71aa9f692`.

**Hold:** No live writer retry occurred. No original quality/Gold/model/index/runtime data was read during this fix; tests used synthetic fixtures only. Await the original reviewer's scoped approval and a separate root release before another manifest-only attempt. Native launch remains separately held.

## Initial source handoff history

Recorded UTC: 2026-10-15T01:52:41+00:00. Sole implementer release started from `887ca711dc7f1caa0f7425b0be5eaba39ec83cbd` on `main`; source commit is `1f8a30436405afbec7023a809b35ddd1feefd273`.

## Delivered scope

Only four new tracked files:

- `tools/task17_manifest.py` — manifest-only writer, existing production verifier/source capture/scheduler, exact raw sample copying, source/artifact/index-origin binding, new roots, no overwrite/resume and no launch.
- `tests/test_task17_manifest.py` — synthetic parent generated through the real frozen protocol producer; original 480/N7344 shape, actual verifier/scheduler/source capture with only Git subprocess responses controlled; no live inputs.
- `configs/task17-timing-replication.json` — expected original protocol hash, separate output/run roots, unchanged original deadlines plus declared latest launch/collection cutoff.
- `docs/amendments/A03-timing-replication.json` — explicit outcome-blind amendment, original timing invalidation and original-data preservation, selected B* comparison only, fixed complete roster and cost/operational rules.

The new methods differ only in `representatives=[]`, own operational index realization path, and `deadline_utc=2026-10-15T10:12:52+00:00`. The raw original sample bytes, 480 task IDs/order/tasks, N7344, algorithm/seed/document hash, selected policies, models, reader/prompt/token/timeout/encoder/retrieval algorithm, repetitions and statistical settings are preserved. The unchanged scheduler produces 3360 jobs: 1920 primary plus 480 each anchor, random and oracle-source.

Original source hashes must equal the new committed source capture. The new writer/tests/config/A03 are explicitly added to the source seal. Parent protocol and scientific sidecars, original index seal and its bound file hashes are additionally bound without replacing any original artifact binding. Index completion metadata and its successful physical attempt are checked without constructing/loading an index. The parent index's original owner protocol/root and physical source ID are retained; separate run setup/execution IDs use protocol/root namespacing. New native receipts remain the unchanged runtime's responsibility.

## Verification evidence

- Initial RED: `.venv/bin/python3.12 -m pytest tests/test_task17_manifest.py::test_manifest_writer_is_available -q` — **1 failed**, missing writer, at approximately 01:44 UTC; `task-17-red.log`.
- Behavioral RED against writer stub: `.venv/bin/python3.12 -m pytest tests/test_task17_manifest.py -q` — **23 failed, 1 passed in 88.79s**, completed approximately 01:47 UTC; `task-17-red-behavior.log`. Missing manifest construction produced the expected failing behavioral tests; interruption test also required the not-yet-present writer atomic-write symbol.
- First focused GREEN: byte/settings/schedule preservation plus interruption/unbound-read tests — **2 passed in 13.86s**, approximately 01:49 UTC; `task-17-first-green.log`.
- Additional RED: mismatched amendment parent identity — **1 failed** because the writer did not reject it; fixed by binding A03's parent hash and declared deadlines, approximately 01:50 UTC; `task-17-amendment-red.log`.
- Final focused command: `.venv/bin/python3.12 -m pytest tests/test_task17_manifest.py tests/test_protocol.py -q` — **47 passed in 104.51s**, exit0, launched 01:50:10 UTC, completion read 01:52:15 UTC; `task-17-focused.log`.
- `.venv/bin/python3.12 tools/task17_manifest.py --help` — exit0; help only, no manifest construction.
- `git diff --cached --check` before commit — exit0. Frozen source/config/lockfile/native/calibration diff against BASE was empty. `git diff --name-status 887ca71 HEAD` after commit lists exactly the four additions above.
- Broad suite is deferred to root's later gate, as explicitly directed. No claim that the full suite ran in this task.

No live data, protected sample/protocol/run/index/model/Gold/score/transfer artifacts or runtime forecast file were read during implementation. No native generation, model loading, index construction, live manifest creation or execution occurred. No children/worktree/branch/push. Untracked provenance files belonging to other activity remain untouched.

## Operational limits and separate release

**Source review is still required. Source approval alone does not release live manifest creation or launch.** The writer records `launch_authorized=False` and inherited forecast `operational_feasibility_established=False`, never calls `protocol.plan`, and cannot authorize execution. Root must separately release manifest construction and own the original-close/stop, measured-budget, awake-evidence and native-launch decision.

The unchanged runner checks the collection deadline between jobs. Root must include setup, final in-flight job and closure time, preserve the two-hour report reserve, and enforce measured feasibility even when it demands a launch earlier than the declared08:12:52 UTC ceiling. Root supplied a metadata-only planning estimate9641.586s (about2h40m42), with assumed closure component and no quality access; that operational evidence was **not read from disk, copied into the original forecast, or represented as stable-runtime certification** here.

A03 allows at most one conditional complete replication, after original closure/stop and with no concurrent model/index work. Unestablished awake conditions or inability to fit means wholly unexecuted; verified suspension invalidates the new wall-time endpoint. No power/thermal bypass, selective removal, clock repair, third attempt, post-outcome extension, family-wide superiority claim or additional independent questions.

No source API blockers remain. Await root's fresh source review and separate live-work release.

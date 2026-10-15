# Task 17 source handoff — READY FOR SOURCE REVIEW

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

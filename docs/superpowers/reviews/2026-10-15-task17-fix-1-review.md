### Spec Compliance

- ✅ Spec compliant for scoped FIX ROUND 1, reviewing `27b61596c0b61c49b3493d0a8b99bf9b73f3fad1..1ad111e8055aa022787dc1e7a548d497f676a693`.
- **Important finding — ADDRESSED:** The original shared `artifacts/` container no longer excludes fresh descendant destinations. `_new_roots` protects the four scientific sidecars and every original source/artifact binding individually, while preserving exclusive original run/index roots (`tools/task17_manifest.py:40`).
- **Protection requirements — ADDRESSED:** Existing paths/symlinks are still rejected before resolution; resolved roots retain symmetric overlap checks against protected paths and each other. Thus the fix permits fresh siblings under the shared container without permitting original-file descendants, original-run/index descendants, protected ancestors or nested new roots (`tools/task17_manifest.py:32`, `tools/task17_manifest.py:46`).
- **Actual-layout regression — ADDRESSED:** The synthetic fixture uses the existing protocol producer with `output_dir=artifacts`, `run_dir=artifacts/runs/confirmation`, a bound artifact in the shared container and the reviewed new destinations. The full preservation test now runs for both dedicated and shared containers; nine added rejection cases retain original bytes (`tests/test_task17_manifest.py:50`, `tests/test_task17_manifest.py:126`, `tests/test_task17_manifest.py:175`).
- **Failed physical preparation preservation — ADDRESSED:** All five saved files in `artifacts/runs/operational-planning/task17-preparation-attempts/attempt-0001/` match both `copy-sha256.json:1` and their original scratch copies. The saved result receipt retains failure return code 1, wall cost 6.492255 seconds, performance-clock cost 6.492238208 seconds and unchanged-original-file evidence. Its SHA256 is `d6c4f4ee9412099ef361b7c2a9fbc09f10cbdba5d25fff1416e0b5f71aa9f692`. These are duplicate records of one physical attempt, not another incurred cost.
- **Live retry hold:** The latest handoff reports no retry. Metadata-only checks found neither `artifacts/protocol-task17-timing` nor `artifacts/runs/task17-timing-replication` exists or is a symlink. This corroborates absence of published new output; it does not independently prove that no process was ever invoked.
- **NOT ADDRESSED findings:** None.
- **New breakage:** None found in this fix.
- **Out of scope:** Live manifest construction, operational launch authorization, future timing validity and broad-suite revalidation. This source approval releases none of those activities.

### Strengths

- The fix changes only the destination protection model, leaving source/artifact verification, sample copying, schedule construction and publication unchanged (`tools/task17_manifest.py:40`).
- The shared-layout success case exercises the full existing preservation assertions, and the new negative cases verify unchanged original bytes after rejection (`tests/test_task17_manifest.py:126`, `tests/test_task17_manifest.py:175`).

### Issues

- Critical: none.
- Important: none remaining.
- Minor: none.

### Checks

- Read the supplied fix diff once and reviewed only the reported finding and its fix; no broader source rereview, Git crawl, child agent, test rerun or live writer invocation.
- Existing RED evidence reproduces the reported overlap failure: `task-17-fix1-red.log:1`, 1 failed in 2.99s. Existing GREEN evidence is clean: `task-17-fix1-layout.log:1`, 10 passed in 43.22s; `task-17-fix1-focused.log:1`, 57 passed in 177.18s.
- Hashed only the five explicitly identified failed-preparation records and their copies, read the saved operational result receipt, and checked existence/symlink metadata for the two new destinations. No original protocol, sample, run output, model, index, Gold or quality data was opened.

### Assessment

**Task quality:** Approved

**Reasoning:** The scoped fix resolves the actual shared-container incompatibility while preserving the required file-level and exclusive-root protections. Regression evidence covers the permitted layout and prohibited collisions, and the failed preparation's physical cost remains preserved outside scratch; another live attempt still requires the root's separate release.

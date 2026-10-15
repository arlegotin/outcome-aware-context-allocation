# Task 18 fix round 1 source re-review

**SpecCompliance verdict: Approved.**

**Quality verdict: Approved.**

Scope: the previously reported Important finding I1 and new breakage introduced by the supplied `941e51a45719c937cad6f1841a1cdcef91631fe8..f12491c6f684250fa2b9ea0df10b6b46368042fd` fix. This carries forward the original review's unaffected findings and limits; it is not a new broad source audit.

## Finding disposition

**I1 — ADDRESSED.** At `src/outcome_poc/action_replay.py:148`, admission now explicitly captures `protected-run.closed.json` and, for native runs or a present synthetic completion fixture, `launch.completed.json`. It retains each marker's hash and every declared dependency hash. It checks the native completion protocol/success fields and verifies each dependency's digest before admitting it.

At `src/outcome_poc/action_replay.py:159`, resolved dependency paths must remain inside the run root. This rejects traversal or symlink targets outside that root before the new traversal hashes them. No existing output guard or immutable-write behavior is relaxed. The fix does not change the frozen validators or their earlier reads.

The captured hashes flow into `input_hashes`. The existing publication loop at `src/outcome_poc/action_replay.py:356` rechecks all of them before either `immutable_json` publication call, and the separate analysis closure retains the complete hash map. Consequently, the previously demonstrated resource mutation and changes to the native completion marker/dependencies now prevent report publication.

**New breakage: none found in the scoped fix.** The diff adds only the dependency capture and four regression cases in the new Task 18 adapter/test files. No frozen runtime source, Task 15 code, protocol/config/sample/schedule, model asset, release guard, or primary analysis is changed.

**Not addressed: none.**

**Out of scope:** actual A03 closure, installed model/index execution, actual output parity and root analysis release. Source approval does not authorize those actions.

## Verification

Reviewed the fix report, supplied diff, relevant publication code, and archived raw logs/receipts in `scratch/task18-fix-round1`. All five file hashes recorded by `archive.json` match their archived bytes.

- RED: four selected operational-closure regressions failed before the fix, with three expected-rejection cases reporting `DID NOT RAISE` and the retained-binding case reporting a missing operational dependency; **4 failed, 26 deselected in 8.20s**.
- GREEN: the same focused/neighboring suite plus these regressions passed: **59 passed in 32.90s**, exit 0.
- Compile: the two changed Python files compiled successfully, exit 0.
- Receipts consistently identify the explicit project `.venv/bin/python3.12`, Python **3.12.9**, `PYTHONPATH=src`, and `PYTHONDONTWRITEBYTECODE=1`. The recorded subprocess intervals and pytest-reported durations have distinct, consistent scopes.

The new tests exercise mutation of the real synthetic producer's `resources.jsonl`, mutation of a native-shaped completion marker, mutation of its dependency, and successful persistence of both markers and all declared dependencies. Mutation cases assert that neither report nor closure exists after rejection. The native-shaped fixture is correctly described as synthetic evidence, not an executed native process.

No suite rerun or additional behavioral probe was needed for this re-review. Only archived-evidence hashing was executed. No actual protected protocol/run/sample, model/index, Gold or outcome was read; no implementation or git state was changed. Actual analysis remains held and requires separate explicit root release.

# Citation-chain study software review

The prospective spec is [here](../specs/2026-10-15-citation-chain-reader-study.md). These are software reviews, not experimental results.

Task1 (`f3e8257..6217ab9`) passed independent spec/quality review with no findings. It freezes prompt conditions, fresh cohorts, stage-local stores and source/input bindings. Authored tests:10 focused; repository suite879 passed with no skips.

Task2 (`6217ab9..0db12e1`) passed29 focused tests and a repository suite of898, with no skips. Independent review found one Important cost-accounting defect: initial closure/source/assets/input validation occurred outside the scoring-attempt envelope, so rejected validation attempts were absent. Fix `bef34c9` moved validation inside the timed guarded envelope, preserving closure-before-Gold. Two authored regressions first failed;17 covering tests then passed. A scoped independent rereview marked the finding addressed with no new breakage. The898-test full-suite result belongs to `0db12e1`, before this one-line production fix; it is not represented as a new full-suite run at `bef34c9`.

One Minor test-isolation observation remains for the final review: the session-probe negative fixture supplies one observation, so the384-observation admission denominator also makes it fail. The positive native admission fixture exercises full provenance, but that negative fixture should isolate its named condition.

The native tests use authored data/backends. They exercise actual kernel network/Gold/comparison denials, spawned import guards, SQLite, a complete384-cell fixture, scoring/admission, retained paid partials and interruption accounting. They establish no real-model quality or timing finding. Real cohort reconciliation, generation, scoring/reproduction, historical-byte checks and public reporting remain root-owned execution steps.

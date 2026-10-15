# Final whole-branch review: citation-chain reader study

Reviewed range: `0ca7b0423bc72c9024bf50ec240270931816f98f..57d48bf` (all six commits). Requirements: `docs/superpowers/specs/2026-10-15-citation-chain-reader-study.md` and the corresponding implementation plan. This is the single broad final review, covering software, experimental integrity, and public claims together. Applied the Superpowers 7 requesting-code-review reviewer contract, including the explicit declined-to-judge ledger below.

## Strengths

- **The intervention is isolated and prospectively bound.** `src/outcome_poc/citation_study/prompts.py:7` preserves the baseline string and appends exactly the prescribed sentence through a local one-call message adapter. `study.py:26` expands reservation/normalized-duplicate exclusions to a fixed point and selects from sorted IDs with the specified PCG64 permutation. `preparation.py:130` freezes source, assets, inputs, settings, prompt registry, cohorts and schedule before the diagnostic Gold projection; `runtime.py:87` and `runtime.py:95` bind assigned factors and actual generation settings into validated completions. The source snapshot identities independently match every corresponding file at measured commit `14544f6a6c1c88ce67d647fc616faaf8aef3b6c4`.
- **Serving and privileged analysis remain separate.** `runtime.py:31`, `runtime.py:53` and `runtime.py:374` guard coordinator and spawned imports, validate source origins and exact native profiles, and require real denial probes before acquisition/work. Diagnosis denies both comparison inputs and derived comparison-stage files. The comparison handoff at `runtime.py:67` binds externally produced admission identities without opening the denied score store. Authored native tests at `tests/test_citation_native.py:9` and `:95` exercise actual Seatbelt/SQLite/spawn behavior and a positive full-denominator admission path.
- **Failures cannot become a favorable smaller sample.** `runtime.py:114`, `:172` and `:333` retain paid intents, partial tokens and interrupted work; fatal assigned failures abort permanently; constructor failure checks owned-worker quiescence before backend assignment. Uncertain session stops retain null exact endpoints. `runtime.py:131` seals every assigned completion before scoring; `scoring.py:12` now times and retains the entire scoring attempt, including rejected initial validation, before any Gold iteration. The previous Important finding is resolved in the reviewed code.
- **Analysis and admission match the frozen design.** `scoring.py:72` applies healthy completion, strictly greater natural-10 joint count and both nonlower observed answer guards. `analysis.py:7` requires complete factorial pairs, uses the declared finite-population tails, retains all work in success ratios, and removes the generic helper's preservation claim. The public report at `docs/experiments/2026-10-15-citation-chain-reader-study.md:3`, `:44` and `:76` clearly distinguishes development diagnostics, wide uncertainty, an unexecuted independent comparison and descriptive costs with explicit exclusions. README claims agree with those limits.
- **The real-run evidence supports the published result.** The sealed diagnosis contains 384 observations on 64 questions and one separately paid authored warmup; all 1,024 comparison jobs are still unexecuted. Natural-10 joint successes are 4→6 and answer matches 43→42. The immutable decision is `defer`, with healthy execution and the answer guard false. The public summary exactly matches the retained private aggregate, and its allocation diagnostic matches paired counts computed from already sealed scalar score fields. No new scoring or prediction-text review was needed.

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

None found.

### Minor (Nice to Have)

**M1 — The session-probe negative test does not isolate probe provenance.** `tests/test_citation_runtime.py:172` supplies one completion to `execution_health`, while `src/outcome_poc/citation_study/scoring.py:99` requires 384. Consequently both assertions at test lines 173 and 176 remain false even if the named provenance checks regress. This is the previously deferred Minor, confirmed at the final line locations. Use an otherwise healthy 384-record fixture, first establish that it passes, then remove or mismatch a session's probe; alternatively test a narrowly extracted provenance predicate. The actual per-session checks at `scoring.py:103`–118, the positive native test, and this run's matched session/probe records provide independent evidence, so this remains optional coverage improvement rather than a correctness or publication blocker.

## Evidence and checks performed

- Reviewed the changed source/config/test files and public report, README diff, machine-readable provenance, spec and plan; inspected the inherited completion/commit, sandbox/import/worker, warmup, session accounting/reconciliation, parser, reader factory and exact paired-bound helpers where their contracts affect this adapter. The branch is additive apart from the authorized README update; historical source/config/report files are not modified by its diff. `git diff --check 0ca7b04 57d48bf` produced no errors.
- Verified the canonical plan hash `640aa00bfd6b850c168e4e0441027ac10efa3f46e6601b49b927a535fca30a6d`, bindings/cohort/schedule hashes and sorted eligibility hash. The retained metadata contains 88,907 eligible representatives, 672 prior reservations, 7,344 protected representatives, an 8,016-ID exclusion fixed point, disjoint 64/256 reservations, and remaining comparison population 88,843.
- Independently checked all public proof-file identities, all 2,388 files in the diagnosis prediction closure by opaque byte hashes, and all 51 plan-inventory identities. Compared every source-snapshot identity with the recorded Git commit. No question, Gold, rendered real prompt or prediction text was exposed or adjudicated.
- Checked complete schedule/receipt counts, the score seal and decision bindings, absent comparison index/closure/admission, one exact session receipt, its matched native denial probe, worker registration, and both passing resource gates. There are no assigned fatal statuses or recorded stage failures. Counts total 356 `ok`, 19 abstentions, 5 parse errors, 2 invalid citations and 2 output-cap failures.
- Checked all cell success counts, all joint/answer/support paired four-cell counts, service totals and seconds/success ratios against retained scalar score records. Public and private diagnosis/comparison aggregates and physical-cost fields are identical. Natural-10 joint pairing is both 4, baseline-only 0, chain-only 2, neither 58; answer pairing is 41, 2, 1, 20. The conservative intervals use N=88,907 for diagnosis and the prescribed .0125/.00625 tails. The unexecuted comparison retains its distinct N=88,843 design.
- Reconciled the recorded disjoint preparation, index, session and two successful scoring envelopes to 758.317299334 seconds. Session cost is 692.6688395 seconds; scoring is 30.462316501 seconds. Publication explicitly excludes launcher/preflight, admission, standalone verification, reporting, engineering/tests, review, prior assets and deployment work, and does not double-count nested jobs/warmup/lifecycle intervals.
- Inspected primary preservation/reproduction evidence in `artifacts/runs/citation-study-recon/`: `historical-before.json`, both `historical-after-*.json` receipts, `scores-before-reproduction.json`, `score-reproduction.json`, `rescore-diagnosis-v1.log` and `verify-v1.log`. Both historical checks report 5,834 checked and no changes, referring to the independently matched before-manifest SHA256 `a629bacd40fd6dbf7c1556a056e4c2d606dce65d06a1622771d7b96bc7239bef`. All four reproduction identities match current retained files and the public record; the fresh-process output carries the same summary/plan identity.
- Did not rerun suites or scoring. Existing scoped evidence is 898 full-suite passes at `0db12e1`, followed by 17 covering passes at `bef34c9`; the public provenance accurately attaches each result to its revision. Reviewed the scoring-envelope regression tests and scoped rereview rather than representing these as new final-head test runs.
- No subagents, model invocation, new Gold inspection, network, Git mutation, or production-source/test mutation. Only this explicitly requested ignored review artifact was written.

## Recommendations

Record M1 as accepted optional coverage debt. Preserve the failed admission decision and reserved comparison cohort exactly as recorded. Complete the already planned review resolution, process archive and final repository/push checks; they are outstanding coordinator steps, not defects in the reviewed experiment or a reason to repeat the completed suite/study.

## Declined to judge

- Benchmark answers, citation sufficiency, alternative valid citations and qualitative score overrides: explicitly excluded from this review; no real question/Gold/prediction text was inspected, and the study deliberately retains the original strict metric.
- A real-model comparison effect or comparison cost: all 1,024 comparison calls are properly deferred, so no such empirical evidence exists. Reviewed its admission/isolation implementation and authored integration coverage only.
- Customer-workload generalization, pretraining contamination, routing learnability, controller value, confirmed efficiency, preservation, deployment break-even and production stationarity: outside this fixed reader study's deliverable and expressly disclaimed in publication.
- A more permissive recovery, retry, treatment-search or sample-extension policy: the prospective conservative fail-stop/admission rules are intentional constraints, not implementation omissions to relax after observing results.
- New independent execution of the real scorer, all existing tests, or the historical preservation audit: duplicating those runs was prohibited/unnecessary; inspected their retained evidence and independently authenticated relevant current seals/counts/source identities instead.
- External revalidation of upstream licenses, model cards or literature: no network was authorized for this review; publication identifies pinned assets and references existing repository notices without redistributing raw data/models.
- Final archive completion and remote push: explicitly still owned by the coordinator after this review. The last combined plan item remains unchecked correctly; no claim of remote publication completion was assessed.

## Assessment

**Ready to merge/publish? Yes.** No Critical or Important finding remains. The software, retained aggregate evidence and public interpretation agree on a healthy but failed development screen; M1 is a nonblocking test-isolation improvement. Final process archival and push remain to be completed by the coordinator.

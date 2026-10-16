# Independent reader admission: passed; allocation efficiency untested

The unchanged evidence-first-v1 prompt passed the prespecified independent reader
admission contract on512 new normalized question groups. Strict benchmark success
rose from27 to103 and answer EM from260 to344. All simultaneous zero-margin quality
guards passed, the strict-quality lower bound is strictly positive, and
invalid/runtime failures decreased17→7. This establishes benchmark reader admission
for this pinned reader/packet/recipe. Human semantic adjudication, operational
usefulness and allocation efficiency remain unestablished.

| Endpoint | Baseline ten | Evidence-first ten |
| --- | ---: | ---: |
| Assigned questions | 512 | 512 |
| Answer exact matches E | 260 (50.78%) | 344 (67.19%) |
| Strict successes S | 27 (5.27%) | 103 (20.12%) |
| Exact support-set EM | 14.65% | 25.59% |
| Invalid/runtime failures | 17 | 7 |
| Abstentions | 14 | 3 |
| Mean complete warm T | 2.79854 s | 2.89224 s |
| p95 / p99 T, descriptive | 4.08302 / 4.90591 s | 3.93352 / 4.58715 s |
| R, descriptive only | 53.06854 s/S | 14.37694 s/S |

The candidate took0.09370 seconds more per request on average, about3.35%.
Its lower descriptive R reflects substantially more strict successes. No frozen
allocator A*/development-selected B*, eligible primary R interval, final routing
trial or operational saving is demonstrated by this reader-only comparison.
Absolute strict quality20.12% is not an established service-quality floor.

| Paired endpoint | Both succeed | Candidate rescue | Candidate harm | Both fail | Difference | Existing simultaneous interval |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Strict S | 16 | 87 | 11 | 398 | +.1484375 | [.08182694, .21151471] |
| Answer E | 243 | 101 | 17 | 151 | +.1640625 | [.09065564, .23370545] |

The finite sampling frame was recomputed as N88235, not inherited from historical
N88427. Each tail alpha remains.003125; selected comparator and fixed-ten are the
same unchanged baseline-ten action, with all four original guards retained.
The previous64 are development evidence; the old reserved128 remain excluded.
All512 new cases are now consumed. No cases were appended, dropped or replaced,
and no interim quality scoring occurred. Baseline statuses were481 ok,
14 abstain,14 invalid_citation and3 parse_error; candidate502 ok,3 abstain and
7 invalid_citation. Every failure and its serving cost remains in the assignment.

The source was frozen before generation at base commit
bb0de32cfbc5488d8563fd73ef0b3d38d04d020e plus the bound dirty source inventory
b7396d6e6ae6481d3b1006f8ea0fc5c7cbd98e253e650a98d9d4fbc9383b5c8f.
This is an actual inference run on that78-file Python/build snapshot, not on a
later final commit. The plan hash is
216909fd9d58a2785fdea3fb0e50b03b08d6fe0cdbdfb0bc402561a5c7bc1517.
Source, configs, cohorts, schedule, pinned model/tokenizer/template bytes, complete
paid calls, continuous receipts, exact assignment, recursive index ancestry,
OS denials in coordinator/child and parent/worker closure authenticate locally.
Actual per-question text/output and private archives remain external.

The admitted candidate text and generation settings are unchanged from the earlier
candidate. The NEW native path uses the actual allocation runner, exact original
fit_extension tasks, frozen stage authorization and continuous request-through-
durable-response/receipt accounting. Active worker telemetry stays diagnostic;
nested costs are not added. Unsupported legacy native recipe/timing flags fail
closed; historical collection/tune/confirmation runners and ledgers were not
silently migrated or resealed. The general allocation default remains baseline.

The fixed prospective design chose n512 from256/512/1024 using hypothetical
paired E/S/failure scenarios, target+.10 strict and+.10 answer improvement, and
joint-power Monte Carlo95 lower bound≥.80. Estimated target power was.8746
[.86513,.88349]; half-effect and equal-discordant-failure stress power was only
.1342 and.4938. These were research assumptions, not stakeholder requirements.
The actual1024 assigned calls plus one warmup completed inside the registered
5400-second native cap. Two separately identified authored native smokes made
five calls each; the second verified the final measured cleanup fix. Their
invented answers are software fixtures, not benchmark evidence.

Complete request seconds sum to2913.67564, nested within the2939.27991-second
resident envelope. The authenticated continuous index-setup envelope was80.62498
seconds. CLI validation before that index envelope was not fully timed; complete
index-invocation/adaptation overhead, historical engineering and human-review
costs remain unknown. Do not add service/lifecycle/warmup again to the resident
cost or claim an operational break-even from R. All registered resource gates
passed. Observed parent/child RSS maxima were795918336/2968993792 bytes; swap was
nonzero. These are sampled measurements, not exact peak-working-set guarantees.

First-half/second-half mean T increased from2.64583→2.95124 seconds for baseline
and2.73503→3.04944 for candidate. Balanced paired order does not certify
stationarity or attribute that descriptive drift. One timing per condition,
unmeasured thermal/system load, unverified repeat determinism and no controlled
suspension test preclude an eligible efficiency claim. Maximum observed
continuous/active drift was39.4 microseconds; this does not certify suspend
behavior. Native timeout/cleanup/source-domain tests and injected clocks provide
software coverage only for their tested conditions.

The held measured source passed1163 native tests, zero skips, in359.49 seconds.
The first in-progress full run overlapped source edits and correctly failed
source-drift checks (2 failures,1 error,1156 passes); its log is preserved. After
reviewed source hold, the suite passed. Post-freeze diagnostic/guard additions
then passed1170 tests, zero skips, in377.82 seconds; their separate inventory is
recorded and is not attributed to this inference. Official parity ran with the
authenticated4257-byte evaluator at SHA256
d35fc91a6db21d791dbdda11daf3856e9359f5701d54e3eefba20d88fecc02c0.
Project Scorer retains its intentional valid/nonempty strict gate and separate E.

Fresh-process, fresh-output actual Scorer recomputation reproduced every measured
E/S/cost field and independent aggregate sum; retained trial inputs stayed
byte-identical. Read-only diagnostics separately recomputed admission, paired
tables, failure/status counts, timing quantiles, order/drift and resources. See
[evidence/analysis.json](evidence/analysis.json),
[evidence/fresh-rescore.json](evidence/fresh-rescore.json) and
[evidence/prospective-freeze.json](evidence/prospective-freeze.json).

This passes WP3's unchanged-benchmark reader gate and permits the separately
registered [v4 action-value screen](../allocation-action-v4/protocol.md).
It does not establish useful pre-answer allocation. Qualified independent human
review is unavailable, so semantic/reference and real-world usefulness claims
remain blocked. Actual quality floor, worthwhile saving, latency/failure limits,
representative workload and deployment horizon remain unknown. No Gold changes,
model enlargement, paid sentence selector or production deployment occurred.

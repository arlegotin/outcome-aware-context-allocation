# Reader recovery: three final reviews and evidence disposition

This review concerns new uncommitted source based on `ae1706bb1739c1c0a4e724b33feaa8b01289d292` in an isolated worktree. The measured160-call snapshot is separately identified in the [report](../../experiments/2026-10-15-reader-recovery.md). Historical source, configs, mutable ledgers and seals were not edited.

## 1. Paths, contracts, source and executable dependencies

An independent code-review agent inspected the actual producer and consumers. It did not inspect benchmark outputs or select models. Substantive findings and corrections:

- A recursive validator needed to appear in source capture, not just in imports. It is now included in protocol and transfer/action-replay source inventories.
- Actual transfer serving could bypass index validation after preparation. It now loads the validated recursive lineage.
- A resealed manifest could omit SQLite metadata. The validator requires the exact two real-producer payloads with valid identities and consistent window counts.
- Shared-ancestor traversal could grow exponentially. A validated canonical-path cache prevents repeated traversal; references and conflicting attempt identities still bind before deduplication.
- Identity changes during traversal needed a final check. Manifest, vector and ledger-prefix rechecks reject injected mutation. This is an authenticated capture, not an OS immutable-filesystem guarantee.
- Later unrelated appends must not rewrite frozen costs, but duplicate/conflicting IDs in present tails must still fail. The validator authenticates frozen newline-aligned prefixes and checks the current tail without charging it to the old interval.
- Action replay needed to validate new seals while preserving explicit legacy handling. New-lineage validation and helper-source capture were added; old seals are not silently upgraded.
- New recovery closure needed all stage telemetry and exact full Cartesian assignment, not just per-job receipts. Source drift, extra telemetry and a resealed empty schedule now fail before Gold.
- A startup deadline alone did not bound a late paid call. The wrapper checks every actual generation, including shared warmup, with remaining request, synchronization and cleanup allowance.

Root inspection found a separate missing direct index revalidation in the scorer. The real measured run had already retained explicit `verify_index` admission before Gold, so its records were not rebound. New source now checks the index in `closed_records`. The initial authored fixture accidentally froze the index with pre-index inputs and masked this omission. It was corrected to the real preparation order; the test then failed on a missing Gold read instead of rejecting the tampered vector, and passed after the guard. The changed source and test are separately inventoried from the measured snapshot.

Executed evidence:45 targeted cases passed after that correction, followed by the stable full native suite: **1,109 passed, zero skips,322.27s**. All51 lock entries match the retained native Python3.12.9/macOS arm64 environment; `pip check` passed. Actual pinned4B/BGE asset bytes and model/tokenizer/template inventories were authenticated. Native parent and child denial probes ran during actual inference. A new environment reinstall was not performed. The original checkout remains clean at the inspected HEAD.

## 2. A scenario where all code passes but useful QA/efficiency fails

A separate research-contract reviewer assumed the software passed and constructed counterexamples:

- A shorter Gold-selected view can be cheaper and score better while being unavailable to deployment. Its time/quality numbers must remain privileged diagnostics.
- A clairvoyant frontier can show a saving even when no cheap observables predict the good action. It establishes neither learnability nor paid training amortization.
- An exact reference set can omit a needed bridge or reject an adequate alternative; optimizing it need not improve useful evidence support. An LLM judge cannot validate a replacement endpoint.
- A model can answer from memorization, with plausible citations added later. Answer EM plus exact reference-set agreement cannot certify causal evidence use or truth.
- Thirty-two sparse questions can yield wide intervals and accidental apparent wins. A passing30-success ratio gate would still not establish useful power or absolute quality.
- Mean time can hide reliability and tails, and unknown engineering/annotation cost can make amortization unavailable.

Reporting corrections: all four setup costs are included, along with separate launcher/scoring/probe envelopes. Resident/service/warmup intervals are disclosed as nested rather than added twice. General preparation/engineering/history remain unknown. Diagnostic `preserved` fields are not presented as simultaneous guards. The oracle explicitly lacks an answer guard. No reader/allocation/operational claim is admitted. The fixed natural-before-oracle order is disclosed as a timing confound. A partial assignment cannot be scored as a smaller experiment.

These are conceptual counterexamples and reporting checks, not new empirical proof. The independent blind evidence review is auxiliary LLM rubric evidence, not an independent human audit. Its two strict-success flags concern one repeated question; human adjudication remains outstanding.

## 3. Failure stress and actual execution

Root reviewed the following against implemented tests and observed execution:

| Stress case | Executed software/native evidence | Remaining limit |
| --- | --- | --- |
| Missing/tampered parent, vector, ledger, malformed schema, cycle, duplicate ID | Real index producer with authored documents and deterministic fake encoder; chain/diamond/reload/parity regressions | Synthetic software fixtures do not authenticate historical dependencies automatically |
| Later unrelated ledger append or failed index attempt | Frozen-prefix/additional-cost regressions; all four real no-reuse setup journals retained | Attribution is distinct from dependency ancestry; engineering cost unknown |
| Worker startup error, exception, timeout, death, stalled/partial IPC, sync/cleanup failure | Existing continuous-supervisor/runtime native subprocess and injected-failure tests passed | Actual160-call run had no such failures; reliability rate is not operationally established |
| Interrupted/partial closure, missing Gold, altered source or telemetry | Existing closure tests plus new real diagnostic transaction/scorer fixture | New adapter intentionally has no automatic group resume; incomplete groups stay unscored |
| Suspension and reboot | Integer tick conversion, simulated clock/deadline/reboot tests, actual native boot/domain validation | Controlled native suspension and actual reboot during a run were not performed |
| Empty/malformed evidence, alias permutations, original indices, booleans/duplicate JSON keys | Authored recovery and existing parsing/scoring regressions passed | Semantic adequacy requires more than membership |
| Zero successes/no-op, negative outcomes/nonfinite features | Existing/new ratio, target, feature and frontier tests passed; actual2/10 zero-success outputs retained | No finite R or quality-preservation claim follows |
| Fresh-root/source/model/prompt/clock mismatch | Source-binding/native denial/asset/clock tests plus actual snapshot execution | Original mutable-CLI consumers remain historical; the new path must be used explicitly |
| Stochastic decoder | New contract requires unchanged greedy recipe; no seed search | Stochastic evaluation and interval redesign were not implemented or validated |

Actual inference completed natural96 and oracle64, two known-answer warmups, both owned-worker quiescence closures and both fresh scorer passes. All160 failures/statuses remain in scored denominators. Full-suite synthetic/fake-encoder cases are software checks, not model outcomes. All seven official evaluator parity cases ran with authenticated external source; without it they correctly skip. No controlled power setting, system suspend, production use, paid remote service or restricted-data upload occurred.

## Disposition

Implementation of the bounded diagnosis and lineage repair: complete. Native technical checks and actual local diagnosis: executed, with the limits above. Useful reader improvement: unproven. Outcome-trained allocation advantage: unproven. Operational usefulness: unassessed because actual requirements are absent. Conditional reader/allocation/final phases were not launched;64 validation and128 evaluation IDs remain reserved and untouched.

Next decisive prerequisite: independent human adjudication of the private evidence/annotation packet. If that supports a citation-generation intervention under the unchanged strict target, freeze one authored evidence-first candidate and its independent validation protocol. Do not increase routing-label acquisition or repurpose the final pool to resolve this diagnosis. Native controlled-suspend validation remains a separately authorized check before a suspend-sensitive efficiency claim.

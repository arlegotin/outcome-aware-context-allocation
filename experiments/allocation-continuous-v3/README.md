# Continuous allocation serving and independent reader admission

This NEW v3 experiment uses the actual durable allocation runner for a fixed,
independent baseline/evidence-first reader comparison. It follows the
[prospective protocol](protocol.md) and the user's unchanged WP0–WP6 gates.
It does not reopen either completed-v1 protocol or the preparation-only v2.
The original checkout and historical ledgers remain retained and unchanged.

The complete512-question trial passed the unchanged reader-admission gate.
See [report.md](report.md) for outcomes, exact bounds and limitations. Allocation
efficiency remains untested; downstream action acquisition has its own v4 gate.
The prior [v2 report](../allocation-recovery-v2/report.md) records its earlier
preparation increment; its source/evidence snapshot is preserved separately.

NEW scientific schema3 separates `study_kind=allocation-reader-admission-v3`
from the unique `protocol_id`. `purpose` is either the two-case
`authored-native-smoke` or fixed `reader-admission`. Both use `frozen-native`,
unchanged reader settings, one repetition, explicit baseline/evidence-first arms,
`request_timing=complete-continuous-v3`, exact call and continuous compute caps,
current administrative window and reporting reserve. The config authenticates
retained roots/catalog, pinned asset authority, historical private reservation
identities and prepared manifest. Reader admission additionally binds prospective
precision/eligible-frame identities and a successful native smoke with identical
source/assets. These fields are NEW interfaces, not historical config options.

All scientific roots must be outside active/retained source/evidence. The
preparer locks the catalog, closes duplicate-group exclusions, selects before
Gold, then reserves the assignment append-only. Missing private metadata, changed
source/assets, unsupported schedules, reused IDs or root collisions fail closed.
An interrupted fixed assignment remains incomplete and cannot be subset-scored.
Serving denies raw/Gold, score projections, prior studies/archives and live source
in both coordinator and reader process. Only assigned natural paragraphs enter
paid prompts. Fresh stages preserve the original `fit_extension` split;
protected confirmation keeps its independent original authorization.

The selected immutable recipe reaches actual paid calls and prompt/signature
identities. The complete continuous interval encloses validation, initial/final
synchronization, retrieval/routing/rendering, all paid calls, parsing, durable
payload/completion and receipt. The study's outer interval also charges its
required per-request closure work. Worker active timing is diagnostic and nested.
Unknown sync/generation cleanup, domain/reversal, failed receipt publication or
missing parent/group closure blocks scoring. Scientific timing refuses replay or
cache modes; legacy replay stays a development diagnostic. Legacy native
collection/tune/confirmation/transfer entrypoints keep their existing baseline
behavior and reject unsupported new recipe/timing flags. This study does not
silently migrate historical assignments or checkout-relative execution windows.

The following are the actual preparation/acquisition commands used in the isolated
checkout; preparation is single-use and rerunning it must reject the reserved ID:

```sh
cd /Users/artemlegotin/.codex-s/worktrees/9c9b/outcome-aware-context-allocation
.venv/bin/python -m outcome_poc.reader_recovery prepare-scientific --config experiments/allocation-continuous-v3/authored-smoke-v3b.config.json --root /private/tmp/oaca-allocation-native-smoke-20261016-v3b
.venv/bin/python -m outcome_poc.reader_recovery index --root /private/tmp/oaca-allocation-native-smoke-20261016-v3b
.venv/bin/python -m outcome_poc.reader_recovery run --root /private/tmp/oaca-allocation-native-smoke-20261016-v3b --group natural
.venv/bin/python -m outcome_poc.reader_recovery prepare-scientific --config experiments/allocation-continuous-v3/reader-admission.config.json --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3
.venv/bin/python -m outcome_poc.reader_recovery run --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3 --group natural
```

The benchmark's separate index acquisition used `index` under the same continuous
parent supervisor with600 seconds; its exact command, budget and parent closure
remain at the private run's `index-parent/`. The stage allows1025 reader calls
including warmup and5400 continuous seconds. See the configs and protocol for all
research assumptions. Operational requirements remain unknown.

After complete native closure, the first scoring invocation loaded the measured frozen source. For retained evidence, use the read-only fresh-output audit below; score appends an attempt record and would change its sealed input inventory.
The following records the original first scoring invocation, which recomputed rather than returned a cached score (do not invoke
on an incomplete assignment):

```sh
cd /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3
PYTHONPATH=/private/tmp/oaca-allocation-reader-admission-20261016-n512-v3/source/src /Users/artemlegotin/Documents/git_alter/outcome-aware-context-allocation/.venv/bin/python -B -m outcome_poc.reader_recovery verify --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3
PYTHONPATH=/private/tmp/oaca-allocation-reader-admission-20261016-n512-v3/source/src /Users/artemlegotin/Documents/git_alter/outcome-aware-context-allocation/.venv/bin/python -B -m outcome_poc.reader_recovery score --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3
```

NEW read-only aggregate diagnostics and existing fresh-output rescore tools run
from the same frozen project modules. Outputs must use new private roots and
must not overlap retained source/evidence. Restricted rows/text remain private.
A public clone lacks the private inputs and cannot authenticate/reproduce them.

```sh
PYTHONPATH=/private/tmp/oaca-allocation-reader-admission-20261016-n512-v3/source/src /Users/artemlegotin/Documents/git_alter/outcome-aware-context-allocation/.venv/bin/python -B /Users/artemlegotin/.codex-s/worktrees/9c9b/outcome-aware-context-allocation/tools/audit_recovery_run.py --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3 --output /private/tmp/oaca-reader-v3-rescore-01
PYTHONPATH=/private/tmp/oaca-allocation-reader-admission-20261016-n512-v3/source/src /Users/artemlegotin/Documents/git_alter/outcome-aware-context-allocation/.venv/bin/python -B /Users/artemlegotin/.codex-s/worktrees/9c9b/outcome-aware-context-allocation/tools/analyze_reader_trial.py --root /private/tmp/oaca-allocation-reader-admission-20261016-n512-v3 --output /private/tmp/oaca-reader-v3-analysis-01
```

Native software verification used the disposable unchanged pinned environment:

```sh
HOTPOT_EVALUATOR_PATH=/private/tmp/oaca-recovery-evidence/hotpot_evaluate_v1.py .venv/bin/python -m pytest -q -ra
.venv/bin/python -m pip check
.venv/bin/python -m outcome_poc --help
.venv/bin/python -m outcome_poc.reader_recovery --help
```

The held source passed1163 native tests with zero skips. The authored v3b smoke
strictly answered/cited both invented questions in both conditions, with actual
sandbox/parent/worker closure. Neither result establishes allocation effectiveness
or controlled-suspension behavior. Post-freeze software diagnostics are explicitly
distinguished from the measured source by the evidence inventory.

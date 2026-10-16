# Allocation recovery v2 continuation

This increment prepares safer benchmark research. It does **not** complete
continuous-clock allocation integration, admit a reader, or demonstrate useful
allocation. The [prospective protocol](protocol.md) records the unchanged claim
contract, unknown operational requirements and zero new-generation budget.
The [status file](research-status.json) is a nonexecuting research record, not a
preparation config.

Implemented software includes a distinct preparation-only validation schema,
balanced paired schedules, authenticated original and additional exclusions,
resolved retained-root checks, immutable recipe identities, actual paid/prefix
render selection, recipe-bound resume/replay signatures, selected-budget
forecasts, and a read-only fresh-output historical rescorer. Native candidate
allocation and v2 scientific execution fail closed. Their clock, cleanup and
fresh-stage integration remain required. Existing baseline behavior and all
historical evidence/seals remain intact.

These are the **actual local commands**, using the isolated checkout and its
independently installed pinned environment:

```sh
cd /Users/artemlegotin/.codex-s/worktrees/9c9b/outcome-aware-context-allocation
.venv/bin/python -m pip check
PYTHONDONTWRITEBYTECODE=1 \
HOTPOT_EVALUATOR_PATH=/private/tmp/oaca-recovery-evidence/hotpot_evaluate_v1.py \
.venv/bin/python -m pytest -q -rs -p no:cacheprovider
.venv/bin/python -m outcome_poc --help
.venv/bin/python -m outcome_poc.reader_recovery prepare-fresh-validation --help
```

Native sandbox fixtures need a host that permits macOS kernel profiles. The
complete native suite was run outside the outer tool sandbox; a normal outer
sandbox may deny those checks. Test fixtures use invented data. No test result
constitutes benchmark or controlled-suspension evidence.

Fresh historical Scorer recomputation uses each run's **bound original source**,
the exact complete assignment/receipts, a fresh process and a new output directory.
It does not call the mutable historical `score` stage, append its attempt ledger,
or return cached scores. These retained-input commands are local/private; the
output directory created by `mktemp` is only an unused parent:

```sh
cd /Users/artemlegotin/.codex-s/worktrees/9c9b/outcome-aware-context-allocation
OACA_AUDIT_PARENT=$(mktemp -d /private/tmp/oaca-recovery-audit.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/private/tmp/oaca-reader-evidence-first-v1/source/src \
.venv/bin/python tools/audit_recovery_run.py \
  --root /private/tmp/oaca-reader-evidence-first-v1 \
  --output "$OACA_AUDIT_PARENT/validation"
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/private/tmp/oaca-reader-recovery-v1-attempt4/source/src \
.venv/bin/python tools/audit_recovery_run.py \
  --root /private/tmp/oaca-reader-recovery-v1-attempt4 \
  --output "$OACA_AUDIT_PARENT/diagnosis"
```

These paths were available and authenticated on this host. They are not public
clone prerequisites. A public clone can run the authored fixtures but cannot
authenticate unavailable private cohorts, Gold, model bytes or raw outputs.
Never restore over an existing sealed root or alter a seal to relocate it.

Two successful fresh validation recomputations from the final audit tool produced
identical new score bytes. Diagnosis was independently recomputed twice as well.
Every recomputation checked that the entire retained input inventory stayed
unchanged. Public evidence contains aggregate results and identities only;
per-question rows and restricted corpus/annotation text remain external.
See [the audit report](report.md) and [evidence manifest](evidence/manifest.json).

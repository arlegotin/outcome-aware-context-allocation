# Outcome-aware context allocation

**Result: inconclusive.** The fixed experiments and scoring reproduction are complete; the original full-family run remains incomplete and unscored.

This experiment asks whether a cheap controller trained on actual reader outcomes can choose between two and ten retrieved paragraphs better than a controller trained on cheaper proxy labels. Success requires both the correct answer and exact annotated supporting citations. The reader and retriever run locally; this is a HotpotQA distractor-packet experiment, not web search.

The completed A03 comparison used the same 480 preregistered questions. The outcome-trained controller had **14 strict successes**, the proxy controller **17**, and FIXED10 **11**. These sparse outcomes do not support the frozen primary interval, and none of the four simultaneous quality guards establishes preservation. Both runs excluded host-suspension time from their timers, so no wall-time efficiency or break-even claim is valid. The original full-family run remains incomplete at 6,510/8,640 jobs and is deliberately unscored.

There is useful answer-level variation in which context budget works, but little observed room under the strict target: a clairvoyant two-budget oracle achieves 20 strict successes versus 16 for the best fixed budget. Eight enriched, agent-reviewed citation disagreements suggest a mixture of real citation gaps and plausible nonexact reference-set penalties. That diagnostic changes no scores and estimates no prevalence. Richer outcome labels have not shown added value here; citation/reader reliability and an informative strict target should be checked in a fresh protocol before expensive label expansion.

Read the [final report](artifacts/final_report.md) for the same-denominator tables, quality guards, timing failures, conditional replay, costs and limitations. The technical appendices preserve machine-readable evidence. The latest unchanged-source verification passed 802 native Python 3.12.9 tests with zero skips; documentation work does not require a broad repeat.

## Native setup for a fresh checkout

The verified platform is arm64 Python 3.12.9 on an Apple M3 Max with 36 GiB RAM and macOS 26.7.1. The hashed lock targets this platform; another platform needs its own explicitly verified environment. In a fresh checkout, install without changing the pinned dependencies:

```sh
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip --cache-dir .cache/pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip --cache-dir .cache/pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip --cache-dir .cache/pip check
.venv/bin/python -m outcome_poc --help
```

These are setup/help instructions, not commands to replay collection over retained evidence. Before any data, asset, index or generation stage, configure fresh isolated output/index roots and a new experiment protocol. Public metadata does not include private raw data or model snapshots.

- [Implementation specification](docs/superpowers/specs/2026-10-14-outcome-aware-context-allocation-design.md)
- [Implementation plan and execution status](docs/superpowers/plans/2026-10-14-outcome-aware-context-allocation.md)
- [Research and attribution handoff](research_poc_plan.md)
- [Pinned assets and license provenance](artifacts/provenance/asset-manifest.json), [environment](artifacts/provenance/environment.json), and [dataset/source audit](artifacts/provenance/wp1-data.json)

## Reproduce retained evidence

With the original private artifacts retained, fresh scoring reproduction reads the complete A03 evidence and writes a new receipt outside its frozen run:

```sh
.venv/bin/python3.12 -m outcome_poc reproduce --scores-only \
  --protocol artifacts/protocol-task17-timing/protocol.json \
  --output artifacts/runs/reproduction-check/a03-receipt.json
```

The original run's corresponding reproduction returns unavailable/incomplete without opening Gold. Deterministic score reproduction does not validate wall time. Public metadata alone cannot reproduce the run without the retained private datasets, assets and ledgers.

## Start a new experiment safely

Use fresh output/index roots and configuration with a new protocol. A fresh clone contains source and sanitized metadata, not the private datasets, annotation-bearing protocol or closed predictions; it requires a separate new-run data/setup workflow. Do not rerun mutable discovery, asset acquisition, preparation or index commands over retained frozen artifacts. In particular, A03 binds the shared index-attempt ledger; an ordinary index run under that parent can invalidate its binding. Share existing immutable assets read-only only where the new configuration permits it.

The prospectively sealed pooled diagnostic completed 32 queries / 96 jobs: A* achieved 4 strict successes, B* 3 and FIXED10 2. These queries are part of the main 480; the small descriptive difference is not independent confirmation. Original-reference document-ID recall@10 was 0.796875, without certifying sentence-level support. The report discloses the native reuse-provenance extraction defect and verified external reconciliation; the frozen source was not repaired. Original full-roster protected POST/LLM results, optimized prefix reuse, MuSiQue and additional stress/generalization tests remain unavailable or unexecuted.

The [machine summary](artifacts/summary.json) and [risk ledger](artifacts/remaining-risks.json) preserve the conclusion and limits. Exact raw evidence remains local; sanitized public metadata and source alone are not a self-contained dataset release. Final branch review and a post-review process-archive refresh remain pending.

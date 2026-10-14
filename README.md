# Outcome-aware context allocation

A local experiment in development: train a cheap controller to choose two or ten already-retrieved paragraphs before a QA reader generates its answer. Evaluate complete serving time per HotpotQA joint-EM success against strong tuned baselines.

Validated records, durable storage, native discovery, pinned assets, isolated data preparation, deterministic CPU retrieval, and the citation reader/scorer are implemented and reviewed. Controller training and comparative experiments remain ahead. Passing these gates is not evidence of a research improvement.

- [Implementation specification](docs/superpowers/specs/2026-10-14-outcome-aware-context-allocation-design.md)
- [Implementation plan](docs/superpowers/plans/2026-10-14-outcome-aware-context-allocation.md)
- [Research and attribution handoff](research_poc_plan.md)
- [Planning review](docs/superpowers/reviews/2026-10-14-planning-review.md)

## Native setup

The verified environment is arm64 Python 3.12.9 on an Apple M3 Max with 36 GiB RAM, macOS 26.7.1. The lock contains exact wheel hashes for this platform, including MLX 0.32.3 / MLX-LM 0.32.0, Sentence Transformers 6.1.0, Transformers 5.19.0, and CPU PyTorch 2.14.1. A different platform needs an explicitly resolved and verified environment; do not silently upgrade packages during comparisons.

```sh
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip --cache-dir .cache/pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip --cache-dir .cache/pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip --cache-dir .cache/pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m outcome_poc discover --config configs/base.json
.venv/bin/python -m outcome_poc assets --config configs/base.json
.venv/bin/python -m outcome_poc smoke --config configs/base.json
```

Model/data downloads stay in ignored `models/pinned`; dependency caches stay in `.cache`. Serving adapters require existing local paths. Downloads resolve commit metadata before fetching safe files, preserve/hash model cards and original licensing, and reject external pickle or executable snapshot files. `assets` retains bounded access failures and returns nonzero if an indispensable asset remains blocked. `discover` leaves denied measurements null and fails its resource gate. On this managed Mac, approved execution outside the ordinary sandbox is required for public downloads, read-only `sysctl`, and Metal access.

`smoke` uses the installed chat template, greedy decoding, one sequence, 8,192 total-token and 256 output-token caps, no speculative decoding, fresh unquantized/nonrotating KV caches, and explicit MLX synchronization. It compares two generated token-ID sequences, validates a short citation JSON example, checks normalized finite CPU float32 384-column encoder vectors, and records load times, RSS/MLX peaks, and swap. It leaves at least the greater of 4 GiB or 20% of physical RAM outside a conservative RSS-plus-MLX bound. The short smoke does not establish capacity for the longest benchmark prompts; those checks remain required before protocol freeze.

Offline smoke also denies Python socket connections and sets Hub/Transformers offline flags. The verified run additionally used macOS OS-level network denial:

```sh
sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  .venv/bin/python -m outcome_poc smoke --config configs/base.json
```

An unguarded socket probe confirmed this OS policy denied connections. Current gate details are written to `artifacts/provenance/wp0.json`; environment, asset and wheel manifests, package freeze, API signatures, original execution-window record, and failed attempts are preserved separately. A reader-only smoke cannot pass the overall data-required WP0 gate.

## Asset provenance and source amendment

The reader is `mlx-community/Qwen3-4B-Instruct-2507-4bit` at `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`, declaring Apache-2.0 and linking the original Qwen license. Original `Qwen/Qwen3-4B-Instruct-2507` licensing/configuration is pinned at `cdbee75f17c01a7cc42f958dc650907174af0554`. The CPU encoder is `BAAI/bge-small-en-v1.5` at `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; its pinned author card declares MIT. The separately preserved upstream FlagEmbedding license is the file linked by that card, with its provenance recorded explicitly.

Live official CMU training and distractor-development URLs timed out. Acquisition amendment **A01**, recorded before data collection, permits the unaltered raw Internet Archive replay of those exact author-origin filenames at capture `20250512032701`. The loader from a third-party Hugging Face archive was inspected as text and never executed; transformed records and parquet reconstruction are not used. Full native JSON/schema, expected lengths and row counts, memento/WARC/original response metadata, local SHA-256, and the available training CDX SHA-1 payload digest were checked. No archive digest was independently obtained for dev. The archive distribution has no established author endorsement, and byte equivalence to a separately fetched current author copy cannot presently be established. Any protected population must identify this archived author-origin snapshot.

HotpotQA is the dataset of Yang et al., *HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering* (2018), released under [CC BY-SA 4.0 by its authors](https://hotpotqa.github.io/). Retain attribution and applicable share-alike obligations when distributing data or derivatives. Raw/model/data text and caches are not committed by default.

`discover`, `assets`, `smoke`, `prepare`, `audit-data`, `index`, `reader`, and `score` currently execute stages. Other commands listed by `--help` remain proposed interfaces and return an explicit unavailable-stage error. Preparation produced a protected population of 7,344 structurally valid representative questions; it has no model outcomes. The current index covers only the first 32 development pilot questions.

One ten-paragraph development reader diagnostic returned valid JSON/citations but failed answer and support scoring. Its raw output and failure are retained locally. This checks the plumbing, not allocation headroom or efficiency. The next experimental gate is a paired two/ten pilot with complete warm serving costs; no controller fitting or protected generation has run.

The experiment tests context allocation on supplied evidence packets. It does not establish open-web search savings, commercial value, algorithmic novelty, or a full reproduction of related papers. Negative, tradeoff, inconclusive and prerequisite-blocked outcomes are valid handoffs.

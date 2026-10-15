# Outcome-aware context allocation

We are testing whether an AI can read less evidence and still answer correctly. A cheap controller chooses two or ten retrieved passages before the answer is generated. Success requires both the correct answer and the correct supporting citations; the cost includes all work, including failures and extra model calls.

Practice runs are complete. The outcome-trained controller has not beaten the simpler support-label-trained alternative on the development comparison. That finding is preliminary.

The frozen 480-question test is running. Repeated Mac sleep interruptions exposed a timer that excludes suspended time, so the original run cannot establish the intended wall-time efficiency claim. Its raw work is retained. The [execution checkpoint](artifacts/checkpoint_report.md) records current status, remaining work and the deadline. No improvement or preserved-quality claim has been established.

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

`discover`, `assets`, `smoke`, `prepare`, `audit-data`, `index`, `reader`, `validate-harness`, `pilot`, `collect`, `fit`, `tune`, `freeze`, `plan`, and `score` currently execute stages. Other commands listed by `--help` remain proposed interfaces and return an explicit unavailable-stage error. Preparation produced a protected population of 7,344 structurally valid representative questions; it has no model outcomes. The current indexes cover 64 reserved pilot questions, 256 separate fit questions and 128 tuning questions, with exact-identity document-vector reuse across stages.

One ten-paragraph development reader diagnostic returned valid JSON/citations but failed answer and support scoring. Its raw output and failure are retained locally. This checks the plumbing, not allocation headroom or efficiency. The accounting/recovery harness has passed its scoped reviews and native checks; its six development calls remain recorded. The paired two/ten pilot has now closed and scored all 64 assigned questions. Nine control models have been fitted; the frozen protected collection is running and its outcomes remain unscored.

Development-only structural checks found top-two prompts of 283–670 tokens and top-ten prompts of 1,203–2,304 across the reserved 32-question pilot, with no initial-cap overflow. Top two contained every annotated support document on 17 questions; all ten did on 32. Support inclusion is a proxy, not observed reader success or a controller advantage. The separate audit costs and counts are retained in `artifacts/provenance/pilot-token-length-audit.json` and `pilot-retrieval-coverage-audit.json`.

The reviewed pilot found two strict joint-EM successes at each budget, with two rescues and two harms from larger context. Answer EM was 23/64 at two paragraphs and 32/64 at ten; mean warm serving time was 0.85 versus 2.49 seconds. The clairvoyant oracle covers four successes, just enough to pass the declared development gate. Missing or mismatched supporting sentences make the learning signal sparse. These are development diagnostics, with no trained-controller or protected superiority finding. Every baseline family completed the disjoint tuning comparison before the protected protocol was frozen. Evidence and complete acquisition costs are in [the experiment state](artifacts/provenance/experiment-state.json) and [the pilot gate](artifacts/provenance/task9-pilot64/wp3-gate.json).

The independent fit batch retained 512 budget observations: 18/256 strict successes at two paragraphs and 12/256 at ten, with 11 harms and five rescues. Answer EM was 112/256 versus 131/256. These are training outcomes; the separate development comparison below measures tuning performance, while protected generalization remains untested. Model fitting took 0.485 seconds, while label acquisition took about 926 seconds. [Fit provenance](artifacts/provenance/task10-fit256/fit-summary.json) records all controls and [the source qualification](artifacts/provenance/task10-fit256/native-source.json) describes retrospectively reconstructed development instrumentation. The tuning implementation now validates complete-ledger accounting once per closed snapshot while retaining exact saved costs; [the scaling checks](artifacts/provenance/task12-accounting-scaling.json) record its boundaries.

Paid-control checks retained 102 native development calls and a separately fitted POST controller using the existing labels. Exact greedy output and scoring matched with prefix reuse, but a declared numerical check failed on two cases. Comparisons therefore use the actual no-reuse POST path and retain an optimistic lower-cost bound to avoid overstating its disadvantage. [The comparator gate](artifacts/provenance/task11/comparator-gate.json) and [development report](artifacts/provenance/task11/report.md) preserve both runs, failures, costs and source hashes. The protected comparison has not yet been scored.

The reviewed 128-question tuning comparison retained all 246 configurations. The chosen outcome-trained GBM produced 10 strict successes and 58 answer-only successes; the chosen support-coverage proxy produced 11 and 60. Their reconstructed serving seconds per strict success were 19.11 and 14.66. Ridge, query-only and random-forest controls also beat the candidate on this development objective. These sparse tuning results do not establish a protected effect. A small held-out 128-versus-256 training check showed no stable progress, so additional labels are not justified now. [Selection and all family representatives](artifacts/provenance/task12-selection.json) preserve the losing rows, common quality rule and optimized-POST sensitivity.

The receipt integrity review found and fixed two forward-closure defects before protected work. New closures require complete paid-call evidence and preserve existing closure bytes; original development v1 closures retain their explicit retrospective qualification. [The scoped approval](docs/superpowers/reviews/2026-10-14-task12-fix-1-review.md) records 570 passing tests and the unchanged original data/model/selection hashes. [The recovery checkpoint](artifacts/checkpoint_report.md) records unfinished work and the original deadline. [Capacity](artifacts/provenance/capacity-input-audit-summary.json) and [complete-roster cost forecasts](artifacts/provenance/confirmation-cost-forecast-audit.md) inform the upcoming freeze without selecting favorable protected questions.

The reviewed confirmation protocol fixes 480 questions, all eleven family representatives, fixed-two/fixed-ten diagnostics and two fresh paired repetitions of the main contenders: 8,640 complete pipeline jobs. Calibration retained 286 paid calls and passed two exact 7,936-input/256-output checks. The 37.0816-second timeout and runtime forecast are measured; timing stationarity remains unverified. [Freeze and calibration evidence](artifacts/provenance/task13-report.md) and [the protocol review](docs/superpowers/reviews/2026-10-14-task13-review.md) preserve the hashes, costs and limitations. Protected execution is underway; original wall-time inference is invalidated by the recorded host-sleep clock discrepancy. Separate scoring remains held.

The experiment tests context allocation on supplied evidence packets. It does not establish open-web search savings, commercial value, algorithmic novelty, or a full reproduction of related papers. Negative, tradeoff, inconclusive and prerequisite-blocked outcomes are valid handoffs.

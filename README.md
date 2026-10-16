# Outcome-aware context allocation

A local research harness for testing **how much context a RAG reader needs before it answers**. Train a small controller on paired reader outcomes, compare it with fixed budgets and cheaper controls, and measure **seconds per successful task**, including retrieval, routing, generation and failures.

The controller chooses between two and ten retrieved paragraphs using the question and retrieval metadata. It makes that choice before generation, without an extra language-model judging call.

## Results

**An evidence-first prompt nearly quadrupled strict benchmark successes** on 512 fresh HotpotQA questions. Both prompts used the same pinned Qwen3-4B-Instruct-2507 reader, BGE-small-en-v1.5 retrieval and ten-paragraph evidence packets.

| Metric | Baseline prompt | Evidence-first prompt |
| --- | ---: | ---: |
| Correct answer + exact supporting citations | 27 / 512 | **103 / 512** |
| Correct answer string | 260 / 512 | **344 / 512** |
| Invalid outputs / runtime failures | 17 | **7** |
| Mean complete request time | 2.80 s | 2.89 s |

The [prompt](src/outcome_poc/reader_recipes.py) asks the reader to select the sentences supporting the complete answer path, then answer. All prespecified benchmark quality guards passed. Strict success requires the reference answer and exactly the annotated supporting sentences; it measures benchmark agreement. See the [independent reader report](experiments/allocation-continuous-v3/report.md).

**Learned allocation hasn't established a saving.** On 256 held-out questions, the outcome-trained controller matched fixed-ten's 66 strict successes, lost one answer match and reduced reconstructed seconds per strict success by only 2.13%. It failed the registered continuation screen, and further label collection under that hypothesis stopped. The [routing report](experiments/allocation-learning-v5/report.md) contains all controls and learning curves.

## What you can reuse

- **Paired budget evaluation.** Run the same reader at different context sizes and learn from the change in answer and citation success.
- **Held-out policy comparisons.** Select models and thresholds on fit data, then evaluate locked rules against fixed budgets and simpler learners.
- **Complete request accounting.** Include routing overhead, parsing and durable response storage; retain failed attempts in the record.
- **Bound experiments to their inputs.** Freeze source, prompts, assets and cohorts, keep reference annotations out of serving inputs, and verify index ancestry.

Source, tests, configs, aggregate reports and selected provenance are included. Model weights, raw benchmark data, per-question outputs and fitted models remain external. Full result authentication requires the retained research assets; see [publication scope](docs/PUBLICATION.md).

## Run the checks

The hash lock targets **Python 3.12 on macOS ARM64**. Other platforms need separate dependency resolution and verification.

```sh
git clone https://github.com/arlegotin/outcome-aware-context-allocation.git
cd outcome-aware-context-allocation
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -m pytest -q
python -m outcome_poc --help
python -m outcome_poc.reader_recovery --help
```

These checks need no model weights or benchmark downloads. Seven official-evaluator parity cases require `HOTPOT_EVALUATOR_PATH`; native sandbox checks may skip where unavailable.

For a new experiment, follow the [fresh-experiment guide](docs/fresh-experiment.md) with separate output roots and a newly frozen protocol. The [release notes](docs/releases/v0.3.0.md) and [original findings](artifacts/final_report.md) retain the detailed results and history.

## License and citation

Copyright © 2026 Artem Legotin. Original software: **AGPL-3.0-only**. Original writing and result presentation: **CC BY 4.0**. See [licensing](LICENSING.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [citation](CITATION.cff). Implementation, experiments and documentation used AI assistance under the project owner's direction.

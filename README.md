# Outcome-aware context allocation

Can a small controller learn how much evidence an AI reader needs **before the reader answers**? This project tests that question with a local language model, a fixed packet of retrieved paragraphs, and a choice between reading two paragraphs or all ten.

**The experiment didn't establish an advantage.** On 480 questions, the controller trained on actual answer outcomes produced 14 fully correct, correctly cited answers. A controller trained on cheaper evidence-coverage labels produced 17. Sleep interruptions invalidated the speed measurements, so there's no demonstrated efficiency improvement either.

A fresh follow-up found real reading costs and room for better budget choices, but also a reader/citation problem that more controller training won't resolve by itself. On 128 new development questions, reading 2, 5 and 10 paragraphs produced **5, 7 and 8 correct answers with the exact reference citations**. A chooser that knew every outcome in advance could reach 12.

The next test added one sentence asking the reader to cite every link leading to the answer. On 64 fresh questions with ten paragraphs, strict successes rose from **4 to 6**, while correct answer strings fell from **43 to 42**. That failed the quality screen fixed before the run, so the larger comparison stayed unrun. It's a mixed development result. The project still has no demonstrated controller or efficiency advantage.

Switching to a larger reader didn't clear the next screen either: on 16 reused questions with ten paragraphs, it produced **1 strict success versus 2** for the smaller reader. The larger independent comparison remains unrun. There is still no demonstrated saving.

[Original findings](artifacts/final_report.md) · [Reader/headroom study](docs/experiments/2026-10-15-reader-headroom-followup.md) · [Citation-chain test](docs/experiments/2026-10-15-citation-chain-reader-study.md) · [14B feasibility](docs/experiments/2026-10-15-reader-capability-preflight.md) · [Reader comparison](docs/experiments/2026-10-15-reader-quality-comparison.md) · [Research and prior art](research_poc_plan.md) · [Publication scope](docs/PUBLICATION.md) · [Citation](CITATION.cff)

## The idea

A retrieval-augmented answering system often gives its reader a fixed amount of evidence. Some questions need less; others need more. Reading everything costs time, but stopping early can lose the sentence that connects the answer.

The proposed controller learns from that difference. During training, the same reader answers each question twice: once with two paragraphs, once with ten. The label is the change in task success. A small gradient-boosted regressor then predicts that change from the question and retrieval metadata. It chooses the budget before any answer is generated; it doesn't get a draft answer or a language-model judging call for free.

The intended objective is **seconds per successful task**, including retrieval, routing, generation, parsing and failed work. Fewer input tokens alone wouldn't settle it. All ten candidate paragraphs are already available in this experiment, so selecting two doesn't save a web search.

Adaptive retrieval and outcome-based routing have substantial prior art. The [research handoff](research_poc_plan.md) explains the overlap. The question here is whether this particular cheap controller earns its overhead against tuned alternatives on one frozen local system.

## What happened

The completed comparison used **480 questions from HotpotQA's distractor development set**, a pinned Qwen3-4B-Instruct-2507 reader running through MLX, and BGE-small-en-v1.5 retrieval. A strict success requires both the reference answer and exactly the annotated supporting sentences. That measures benchmark agreement; it doesn't certify truth or prove the reader used its citations.

Every row has the same 480-question denominator, including abstentions and failures. The two learned controllers each had two timing repetitions, producing identical answers; repetitions don't add independent questions.

| Policy | Correct answers | Correct answers **and** exact supporting citations |
| --- | ---: | ---: |
| Outcome-trained controller | 150 / 480 | 14 / 480 |
| Cheaper coverage-label controller | 155 / 480 | 17 / 480 |
| Always read ten paragraphs | 173 / 480 | 11 / 480 |
| Always read two paragraphs | 143 / 480 | 16 / 480 |
| Random two/ten mixture | 149 / 480 | 16 / 480 |

The differences don't establish quality preservation or a supported quality loss. Strict successes were too sparse for the prespecified primary efficiency interval, independently of the broken timing. The original, larger baseline run remains incomplete and unscored. Its partial results weren't turned into a smaller test set. The completed run contains 3,360 jobs on the same 480 questions.

There is a useful limit hiding in these numbers. Even a chooser that knew both outcomes in advance would get only **20 strict successes**, versus 16 for the better of the two fixed budgets. Answer-only outcomes have more room: that oracle gets 205, versus 173 for always-ten. A better budget choice cannot fix most failures under this strict target. Citation/reader reliability and the usefulness of the training target deserve attention before collecting more expensive outcome labels.

A pooled-corpus diagnostic gave 4 versus 3 strict successes on 32 queries drawn from the main 480: exploratory evidence, not independent confirmation. The [report](artifacts/final_report.md) retains that diagnostic, quality intervals, citation review, baseline replay, failures and costs.

## What the follow-up clarified

The separate [reader/headroom study](docs/experiments/2026-10-15-reader-headroom-followup.md) kept the same model and prompt, fixed new questions before outcomes, and used a continuous clock that includes sleep. All 688 assigned generations completed. Timings were stable: on its 128-question headroom set, two paragraphs averaged 1.00 second and ten averaged 2.78 seconds. No new controller was trained, so these timings establish reading costs, not a learned speed improvement.

The reader's evidence handling needs work. Even when given the known supporting documents in a separate 64-question diagnosis, it achieved only 3 exact answer-plus-citation successes. In an enriched eight-case review, an agent judged six citation sets to be missing a necessary relation and two to be plausible alternative sentence choices. That review leaves the primary scores unchanged; exact benchmark agreement and useful evidence support aren't interchangeable.

The [citation-chain test](docs/experiments/2026-10-15-citation-chain-reader-study.md) completed 384 answers across two prompts and three evidence conditions on 64 questions. Its one-sentence reminder didn't clear the development screen; the 256-question comparison remains deferred. At ten paragraphs it rescued two strict successes and lost none. Two previously matching answer strings stopped matching the reference, and one started matching it. The uncertainty is wide. This neither confirms the improvement nor establishes a real quality loss.

The prerequisite remains citation reliability and a useful success target. With the reminder, only 2 of 64 questions had different strict outcomes at two versus ten paragraphs. More expensive controller labels haven't earned their place yet. A stronger reader or a validated measurement change needs its own fresh test before the allocation experiment grows.

A larger reader passed its [local feasibility check](docs/experiments/2026-10-15-reader-capability-preflight.md), then failed the [16-question quality screen](docs/experiments/2026-10-15-reader-quality-comparison.md). With ten paragraphs it got **8 answer strings correct and 1 answer-plus-citation success**, versus **10 and 2** for the smaller reader. All 96 screening calls completed. The 128-question comparison stays unrun; its questions remain reserved. This small reused sample doesn't prove the larger reader is generally worse. It didn't earn more allocation-label collection in this setup.

## What you can reuse

You can use the harness to collect paired answers, compare fixed and learned budgets, score sentence-level citations, and account for every paid action. It separates annotations from serving inputs, freezes selection before evaluation, and preserves interrupted work. That gives the next allocation policy a concrete test, with its overhead included.

There is a known defect in native index ancestry bookkeeping: `protected.py` and `transfer_runtime.py` read reuse metadata from the wrong manifest level. A separate audit qualifies the recorded run's lineage; the frozen consumers remain unfixed. Correct both in separately versioned source before another experiment relies on native reuse provenance. Full adaptation cost and deployment break-even remain unknown. See the [review disposition](docs/superpowers/reviews/2026-10-15-final-review-disposition.md).

The follow-up has a separate runner with continuous deadlines and a fresh index that reuses no embeddings. It also includes a native regression for a sandbox/SQLite failure discovered during execution. The failed attempt remains recorded separately; none of the original results were repaired or overwritten.

This checkout includes source, tests, configuration, reports and selected provenance. Raw benchmark text, predictions, fitted models, downloaded assets and detailed archives stay external. A clone can run software checks and inspect the findings. Raw follow-up authentication requires the recorded `9ddc4ae` checkout at its bound original paths and the retained research assets; later hardening intentionally fails that run's source binding. A separate read-only archive audit checks retained hashes. See [follow-up reproduction](docs/experiments/2026-10-15-reader-headroom-followup.md#provenance-and-reproduction) and [publication scope](docs/PUBLICATION.md).

## Run the checks

The measured machine was an Apple M3 Max with 36 GiB RAM, macOS 26.7.1 and native Python 3.12.9. The hash lock targets that Python/macOS ARM64 environment. Other platforms need their own dependency resolution and verification.

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
python -m outcome_poc.reader_probe --help
python -m outcome_poc.reader_study --help
```

The latest suite passed **1,064 tests with zero skips** at `1be34ab`, including the paired-reader study. Earlier experiment source and results remain intact. The [reader-study software review](docs/superpowers/reviews/2026-10-15-reader-quality-software-review.md) records its checks and crash-recovery fix. The [final review](docs/superpowers/reviews/2026-10-15-reader-quality-final-review.md) also records the clean-clone test repair. Passing tests doesn't validate the original speed measurements or establish a research win. On non-macOS systems or inside an outer sandbox, the macOS denial-profile checks can skip.

These commands don't start a benchmark experiment. For a new study, follow the [fresh-experiment guide](docs/fresh-experiment.md): use a separate checkout, fresh output roots and attempt-ledger parents, new development outputs, and a newly frozen protocol. Historical configurations record this experiment. Running mutable setup or indexing over the retained evidence can invalidate its bindings.

The [implementation specification](docs/superpowers/specs/2026-10-14-outcome-aware-context-allocation-design.md), [execution plan](docs/superpowers/plans/2026-10-14-outcome-aware-context-allocation.md) and [pinned asset manifest](artifacts/provenance/asset-manifest.json) retain the detailed contracts. For raw-score reproduction with the private archive present, use the command in the [final report](artifacts/final_report.md#reproduction-evidence-and-next-steps).

## License and citation

Copyright © 2026 Artem Legotin. Original software is **AGPL-3.0-only**; original writing and result presentation are **CC BY 4.0**. [Licensing](LICENSING.md) defines that split. HotpotQA, Qwen, BGE and installed dependencies retain their own terms; see [third-party notices](THIRD_PARTY_NOTICES.md).

Please cite [CITATION.cff](CITATION.cff) and record the commit you used. Citation is requested separately from the licenses' conditions. Implementation, experiment execution and documentation used AI assistance under the project owner's direction.

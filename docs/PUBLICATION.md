# Public release scope

This repository publishes the implementation, the reported **inconclusive**
allocation result, and separately identified reader experiments. The original
publication preparation starts from scientific handoff commit
`c61ed7d`. It changes documentation, licensing and package metadata; it does not
change the frozen reader, retriever, scoring code, data, selected controllers,
sample, predictions or scientific conclusions.

The subsequent [reader/headroom follow-up](experiments/2026-10-15-reader-headroom-followup.md)
adds separate software, fresh development results and aggregate provenance. Its
867-test native suite and stable descriptive timings belong to that new study at
recorded source `9ddc4ae`. Later failure-accounting hardening at `c1c1720` passed
869 native tests separately; it was not used for the study or its rescoring.
The original source bindings, results and invalid speed endpoints remain unchanged.
The follow-up's private runs, benchmark text and model assets are not bundled.

The [0.2.0 research release](releases/v0.2.0.md) adds independently identified
reader-recovery and evidence-first validation protocols, continuous-time serving
and recursive index-lineage safeguards. On 64 reserved validation questions the
evidence-first prompt produced 19 strict successes versus 6, with a positive
prespecified strict interval. The answer-preservation guard crossed zero, so the
full reader admission gate failed. No new allocation or operational advantage is
established. The [validation report](experiments/2026-10-15-evidence-first-validation.md)
separates the measured frozen source from later reservation guards and release
metadata; none of the historical source bindings or seals were rebound.

## What a clone contains

The public tree includes original source, authored software fixtures, executable
configuration, the hashed platform lock, aggregate findings, review documents,
and selected provenance/path/hash records. The complete historical Git record is
retained so recorded source commits keep their meaning.

Raw benchmark files, prepared questions/documents/Gold, the annotation-bearing
protocol and sample, full predictions and event ledgers, fitted estimators,
model weights, environments, caches and detailed process archives remain local.
The public archive manifests describe retained bytes; they are not downloads of
the private archive. Some diagnostic metadata includes benchmark task IDs and
per-case score counts without question, answer or source-passage text.

Historical metadata retains machine-local paths and author identity. Some
original asset-download receipts retain Internet Archive operational headers,
including infrastructure routing cookies and ASN/ISP markers. These are retained
as provenance, not active credentials or portable configuration. A history scan
found no credentials, client/home IP, precise location or hardware identifiers;
that bounded scan is not a guarantee about every possible secret format.

## Three different reproduction tasks

1. **Check the software.** Follow the README's [setup and test commands](../README.md#run-the-checks).
   The suite uses authored fixtures and requires no downloaded benchmark, model
   weights or retained run archive. The measured dependency lock targets native
   Python 3.12/macOS ARM64. Other platforms need separate verification, and the
   macOS denial-profile checks may skip outside a supported native context.
2. **Authenticate the recorded experiment.** This requires the retained private
   datasets, assets, frozen protocols and complete closed ledgers. The
   [report's reproduction command](../artifacts/final_report.md#reproduction-evidence-and-next-steps)
   reruns scoring from raw predictions; aggregate tables and hashes alone cannot
   substitute for those inputs. The recorded fresh-process reproduction matched
   all 3,360 completed jobs. The original incomplete assignment remains unscored.
3. **Run a new experiment.** Follow the [fresh-experiment guide](fresh-experiment.md).
   Use a separate checkout, new writable roots and index-attempt ledger parents,
   newly generated development outputs and a new protocol/deadline. The supplied
   configs are historical records. Do not overwrite this experiment or treat its
   fixed sample as a new independent test.

Raw authentication of the follow-up requires its recorded `9ddc4ae` checkout at
the original absolute paths bound by the plan, plus the retained private assets
and closed run. The later hardened source deliberately rejects the frozen v2
mutable-source binding. No snapshots or manifests were rebound. A separate
read-only inventory and Git-source audit confirms archived hashes without
inference or scoring; it does not reproduce raw scores. The
[follow-up reproduction instructions](experiments/2026-10-15-reader-headroom-followup.md#provenance-and-reproduction)
and aggregate provenance distinguish these checks and source versions.

## Known limits remain in force

The outcome-trained controller has 14 strict successes out of 480, versus 17 for
the selected coverage-label controller. Sparse strict outcomes fail the frozen
ratio-interval gate. Both wall-time endpoints are invalid; active-clock
diagnostics establish no speed saving. No quality-preservation, complete-cost,
break-even, open-web, customer-value or algorithmic-novelty claim is made.

The historical protected and pooled index-seal consumers have a native reuse
ancestry defect. A reviewed external graph and pre/post guards qualify the
retained historical run only. Version 0.2.0 corrects both consumers through a
shared recursive validator, with real-producer chain, diamond, corruption,
failed-attempt and frozen-ledger-prefix tests. Historical source and seals remain
unchanged; old seals are not silently upgraded. The historical
[review disposition](superpowers/reviews/2026-10-15-final-review-disposition.md)
still describes its own source version. The new
[diagnosis and safeguards](experiments/2026-10-15-reader-recovery.md) describe the
repair. This is a provenance correction, not a measured quality gain or
production-readiness certification.

The 32-query pooled diagnostic is nested within the main 480. The eight-case
citation review is enriched, agent-assisted diagnosis. Neither supplies an
independent confirmation or changes any primary score. Dataset-source
equivalence, public-benchmark contamination and annotation limitations remain
explicit in the report.

## Publication verification

At publication-preparation commit `a9f7682`, a clean local clone with no benchmark,
model or retained-run assets passed **802 tests with zero skips** in 125.03 seconds.
That check reused the pinned native Python/dependency environment; the imported
project package came from the clean clone. It was software verification, not
another benchmark run or a newly resolved environment.

The citation passed the official CFF 1.2.0 schema. The package built without
dependency resolution and retained its exact license/notice files and README.
An independent review approved the publication changes. The bounded history scan
covered the 74 locally reachable commits at the scientific handoff; the new
publication files were reviewed separately. The [verification receipt](../artifacts/provenance/public-release-checks.json)
records these historical checks. Scientific source, tests, tools, experiment
configurations, the dependency lock and reported results were unchanged by that
original publication-only preparation. The separately versioned 0.2.0 software
and new experiments are described above; its release verification is recorded
separately in the [release notes](releases/v0.2.0.md).

## Rights and attribution

[LICENSING.md](../LICENSING.md) applies AGPL-3.0-only to original software and
CC BY 4.0 to original writing/result presentation. [Third-party notices](../THIRD_PARTY_NOTICES.md)
keep HotpotQA, model assets and dependency terms separate. [CITATION.cff](../CITATION.cff)
provides the software citation without an invented DOI or publication claim.

# Outcome-aware context allocation

A proposed local experiment: train a cheap controller to choose two or ten already-retrieved paragraphs before a QA reader generates its answer. Evaluate complete serving time per HotpotQA joint-EM success against strong tuned baselines.

This repository currently contains the specification and implementation plan. No PoC code, asset downloads, inference, controller training or benchmark results have been produced.

- [Implementation specification](docs/superpowers/specs/2026-10-14-outcome-aware-context-allocation-design.md)
- [Implementation plan](docs/superpowers/plans/2026-10-14-outcome-aware-context-allocation.md)
- [Research and attribution handoff](research_poc_plan.md)
- [Planning review](docs/superpowers/reviews/2026-10-14-planning-review.md)

The plan includes prerequisites, leakage/scoring/accounting tests, all required comparators, protocol freeze, protected paired execution and honest reporting within a 24-hour execution window. Project commands in the documents are proposed interfaces, available only after implementation.

The experiment tests context allocation on supplied evidence packets. It does not establish open-web search savings, commercial value or algorithmic novelty. Negative, tradeoff, inconclusive and prerequisite-blocked outcomes are valid handoffs.

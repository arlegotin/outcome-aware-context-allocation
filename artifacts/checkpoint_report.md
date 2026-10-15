# Execution checkpoint

Recorded 2026-10-15T01:11:41.356552+00:00. This is an in-progress recovery checkpoint; the final deliverable remains `artifacts/final_report.md`.

We are testing whether a cheap controller can choose how much evidence an AI reads before answering. The outcome-trained controller learns when extra evidence changes final answer-and-citation success. The main question is whether that training earns its cost compared with simpler alternatives.

The practice comparison is complete on 128 development questions. The chosen outcome-trained controller achieved 10 strict answer-and-citation successes, versus 11 for the chosen simpler support-coverage proxy. Their estimated serving seconds per strict success were 19.11 and 14.66 respectively. These are tuning observations with sparse successes, not an untouched-test finding. The proxy, ridge, question-only and random-forest representatives all beat the proposed controller on the tuning efficiency objective. A small 128-versus-256 training check showed no stable progress, so no larger training collection is justified now.


The protected protocol assigned 480 questions from a finite population of 7,344, with 8,640 physically separate pipeline jobs and two fresh paired timing repetitions of the main contenders. Collection started at 2026-10-14T22:09:27.535017UTC under reviewed immutable source. The latest operational receipt records 2357/8,640 terminal pipelines at 2026-10-15T01:11:39.121905+00:00. This is progress, not a scored sample or a quality finding. Gold answers and protected scores remain unopened.

Repeated host sleep/wake cycles caused a known measurement failure: one pipeline interval spanned 300.750162 seconds of UTC time while the high-resolution timer recorded only 2.446765125 seconds. Other affected intervals are retained too. The original run cannot support its intended wall-time efficiency claim. No elapsed value has been repaired, no affected question removed and no smaller confirmation sample substituted. This environmental failure does not establish evidence against the proposed mechanism.

The collector has an outcome-blind cutoff of 2026-10-15T06:12:52UTC, enforced at the first available safe boundary if the host is suspended, to preserve six hours for reporting, reproduction and review. Any incomplete assignment remains incomplete. A separate clean timing replication is being assessed; it has not been authorized or run. Keeping the Mac awake was requested once because the interruptions affect measurement; no power setting or thermal-protection bypass has been made.

The hardware is an M3 Max with 36 GiB RAM, native Python 3.12.9 and macOS 26.7.1. Assets, dependency hashes, isolated data, deterministic retrieval, strict scoring, fixed/simple/learned/paid controls and complete service accounting are implemented. The final execution source passed independent review and 631 tests. Follow-up attribution and an independent fixed-32 pooled diagnostic have been implemented with synthetic checks; their source review found setup and interrupted-parent accounting issues, fixed and approved in scoped review round 1. Actual follow-up data/model/index/generation stages remain held. The whole suite will run again after the new modules and fixes are complete.

The archived author-origin HotpotQA snapshot remains qualified by amendment A01. Development history retains the retrospective source/receipt qualifications, the failed numerical prefix-reuse check, original raw failures and all 246 tuning configurations. No historical completion-time guarantee is invented. The final report will distinguish known measured costs, unknown costs and nonadditive enclosing intervals.

Remaining work: finish reviewed analysis/report tooling; close the original collection or preserve its original-assignment incomplete record; decide any feasible clean timing or pooled diagnostic without reading outcomes first; reproduce valid saved scoring; write complete local tables, uncertainty or explicit unavailability, and the final report. No web-search savings, algorithmic novelty, commercial benefit or quality preservation has been established.

The original 24-hour deadline remains 2026-10-15T12:12:52UTC.

inconclusive

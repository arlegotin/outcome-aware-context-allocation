# Task 14 execution handoff

The original experiment remains **incomplete**: 6,510 of 8,640 assigned jobs completed, with the full denominator of 480 questions retained. The separately preregistered A03 comparison completed **all 3,360 assigned jobs for the identical 480 questions**. Both wall-time efficiency endpoints are invalid because verified host suspension was excluded from the performance clock. No timing repair, selective exclusion, smaller replacement sample or third timing experiment was performed.

## Original execution

The original reviewed source began on 2026-10-14 at 22:09:27.535017 UTC. The approved A04 external control sent SIGINT at a verified paid-call boundary on 2026-10-15 at 04:30:00.253260 UTC; genuine process exit was recorded at 04:30:00.798081 UTC with return code −2. The previous 06:12:52 cutoff remains historical and was superseded by A04.

The retained records contain 6,511 started attempts, 6,510 completed jobs, and 6,940 paired paid-start/finish receipts with no unmatched paid start. There are 361 full question blocks and 12 further jobs; this is not a replacement sample. One additional attempt is unclosed without an active paid call, and its unresolved serving cost remains null. No complete native closure exists and the original subset was not scored. Every original attempt, failure, setup/reload/shared-cost and operational receipt remains in `artifacts/runs/confirmation/`.

Original protocol: `415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100`. A04: `35619ce1cd67508e437f6d42c2d6974b1bae8552bd421abd98ee789b0dc64111`. The immutable incomplete summary is `artifacts/runs/confirmation/operational-observations/a04-incomplete-summary.json`, SHA256 `97891b506e11f9a33659063493dae8963241054e5c247460e64f5771c5a65148`.

## A03 execution

Root separately authorized the unchanged A03 source/protocol after fresh source, process, clock and budget checks. The native launch began at 04:37:26.968875 UTC, completed its last assigned job at 06:59:20.490028 UTC, and genuinely exited at 06:59:40.348835 UTC with return code 0. All 3,360 scheduled jobs and attempts have 3,360 paired paid-start/finish receipts; no paid start is unmatched. The exact assigned job set, both closure hash sets and all 26 bound source hashes were verified without interpreting predictions or quality.

A03 protocol: `ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07`; source: `869b701f4d3d0c23a02a3fe36be66af298d924c4`. Protected closure: `193db8de7b4dae109e2b662e8bcf8d84522996e61366094d9199e9121ae94c80`; native launch closure: `e7c906980c494946bf8684b6c4914b972be1010db60830f58886ea3a61f3bf48`. Full metadata handoff: `artifacts/runs/task17-timing-replication/operational-observations/a03-native-closure-handoff.json`, SHA256 `067998fa270bf8a46c3946856e777ab1fbe499a4c0ac2a049f7f51658be68b8f`.

All five raw/Gold OS denial probes and the network denial probe passed; native network attempts were zero, and the measured resource gate passed. The selected index retained its true original physical source `index-attempt:927ba64d93084cd2a6d43ead0b85ee54`. Its construction is not charged again; new setup/loading work remains actual and namespaced by protocol/run root. The native active envelope (6,652.692496791 seconds) and outer launch envelope (6,656.832093125 seconds) contain nested work and must not be added again to component costs. All actual attempt and shared-cost evidence remains intact.

The A03 safe-boundary cutoff watcher retained the unchanged 10:12:52 UTC ceiling. Native launch session 16459, metadata monitor session 5791 and cutoff-control session 98922 all exited successfully. The watcher sent no signal because genuine full completion occurred first. Final external-monitor hash: `f9c0bf40ca7da706a10d06123c0d05aa75d7361d3463b1d50443d11104f72041`; cutoff-exit receipt hash: `0942cfb8a059eb00d004ccdf592cd5c50b3a98e900c02ffbb3043b5ab0ad3bb8`.

## Operational validity and handoff

A03 sampler gaps were 942.683842 seconds (04:38:57–04:54:39 UTC) and 937.827964 seconds (04:57:01–05:12:39 UTC). Independent monitor UTC/performance-clock intervals excluded approximately 940.660823 and 936.509859 seconds. These observations establish the wall-time boundary failure; later continuous operation and the user's approximately 06:22 UTC intention to keep the host awake do not restore retrospective validity or certify stationarity. No further sampler gaps were observed through closure.

Original concurrent synthetic/test work remains disclosed, including the root integration interval 02:42:29.713048–02:46:03.540053 UTC. A Python 3.14 pytest process was observed before A03 launch and was absent during the final clean prelaunch check. During A03, the lightweight process monitor recorded transient test-command candidates at 06:34:47 UTC (PIDs 66749/66751) and 06:51:49 UTC (PID 70319). These were substring matches, not proof of heavy workload or ownership; each was absent at narrow follow-up, leaving origin and intensity unknown. No unidentified process was signaled.

The operator did not open Gold, calculate scores or interpret answer quality. Root separately released Task16 to score through the frozen scorer after full A03 closure. Downstream analysis, transfer/robustness decisions and final review belong to root and its designated agents. No source, frozen configuration, sample, settings or model changes were made during execution.

The final evidence manifest, including stable shared-cost, closure, monitor, control and incident hashes, is preserved outside scratch at `artifacts/runs/operational-planning/task14-final-operational-handoff.json` and as a sanitized identical public copy at `artifacts/provenance/task14-final-operational-handoff.json`.

# Reader feasibility software review and verification

The additive `reader_probe` implementation was task-reviewed before real model loading. The asset/profile task passed independent spec and quality review at `b94458e`; a live Hub 1.33 bookkeeping incompatibility was reproduced, fixed at `cb1d5b2`, and approved in a scoped review. All model payload sizes/digests continued to match their pins.

The native task's initial review found one Important launcher/closure race (T2-R1). Actual concurrent-launch tests reproduced it. Commit `a7e720f` shares writer-lock ownership through the launcher and native coordinator and checks closed state before mutation; scoped review approved the fix. A 983-test full suite passed at that revision.

Before inference, target-machine metadata inspection found the actual raw datasets outside the assumed conventional folder (T2-R2). The first prepared plan remains unexecuted. Commit `24701dd` seals registry-derived annotation locations and explicitly probes existing raw and Gold files. Authored tests first reproduced the native denial failure, then verified denials in both coordinator and spawned worker. Scoped review approved the fix; 31 targeted adapter tests passed.

The final full suite ran on `24701ddd3edd1431346834eada6b2ac99a1cf2d6`: **988 passed, zero skips, 218.79 seconds, exit 0**. The retained log's SHA256/size are in [aggregate provenance](../../../artifacts/provenance/reader-capability-preflight-summary.json). There were no subsequent source/test changes before the final review. All earlier source, configurations and scientific result files remained unchanged; README and third-party notices were intentionally updated.

The [actual preflight](../../experiments/2026-10-15-reader-capability-preflight.md) used a sealed snapshot at that source revision. It retained three authored calls, exact repetition, native probes, resource gates and known worker quiescence. Fresh verification and verify-only rerun changed none of its 88 file identities. Those checks establish software and authored feasibility evidence; benchmark quality and allocation value remain untested by this phase.

Full task reports, authored test transcripts, review packages and coordination records remain in the private process archive after closure. This public note summarizes the recorded reviews; it is not an additional independent review seat. The final whole-branch review is recorded separately.

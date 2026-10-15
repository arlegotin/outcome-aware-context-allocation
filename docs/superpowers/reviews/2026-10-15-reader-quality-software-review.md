# Reader-quality study software gates

The additive preparation and execution layers passed their independent task reviews before any actual benchmark preparation or generation. The comparison remains a prospective reader-quality study, not evidence of allocation savings.

Task 1 (`0dcdd46..51ec2ee`) was approved for specification compliance and code quality, with no findings. Its 181 focused tests covered reservation exclusion, duplicate groups, explicit reader factors, sealed inputs/source/profiles and fresh shared-index bindings.

Task 2 initially required one Important fix: an abrupt coordinator death after an acquisition marker but before worker identity could permit another acquisition. Commit `0e90291` requires identity for both native reader leaves before reconciliation and permanently refuses an unidentified acquired session. The independent scoped rereview marked RQR-001 addressed, with no new breakage. Nine targeted cases passed, including the missing-identity window and a verified stopped-worker control.

The complete suite at `0e90291` passed **1,064 tests, zero skipped**, in 319.49 seconds. All 140 tested source/test/config/lock identities remained unchanged afterward. The 8,756-file preservation audit found only the intended prospective startup-rule clarification; historical source, configuration and scientific results remained intact. The prior full suite had passed 1,059 tests before the additional crash-window regression; that earlier pass did not cover the discovered defect.

The startup-only exception was fixed before outcomes: an exact, isolated, unpaid startup failure with known quiescence may be repaired while retaining its costs. Paid warmup failures, assigned attempts, missing worker identity and unknown endpoints cannot use it. Tests use invented records/fake readers, including actual macOS Seatbelt and spawned processes. They establish software behavior, not model quality, actual eligible-population identity, resource suitability or research success.

Root execution and one final whole-branch review remain required. Detailed task reports, test logs and authored fixtures' process records stay in the private process archive; only this aggregate disposition is published.

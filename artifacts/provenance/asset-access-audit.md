# HotpotQA author-asset access audit

Checked 2026-10-14 around 12:19 UTC from the current Mac. Read-only public-network probes used approved `require_escalated` access; no dataset bodies, packages, or model assets were downloaded.

## Provenance evidence

- Author project page: https://hotpotqa.github.io/ — reachable. Its actual HTML links training and distractor development data exclusively to `http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json` and `http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json`. The page declares CC BY-SA 4.0.
- Official repository: https://github.com/hotpotqa/hotpot — reachable. README and `download.sh` use those same HTTP file URLs; no alternative download host appears. Master resolved to `3635853403a8735609ee997664e1528f4480762a` (commit dated 2019-02-14). Pinned source: https://github.com/hotpotqa/hotpot/blob/3635853403a8735609ee997664e1528f4480762a/README.md and https://github.com/hotpotqa/hotpot/blob/3635853403a8735609ee997664e1528f4480762a/download.sh .
- https://api.github.com/repos/hotpotqa/hotpot/releases returned an empty array. Its recursive master tree contains code/README/license only, with no raw dataset assets.
- Official issue https://github.com/hotpotqa/hotpot/issues/34 contains collaborator `qipeng` responses about temporary/connectivity issues, without an alternate host. Issues https://github.com/hotpotqa/hotpot/issues/45 and https://github.com/hotpotqa/hotpot/issues/46 report historical HTTP 403 failures and have no comments.
- https://github.com/hotpotqa/hotpot/issues/49#issuecomment-2887743087 mentions `vincentkoc/hotpot_qa_archive` on Hugging Face, using a webarchive copy. The commenter has `author_association=NONE`; this is a third-party mirror, with no author endorsement or independently demonstrated identity to the required author files. It was not downloaded or substituted.

## Local accessibility

`curl -ILsS --max-time 20` probes of training and distractor-dev endpoints over both HTTP and HTTPS timed out with curl exit 28, HTTP status `000`, and no redirect/final response. This demonstrates failed access during these bounded probes, not a claim that the origin is globally or permanently unavailable.

Filename search used `rg --files --hidden` in `/Users/artemlegotin/.cache`, `/Users/artemlegotin/Documents`, and `/private/tmp`, matching `*hotpot*` and `*Hotpot*`, excluding `.git`, `node_modules`, and `Library`. No candidate file was found. `/private/tmp/codex-daemon-501` was unreadable (`Operation not permitted`); the search is bounded and cannot establish absence from every location on the Mac. No usable existing exact-file cache was established.

## Recommendation

No faithful author-provided release alternative or usable exact-file cache was established. Preserve the official URLs in configuration and fail WP0 closed as `blocked by prerequisites` / official data unavailable from this execution environment. Do not reconstruct from Hugging Face parquet or use the third-party archive mirror to pass this gate. If the origin becomes accessible or a documented author-provided exact-file source/cache is supplied, acquire the two required files and record source/final URL, bytes, SHA-256, provenance, and license before allowing data collection.

This recommendation follows design spec sections 2/3: author official filenames are mandatory and WP0 fails closed on unavailable official data. Asset access failure is not experimental evidence against the research mechanism.

# 14B reader feasibility: passed, quality still untested

The pinned Qwen3-14B 4-bit reader completed the three prespecified authored calls on the 36 GiB M3 Max. It returned the required answer and sentence citation, repeated the short output token-for-token, and handled a 7,803-token prompt. This admits a small reader-quality study. No benchmark questions were answered, no controller was trained, and no quality or efficiency improvement is established.

The reason to try another reader comes from the previous [citation-chain study](2026-10-15-citation-chain-reader-study.md): at ten paragraphs the original 4B reader matched 43 of 64 answers but only 4 complete answer/citation references. A reminder produced a mixed result and did not earn its larger comparison. This check tests a dependency of a different continuation, rather than repeating that prompt trial.

## Frozen configuration and observations

Measured source: `24701ddd3edd1431346834eada6b2ac99a1cf2d6`. Native Python 3.12.9, macOS 26.7.1, Apple M3 Max, 38,654,705,664 physical bytes (36 GiB). No package upgrades or paid services. Reader: `mlx-community/Qwen3-14B-4bit`, revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`; local snapshot hash `db6642cc8c8d481f64de506e02f1bef3ab75f07ecbd0ad0d20395bd36aa28414`.

The official installed template was explicitly rendered with `enable_thinking=False`. Other settings were greedy decoding, one sequence, total context 8192, maximum output 256, prefill 512, continuous startup/generation deadlines of 120 seconds, no result/prefix reuse, no rotating or quantized KV cache, and no repair or generation retry. The existing answer contract and citation parser were retained.

All prompts were authored fixtures asking for an invented cabinet code from a supplied sentence. They measure format and resource feasibility. They are not three independent natural tasks, a contamination check, or a multi-hop capability benchmark. Request durations begin after prompt construction; the complete resident-session envelope below also covers prompt construction, model startup, resource checks and cleanup.

| Authored call | Input tokens | Output tokens | Request seconds | Answer/citation contract |
| --- | ---: | ---: | ---: | --- |
| Short, first execution |183|43|4.5665|Passed|
| Identical short repetition |183|43|2.2534|Passed; identical output tokens and payload|
| Long evidence |7,803|43|30.1260|Passed|

All three generated answers were retained. There were no failures, semantic retries, truncations or unresolved paid attempts. The single resident session was exactly 66.165313084 continuous-clock seconds with known worker quiescence. Its nested backend-startup interval was 27.931045834 seconds; it is not added again. These are authored measurements including cold/shape effects, not steady-state benchmark latency comparisons.

## Resources and isolation

All five resource boundaries passed the unchanged overlapping RSS-plus-MLX project gate. The operational reserve was 7,730,941,133 bytes. The bound is deliberately conservative and is not disjoint physical allocation or a required amount of globally available memory. Separate observed peaks were MLX 10,064,214,104 bytes, sampled coordinator RSS 617,005,056 and sampled child RSS 692,813,824. Do not add them as physical usage. There were 39 resource samples.

System-wide swap rose from 7,039,156,224 to 13,958,905,856 bytes, about 6.44 GiB. Minimum sampled system-available memory was 3,739,369,472 bytes. These global observations cannot be uniquely attributed to this process. They qualify practical feasibility: this run completed, but it does not establish spare capacity, stationarity or production latency. The protocol introduced no new swap/availability threshold after seeing those observations.

Both coordinator and spawned worker checked native denial of network and eight existing files, including the two raw datasets and three Gold stores. Annotation-enabled imports were denied before model acquisition. Serving used the sealed source snapshot and local verified safetensors, with remote code disabled. The temporary idle-sleep assertion ended with the command; no system memory limits or permanent power settings changed.

The first prepared plan, `c2c92c6137943474f53bad9d652a3a0995ae3d82002a1844f9d08bbb93003806`, is retained unexecuted. Preparation originally assumed raw data lived under `data/raw`; metadata inspection showed the actual assets in `models/pinned/data`. The corrected version seals actual registry-derived locations and probes real raw/Gold files. V1 had zero sessions and zero calls; no output was repaired or retried. A separately reviewed launcher-lock fix also preceded all real inference.

## Assets, accounting and reproduction

The conversion and inspected original model are identified under Apache-2.0. The inspected original `Qwen/Qwen3-14B` revision is `40c069824f4251a91eefaf281ebe4c544efd3e18`; the conversion does not declare its historical original commit. See the [pinned conversion card](https://huggingface.co/mlx-community/Qwen3-14B-4bit/blob/a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4/README.md), [inspected original license](https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/LICENSE) and [third-party notices](../../THIRD_PARTY_NOTICES.md). No upstream model/data files are redistributed.

The two tensor shards total 8,307,898,514 bytes. The complete admitted payload, including conversion tokenizer/config/card and original license/card/config, totals 8,323,897,691 bytes. Every payload matched its pinned size and LFS SHA256 or Git blob identity and received an independent SHA256.

The initial download completed but the verifier rejected two legitimate Hub 1.33 bookkeeping files. That failed acquisition remains recorded; a narrow regression/fix preserved all model-byte checks. Its log spans approximately 147.01 wall seconds by filesystem timestamps, which is not an exact continuous acquisition envelope. The successful retry took 18.198157292 seconds, reused all 8,323,868,950 conversion bytes and added 28,741 original-provenance bytes. That retry duration is not the full download cost. Wire-transfer bytes, complete adaptation cost and break-even remain unmeasured.

Run root: `artifacts/runs/reader-capability-preflight-v2`. Plan hash: `994621af2b04be267f1a370e67fae89a37747cb1af80b51f09a5367042dfb19c`. Closure hash: `d6872123cd1c64c181dd3705ee7b3d8a24cb46097a64a26658af26d29b1733c7`. Fresh-process verification and a verify-only rerun both succeeded; all 88 retained run-file identities stayed unchanged, with no additional generation. Aggregate evidence is in [the machine-readable summary](../../artifacts/provenance/reader-capability-preflight-summary.json).

A public clone can run authored software tests and inspect aggregate evidence. Authentication of this actual preflight requires the retained run and assets at their bound paths, using the recorded source or its exact sealed snapshot. Never edit a frozen plan to match later code. New execution requires its own empty run root and independently verified public assets:

```sh
python -m outcome_poc.reader_probe --help
python -m outcome_poc.reader_probe verify --root artifacts/runs/reader-capability-preflight-v2
python -m outcome_poc.reader_probe run --root artifacts/runs/reader-capability-preflight-v2
```

## Next gate

The next question is whether this reader improves exact answer/citation success on real questions enough to justify collecting new allocation labels. It has a different training lineage from the July 4B Instruct model; parameter count alone is insufficient evidence. A separate prospective protocol must freeze reader factors, development admission and an untouched sample before any benchmark generation. Even a successful reader comparison would still leave learned allocation, strong fixed/proxy/post-answer comparators, charged overhead and customer utility to establish.

**inconclusive**

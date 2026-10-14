# Structural input capacity audit

All 7,344 structurally valid protected packets were counted with the exact current answer renderer and pinned local Qwen tokenizer, without MLX imports, model initialization, generation, retrieval ranking, embedding/index construction, scoring, gold, answers, support annotations, or outcome reads. `data_runtime.DocumentStore` validated the annotation-free document store; per-packet access included exactly each packet's ten candidates. No protected sample was selected.

Canonical order is ascending lexicographic document content hash. D0 through D9 aliases are assigned in that order, consistently as a hypothetical shared full ranking. Every original sentence and sentence index is preserved. Counts use the installed chat template once with the generation prompt, then `encode(add_special_tokens=False)`, matching the native reader's rendered-prompt counting. This is a structural canonical order, not the runtime retrieval ranking.

| Canonical full-ten measurement | Tokens / count |
|---|---:|
| Minimum | 621 |
| Median (nearest indexed observation) | 1,694 |
| Mean | 1,733.1123 |
| P90 | 2,224 |
| P95 | 2,404 |
| P99 | 2,880 |
| Maximum | 4,396 |
| At or below 7,936 prompt tokens | 7,344 |
| Above 7,936 prompt tokens | 0 |

The declared initial total limit is 8,192 tokens with 256 reserved output tokens, leaving 7,936 prompt tokens. The canonical maximum plus output reserve is 4,652, leaving 3,540 tokens of headroom. Of the packets, 6,013 use at most 2,048 tokens; 1,329 use 2,049–4,096; two use 4,097–6,144.

For order sensitivity, the first twelve pilot task IDs in sorted order were each rendered in 31 deterministic permutations: canonical, reversed, nine cyclic rotations, and twenty pseudorandom shuffles with seed 1729. Aliases were reassigned consistently with each order. Every tested task had zero token-length spread. This is a finite development sample: neither exact all-ranking invariance nor the all-ranking protected maximum is established. Later frozen execution must check the actual runtime prompt ordering and count any overflow.

A candidate raw-UTF-8-byte bound was withdrawn because the tokenizer normalizes NFC and an ancillary structural check found an original sentence not already NFC. The failed assertion emitted no input text or task ID. No valid all-ranking capacity bound is claimed. The initial console and audit script retain the superseded candidate for provenance; `summary.json` and `corrections.json` record its withdrawal.

The successful full audit took 26.9633 seconds wall time and 26.9110 seconds CPU time; peak RSS was 656,982,016 bytes (626.55 MiB). Its measured UTC interval was 2026-10-14T19:28:25.360163+00:00 to 2026-10-14T19:28:52.323470+00:00. Exact additional elapsed CPU/RSS costs for the failed ancillary NFC check were not captured before the assertion; its script and failure log remain preserved. No native or Metal execution occurred. No package, model asset, repository source, git branch/commit, or execution-window artifact was changed.

Reader revision: `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`. Offline local loading used `local_files_only=True`, `trust_remote_code=False`, `use_fast=True`, and disabled torch/tensorflow/flax backend detection. Installed versions: transformers 5.19.0, tokenizers 0.23.3, Jinja2 3.1.6; returned tokenizer class Qwen2Tokenizer with `is_fast=True`.

| Identity | SHA-256 |
|---|---|
| `data/prepared/tasks.jsonl` | `45d9baf5b5a05de38d3aa37494b952247c04c04e24ac0dc7454f328573a11fc2` |
| `data/prepared/documents.jsonl` | `032079542ef8692f7272ff3692dc44b4cfa9ce41f376daa2abf1b5508a2c08bd` |
| `data/prepared/protected-population.json` | `35daf13300851d95196f45279545dc1b75f112dfc08cdeb36ed3510191181520` |
| `src/outcome_poc/data_runtime.py` | `fa0382c0b38867e8e3a5d863db01dc5b2a08a081355093650850d8e89535f87e` |
| `src/outcome_poc/generation.py` | `d7bd43ee780d097982d01a7bd504758e3dba350e50f072ed1d0e98131c996cd6` |
| Reader `tokenizer.json` | `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4` |
| Reader `tokenizer_config.json` | `4397cc477eb6d79715ccd2000accd6b3531928f30029665832fa1b255f24d2b9` |
| Reader `chat_template.jinja` | `40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541` |

All source and tokenizer asset byte sizes/hashes, including added tokens, special token map, vocabulary and merges, are in `artifacts/runs/capacity-input-audit/identity.json`. Generated artifact hashes are in `artifact-hashes.json`. Protected per-task counts and the twenty longest IDs exist only in ignored `protected-lengths.private.jsonl` and `longest-inputs.private.json`; sampled development permutation details are in `development-order-sensitivity.private.json`. No raw evidence or questions are stored in audit outputs.

Longest protected IDs are structural metadata only. Task13 calibration must use development or synthetic length-matched prompts. Never generate on actual protected questions before a verified frozen protocol. Uniform protected sampling must remain independent of these lengths. Historical development prompt-length comparisons were omitted because the audit did not need prediction/outcome files.

inconclusive

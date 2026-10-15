# Third-party notices

The project licenses apply to original project material. They do not relicense
datasets, models, installed dependencies, cited publications or external code.
The [asset manifest](artifacts/provenance/asset-manifest.json) and
[research handoff](research_poc_plan.md) preserve the measured identities and
source-access qualifications.

## HotpotQA and Wikipedia-derived evidence

The experiment uses [HotpotQA](https://hotpotqa.github.io/), by Zhilin Yang and
the HotpotQA authors, including Wikipedia-derived evidence and supporting-fact
annotations. The authors describe the dataset/processed Wikipedia release under
**CC BY-SA 4.0**. Those terms remain separate from this project's code and
writing licenses. The public repository does not redistribute the raw benchmark,
prepared question/document/Gold stores, complete task-level predictions or the
private evaluation sample.

The recorded files were obtained through a pinned Internet Archive replay of
the author-origin URLs after direct access failed. Equality to a currently
accessible author copy was not independently established. That source
qualification remains in the report; a mirror receipt is not an authorship or
licensing transfer. Obtain data through the authors' release paths and retain
their attribution and applicable share-alike obligations when redistributing
covered data or derivatives.

`src/outcome_poc/scoring.py` locally implements the metric behavior of the
[official HotpotQA evaluator](https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py).
Its module documentation records the pinned evaluator provenance. The upstream
script itself is not vendored. Agreement with its answer/support annotations
does not certify truth or logically complete evidence.

## Reader and embedding assets

- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
  by the Qwen team, and its
  [MLX Community 4-bit conversion](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)
  are identified under **Apache-2.0** in the recorded asset provenance. The
  original model revision is `cdbee75f17c01a7cc42f958dc650907174af0554`;
  the conversion revision is `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`.
- [BGE-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), by the
  Beijing Academy of Artificial Intelligence, is identified under **MIT** at
  revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.

Model weights, tokenizers, upstream model license files and generated embeddings
remain external assets. This release grants no new rights over them. Preserve
the exact upstream terms when acquiring or redistributing those assets; a
license choice for this harness does not change them.

## Installed dependencies

MLX and MLX-LM use MIT terms. Sentence Transformers, Transformers and Hugging
Face Hub use Apache-2.0 terms. NumPy, SciPy, scikit-learn, PyTorch, psutil and
other runtime packages have their own project and bundled-component notices.
The installed distributions' notices govern those components.

[requirements.lock](requirements.lock) records the measured Python/macOS ARM64
environment. It is not a redistribution of dependency binaries or a complete
native-component clearance inventory. Environments, wheels, caches and native
libraries are excluded from this source release and project wheel.

## Referenced research and tools

The research handoff attributes Adaptive-k, Adaptive-RAG, RASER, DynaKRAG,
sufficiency/verification work and other related methods. Local comparator
adaptations are not faithful reproductions of those full systems. Their source,
checkpoints and papers retain their original rights; a citation does not grant
redistribution permission. No external router checkpoint is bundled here.

README editing used the requested
[write-like-me](https://github.com/arlegotin/write-like-me) skill. Its code and
reference material are not included in the source distribution. Project
development and reporting used AI assistance under the owner's direction.

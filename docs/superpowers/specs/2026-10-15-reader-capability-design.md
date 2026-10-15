# A reader that can earn a useful context-allocation test

Status: prospective continuation, following the closed citation-chain study. The user authorized autonomous execution on the current branch, subagents, meaningful commits and public reporting. The choices below are the controller's calls, not measured findings or user-supplied scientific requirements.

## Question and value

The repository asks whether a cheap controller can save reading work while retaining successful, evidence-supported answers. The current 4B reader produces too few strict successes and too few useful two-versus-ten outcome differences to train that controller convincingly. A citation reminder did not pass its development admission rule. Repeating prompt variants is not the next test.

Test one larger local reader instead. First establish that it runs faithfully within the existing resource policy. Only a successful resource preflight earns a separately frozen benchmark capability study. A larger model is a candidate, not a claim of better answers, greater allocation headroom or customer value.

This design has two distinct delivery gates. The implementation plan paired with it covers **Gate 1 only**. Do not build another benchmark orchestration layer before the indispensable model path works. Gate 2's prospective direction is recorded here to make the purpose and stop conditions visible; its exact sampling protocol must be committed before any new benchmark generation.

## Gate 1: exact-model resource and format preflight

Use the existing native Python 3.12/MLX environment. No dependency changes, paid services, remote compute, system memory-limit changes, termination of unrelated processes, power-setting changes or battery polling. The existing supervisor may terminate its own identified worker during ordinary closure, timeout or failure recovery.

Prespecified sole candidate: `mlx-community/Qwen3-14B-4bit` at revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`. The original is `Qwen/Qwen3-14B`; inspect its Apache-2.0 license/card at `40c069824f4251a91eefaf281ebe4c544efd3e18`. The conversion does not pin its historical original source revision; do not assert that this inspected original commit produced the conversion.

This April 2025 hybrid model differs from the July 2025 4B Instruct lineage. Explicitly render its installed official chat template with `enable_thinking=False`. Use a local tokenizer facade that forwards other methods and prevents overriding that choice; never edit the tokenizer asset or historical module globals. Record the mode in settings, decoding identity and rendered prompt identity. Greedy decoding is a controlled-study choice, not Qwen's recommended sampling preset.

Keep the existing answer system message and parser, 8,192 total tokens, 256 maximum new tokens, greedy sampling, batch one, prefill steps of 512, 120-second continuous generation and model-startup deadlines, no rotating/quantized KV cache, no prefix/result reuse, no repairs or semantic retries. Use `ContinuousBackend` and the existing reader backend without editing them. A factory composes the verified native reader with the tokenizer facade; generation receives an already rendered string.

Download only the pinned conversion's safe tokenizer/configuration/card/safetensors files and original license/card/config into a new ignored asset directory. Never overwrite prior assets or their manifests. Verify the exact required inventory, file sizes/digests, shard index coverage, license and installed architecture support before acquisition. Download resumption may reuse verified bytes; a partial or mismatched file is never an admitted asset. Retain the acquisition duration and actual bytes separately from inference.

The conversion has two shards (8,307,898,514 bytes combined):

- `model-00001-of-00002.safetensors`: 5,354,381,380 bytes, SHA256 `5795efcfc7c96fd273e600562e8b111bfcc427415de9001d0a07e70cd99cff19`.
- `model-00002-of-00002.safetensors`: 2,953,517,134 bytes, SHA256 `2814562d654fe2d541fd4682804a0ccaa400e79701872c8e9f5998cf9481fdf8`.

Record pinned metadata provenance and the original license digest. The full repository listing is 8,323,870,520 bytes, including an unnecessary `.gitattributes` file; this is a static metadata total, not a promised download measurement. Do not commit weights or third-party raw assets.

### Why this candidate

The inspected 30B-A3B 4-bit conversion has about 16 GiB of tensors. It plausibly fits physical RAM, but its overlapping RSS-plus-MLX bound can exceed the existing operational gate. No public pinned 3-bit conversion was verified. The 14B 4-bit tensors occupy about 7.74 GiB; its logical unquantized KV at 8,192 tokens is 1.25 GiB (40 layers, 8 KV heads, head dimension 128). These are estimates, not measured working sets. There is no silent smaller-model fallback or model search after observing results.

### Immutable inputs, isolation and records

Create additive `src/outcome_poc/reader_probe/` modules, a new configuration, tests and run root. Preserve every existing source/config/result file. Preparation seals the new config, environment/lock identities, asset manifest, source snapshot and sandbox profile into a hashed plan before loading a model. Verification must reject changed settings, source, assets or profile. Do not import mutable checkout source in the native coordinator or spawned worker. Inference probes, session ownership and resource gates surround local model loading and generation; network-enabled asset downloading is a separate, measured acquisition operation before sealing, not part of that offline inference session.

Inference has no benchmark task inputs. Deny Gold, raw/prepared data, indexes and all historical run directories through a native macOS Seatbelt profile; deny network at the OS level and set Hub offline flags. Probe those denials in both coordinator and spawned worker before model acquisition. Block annotation-enabled module imports in both processes, including future reader-study preparation/scoring namespaces. Authored preflight text is embedded in the sealed source. Tests use authored data and fake backends, never real benchmark outcomes.

Use a single-writer run lock. Start a durable session before model acquisition. Persist paid request/start, incremental output/token IDs, terminal result and cleanup status atomically. Every attempted generation has an immutable terminal record or an explicitly unresolved interrupted attempt. Record continuous and active clocks, boot/process identity, cold startup, total session duration and available lifecycle bounds. Never turn an interrupted assigned call into a clean retry. A startup failure before any paid generation may be retried in a new retained session only after owned-worker quiescence is proven. Unknown worker identity/quiescence blocks resumption. A closed successful preflight is immutable and rerunning it verifies rather than regenerates.

### Prespecified authored calls

1. A short authored evidence question with one sentence, using the existing JSON/citation contract. Require valid nonempty answer and the supplied sentence ID; this is a format fixture, not benchmark accuracy.
2. Repeat exactly that prompt/settings. Require identical prompt/output token IDs and parsed payload. Count the second call normally.
3. An authored long-evidence prompt with the answer sentence first and deterministic numbered irrelevant sentences. Construct it using the actual tokenizer so the rendered prompt has 7,800–7,936 tokens and the 256-token output allowance fits 8,192. Preserve full sentences, IDs and exact prompt tokens. Require a valid supported answer; no benchmark annotations are involved.

No request may execute before its exact rendered prompt/request identity is durable. Output truncation, invalid format/citations, timeout, overflow, backend or cleanup failure fails the preflight. No extra diagnosis generation is allowed automatically. A resource failure is a prerequisite block; format/repeatability failure is a reader/configuration limitation, not evidence against outcome-aware allocation.

### Resource rule and interpretation

Retain the existing `followup.runtime.resource_check` unchanged: the conservative overlapping parent RSS + children RSS + MLX peak bound must leave at least max(4 GiB, 20% physical RAM). Gate before acquisition, after acquisition and after each call. Monitor separate RSS, MLX peak, global swap and system available memory throughout. Missing required counters or failed gates block admission. Never present the overlapping bound as measured disjoint physical allocation. Global swap/availability are diagnostics; they are not a newly invented threshold or proof of project-induced pressure. A process may be safely terminated at a request boundary on gate failure; all work remains visible.

Successful admission also requires native network/file/import probes, all three terminal records, repeatability, long-prompt coverage, known worker quiescence and a sealed closure. It establishes only that this exact model/configuration can run these authored shapes on this machine at that time. It does not validate benchmark quality or eliminate future long-output memory risk.

## Gate 2: continuation earned by Gate 1

If Gate 1 passes, write and commit a separate implementation plan/protocol for a bounded capability comparison. Keep the original prompt, retriever and scorer. Compare explicit reader profiles, not a disguised prompt condition.

Recommended controller choice: select 16 prior citation diagnosis questions by a new deterministic metadata-only hash order, with no per-question correctness selection. Execute the larger reader at two, ten and support-document budgets (48 observations). Compare quality with the closed historical 4B baseline for identical question/ranking/evidence identities. This is reused development, not confirmation; historical and new latency are not a controlled efficiency comparison. Require strictly more natural-ten joint successes and no lower answer-EM counts at both natural budgets to earn fresh evaluation. Support-document results diagnose retrieval versus reading limitations; they do not change that admission rule.

Before these development outcomes, freeze and reserve an independent sample of 128 questions from the fresh training representative population, excluding all earlier reservations including unexecuted ones. Metadata reconnaissance found 88,587 eligible representatives, canonical sorted-ID hash `340ac60b947956a03da43fa0a3bead3d1ceb60d39d648f658404bc8262f9fdc0`; recompute and verify it prospectively. Do not release reservations after an unfavorable gate.

On admission execute both readers at natural two/ten on those 128 tasks (512 observations), one resident reader at a time. Primary quality contrast: paired joint EM at ten, larger minus current reader; retain all failures. Use prespecified finite-population harm/rescue bounds, simultaneous answer-quality guards, all-query costs and explicit sample/precision limitations. No interim quality inspection, extensions, model/prompt/metric search, or efficiency superiority claim from one timing repetition. A positive reader finding only earns a separately frozen allocation experiment; it does not prove that a controller saves time or that a business will pay.

If either gate fails, report the constraint and stop this candidate. Do not build or run downstream stages merely to complete a checklist. Public reports distinguish measured results, static estimates and unexecuted experiments; finish with the applicable honest outcome category.

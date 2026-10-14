# Reviewable HotpotQA archived-source fallback

Read-only investigation on 2026-10-14 around 12:38 UTC. No dataset bodies were downloaded, no third-party loader was executed, and no scientific/source gate was changed.

## Pinned Hugging Face evidence

Repository `vincentkoc/hotpot_qa_archive` resolved to revision **`c0606612edaf72afd4510abea7c903eedb6e99c7`**, last modified 2025-05-16T23:27:44Z. Metadata API: https://huggingface.co/api/datasets/vincentkoc/hotpot_qa_archive .

The pinned tree contains exactly three files, **neither raw JSON nor parquet**:

| File | Bytes | Git blob object ID |
|---|---:|---|
| `.gitattributes` | 1,174 | `957b2579c6ef20995a09efd9a17f8fd90606f5ed` |
| `README.md` | 9,438 | `57891cd9588658b2e329fe640d3c45cd1e3d72fa` |
| `hotpot_qa_archive.py` | 6,468 | `5fb322b05ad46f7957e2dad92e8211af184e4163` |

Tree metadata: https://huggingface.co/api/datasets/vincentkoc/hotpot_qa_archive/tree/c0606612edaf72afd4510abea7c903eedb6e99c7?recursive=true&expand=true . Git blob IDs are metadata identifiers, not dataset payload SHA-256 checksums.

Pinned card: https://huggingface.co/datasets/vincentkoc/hotpot_qa_archive/blob/c0606612edaf72afd4510abea7c903eedb6e99c7/README.md . It states that the fork rewrites the original host URLs to Wayback snapshots, declares **CC BY-SA 4.0**, and supplies original HotpotQA author/paper attribution. Its claim that the original host was offline in May 2025 is the mirror maintainer's statement, not an independently established global outage.

Pinned loader: https://huggingface.co/datasets/vincentkoc/hotpot_qa_archive/blob/c0606612edaf72afd4510abea7c903eedb6e99c7/hotpot_qa_archive.py . Read as text only. It has an Apache 2.0 code header and sets `_URL_BASE` to `https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/`, then appends the exact required raw filenames. Its generator transforms `_id` to `id` and nested pairs into feature dictionaries, so running `load_dataset` would not preserve the raw author JSON bytes. No need to execute that script for the proposed direct-archive path.

The card lists 90,447 train and 7,405 distractor validation examples; `download_size=612746344`, exactly the sum of the two raw response lengths below. These are inherited card metadata, not verified downloaded row counts.

## Reachable direct raw-file archive paths

Both requests used `curl -ILsS --max-time 25` with approved public-network access, curl exit 0, HTTP **200**, and no URL redirect. Both returned `Content-Type: application/json`, `memento-datetime: Mon, 12 May 2025 03:27:01 GMT`, and `x-archive-src: LNUS-20250512022329-crawl901/LNUS-20250512032650-00037.warc.gz`.

| Required file | Direct raw replay URL | Replay and original content lengths | Original Last-Modified | Original ETag |
|---|---|---:|---|---|
| `hotpot_train_v1.1.json` | https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json | 566,426,227 | Tue, 06 Nov 2018 18:01:26 GMT | `"21c2fa73-57a02ca57c375"` |
| `hotpot_dev_distractor_v1.json` | https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json | 46,320,117 | Tue, 25 Sep 2018 04:49:54 GMT | `"2c2c9f5-576aad63ac352"` |

For each, response `Link` identifies the corresponding `http://curtis.ml.cmu.edu/datasets/hotpot/<filename>` as `rel="original"`. The `x-archive-orig-date` is also 2025-05-12T03:27:01Z; origin server identifies Apache/2.4.29 (Ubuntu). Headers support a direct archived response of the author-hosted exact filename. They do **not** alone establish complete payload integrity, independently verified author checksums, or author endorsement of this distribution path. Apache ETags are not cryptographic payload hashes.

Broad CDX GET requests for both files returned HTTP 503 / curl exit 56; a CDX HEAD probe returned 200 without capture-list data. A narrowly scoped training query succeeded (HTTP 200), returning timestamp `20250512032701`, original `http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json`, status `200`, MIME `application/json`, archive-supplied digest `BDCCIMOCFGCPGYXJJXQOMNOHXBMMHT7Q`, and CDX `length=206691400`. The CDX length describes the stored archive record and must not replace the replay/original body length of 566,426,227. The analogous narrowly scoped dev query timed out after 20 seconds, curl exit 28 / status 000. No independent payload SHA-256 has been obtained. Archive-supplied digest metadata is not an author-published checksum or a locally recomputed full-body hash.

Training CDX evidence URL: https://web.archive.org/cdx/search/cdx?url=http%3A%2F%2Fcurtis.ml.cmu.edu%2Fdatasets%2Fhotpot%2Fhotpot_train_v1.1.json&output=json&from=20250512032701&to=20250512032701&fl=timestamp,original,statuscode,mimetype,digest,length&limit=1 .

## Proposed amendment for review, not execution

Explicitly allow **unaltered Internet Archive raw replay of the two official author-hosted URLs at capture `20250512032701`** as a declared acquisition-source fallback when the direct CMU endpoints are inaccessible. Preserve the exact filenames and native JSON structure; do not use HF transformed output, parquet reconstruction, or the external loader. Retain HotpotQA attribution/CC BY-SA 4.0 and document that this is archived author-origin content supplied by a third-party archive, without author endorsement established.

If the source amendment is approved, acquire directly from the pinned replay URLs, record requested/final URL, memento/WARC/original headers, content length, and locally computed SHA-256, verify full-length valid raw JSON/schema and expected row counts, and retain the integrity limitation that origin-published cryptographic checksums were unavailable. Changes to the asset configuration/manifest and affected spec/protocol source allowance must be explicit and recorded before downstream use. If full identity to a separately authoritative source is mandatory, this fallback remains insufficient until that comparison is possible.

Current outcome remains **blocked by prerequisites under the approved direct-author-source gate**. This investigation identifies a concrete reviewable alternate acquisition path; it does not pass that gate or authorize training/inference.

# Outcome-aware context allocation — experimental report

We test whether a cheap controller can choose two or ten already-retrieved paragraphs before answering. The primary success requires both the correct answer and supporting citations. Reading savings are not web-search savings.

Scope: Original full-family assignment on480 archived HotpotQA questions; INCOMPLETE and unscored, wall-time invalid.

Execution: incomplete. Assigned questions: 480; assigned pipeline jobs: 8640; completed jobs: 6510.

Original host sleeps invalidated wall cost boundary; A04 cutoff stopped at6510/8640, full480 assignment retained.. active-compute diagnostic only.

Primary scores and inference are unavailable. The original assignment is retained; no complete-case subset is scored.

No wall-time efficiency claim is established. However, quality preservation remains unresolved without all four guards and regression clearance.

## Selected

```json
{
  "A": {
    "config_id": "PRE-OUTCOME-GBM:17:numeric",
    "family": "PRE-OUTCOME-GBM",
    "model_artifact_sha256": "9a34e2b065e6e94213bcdaaf42e56848e269a74f25a4327cd98d3aff80f69caf",
    "model_name": "PRE-OUTCOME-GBM",
    "threshold": 0.0339522174316994,
    "threshold_mode": "numeric"
  },
  "B": {
    "config_id": "PROXY-LABEL:14:numeric",
    "family": "PROXY-LABEL",
    "model_artifact_sha256": "c669e76c6350fa307f4bfb31457823015dda0954fa89c346f6b0600d3ce636a0",
    "model_name": "PROXY-LABEL",
    "threshold": 0.801315057689046,
    "threshold_mode": "numeric"
  }
}
```

## Work packages

```json
{
  "development": "executed; all246 configurations retained",
  "original_confirmation": "incomplete6510/8640; original480 assigned; never subset-scored",
  "a03_replication": "complete3360/3360 on same480; independently invalid wall endpoint",
  "scoring_reproduction": "A03 fresh raw scoring reproduced; original unavailable/noGold",
  "Task18_conditional_replay": "held pending separate root release and terminal receipts",
  "transfer": "held; manifest sealed prospectively, no execution asserted",
  "blind_review": "presealed selection rule; actual diagnostic held pending root release",
  "final_synthesis": "held",
  "broad_tests": "802native tests/zero skips already passed; unchanged source, no automatic repeat"
}
```

## Environment

```json
{
  "architecture": "arm64",
  "build_tools": {
    "clang": "Apple clang version 17.0.0 (clang-1700.0.13.5)\nTarget: arm64-apple-darwin25.6.0\nThread model: posix\nInstalledDir: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin",
    "xcode": "Xcode 16.4\nBuild version 16F6"
  },
  "cache_bytes": 546086890,
  "chip": "Apple M3 Max",
  "disk_free_bytes": 69883326464,
  "errors": [],
  "macos_build": "25G241",
  "macos_version": "26.7.1",
  "measured_utc": "2026-10-14T13:09:40.151914+00:00",
  "native_supported": true,
  "packages": {
    "Jinja2": "3.1.6",
    "MarkupSafe": "3.0.4",
    "PyYAML": "6.0.3",
    "Pygments": "2.21.0",
    "annotated-doc": "0.0.5",
    "anyio": "4.15.1",
    "certifi": "2026.7.22",
    "click": "8.5.0",
    "cloudpickle": "3.1.2",
    "filelock": "4.1.1",
    "fsspec": "2026.9.0",
    "h11": "0.16.0",
    "hf-xet": "1.7.0",
    "httpcore": "1.0.9",
    "httpx": "0.28.1",
    "huggingface_hub": "1.33.0",
    "idna": "3.20",
    "iniconfig": "2.3.1",
    "joblib": "1.6.0",
    "markdown-it-py": "4.2.0",
    "mdurl": "0.1.2",
    "mlx": "0.32.3",
    "mlx-lm": "0.32.0",
    "mlx-metal": "0.32.3",
    "mpmath": "1.3.0",
    "narwhals": "2.27.1",
    "networkx": "3.7",
    "numpy": "2.5.4",
    "outcome-poc": "0.1.0",
    "packaging": "26.3",
    "pip": "25.0",
    "pluggy": "1.6.0",
    "protobuf": "7.36.2",
    "psutil": "7.2.2",
    "pytest": "9.1.1",
    "regex": "2026.9.29",
    "rich": "15.0.0",
    "safetensors": "0.8.0",
    "scikit-learn": "1.9.1",
    "scipy": "1.18.1",
    "sentence-transformers": "6.1.0",
    "sentencepiece": "0.2.2",
    "setuptools": "84.0.0",
    "shellingham": "1.5.4",
    "sympy": "1.14.0",
    "threadpoolctl": "3.7.0",
    "tokenizers": "0.23.3",
    "torch": "2.14.1",
    "tqdm": "4.70.1",
    "transformers": "5.19.0",
    "typer": "0.27.3",
    "typing_extensions": "4.16.0"
  },
  "physical_memory_bytes": 38654705664,
  "python_executable": "<repository>/.venv/bin/python",
  "python_version": "3.12.9",
  "resource_gate": {
    "limit_bytes": 30923764531,
    "passed": true,
    "reserve_bytes": 7730941133,
    "working_set_bytes": 33275904
  },
  "rss_bytes": 33275904,
  "swap_used_bytes": 8334213120
}
```

## Assets

```json
{
  "assets": {
    "encoder": {
      "base_model": null,
      "files": {
        "1_Pooling/config.json": {
          "bytes": 190,
          "sha256": "d1caf60c96f5fba2157c0c26b76d80818fad6cf0b8eb5e73ec372ff9818eba5c"
        },
        "README.md": {
          "bytes": 94783,
          "sha256": "ddb964361a55c6e5dfca6361615854b260c9c960205d04c7520151aaa1d75837"
        },
        "config.json": {
          "bytes": 743,
          "sha256": "094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750"
        },
        "config_sentence_transformers.json": {
          "bytes": 124,
          "sha256": "940d5f50db195fa6e5e6a4f122c095f77880de259d74b14a65779ed48bdd7c56"
        },
        "model.safetensors": {
          "bytes": 133466304,
          "sha256": "3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad"
        },
        "modules.json": {
          "bytes": 349,
          "sha256": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf"
        },
        "sentence_bert_config.json": {
          "bytes": 52,
          "sha256": "84e39fda68ccbff05bfa723ae9c0e70e23e2ec373b76e0f8c6e71af72a693cbf"
        },
        "special_tokens_map.json": {
          "bytes": 125,
          "sha256": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3"
        },
        "tokenizer.json": {
          "bytes": 711396,
          "sha256": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"
        },
        "tokenizer_config.json": {
          "bytes": 366,
          "sha256": "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3"
        },
        "vocab.txt": {
          "bytes": 231508,
          "sha256": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"
        }
      },
      "kind": "model",
      "license": "mit",
      "license_link": null,
      "repo_id": "BAAI/bge-small-en-v1.5",
      "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
      "snapshot_hash": "0883c9ca2b589beb4d2ad6150d9c96e7c9400d2f1eadf29ad9542af82601f54a",
      "source_url": "https://huggingface.co/BAAI/bge-small-en-v1.5/tree/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
      "status": "ok"
    },
    "hotpot_dev_distractor": {
      "archive_capture": "20250512032701",
      "archive_digest_verified": false,
      "files": {
        "hotpot_dev_distractor_v1.json": {
          "bytes": 46320117,
          "sha256": "4e9ecb5c8d3b719f624d66b60f8d56bf227f03914f5f0753d6fa1b359d7104ea"
        }
      },
      "final_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
      "integrity_limitation": "No separately fetched current author file or author cryptographic checksum.",
      "kind": "data",
      "license": "cc-by-sa-4.0",
      "provenance_url": "https://hotpotqa.github.io/",
      "requested_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
      "rows": 7405,
      "schema_verified": true,
      "sha1_base32": "QJNWZ7BUUYO3IHUCXOYU3F4NLKBUSJPY",
      "source_amendment": "A01",
      "source_policy": "direct_author_or_pinned_raw_author_archive",
      "source_url": "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
      "status": "ok"
    },
    "hotpot_train": {
      "archive_capture": "20250512032701",
      "archive_digest_verified": true,
      "files": {
        "hotpot_train_v1.1.json": {
          "bytes": 566426227,
          "sha256": "26650cf50234ef5fb2e664ed70bbecdfd87815e6bffc257e068efea5cf7cd316"
        }
      },
      "final_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
      "integrity_limitation": "No separately fetched current author file or author cryptographic checksum.",
      "kind": "data",
      "license": "cc-by-sa-4.0",
      "provenance_url": "https://hotpotqa.github.io/",
      "requested_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
      "rows": 90447,
      "schema_verified": true,
      "sha1_base32": "BDCCIMOCFGCPGYXJJXQOMNOHXBMMHT7Q",
      "source_amendment": "A01",
      "source_policy": "direct_author_or_pinned_raw_author_archive",
      "source_url": "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
      "status": "ok"
    },
    "original_reader": {
      "base_model": null,
      "files": {
        "LICENSE": {
          "bytes": 11343,
          "sha256": "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e"
        },
        "README.md": {
          "bytes": 8168,
          "sha256": "8e3dd0c3b5b11897cc71092ccfe517bb7a9783479baa3665aad73c8d1a2041cd"
        },
        "config.json": {
          "bytes": 727,
          "sha256": "5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba"
        }
      },
      "kind": "model",
      "license": "apache-2.0",
      "license_link": "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE",
      "repo_id": "Qwen/Qwen3-4B-Instruct-2507",
      "revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
      "snapshot_hash": "f088f01763eb5345cd191e687372617d8d52ddb6fa9671ed883e2c6953abc9c9",
      "source_url": "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/tree/cdbee75f17c01a7cc42f958dc650907174af0554",
      "status": "ok"
    },
    "reader": {
      "base_model": "Qwen/Qwen3-4B-Instruct-2507",
      "files": {
        "README.md": {
          "bytes": 969,
          "sha256": "7b17ce562d7ea121c86d2ffdf660eed3726ac5b52cacfa9f1de11a65969f5657"
        },
        "added_tokens.json": {
          "bytes": 707,
          "sha256": "c0284b582e14987fbd3d5a2cb2bd139084371ed9acbae488829a1c900833c680"
        },
        "chat_template.jinja": {
          "bytes": 4040,
          "sha256": "40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541"
        },
        "config.json": {
          "bytes": 938,
          "sha256": "574349e5a343236546fda55e4744a76e181f534182d7dc60ff1bad7e7a502849"
        },
        "generation_config.json": {
          "bytes": 238,
          "sha256": "835fffe355c9438e7a25be099b3fccaa98350b83451f9fd2d99512e74f1ade48"
        },
        "merges.txt": {
          "bytes": 1671853,
          "sha256": "8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5"
        },
        "model.safetensors": {
          "bytes": 2263022417,
          "sha256": "2a73c6c248601ab904e035548abd8e6abb65ea27dcb5f342fb0a8910eb44173f"
        },
        "model.safetensors.index.json": {
          "bytes": 63964,
          "sha256": "388d811b8b7c2608dd04cce1bcb04a8bf715d19b42790894e6d3427ff429a777"
        },
        "special_tokens_map.json": {
          "bytes": 613,
          "sha256": "76862e765266b85aa9459767e33cbaf13970f327a0e88d1c65846c2ddd3a1ecd"
        },
        "tokenizer.json": {
          "bytes": 11422654,
          "sha256": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"
        },
        "tokenizer_config.json": {
          "bytes": 5440,
          "sha256": "4397cc477eb6d79715ccd2000accd6b3531928f30029665832fa1b255f24d2b9"
        },
        "vocab.json": {
          "bytes": 2776833,
          "sha256": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
        }
      },
      "kind": "model",
      "license": "apache-2.0",
      "license_link": "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE",
      "repo_id": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
      "revision": "50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b",
      "snapshot_hash": "ecf7edd130ec9663e80927112f50d4aab12143a43c4a1f4c532f99d0379e1660",
      "source_url": "https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit/tree/50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b",
      "status": "ok"
    }
  },
  "encoder_license_provenance": {
    "identity": {
      "bytes": 1065,
      "sha256": "587a673933425dbc36ec61268d3b954051b2d3ef3c9b322ede357976055ffdd5"
    },
    "repo": "FlagOpen/FlagEmbedding",
    "revision": "fd1a2bdf69488ffebe0327999d4400d8c8058a0b",
    "scope": "Upstream project MIT license directly linked by pinned BGE model card; encoder weight license declaration is the pinned model card itself.",
    "source_url": "https://raw.githubusercontent.com/FlagOpen/FlagEmbedding/fd1a2bdf69488ffebe0327999d4400d8c8058a0b/LICENSE"
  },
  "manifest_hash": "7d16544f0f353453671b37fb6aab96f958c8da004b630fdf1dc2f974da680f35",
  "qualification": "Asset hashes inherited from pinned acquisition records; model/data bytes not reopened or rehashed in Phase2A. Archived snapshot not independently proven byte-identical to currently inaccessible author endpoint files."
}
```

## Dependencies

```json
{
  "requirements_lock": {
    "bytes": 5009,
    "sha256": "e1bd09c1dc51f39bd53e62df6ce79eb2d726b26fa30d486ac3d584f297c2d8c8"
  },
  "wheel_manifest": {
    "annotated-doc": {
      "bytes": 5302,
      "filename": "annotated_doc-0.0.5-py3-none-any.whl",
      "sha256": "117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101",
      "version": "0.0.5"
    },
    "anyio": {
      "bytes": 132079,
      "filename": "anyio-4.15.1-py3-none-any.whl",
      "sha256": "6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101",
      "version": "4.15.1"
    },
    "certifi": {
      "bytes": 136983,
      "filename": "certifi-2026.7.22-py3-none-any.whl",
      "sha256": "62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775",
      "version": "2026.7.22"
    },
    "click": {
      "bytes": 125251,
      "filename": "click-8.5.0-py3-none-any.whl",
      "sha256": "255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360",
      "version": "8.5.0"
    },
    "cloudpickle": {
      "bytes": 22228,
      "filename": "cloudpickle-3.1.2-py3-none-any.whl",
      "sha256": "9acb47f6afd73f60dc1df93bb801b472f05ff42fa6c84167d25cb206be1fbf4a",
      "version": "3.1.2"
    },
    "filelock": {
      "bytes": 132460,
      "filename": "filelock-4.1.1-py3-none-any.whl",
      "sha256": "3f4a557945a7b0f95efeb1f432267affe5d45ac8ddde2aed1b97ebb62382c089",
      "version": "4.1.1"
    },
    "fsspec": {
      "bytes": 221738,
      "filename": "fsspec-2026.9.0-py3-none-any.whl",
      "sha256": "8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f",
      "version": "2026.9.0"
    },
    "h11": {
      "bytes": 37515,
      "filename": "h11-0.16.0-py3-none-any.whl",
      "sha256": "63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86",
      "version": "0.16.0"
    },
    "hf-xet": {
      "bytes": 3560352,
      "filename": "hf_xet-1.7.0-cp38-abi3-macosx_11_0_arm64.whl",
      "sha256": "59fba37039233c7fcbe196817d6cdcf1b40dfb17b410f229d85b0cf0a1848da4",
      "version": "1.7.0"
    },
    "httpcore": {
      "bytes": 78784,
      "filename": "httpcore-1.0.9-py3-none-any.whl",
      "sha256": "2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55",
      "version": "1.0.9"
    },
    "httpx": {
      "bytes": 73517,
      "filename": "httpx-0.28.1-py3-none-any.whl",
      "sha256": "d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad",
      "version": "0.28.1"
    },
    "huggingface-hub": {
      "bytes": 846435,
      "filename": "huggingface_hub-1.33.0-py3-none-any.whl",
      "sha256": "04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899",
      "version": "1.33.0"
    },
    "idna": {
      "bytes": 69583,
      "filename": "idna-3.20-py3-none-any.whl",
      "sha256": "ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c",
      "version": "3.20"
    },
    "iniconfig": {
      "bytes": 7552,
      "filename": "iniconfig-2.3.1-py3-none-any.whl",
      "sha256": "9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7",
      "version": "2.3.1"
    },
    "jinja2": {
      "bytes": 134899,
      "filename": "jinja2-3.1.6-py3-none-any.whl",
      "sha256": "85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67",
      "version": "3.1.6"
    },
    "joblib": {
      "bytes": 306115,
      "filename": "joblib-1.6.0-py3-none-any.whl",
      "sha256": "3dbbf9f6e4b592a2357b854608e980fe6390d131d7a82f011a377ef2ebef7aba",
      "version": "1.6.0"
    },
    "markdown-it-py": {
      "bytes": 91687,
      "filename": "markdown_it_py-4.2.0-py3-none-any.whl",
      "sha256": "9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a",
      "version": "4.2.0"
    },
    "markupsafe": {
      "bytes": 12050,
      "filename": "markupsafe-3.0.4-cp312-cp312-macosx_11_0_arm64.whl",
      "sha256": "0930db9bdc62d22944e10b066448bb65dc9abe9112880c7cab8da54db4284d5f",
      "version": "3.0.4"
    },
    "mdurl": {
      "bytes": 9979,
      "filename": "mdurl-0.1.2-py3-none-any.whl",
      "sha256": "84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8",
      "version": "0.1.2"
    },
    "mlx": {
      "bytes": 651118,
      "filename": "mlx-0.32.3-cp312-cp312-macosx_26_0_arm64.whl",
      "sha256": "72711cb23cc6dccc5a460f63f39c11931a00b2c6dcd6fba253921090072e21bc",
      "version": "0.32.3"
    },
    "mlx-lm": {
      "bytes": 513667,
      "filename": "mlx_lm-0.32.0-py3-none-any.whl",
      "sha256": "9a0f3843135fd88d36ad791f0d82210cdc4130c5c1cb5416f5f0c4b56a135778",
      "version": "0.32.0"
    },
    "mlx-metal": {
      "bytes": 67661845,
      "filename": "mlx_metal-0.32.3-py3-none-macosx_26_0_arm64.whl",
      "sha256": "34ae9b83ad2f0ccdd3e5d48ec35176e7119f57069eef187122916dc941a4ae1f",
      "version": "0.32.3"
    },
    "mpmath": {
      "bytes": 536198,
      "filename": "mpmath-1.3.0-py3-none-any.whl",
      "sha256": "a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c",
      "version": "1.3.0"
    },
    "narwhals": {
      "bytes": 483211,
      "filename": "narwhals-2.27.1-py3-none-any.whl",
      "sha256": "d057df13f5852b8e157596e82eb5e955fad267425df5e420e0ee9863da483b31",
      "version": "2.27.1"
    },
    "networkx": {
      "bytes": 2142205,
      "filename": "networkx-3.7-py3-none-any.whl",
      "sha256": "e3fd2c13a7814cee3746340d8d7f8598a67f16a58bf47fb7f8793fab6efca1b0",
      "version": "3.7"
    },
    "numpy": {
      "bytes": 5451717,
      "filename": "numpy-2.5.4-cp312-cp312-macosx_14_0_arm64.whl",
      "sha256": "9cb18a327b49c5c337f972b03682f6a49855525faaf3c0d3e9c96cd0fd8880a8",
      "version": "2.5.4"
    },
    "packaging": {
      "bytes": 129956,
      "filename": "packaging-26.3-py3-none-any.whl",
      "sha256": "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c",
      "version": "26.3"
    },
    "pip": {
      "bytes": 1841506,
      "filename": "pip-25.0-py3-none-any.whl",
      "sha256": "b6eb97a803356a52b2dd4bb73ba9e65b2ba16caa6bcb25a7497350a4e5859b65",
      "version": "25.0"
    },
    "pluggy": {
      "bytes": 20538,
      "filename": "pluggy-1.6.0-py3-none-any.whl",
      "sha256": "e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746",
      "version": "1.6.0"
    },
    "protobuf": {
      "bytes": 456039,
      "filename": "protobuf-7.36.2-cp310-abi3-macosx_10_9_universal2.whl",
      "sha256": "cbc70b17ee27e28894c7fee8bb04be1abead49e936bc70eb60052531eee2079e",
      "version": "7.36.2"
    },
    "psutil": {
      "bytes": 129859,
      "filename": "psutil-7.2.2-cp36-abi3-macosx_11_0_arm64.whl",
      "sha256": "1a7b04c10f32cc88ab39cbf606e117fd74721c831c98a27dc04578deb0c16979",
      "version": "7.2.2"
    },
    "pygments": {
      "bytes": 1250147,
      "filename": "pygments-2.21.0-py3-none-any.whl",
      "sha256": "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9",
      "version": "2.21.0"
    },
    "pytest": {
      "bytes": 386536,
      "filename": "pytest-9.1.1-py3-none-any.whl",
      "sha256": "37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c",
      "version": "9.1.1"
    },
    "pyyaml": {
      "bytes": 173973,
      "filename": "pyyaml-6.0.3-cp312-cp312-macosx_11_0_arm64.whl",
      "sha256": "fc09d0aa354569bc501d4e787133afc08552722d3ab34836a80547331bb5d4a0",
      "version": "6.0.3"
    },
    "regex": {
      "bytes": 293633,
      "filename": "regex-2026.9.29-cp312-cp312-macosx_11_0_arm64.whl",
      "sha256": "f57dc6b8fef170f105d2cf5cdce254f47b137d7755086cf7050f47e16582abba",
      "version": "2026.9.29"
    },
    "rich": {
      "bytes": 310654,
      "filename": "rich-15.0.0-py3-none-any.whl",
      "sha256": "33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb",
      "version": "15.0.0"
    },
    "safetensors": {
      "bytes": 484562,
      "filename": "safetensors-0.8.0-cp310-abi3-macosx_11_0_arm64.whl",
      "sha256": "c80201d22cbf405b80647a60ada77bba06c8fba2da2743ba1e89cdcc39a81f25",
      "version": "0.8.0"
    },
    "scikit-learn": {
      "bytes": 8295541,
      "filename": "scikit_learn-1.9.1-cp312-cp312-macosx_12_0_arm64.whl",
      "sha256": "8c14ce41d561f7749f990b41d6703fe02c4669fbc485e598e069e0a1967b488e",
      "version": "1.9.1"
    },
    "scipy": {
      "bytes": 20475078,
      "filename": "scipy-1.18.1-cp312-cp312-macosx_14_0_arm64.whl",
      "sha256": "7bbf207c4453ce1ad2e00b17313852b33310b83090c2311bdaf97f93c0380d12",
      "version": "1.18.1"
    },
    "sentence-transformers": {
      "bytes": 740560,
      "filename": "sentence_transformers-6.1.0-py3-none-any.whl",
      "sha256": "eb8122f4d180f552eda26dc3d77e84e8c11dc2b1d456a406b9f24abb70ceeadd",
      "version": "6.1.0"
    },
    "sentencepiece": {
      "bytes": 1347176,
      "filename": "sentencepiece-0.2.2-cp312-cp312-macosx_11_0_arm64.whl",
      "sha256": "38111ed1f79268f399c505028023d5eaaf0ab4e5eafceb709468b0d3323e7838",
      "version": "0.2.2"
    },
    "setuptools": {
      "bytes": 818216,
      "filename": "setuptools-84.0.0-py3-none-any.whl",
      "sha256": "51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670",
      "version": "84.0.0"
    },
    "shellingham": {
      "bytes": 9755,
      "filename": "shellingham-1.5.4-py2.py3-none-any.whl",
      "sha256": "7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686",
      "version": "1.5.4"
    },
    "sympy": {
      "bytes": 6299353,
      "filename": "sympy-1.14.0-py3-none-any.whl",
      "sha256": "e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5",
      "version": "1.14.0"
    },
    "threadpoolctl": {
      "bytes": 26362,
      "filename": "threadpoolctl-3.7.0-py3-none-any.whl",
      "sha256": "cd8b60b5641b45c67bbf73c64c843235fc2d8a480c87389f52f5dbee893b86be",
      "version": "3.7.0"
    },
    "tokenizers": {
      "bytes": 3101381,
      "filename": "tokenizers-0.23.3-cp310-abi3-macosx_11_0_arm64.whl",
      "sha256": "68649e97d5b43c44c031d8d848874a6eecae8f8fe40ea989aa777a5a83aca716",
      "version": "0.23.3"
    },
    "torch": {
      "bytes": 127307099,
      "filename": "torch-2.14.1-cp312-cp312-macosx_14_0_arm64.whl",
      "sha256": "420dbf314c180ee4b86e9bc00aee5746a7d6e5bacdd7df925af671ed393f0b2e",
      "version": "2.14.1"
    },
    "tqdm": {
      "bytes": 80199,
      "filename": "tqdm-4.70.1-py3-none-any.whl",
      "sha256": "c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73",
      "version": "4.70.1"
    },
    "transformers": {
      "bytes": 12599123,
      "filename": "transformers-5.19.0-py3-none-any.whl",
      "sha256": "afcd2dd5f603ed28c1e1fcb00a338ccbb4ef5f878ed289635df8b58187afb518",
      "version": "5.19.0"
    },
    "typer": {
      "bytes": 123312,
      "filename": "typer-0.27.3-py3-none-any.whl",
      "sha256": "e50022f28b82a86313e54501317a1db64bf8f8d036ff8cfe5ca7e47675454aff",
      "version": "0.27.3"
    },
    "typing-extensions": {
      "bytes": 45571,
      "filename": "typing_extensions-4.16.0-py3-none-any.whl",
      "sha256": "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
      "version": "4.16.0"
    }
  }
}
```

## Population

```json
{
  "audit_status": "ok",
  "counts": {
    "documents": 507793,
    "exact_question_overlap_after_removal": 0,
    "exclusion_reasons": {
      "invalid_support_reference": 23,
      "paragraph_count": 898
    },
    "protected_population": 7344,
    "protected_titles": 66350,
    "raw_dev_rows": 7405,
    "raw_train_rows": 90447,
    "removed_training_rows": 0,
    "shared_exact_titles": 40901,
    "train_titles": 480532,
    "training_groups": 89579,
    "validated_dev_rows": 7344,
    "validated_train_rows": 89587
  },
  "files": {
    "development-reservations.json": {
      "bytes": 8563452,
      "sha256": "505aef32b0eb68da85eaec2aeba66dd5e43752694d53378d6308711e1b9583bf"
    },
    "documents.jsonl": {
      "bytes": 324547371,
      "sha256": "032079542ef8692f7272ff3692dc44b4cfa9ce41f376daa2abf1b5508a2c08bd"
    },
    "duplicate-membership.jsonl": {
      "bytes": 21017819,
      "sha256": "a48fa4823f404436b21d353e6dec85dca81b6df08c49901d49ed4bf30ffccad8"
    },
    "exclusions.jsonl": {
      "bytes": 93864,
      "sha256": "b3afa66ea74df2d93c38bc1e4204d25541651b9edec137e45170feb3215805c3"
    },
    "gold/gold.jsonl": {
      "bytes": 13989662,
      "sha256": "6aae94d71c463b77f90d5ca164402c0fac9ebae05c7550496b5947b03865ba49"
    },
    "protected-population.json": {
      "bytes": 198311,
      "sha256": "35daf13300851d95196f45279545dc1b75f112dfc08cdeb36ed3510191181520"
    },
    "tasks.jsonl": {
      "bytes": 84337859,
      "sha256": "45d9baf5b5a05de38d3aa37494b952247c04c04e24ac0dc7454f328573a11fc2"
    }
  },
  "fingerprint": "0be799643ab549f784c2d214c4c1cedce0a7d9195d25861b762aa6f70f0bf858",
  "fit_prefix_sizes": {
    "1024": 1024,
    "16384": 16384,
    "2048": 2048,
    "256": 256,
    "32768": 32768,
    "4096": 4096,
    "512": 512,
    "65536": 65536,
    "8192": 8192,
    "89387": 89387
  },
  "measurement": {
    "conversion_seconds": 56.703276291984366,
    "max_raw_record_json_bytes": 18560,
    "parser_chunk_characters": 65536,
    "peak_rss_bytes": 138985472,
    "prepared_bytes": 452748338,
    "raw_bytes": 612746344,
    "reader_loaded": false,
    "sqlite_cache_bytes": 8388608
  },
  "raw_text_committed": false,
  "reservation_counts": {
    "active_pilot": 32,
    "fit": 256,
    "fit_extension": 89131,
    "pilot": 64,
    "protected": 7344,
    "tune": 128
  },
  "rules": {
    "annotation_boundary": "serving imports data_runtime directly",
    "document_id": "sha256 canonical [title, original_sentences]",
    "duplicate_id": "reject every occurrence",
    "entity_overlap": "exact titles reported; entity linking not performed",
    "group_key": "NFC then casefold then whitespace collapse",
    "order": "sha256 canonical [split_seed, group_key], then group_key",
    "representative": "minimum task_id"
  },
  "schema_version": 1,
  "sources": {
    "dev": {
      "archive_capture": "20250512032701",
      "bytes": 46320117,
      "final_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
      "integrity_limitation": "No separately fetched current author file or author cryptographic checksum.",
      "license": "cc-by-sa-4.0",
      "path": "<repository>/models/pinned/data/hotpot_dev_distractor_v1.json",
      "provenance_url": "https://hotpotqa.github.io/",
      "requested_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
      "sha256": "4e9ecb5c8d3b719f624d66b60f8d56bf227f03914f5f0753d6fa1b359d7104ea",
      "source_amendment": "A01",
      "source_label": "archived_author_origin_raw_snapshot",
      "source_policy": "direct_author_or_pinned_raw_author_archive",
      "source_url": "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json"
    },
    "train": {
      "archive_capture": "20250512032701",
      "bytes": 566426227,
      "final_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
      "integrity_limitation": "No separately fetched current author file or author cryptographic checksum.",
      "license": "cc-by-sa-4.0",
      "path": "<repository>/models/pinned/data/hotpot_train_v1.1.json",
      "provenance_url": "https://hotpotqa.github.io/",
      "requested_url": "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
      "sha256": "26650cf50234ef5fb2e664ed70bbecdfd87815e6bffc257e068efea5cf7cd316",
      "source_amendment": "A01",
      "source_label": "archived_author_origin_raw_snapshot",
      "source_policy": "direct_author_or_pinned_raw_author_archive",
      "source_url": "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json"
    }
  },
  "split_seed": 20261014
}
```

## Protocol

```json
{
  "protocol_hash": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100",
  "digests": {
    "methods": "6817223fe570e4472df38039e2d0d0624f8f2f9417d79b6ce547300e49af83ad",
    "sample": "fe89db6b1592fcf3ae9bf849187b6ea406b5fe4d20cc1b026b61aeca46be6009",
    "schedule": "7b5e3932a490d75733c8f7e8c085471ab8e229c71d944d3da0dd2761d8862208"
  }
}
```

## Tuning

```json
{
  "A": {
    "Q": 0.078125,
    "R": 19.1111308497,
    "action_rates": {
      "1": 0.0,
      "10": 0.1953125,
      "2": 0.8046875,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    },
    "answer_em": 0.453125,
    "answer_successes": 58,
    "assigned_tasks": 128,
    "config_id": "PRE-OUTCOME-GBM:17:numeric",
    "cost_kind": "development_paid_action_reconstruction",
    "eligible": true,
    "family": "PRE-OUTCOME-GBM",
    "fit_escalation_probability": 0.19921875,
    "ineligible_reason": null,
    "joint_successes": 10,
    "mean_time": 1.4930570976328126,
    "model_artifact_sha256": "9a34e2b065e6e94213bcdaaf42e56848e269a74f25a4327cd98d3aff80f69caf",
    "model_name": "PRE-OUTCOME-GBM",
    "reason": null,
    "selection_pool": true,
    "split": "tune",
    "threshold": 0.0339522174316994,
    "threshold_mode": "numeric",
    "total_experiment_seconds": 198.20652755729898,
    "total_serving_seconds": 191.111308497
  },
  "B": {
    "Q": 0.0859375,
    "R": 14.66098451109091,
    "action_rates": {
      "1": 0.0,
      "10": 0.0625,
      "2": 0.9375,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    },
    "answer_em": 0.46875,
    "answer_successes": 60,
    "assigned_tasks": 128,
    "config_id": "PROXY-LABEL:14:numeric",
    "cost_kind": "development_paid_action_reconstruction",
    "eligible": true,
    "family": "PROXY-LABEL",
    "fit_escalation_probability": 0.25,
    "ineligible_reason": null,
    "joint_successes": 11,
    "mean_time": 1.259928356421875,
    "model_artifact_sha256": "c669e76c6350fa307f4bfb31457823015dda0954fa89c346f6b0600d3ce636a0",
    "model_name": "PROXY-LABEL",
    "reason": null,
    "selection_pool": true,
    "split": "tune",
    "threshold": 0.801315057689046,
    "threshold_mode": "numeric",
    "total_experiment_seconds": 168.394482518299,
    "total_serving_seconds": 161.270829622
  },
  "fixed_ten_anchor": {
    "Q": 0.0390625,
    "R": 78.5252468076,
    "action_rates": {
      "1": 0.0,
      "10": 1.0,
      "2": 0.0,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    },
    "answer_em": 0.453125,
    "answer_successes": 58,
    "assigned_tasks": 128,
    "config_id": "FIXED-10",
    "cost_kind": "direct_source",
    "family": "FIXED",
    "joint_successes": 5,
    "k": 10,
    "mean_time": 3.067392453421875,
    "reason": null,
    "split": "tune",
    "total_experiment_seconds": 399.767147345299,
    "total_serving_seconds": 392.626234038
  },
  "interpretation": "Both selected controllers are cheap learned models. Development proxy baseline has lower seconds/success; added value of richer outcome labels remains unproven. Selection is not confirmation.",
  "learning_curve": {
    "additional_generation_calls": 0,
    "additional_labels": 0,
    "analysis_seconds": 12.308282374986447,
    "caution": "Two sparse held-out points with thresholds selected on the same tune128 are descriptive and not a stable learning trend, confidence interval or justification to acquire more labels. Gate CPU timing sessions differ; paid reader action costs are identical sources. Primary A*/B* remain the original fit256 selection.",
    "fit128_origin_sha256": "fce5e5095c4bb7f58f589428e3c61441f8c6c3672bf5c217e0c1fe7616bd0d24",
    "fit128_training_seconds": 0.04786033398704603,
    "original_fit256_origin_sha256": "189c17f91d58c6c8e646d75374cc5014f2992cc7ce2bddfd840d44f787681507",
    "original_models_and_selection_unchanged": true,
    "original_primary_selection_sha256": "e5f640c6f8a1292089df633e20611f50a074a3b2ade80714334a416414005ee9",
    "points": [
      {
        "Q": 0.0859375,
        "R": 20.74862086290909,
        "answer_em": 0.4765625,
        "answer_successes": 61,
        "config_id": "EXPLORATORY-FIT128-GBM:16:numeric",
        "fit_n": 128,
        "joint_successes": 11,
        "mean_time": 1.78308460540625,
        "threshold": 0.019173497518510055,
        "threshold_mode": "numeric"
      },
      {
        "Q": 0.078125,
        "R": 19.1111308497,
        "answer_em": 0.453125,
        "answer_successes": 58,
        "config_id": "PRE-OUTCOME-GBM:17:numeric",
        "fit_n": 256,
        "joint_successes": 10,
        "mean_time": 1.4930570976328126,
        "threshold": 0.0339522174316994,
        "threshold_mode": "numeric"
      }
    ],
    "scope": "exploratory held-out tune128 after primary fit256 selection; no additional inference/labels",
    "source_bindings": {
      "native": "b4d8e9532fb899a21bf614634270c5ff147b9d5454328f4722506d28cb89ec62",
      "primary_analysis": "3e9cc097b250905c04af47717ac60a72e98e35cc9f5fffccdec121d6b7adf41c"
    },
    "subset_rule": "first128 of original ordered fit256 acquisition; nested prefix, no outcome-based choice"
  },
  "legacy_seal": {
    "development_crosscheck_count": 256,
    "finished_receipts_checked": 1811,
    "limitation": "Original v1 closure did not hash successful ancillary paid receipts. This seals extant bytes after core/content checks; it does not prove their historical completion-time bytes.",
    "original_prediction_closure_sha256": "e7d6dd3967b3ae2e320253c2f294e5e468e6e3cd2aa4e00607716e170b14398c",
    "paid_receipt_file_count": 5433,
    "parsed_final_fields_checked": true,
    "private_seal_path": "artifacts/runs/task12-tune128-retry/paid-receipts.sealed.json",
    "private_seal_sha256": "85bdcd6176b39d043bf6d6c040306b15593f43135a2c8613230a6bb24e9c5073",
    "qualification": "retrospective_not_historical_completion_attestation",
    "sealed_utc": "2026-10-14T20:46:18.199322+00:00",
    "source_binding_hash": "3e9cc097b250905c04af47717ac60a72e98e35cc9f5fffccdec121d6b7adf41c"
  },
  "paid_receipt_coverage": "legacy_retrospective",
  "path": "artifacts/provenance/task16-development/20261015T015117851969Z/tuning-configurations.json",
  "warnings": [
    "Tuning eligibility is an empirical heuristic, not a quality certificate.",
    "All candidate/comparator costs use measured per-request routing and original paid action costs.",
    "The optimized POST numerical-parity gate failed; clean-prefill bounds are unexecuted sensitivities.",
    "Reconstruction replaces source final routing/payload, preserves earlier attempts, and retains shared retrieval exactly once.",
    "PRE endpoint development costs alias fixed actions; POST endpoints retain paid draft work."
  ],
  "configuration_count": 246,
  "family_count": 11,
  "complete_table_sha256": "2ada91030ab13239785f8576d910e168f4491d278d7d58e71df14e74478e4ee7"
}
```

## Memory

```json
{
  "calibration_resource_gate": {
    "limit_bytes": 30923764531,
    "passed": true,
    "reserve_bytes": 7730941133,
    "working_set_bytes": 6756859004
  },
  "harness": {
    "peak_mlx_bytes": 2959672540,
    "resource_gate": {
      "limit_bytes": 30923764531,
      "passed": true,
      "reserve_bytes": 7730941133,
      "working_set_bytes": 4322723036
    },
    "sampled_peak_parent_and_worker_rss_bytes": 1363050496
  },
  "prerequisite": {
    "active_mlx_bytes": 2264693768,
    "peak_mlx_bytes": 2513452612,
    "rss_bytes": 1389772800,
    "sampled_peak_rss_bytes": 2707308544,
    "swap_after_bytes": 8334213120,
    "swap_before_bytes": 8334213120,
    "swap_growth_bytes": 0
  },
  "qualification": "RSS plus MLX is an overlapping conservative bound, not a disjoint physical allocation; existing swap differs from measured swap growth.",
  "tuning": {
    "peak_mlx_bytes": 3293260628,
    "resource_bound_kind": "sampled parent plus recursive child RSS plus MLX overlapping conservative bound",
    "resource_gate": {
      "limit_bytes": 30923764531,
      "passed": true,
      "reserve_bytes": 7730941133,
      "working_set_bytes": 6147713876
    },
    "sampled_peak_process_tree_rss_bytes": 2854453248
  },
  "A03_actual": {
    "assigned_jobs": 3360,
    "elapsed_seconds": 6652.692496791,
    "launch_attempt": 1,
    "network_attempts": 0,
    "os_denials": {
      "0": true,
      "1": true,
      "2": true,
      "3": true,
      "4": true,
      "network": true
    },
    "peak_mlx_bytes": 3367284112,
    "protocol_hash": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07",
    "resource_bound_kind": "sampled recursive process RSS plus overlapping MLX conservative bound",
    "resource_gate": {
      "limit_bytes": 30923764531,
      "passed": true,
      "reserve_bytes": 7730941133,
      "working_set_bytes": 6489140624
    },
    "sampled_peak_process_tree_rss_bytes": 3121856512,
    "status": "closed"
  }
}
```

## Physical costs

```json
{
  "known_physical_seconds": 28786.079555628312,
  "total_physical_seconds": null,
  "reason": "unknown_costs",
  "unknown_physical_ids": [
    "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:unavailable-outer-wall-and-allocations",
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:unavailable-valid-wall-cost",
    "task17-root-manifest-audit:failed-probe",
    "unmetered-development:ancillary-input-audit",
    "unmetered-development:failed-calibration-launch",
    "unmetered-development:failed-native",
    "unmetered-development:outer-native",
    "unmetered-development:phase2a-initial-inspection",
    "unmetered-development:preledger-index-publication",
    "unmetered-development:unmetered-assets-environment",
    "unmetered-development:unmetered-editing-tests"
  ],
  "counted_physical_ids": [
    "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:launch-1-active-envelope",
    "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:unavailable-outer-wall-and-allocations",
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:launch-1-active-envelope",
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:unavailable-valid-wall-cost",
    "asset:hotpot_dev_distractor:download_seconds",
    "asset:hotpot_dev_distractor:validation_seconds",
    "asset:hotpot_train:download_seconds",
    "asset:hotpot_train:validation_seconds",
    "development:calibration-native:calibration-native",
    "development:calibration-prelaunch:calibration-prelaunch",
    "development:capacity-input-audit:capacity-input-audit",
    "development:comparators:native_acquisition_seconds",
    "development:comparators:post_fit_analysis_seconds",
    "development:comparators:separate_scoring_seconds",
    "development:data-conversion:data-conversion",
    "development:development-parity:development-parity",
    "development:fit256:actual_pair_merge_proxy_training_and_draft_preparation_seconds",
    "development:fit256:actual_scoring_seconds",
    "development:fit256:collection_acquisition_wall_seconds",
    "development:freeze-dry-run:freeze-dry-run",
    "development:pilot-retrieval-coverage-audit:pilot-retrieval-coverage-audit",
    "development:pilot-token-length-audit:pilot-token-length-audit",
    "development:pilot:exclusive-ledger-residual",
    "development:task8-harness:task8-harness",
    "development:tune128:accounting_profile_seconds",
    "development:tune128:failed_preflight_cli_seconds",
    "development:tune128:legacy_seal_seconds",
    "development:tune128:native_envelope_seconds",
    "development:tune128:optional_curve_seconds",
    "development:tune128:original_fit512_scaling_audit_seconds",
    "development:tune128:scoring_seconds",
    "development:tune128:selection_analysis_seconds",
    "development:wp0-reader-only:wp0-reader-only",
    "development:wp0:wp0",
    "development:wp2-reader-scoring:wp2-reader-scoring",
    "origin:index-attempt:27ac30dbb3754ab1a0acce582f590725",
    "origin:index-attempt:3ad8c0a858a948d4874b01a3f6d3315d",
    "origin:index-attempt:3e824ed66e7343dcb4df27826ea41a68",
    "origin:index-attempt:57a3b52fb4954b5b8b303f0178f369d5",
    "origin:index-attempt:c6145bc592094fe3979b8550d1f52ac5",
    "origin:index-attempt:e78a67ed335d40378a4b339cef781d3b",
    "origin:task17-root-manifest-audit-success",
    "software-verification:task17-full-suite",
    "software-verification:task18-full-suite",
    "task16-offline:a03-initial-score",
    "task16-offline:a03-reproduce",
    "task16-offline:original-reproduce",
    "task16-offline:protocol-verification",
    "task17-manifest-preparation:attempt_1_perf_seconds",
    "task17-manifest-preparation:attempt_2_verification_perf_seconds",
    "task17-manifest-preparation:attempt_2_writer_perf_seconds",
    "task17-root-manifest-audit:failed-probe",
    "unmetered-development:ancillary-input-audit",
    "unmetered-development:failed-calibration-launch",
    "unmetered-development:failed-native",
    "unmetered-development:outer-native",
    "unmetered-development:phase2a-initial-inspection",
    "unmetered-development:preledger-index-publication",
    "unmetered-development:unmetered-assets-environment",
    "unmetered-development:unmetered-editing-tests"
  ],
  "sources": {
    "origin:index-attempt:3ad8c0a858a948d4874b01a3f6d3315d": {
      "seconds": 19.453162709018216,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "origin:index-attempt:c6145bc592094fe3979b8550d1f52ac5": {
      "seconds": 18.282344709004974,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "origin:index-attempt:3e824ed66e7343dcb4df27826ea41a68": {
      "seconds": 19.22866433300078,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "origin:index-attempt:27ac30dbb3754ab1a0acce582f590725": {
      "seconds": 20.054970666009467,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "development:pilot:exclusive-ledger-residual": {
      "seconds": 476.7747705089665,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:pilot:serving": {
      "seconds": 435.232398968,
      "parent_id": "development:pilot:exclusive-ledger-residual",
      "category": "development",
      "reason": null
    },
    "development:pilot:warmup": {
      "seconds": 89.784132041,
      "parent_id": "development:pilot:serving",
      "category": "development",
      "reason": null
    },
    "development:wp0-reader-only:wp0-reader-only": {
      "seconds": 9.790772000007564,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:wp0:wp0": {
      "seconds": 10.45894749998115,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:wp2-reader-scoring:wp2-reader-scoring": {
      "seconds": 21.949175624991767,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:task8-harness:task8-harness": {
      "seconds": 41.811203707,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:pilot-token-length-audit:pilot-token-length-audit": {
      "seconds": 9.789990416000364,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:pilot-retrieval-coverage-audit:pilot-retrieval-coverage-audit": {
      "seconds": 14.914878582989331,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:data-conversion:data-conversion": {
      "seconds": 56.703276291984366,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "origin:index-attempt:e78a67ed335d40378a4b339cef781d3b": {
      "seconds": 45.1715879169642,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "development:fit256:collection_acquisition_wall_seconds": {
      "seconds": 925.6303293704987,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:fit256:actual_scoring_seconds": {
      "seconds": 70.88125066703651,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:fit256:actual_pair_merge_proxy_training_and_draft_preparation_seconds": {
      "seconds": 33.025188166997395,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:fit256:serving": {
      "seconds": 869.037530531,
      "parent_id": "development:fit256:collection_acquisition_wall_seconds",
      "category": "development",
      "reason": null
    },
    "development:fit256:training": {
      "seconds": 0.48465045797638595,
      "parent_id": "development:fit256:actual_pair_merge_proxy_training_and_draft_preparation_seconds",
      "category": "development",
      "reason": null
    },
    "development:comparators:native_acquisition_seconds": {
      "seconds": 126.411278916,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:comparators:separate_scoring_seconds": {
      "seconds": 18.225356708979234,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:comparators:post_fit_analysis_seconds": {
      "seconds": 36.057644417,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:comparators:model-fit": {
      "seconds": 0.08046620804816484,
      "parent_id": "development:comparators:post_fit_analysis_seconds",
      "category": "development",
      "reason": null
    },
    "development:tune128:native_envelope_seconds": {
      "seconds": 3436.086341334,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:legacy_seal_seconds": {
      "seconds": 17.27881241601426,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:scoring_seconds": {
      "seconds": 14.661938917008229,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:selection_analysis_seconds": {
      "seconds": 14.039366374956444,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:optional_curve_seconds": {
      "seconds": 12.308282374986447,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:accounting_profile_seconds": {
      "seconds": 10.958,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:original_fit512_scaling_audit_seconds": {
      "seconds": 3.996456333,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:tune128:failed_preflight_cli_seconds": {
      "seconds": 0.281374041,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "origin:index-attempt:57a3b52fb4954b5b8b303f0178f369d5": {
      "seconds": 34.082241915981285,
      "parent_id": null,
      "category": "index",
      "reason": null
    },
    "development:tune128:paid_job_serving_seconds": {
      "seconds": 3330.785427891,
      "parent_id": "development:tune128:native_envelope_seconds",
      "category": "development",
      "reason": null
    },
    "development:tune128:paid_job_experiment_seconds": {
      "seconds": 3417.944468275,
      "parent_id": "development:tune128:native_envelope_seconds",
      "category": "development",
      "reason": null
    },
    "development:tune128:task12-native-setup": {
      "seconds": 24.727848,
      "parent_id": "development:tune128:native_envelope_seconds",
      "category": "development",
      "reason": null
    },
    "development:tune128:task12-policy-materialization-and-schedule": {
      "seconds": 0.414402084,
      "parent_id": "development:tune128:native_envelope_seconds",
      "category": "development",
      "reason": null
    },
    "development:tune128:task12-request-routing-measurements-and-receipts": {
      "seconds": 55.873367209,
      "parent_id": "development:tune128:native_envelope_seconds",
      "category": "development",
      "reason": null
    },
    "development:capacity-input-audit:capacity-input-audit": {
      "seconds": 26.96328145795269,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:calibration-prelaunch:calibration-prelaunch": {
      "seconds": 11.07208125,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:calibration-native:calibration-native": {
      "seconds": 473.745710166,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:freeze-dry-run:freeze-dry-run": {
      "seconds": 2.8919876670115627,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:development-parity:development-parity": {
      "seconds": 73.03529654099839,
      "parent_id": null,
      "category": "development",
      "reason": null
    },
    "development:calibration-native:serving": {
      "seconds": 445.307450051,
      "parent_id": "development:calibration-native:calibration-native",
      "category": "development",
      "reason": null
    },
    "asset:hotpot_dev_distractor:download_seconds": {
      "seconds": 5.64313716700417,
      "parent_id": null,
      "category": "asset-acquisition-subpart",
      "reason": null
    },
    "asset:hotpot_dev_distractor:validation_seconds": {
      "seconds": 0.16637133300537243,
      "parent_id": null,
      "category": "asset-acquisition-subpart",
      "reason": null
    },
    "asset:hotpot_train:download_seconds": {
      "seconds": 68.46416375000263,
      "parent_id": null,
      "category": "asset-acquisition-subpart",
      "reason": null
    },
    "asset:hotpot_train:validation_seconds": {
      "seconds": 1.745667749986751,
      "parent_id": null,
      "category": "asset-acquisition-subpart",
      "reason": null
    },
    "unmetered-development:unmetered-assets-environment": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Remaining asset downloads/install and enclosing acquisition duration were not metered; measured dataset subparts are listed separately."
    },
    "unmetered-development:preledger-index-publication": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Historical index work before attempt ledger lacks enclosing measurement."
    },
    "unmetered-development:unmetered-editing-tests": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Historical editing, tests and prelaunch work were not comprehensively metered."
    },
    "unmetered-development:failed-native": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Failed native subprocess envelope unavailable."
    },
    "unmetered-development:outer-native": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Unmeasured outer overhead outside the retained native envelope; not an additional copy of its interior."
    },
    "unmetered-development:failed-calibration-launch": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "First failed launch had zero generation calls but unmetered setup, not zero cost."
    },
    "unmetered-development:ancillary-input-audit": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Ancillary NFC check failure duration unavailable."
    },
    "unmetered-development:phase2a-initial-inspection": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Initial evidence inspection/coordination before timed assembly not comprehensively metered."
    },
    "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:launch-1-active-envelope": {
      "seconds": 15400.9177295,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:launch-1-active-envelope": {
      "seconds": 6656.832093125,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope": {
      "seconds": 6652.692496791,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:launch-1-active-envelope",
      "category": "actual-process-cost",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:total_physical_serving_seconds": {
      "seconds": 6589.289303332,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope",
      "category": "actual-process-cost",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:total_physical_experiment_seconds": {
      "seconds": 6616.754645963,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope",
      "category": "actual-process-cost",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:task14-launch-1:pre-index-setup": {
      "seconds": 13.458778666,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope",
      "category": "cold_setup",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:task14-launch-1:selected-index-build-or-load": {
      "seconds": 0.019759042,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope",
      "category": "offline",
      "reason": null
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:task14-launch-1:post-index-runtime-setup": {
      "seconds": 4.589900792,
      "parent_id": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:native-active-envelope",
      "category": "cold_setup",
      "reason": null
    },
    "origin:415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:index-attempt:927ba64d93084cd2a6d43ead0b85ee54": {
      "seconds": null,
      "parent_id": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:launch-1-active-envelope",
      "category": "index",
      "reason": "Original measured index interval not re-extracted from incomplete collection; its physical work is included once inside original enclosing active interval."
    },
    "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100:artifacts/runs/confirmation:unavailable-outer-wall-and-allocations": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Unclosed final attempt and full per-job allocation unavailable; intended wall boundary invalid. Do not zero-fill or repair timing."
    },
    "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07:artifacts/runs/task17-timing-replication:unavailable-valid-wall-cost": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "Active clock omits verified suspension; no valid per-query wall-cost allocation or reconstructed endpoint."
    },
    "task17-manifest-preparation:attempt_1_perf_seconds": {
      "seconds": 6.492238208,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task17-manifest-preparation:attempt_2_writer_perf_seconds": {
      "seconds": 20.480051584,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task17-manifest-preparation:attempt_2_verification_perf_seconds": {
      "seconds": 5.177372792,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "origin:task17-root-manifest-audit-success": {
      "seconds": 8.802580167015549,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task17-root-manifest-audit:failed-probe": {
      "seconds": null,
      "parent_id": null,
      "category": "unknown",
      "reason": "First root probe failed after verification; wrapper interval was not retained."
    },
    "software-verification:task17-full-suite": {
      "seconds": 183.9030260000145,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "software-verification:task18-full-suite": {
      "seconds": 213.82618183398154,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:a03-initial-score": {
      "seconds": 51.22643041698029,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:original-reproduce": {
      "seconds": 0.17539762501837686,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:a03-reproduce": {
      "seconds": 51.06223170796875,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:initial-score-inner": {
      "seconds": 6.986915750021581,
      "parent_id": "task16-offline:a03-initial-score",
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:reproduce-inner": {
      "seconds": 50.91949945903616,
      "parent_id": "task16-offline:a03-reproduce",
      "category": "actual-process-cost",
      "reason": null
    },
    "task16-offline:protocol-verification": {
      "seconds": 5.148918666993268,
      "parent_id": null,
      "category": "actual-process-cost",
      "reason": null
    }
  },
  "rule": "unique physical roots only; nested components and reused allocations excluded"
}
```

## Adaptation

```json
{
  "A": "Outcome-model fitting needs paired reader-outcome targets and feature/retrieval preparation; model fitting alone is not total adaptation.",
  "B": "Proxy-label fitting uses support-coverage annotations without needing paired reader outcomes. Common outcome-based tuning still costs; proxy is a trained cheap model.",
  "fit_training_seconds_subset": 0.48465045797638595,
  "physical_joint_experiment": "All paid experiments enter physical ledger, including paired reader outcomes, tuning, warmups and failed attempts.",
  "pretrained_assets": "Shared pretrained model/embedding acquisition is separate prerequisite work.",
  "reason": "Per-method deployment attribution and all historical outer costs not fully identified.",
  "shared": "Original physical index/vector reuse paid once. Independent executions namespace setup/job IDs by protocol/root/attempt.",
  "total_seconds": null
}
```

## Break even

```json
{
  "queries": null,
  "delta_t": null,
  "reason": "wall_time_invalid_or_unverified"
}
```

## Direct replay

```json
{
  "development_checks": [
    {
      "config_id": "PRE-OUTCOME-GBM:11:numeric",
      "direct_serving_seconds": 2.473735333,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.061449874
    },
    {
      "config_id": "PRE-RF:11:numeric",
      "direct_serving_seconds": 0.64563325,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 0.5339426260000001
    },
    {
      "config_id": "POST-OUTCOME:11:numeric",
      "direct_serving_seconds": 3.248000708,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.3316059989999998
    },
    {
      "config_id": "ADAPTIVE-k-published-B5",
      "direct_serving_seconds": 2.656022667,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.0611965420000002
    },
    {
      "config_id": "PRE-OUTCOME-GBM:11:numeric",
      "direct_serving_seconds": 1.110908834,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 1.268321042
    },
    {
      "config_id": "PRE-RF:11:numeric",
      "direct_serving_seconds": 1.125853416,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 1.27561325
    },
    {
      "config_id": "POST-OUTCOME:11:numeric",
      "direct_serving_seconds": 1.12972275,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 1.2683019580000001
    },
    {
      "config_id": "ADAPTIVE-k-published-B5",
      "direct_serving_seconds": 1.9974215,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 2.2321526659999997
    },
    {
      "config_id": "PRE-OUTCOME-GBM:11:numeric",
      "direct_serving_seconds": 1.000767334,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 1.0019289590000002
    },
    {
      "config_id": "PRE-RF:11:numeric",
      "direct_serving_seconds": 2.791006792,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.0349650430000006
    },
    {
      "config_id": "POST-OUTCOME:11:numeric",
      "direct_serving_seconds": 3.787718916,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 4.275890541999999
    },
    {
      "config_id": "ADAPTIVE-k-published-B5",
      "direct_serving_seconds": 1.720860042,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 1.720777626
    },
    {
      "config_id": "PRE-OUTCOME-GBM:11:numeric",
      "direct_serving_seconds": 3.02558,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.3266425849999997
    },
    {
      "config_id": "PRE-RF:11:numeric",
      "direct_serving_seconds": 3.014442833,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 3.334225001
    },
    {
      "config_id": "POST-OUTCOME:11:numeric",
      "direct_serving_seconds": 3.910827583,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 4.233554416
    },
    {
      "config_id": "ADAPTIVE-k-published-B5",
      "direct_serving_seconds": 2.018952083,
      "output_status_parity": true,
      "reconstructed_serving_seconds": 2.1683124999999994
    }
  ],
  "qualification": "Development reconstructions reuse paid action outcomes. Direct output/status parity does not imply identical timing; protected comparison needs separate closure/validity assessment."
}
```

## Post cache

```json
{
  "actual_cache_mode": "none",
  "best_eligible_optimistic_bound": {
    "Q": 0.0859375,
    "R": 14.948107479986271,
    "action_rates": {
      "1": 0.0,
      "10": 0.203125,
      "2": 0.796875,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    },
    "answer_em": 0.453125,
    "answer_successes": 58,
    "assigned_tasks": 128,
    "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
    "config_id": "POST-OUTCOME:20:numeric",
    "cost_kind": "development_paid_action_reconstruction",
    "eligible": true,
    "executed": false,
    "family": "POST-OUTCOME",
    "fit_escalation_probability": 0.05078125,
    "joint_successes": 11,
    "mean_time": 1.2846029865613202,
    "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
    "model_name": "POST-OUTCOME",
    "reason": null,
    "selection_pool": false,
    "split": "tune",
    "threshold": 0.06876897153298181,
    "threshold_mode": "numeric",
    "total_experiment_seconds": 230.41022196929896,
    "total_serving_seconds": 164.429182279849
  },
  "gate_status": "no_reuse_plus_optimistic_bound_required",
  "optimistic_bounds": [
    {
      "Q": 0.0390625,
      "R": 51.07486907846201,
      "action_rates": {
        "1": 0.0,
        "10": 1.0,
        "2": 0.0,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:00:always_ten",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 1.0,
      "joint_successes": 5,
      "mean_time": 1.9951120733774221,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": null,
      "threshold_mode": "always_ten",
      "total_experiment_seconds": 552.1598759052989,
      "total_serving_seconds": 255.37434539231003
    },
    {
      "Q": 0.0390625,
      "R": 51.07819841726201,
      "action_rates": {
        "1": 0.0,
        "10": 1.0,
        "2": 0.0,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:01:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.99609375,
      "joint_successes": 5,
      "mean_time": 1.9952421256742972,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.9235826365418169,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 552.1765225992989,
      "total_serving_seconds": 255.39099208631004
    },
    {
      "Q": 0.09375,
      "R": 19.763733507332788,
      "action_rates": {
        "1": 0.0,
        "10": 0.84375,
        "2": 0.15625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4921875,
      "answer_successes": 63,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:02:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.94921875,
      "joint_successes": 12,
      "mean_time": 1.8528500163124488,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.20938413960275207,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 488.77966073229896,
      "total_serving_seconds": 237.16480208799345
    },
    {
      "Q": 0.1015625,
      "R": 17.07521226292256,
      "action_rates": {
        "1": 0.0,
        "10": 0.6875,
        "2": 0.3125,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.484375,
      "answer_successes": 62,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:03:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.8984375,
      "joint_successes": 13,
      "mean_time": 1.7342012454530724,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.060058810557252526,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 431.2316422722989,
      "total_serving_seconds": 221.97775941799327
    },
    {
      "Q": 0.1015625,
      "R": 16.613887343308967,
      "action_rates": {
        "1": 0.0,
        "10": 0.6171875,
        "2": 0.3828125,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4765625,
      "answer_successes": 61,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:04:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.84765625,
      "joint_successes": 13,
      "mean_time": 1.6873479333048171,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.04125826930550488,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 403.886781151299,
      "total_serving_seconds": 215.9805354630166
    },
    {
      "Q": 0.1015625,
      "R": 16.54305174922986,
      "action_rates": {
        "1": 0.0,
        "10": 0.609375,
        "2": 0.390625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.46875,
      "answer_successes": 60,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:05:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.796875,
      "joint_successes": 13,
      "mean_time": 1.6801536932811576,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.0321846956369605,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 397.976871971299,
      "total_serving_seconds": 215.05967273998817
    },
    {
      "Q": 0.09375,
      "R": 17.539575920410783,
      "action_rates": {
        "1": 0.0,
        "10": 0.5625,
        "2": 0.4375,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.46875,
      "answer_successes": 60,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:06:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.75,
      "joint_successes": 12,
      "mean_time": 1.644335242538511,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.022787033590665914,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 380.66064944229896,
      "total_serving_seconds": 210.4749110449294
    },
    {
      "Q": 0.09375,
      "R": 17.436192537583366,
      "action_rates": {
        "1": 0.0,
        "10": 0.546875,
        "2": 0.453125,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.46875,
      "answer_successes": 60,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:07:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.69921875,
      "joint_successes": 12,
      "mean_time": 1.6346430503984406,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.017358973281692683,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 374.21886630829897,
      "total_serving_seconds": 209.2343104510004
    },
    {
      "Q": 0.09375,
      "R": 17.25997950609366,
      "action_rates": {
        "1": 0.0,
        "10": 0.5234375,
        "2": 0.4765625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4765625,
      "answer_successes": 61,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:08:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.6484375,
      "joint_successes": 12,
      "mean_time": 1.6181230786962806,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.012286171823690595,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 365.7359592202989,
      "total_serving_seconds": 207.11975407312391
    },
    {
      "Q": 0.09375,
      "R": 17.09089962500781,
      "action_rates": {
        "1": 0.0,
        "10": 0.5078125,
        "2": 0.4921875,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4765625,
      "answer_successes": 61,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:09:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.59765625,
      "joint_successes": 12,
      "mean_time": 1.6022718398444824,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.008480913579850155,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 357.08349693729895,
      "total_serving_seconds": 205.09079550009375
    },
    {
      "Q": 0.09375,
      "R": 16.985801201003124,
      "action_rates": {
        "1": 0.0,
        "10": 0.5,
        "2": 0.5,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4765625,
      "answer_successes": 61,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:10:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.55078125,
      "joint_successes": 12,
      "mean_time": 1.5924188625940427,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.0036239910814133917,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 353.26540413929894,
      "total_serving_seconds": 203.82961441203747
    },
    {
      "Q": 0.09375,
      "R": 16.72188424642475,
      "action_rates": {
        "1": 0.0,
        "10": 0.484375,
        "2": 0.515625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4765625,
      "answer_successes": 61,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:11:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.5,
      "joint_successes": 12,
      "mean_time": 1.5676766481023203,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": -0.0005761721380870652,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 343.88155405629897,
      "total_serving_seconds": 200.662610957097
    },
    {
      "Q": 0.09375,
      "R": 16.364871798005307,
      "action_rates": {
        "1": 0.0,
        "10": 0.4453125,
        "2": 0.5546875,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4609375,
      "answer_successes": 59,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:12:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.44921875,
      "joint_successes": 12,
      "mean_time": 1.5342067310629974,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.004608850600711457,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 329.91315313229893,
      "total_serving_seconds": 196.37846157606367
    },
    {
      "Q": 0.09375,
      "R": 16.215828375174898,
      "action_rates": {
        "1": 0.0,
        "10": 0.4296875,
        "2": 0.5703125,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.46875,
      "answer_successes": 60,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:13:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.3984375,
      "joint_successes": 12,
      "mean_time": 1.5202339101726468,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.007664612175615249,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 324.355748975299,
      "total_serving_seconds": 194.58994050209878
    },
    {
      "Q": 0.0859375,
      "R": 17.053750635526946,
      "action_rates": {
        "1": 0.0,
        "10": 0.390625,
        "2": 0.609375,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:14:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.3515625,
      "joint_successes": 11,
      "mean_time": 1.465556695240597,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.013749562012233292,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 305.484525756299,
      "total_serving_seconds": 187.5912569907964
    },
    {
      "Q": 0.0859375,
      "R": 16.530409828814427,
      "action_rates": {
        "1": 0.0,
        "10": 0.34375,
        "2": 0.65625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4609375,
      "answer_successes": 59,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:15:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.30078125,
      "joint_successes": 11,
      "mean_time": 1.42058209466374,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.02005763451451425,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 287.75959992729895,
      "total_serving_seconds": 181.83450811695872
    },
    {
      "Q": 0.0859375,
      "R": 16.479365726267403,
      "action_rates": {
        "1": 0.0,
        "10": 0.3359375,
        "2": 0.6640625,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:16:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.25,
      "joint_successes": 11,
      "mean_time": 1.416195492101105,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.02628903820225363,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 284.953964135299,
      "total_serving_seconds": 181.27302298894145
    },
    {
      "Q": 0.0859375,
      "R": 16.253167794541216,
      "action_rates": {
        "1": 0.0,
        "10": 0.3125,
        "2": 0.6875,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:17:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.19921875,
      "joint_successes": 11,
      "mean_time": 1.3967566073433857,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.032181402341891395,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 277.103110514299,
      "total_serving_seconds": 178.78484573995337
    },
    {
      "Q": 0.0859375,
      "R": 15.691216495186996,
      "action_rates": {
        "1": 0.0,
        "10": 0.2578125,
        "2": 0.7421875,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4453125,
      "answer_successes": 57,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:18:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": false,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.15234375,
      "joint_successes": 11,
      "mean_time": 1.3484639175551325,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.04233796418805266,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 254.89840980529897,
      "total_serving_seconds": 172.60338144705696
    },
    {
      "Q": 0.0859375,
      "R": 15.339442988086601,
      "action_rates": {
        "1": 0.0,
        "10": 0.2265625,
        "2": 0.7734375,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4453125,
      "answer_successes": 57,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:19:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": false,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.1015625,
      "joint_successes": 11,
      "mean_time": 1.3182333817886922,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.052658567823729366,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 241.57549814129897,
      "total_serving_seconds": 168.7338728689526
    },
    {
      "Q": 0.0859375,
      "R": 14.948107479986271,
      "action_rates": {
        "1": 0.0,
        "10": 0.203125,
        "2": 0.796875,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.453125,
      "answer_successes": 58,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:20:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": true,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.05078125,
      "joint_successes": 11,
      "mean_time": 1.2846029865613202,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.06876897153298181,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 230.41022196929896,
      "total_serving_seconds": 164.429182279849
    },
    {
      "Q": 0.078125,
      "R": 14.6725432484,
      "action_rates": {
        "1": 0.0,
        "10": 0.0,
        "2": 1.0,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4453125,
      "answer_successes": 57,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:21:numeric",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": false,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.0,
      "joint_successes": 10,
      "mean_time": 1.14629244128125,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": 0.8370998357503909,
      "threshold_mode": "numeric",
      "total_experiment_seconds": 153.84838988029898,
      "total_serving_seconds": 146.725432484
    },
    {
      "Q": 0.078125,
      "R": 14.671174412,
      "action_rates": {
        "1": 0.0,
        "10": 0.0,
        "2": 1.0,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0
      },
      "answer_em": 0.4453125,
      "answer_successes": 57,
      "assigned_tasks": 128,
      "bound_kind": "optimistic removal of all measured clean full-call prefill; no cache parity certificate",
      "config_id": "POST-OUTCOME:22:always_two",
      "cost_kind": "development_paid_action_reconstruction",
      "eligible": false,
      "executed": false,
      "family": "POST-OUTCOME",
      "fit_escalation_probability": 0.0,
      "joint_successes": 10,
      "mean_time": 1.1461855009375,
      "model_artifact_sha256": "ee020f278e43968331ca6f4ee9ab448be7dfdcebd844cf08c7b2dec79409b467",
      "model_name": "POST-OUTCOME",
      "reason": null,
      "selection_pool": false,
      "split": "tune",
      "threshold": null,
      "threshold_mode": "always_two",
      "total_experiment_seconds": 153.83470151629896,
      "total_serving_seconds": 146.71174412
    }
  ],
  "qualification": "Actual POST ran with cache mode none. Optimistic clean-prefill bounds are not executed optimized-comparator results.",
  "selected_logprob_gate_passed": false
}
```

## Attribution

```json
{
  "status": "Task18 actual execution held; no result invented"
}
```

## Transfer

```json
{
  "assigned_jobs": 96,
  "cost_qualification": "Separate prospective preparation; excluded from DEVELOPMENT-only subtotal.",
  "manifest_sha256": "c81c662a7540b4119d65989f8f31471bfd0924f8c38f8c50758767a46fdf7e74",
  "preparation_seconds_from_ledger": 22.858469042,
  "queries": 32,
  "source": "root ledger metadata only",
  "status": "prospectively sealed; actual execution held, no results asserted"
}
```

## Diagnostics

```json
{
  "original_quality": "unavailable; assignment incomplete and never subset-scored",
  "original_stop": {
    "active_timing_boundary_failure": "Verified host suspension excluded from perf clock; intended original wall-time efficiency claim withheld.",
    "actual_signal_utc": "2026-10-15T04:30:00.253260+00:00",
    "amendment_path": "docs/amendments/A04-earlier-operational-cutoff.json",
    "amendment_sha256": "35619ce1cd67508e437f6d42c2d6974b1bae8552bd421abd98ee789b0dc64111",
    "assigned_jobs": 8640,
    "assigned_unique_tasks": 480,
    "complete_question_blocks": 361,
    "completed_jobs": 6510,
    "cost_repair_or_zero_fill": false,
    "created_utc": "2026-10-15T04:31:22.422800+00:00",
    "evidence_sha256": {
      "attempts.jsonl": "014309fc95a90d51b0ee9bca12346daa34a54e3398cc67054d0c651bdc94275f",
      "execution-snapshot/snapshot.json": "72581ff1088d7912957e435f932ce7844bd3c2a4d22abcfcfb32a5f1560368e8",
      "index-realization.json": "78529de254b772de85dd06d35ded224a2e0d11fa35905741a4ab5f8410585d05",
      "launch-1.finished.json": "5639ccd0874884c6918ae097a8841bcaa847fe4b988b85369b092b3b9ae4df12",
      "launch-1.started.json": "8da0365f3681cf2f636166d25875c72675e086c226d68c59a4aa0bb4ecab6aa7",
      "native-1.failure.json": "119f0b2a2f7f719dec38d380ec596fae91a7b73ab50c3a3bf60e398e18ce2411",
      "operational-observations/a04-control-armed.json": "932a16202c145c7d497cb545c8b92637bf5d6185fbe3b2d14c8040831674546d",
      "operational-observations/a04-control-events.jsonl": "bcb7ba9cd7155e7050af6777559a8867f94133f3d7e48caf5942eb7e5fdd605a",
      "operational-observations/a04-stop-control.json": "3adc5c65bce994c65b460a5ff0f7e762f1e7e185033ade9cb4f5d899f3957ed9",
      "os-denials.json": "93179e5a6feb1749b0d568cce2ac35a34b79f0716418e621fc210077099620f8",
      "power.jsonl": "1ef61a38bd79a9bdb158f05e03e8c259904ae95b7475c1eeef1ff5ff8b382bcf",
      "progress.jsonl": "d047d3885d8f603a1ad573d8b38806c433166cedc7a71644d5a704e8a4a64e5f",
      "system-state.jsonl": "fc6e4e16f60490a082a22a58fd50e0c71212f8b14cf72cd239d6d9e68ae90bd5"
    },
    "historical_superseded_cutoff_utc": "2026-10-15T06:12:52+00:00",
    "native_complete_closure": false,
    "observed_original_launch_finished_mtime_utc": "2026-10-15T04:30:00.798081+00:00",
    "original_wall_time_claim_valid": false,
    "owned_native_processes_confirmed_exited": true,
    "paid_calls_finished": 6940,
    "paid_calls_started": 6940,
    "private_summary_path": "artifacts/runs/confirmation/operational-observations/a04-incomplete-summary.json",
    "private_summary_sha256": "97891b506e11f9a33659063493dae8963241054e5c247460e64f5771c5a65148",
    "protocol_hash": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100",
    "publication_note": "Original full assigned denominator remains480 questions/8640 jobs; completed subset is not a replacement sample. Unknown unclosed cost stays null.",
    "quality_outcomes_read": false,
    "reason": "A04 outcome-blind external earlier cutoff to preserve one fixed A03 comparison after known original host-suspension clock failure",
    "scientific_digests": {
      "methods": "6817223fe570e4472df38039e2d0d0624f8f2f9417d79b6ce547300e49af83ad",
      "sample": "fe89db6b1592fcf3ae9bf849187b6ea406b5fe4d20cc1b026b61aeca46be6009",
      "schedule": "7b5e3932a490d75733c8f7e8c085471ab8e229c71d944d3da0dd2761d8862208"
    },
    "scored": false,
    "started_attempts": 6511,
    "status": "incomplete",
    "unclosed_attempt_count": 1,
    "unclosed_attempt_serving_cost_seconds": null,
    "unfinished_paid_receipt_count": 0,
    "writer": "external reviewed A04 operational control; not native complete closure"
  }
}
```

## Amendments

```json
[
  {
    "amendment_hash": "76d7a9a42e8b3e58bcd4c27edfd087da436e5f53bdc663e6cdd9a00e5c168309",
    "amendment_id": "A01",
    "evidence_path": ".superpowers/sdd/2026-10-14-outcome-aware-context-allocation/asset-source-fallback.md",
    "kind": "asset_acquisition_source",
    "limitation": "Archive provenance/integrity is checkable, but byte equivalence to a separately fetched current author-origin file cannot presently be established.",
    "new": {
      "archive_capture": "20250512032701",
      "origins": [
        "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
        "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json"
      ],
      "population": "structurally valid representative HotpotQA distractor-development records in the pinned archived author-origin release",
      "replay_urls": [
        "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
        "https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json"
      ],
      "source_policy": "direct_author_or_pinned_raw_author_archive"
    },
    "previous": {
      "population": "structurally valid representative HotpotQA official distractor-development records",
      "source_policy": "direct_author_host_only"
    },
    "prior_data_or_protected_outcomes_collected": false,
    "rationale": "Direct author endpoints timed out over HTTP and HTTPS. Independently inspected archive metadata identifies unaltered raw responses of the exact author URLs; use a pinned author-origin capture to continue the same local experiment.",
    "requirements": [
      "no external HF loader execution or parquet reconstruction",
      "verify full raw response lengths, JSON and author-origin replay metadata",
      "compute SHA256 for both downloaded bodies",
      "check archive payload digest where available",
      "retain attribution and CC BY-SA 4.0",
      "disclose archive distribution and absent independent author cryptographic checksum"
    ],
    "results_invalidated": [],
    "timestamp_utc": "2026-10-14T12:42:24.090437+00:00",
    "unchanged": [
      "H1-H4",
      "HotpotQA native raw JSON schema and exact filenames",
      "reader/encoder identities",
      "two/ten candidate action space",
      "joint_EM primary success",
      "baseline roster and common tuning rule",
      "cost boundary",
      "split/sampling seeds",
      "protected evaluation separation"
    ]
  },
  {
    "amendment_hash": "a3aa7cf0b6c6230f6fd9ccdb27c7329d1ae83dbdc0194a323c6c4959f9b06a42",
    "amendment_id": "A02",
    "kind": "development_capacity_planning_correction",
    "new": {
      "confirmation_arms": 2,
      "confirmation_envelopes_tasks": [
        128,
        256,
        512,
        1024
      ],
      "confirmation_timing_repetitions": [
        1,
        3
      ],
      "extension_limit": 64,
      "known_stage_jobs": {
        "initial_fit_two_ten": 512,
        "tune_all_k": 1280,
        "tune_judge": 128
      },
      "min_discordant_tasks": 2,
      "min_oracle_successes": 4,
      "min_savings_envelope_seconds_per_task": 0.01,
      "planned_jobs": 1920,
      "protected_n_frozen": false,
      "reserved_reporting_seconds": 3600,
      "rule_frozen_before_generation": true,
      "setup_training_diagnostics_allowance_seconds": 1800
    },
    "previous": {
      "extension_limit": 64,
      "min_discordant_tasks": 2,
      "min_oracle_successes": 4,
      "min_savings_envelope_seconds_per_task": 0.01,
      "planned_jobs": 12000,
      "reserved_reporting_seconds": 3600,
      "rule_frozen_before_generation": true
    },
    "prior_development_generation_in_progress": true,
    "prior_pilot_scoring": false,
    "protected_generation": false,
    "rationale": "Replace unsupported12000-job protected envelope with known development work1920 jobs and separately disclosed confirmation envelopes. Task13 owns protected n/roster/repetitions from then-remaining measured capacity.",
    "results_invalidated": [],
    "timestamp_utc": "2026-10-14T17:12:27.885593+00:00",
    "unchanged": [
      "163-job pilot schedule",
      "reserved32 membership",
      "all-k hash selection",
      "reader/encoder",
      "prompt/decoding",
      "actions",
      "strict joint_EM",
      "oracle headroom",
      "development stability thresholds",
      "cost boundary"
    ]
  },
  {
    "amendment_id": "A03",
    "title": "One conditional clean timing replication after host suspension",
    "registered_utc": "2026-10-15T01:46:12+00:00",
    "parent_protocol_hash": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100",
    "registration_state": "Outcome-blind; original and replication quality outcomes remain unopened until replication closure or an explicit wholly-unexecuted decision.",
    "reason": "Repeated host suspension invalidated the original wall-time endpoint: approximately 300 UTC seconds elapsed while the performance clock advanced approximately 2.4 seconds. No original time is repaired or removed.",
    "original_wall_time_endpoint": "invalid",
    "original_data_preservation": "Retain every original manifest, raw attempt, output, assigned question, physical cost and timing observation unchanged. Task14 and Task15 retain their separate original identities.",
    "previous_settings": {
      "representatives": "All eleven frozen family representatives, in addition to the frozen anchor, random mixture, oracle source and four primary paired executions.",
      "jobs_per_question": 18,
      "assigned_jobs": 8640,
      "deadline_utc": "2026-10-15T12:12:52+00:00",
      "operational_realization_path": "Original run's existing index-realization.json; preserve unchanged."
    },
    "new_settings": {
      "representatives": [],
      "jobs_per_question": 7,
      "assigned_jobs": 3360,
      "direct_primary_jobs": 1920,
      "roster": "Selected A* and B*, two fresh direct/cache-none repetitions each, plus unchanged FIXED-10 anchor, random mixture and FIXED-2 oracle source through the original scheduler.",
      "deadline_utc": "2026-10-15T10:12:52+00:00",
      "operational_realization_path": "New run's own index-realization.json, binding its new scientific digests and the unchanged shared physical index."
    },
    "unchanged": {
      "sample": "Copy original sample.json bytes exactly; same 480 questions/order/tasks/document hash, population N=7344, algorithm and seed271828. No resampling or additional independent examples.",
      "hypothesis": "The frozen PRE-OUTCOME-GBM candidate A* improves complete warm pipeline time per successful answer while preserving the preregistered quality guards against selected B* and FIXED-10.",
      "comparison": "The original selected B* remains the primary comparator. No superiority-to-all-families claim; this reduced roster is a selected-comparison timing replication.",
      "settings": "All selected policy identities, local model manifests, reader/model/prompt/chat-template/decoding identities, token caps, timeout, encoder, retrieval algorithm, random probability, seeds, two paired timing repetitions and statistical rules remain exactly equal to the parent.",
      "inference": "Preserve all four quality guards, repeat-output parity, minimum-success rules, full assigned denominator, finite-population analysis, leave-one-out and documented stationarity/influence requirements. Repetitions and the same questions in another run are not independent new questions. No automatic validity=True."
    },
    "operational_gate": {
      "original_collector_cutoff_utc": "2026-10-15T06:12:52+00:00",
      "latest_launch_utc": "2026-10-15T08:12:52+00:00",
      "collection_deadline_utc": "2026-10-15T10:12:52+00:00",
      "original_project_deadline_utc": "2026-10-15T12:12:52+00:00",
      "launch": "Source review and manifest verification do not authorize launch. Root must separately record original closure/stop, no concurrent model/index workload, a measured prospective budget including setup/final in-flight job/closure, and established awake conditions. Measured feasibility must fit entirely before the collection deadline and preserve the report reserve; it can impose an earlier actual latest start than the declared 08:12:52 UTC ceiling. The inherited original forecast is provenance only; it does not certify the new schedule's feasibility.",
      "awake_evidence": "Root audits prospective and continuing UTC, sampler and OS sleep/wake evidence. A request to the user to keep the host awake is not evidence by itself. Unknown awake coverage cannot establish a clean wall-time endpoint. No power setting, privileged memory limit or thermal-protection bypass.",
      "no_fit_or_awake_evidence": "Wholly unexecuted; no smaller subset, changed sample, one-repeat fallback or extension.",
      "suspension_after_launch": "Any verified suspension invalidates the new wall-time endpoint. Retain all assigned questions and all physical costs. No selective removal, clock repair, favorable rerun, third attempt or significance-driven extension.",
      "maximum_conditional_replications": 1
    },
    "physical_costs": {
      "local_work": "Namespace new native launches, setup, worker reloads and jobs by (protocol_hash, resolved_run_dir, local_source_or_job_id), because confirmation run_id, job_id and task14-launch source strings can recur across roots.",
      "shared_index": "Preserve original index completion attempt and original owner protocol/root. Deduplicate that same physical index construction once across reports. A native seal's new_physical_source_id label alone does not imply a new index build. Charge each new run's actual index load/setup time separately.",
      "execution_identity": "Use new native environment, source snapshot, execution and launch receipts when actually created by the unchanged runtime. A prospective manifest is not a completed execution receipt."
    }
  },
  {
    "a03_protocol_hash": "ad632aa3f9a37765b62d237abb3782251bb54084e6bc6a8309399f873adfba07",
    "amendment_id": "A04",
    "forecast": {
      "active_budget_seconds": 15227.676546682502,
      "additional_last_inflight_seconds": 37.081555666,
      "latest_start_utc": "2026-10-15T05:58:27.241898+00:00",
      "path": "artifacts/runs/operational-planning/task17-runtime-forecast-20261015T040133Z.json",
      "qualification": "Conservative active-clock planning with 1.5 margin, measured setup allowance and assumed 600-second closure allowance; no future wall-time or stationarity guarantee.",
      "sha256": "e7c7fccc5cf12e26bb95a6ebc35de27168cc861b4b59afa8b9684433497835d1",
      "total_budget_seconds": 15264.758102348502
    },
    "new_settings": {
      "boundary": "Stop at the first safe available generation/question boundary; if the host is suspended record actual later control time. Preserve every attempt and the full assigned denominator.",
      "original_collector_cutoff_utc": "2026-10-15T04:30:00+00:00"
    },
    "parent_protocol_hash": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100",
    "previous_settings": {
      "original_collector_cutoff_utc": "2026-10-15T06:12:52+00:00"
    },
    "reason": "Recent measured selected-seven costs require about 4h14m, so A03 cannot fit before its unchanged10:12:52 collection deadline if the original waits until06:12:52. All source implementation/reviews and the802-test integration suite are now complete. Stop already wall-invalid original collection earlier to prioritise one complete fixed480-question A03 comparison, while retaining reporting reserve and all original work. This decision uses operational costs only.",
    "registered_utc": "2026-10-15T04:04:44.225709+00:00",
    "registration_state": "Outcome-blind; no original or A03 benchmark scores or Gold have been opened. Review and operator release remain separate.",
    "risk": "Forgoes the remaining chance of a complete original full-family quality table and may spend additional compute without a valid A03 result. Preserve original480/8640 as incomplete when applicable. Updated cost or awake evidence can still make A03 wholly unexecuted; no smaller sample or deadline extension is allowed.",
    "supersession": "Only the operational original_collector_cutoff_utc in the prior coordinator Ruling and registered A03 metadata is superseded by this external amendment. Those immutable files retain their original registration bytes; actual launch/stop receipts bind A04 and report the deviation explicitly. A03 scientific settings and identity are unchanged.",
    "title": "Advance the original collector cutoff to preserve the fixed A03 comparison",
    "unchanged": {
      "a03_assignment": "Same480questions/sample/order;3360jobs/1920primarydirect;two paired A/B repetitions; no new independent questions.",
      "a03_collection_deadline_utc": "2026-10-15T10:12:52+00:00",
      "a03_declared_latest_launch_utc": "2026-10-15T08:12:52+00:00",
      "data_preservation": "No original or A03 protocol/methods/sample/schedule/source is edited or rebound; original timings remain invalid and all paid attempts remain visible.",
      "launch_gate": "Original must first close or stop. Root separately verifies awake coverage, current measured full-run feasibility, no concurrent model/index workload, setup/final-request/closure and report reserve. No power changes or battery stop.",
      "measured_latest_start_is_stricter": true,
      "original_assignment": "480questions/8640jobs; incomplete stays incomplete and is not subset-scored.",
      "project_deadline_utc": "2026-10-15T12:12:52+00:00",
      "quality_hold": "All benchmark scoring/Gold remains held until A03 closes or is explicitly wholly unexecuted.",
      "science": "All hypotheses, selected A*/B*, anchor/random/oracle, reader/retriever/model/prompt/decoding/token/timeout settings, metrics, thresholds, statistical rules and source hashes stay unchanged. No retuning, sample extension, extra repetition or third timing attempt."
    }
  }
]
```

## Rulings

```json
{
  "distinct_count": 6,
  "exact_paragraphs": [
    "Ruling: Permit pinned, unaltered Internet Archive replay of the exact author HotpotQA JSON URLs under amendment A01 — direct author endpoints are inaccessible, archive provenance/length/license can be verified before any data collection — if wrong, source equivalence is weakened and the benchmark claim must be limited to the recorded archived snapshot or repeated with author-origin files. No hypothesis, metric, baseline, budget or protected-outcome setting changes.",
    "Ruling: Review Task14 frozen execution/scoring implementation after its source commit and development parity checks, before its first protected generation; then let the same implementer execute the reviewed source and let root audit closure/evidence without a second broad code review — fixing a discovered serving/scorer defect before protected access preserves the independent experiment — if wrong, the review lacks live-run evidence until the root operational audit/final whole-branch review; no protected findings may justify silent runtime changes. This stages the existing Task14 steps5/6 without changing methods, sample, schedule, statistics or source-binding rules.",
    "Ruling: Forecast the protected batch using the existing1.5 scheduling margin on the higher measured complete-roster mean (current calibration versus prior tuning reconstruction, both including FIXED2), multiplied by the larger measured native-envelope factor; retain observed maxima as tail/timeout evidence rather than treating every sampled query as the longest stratum — aggregate cost under uniform sampling is governed by the workload mean, and six downstream hours plus2h10fixed work are already reserved — if heterogeneous costs or timing drift exceed that allowance, the assigned run can overrun or remain incomplete; preserve all jobs and report incomplete/inconclusive rather than reducing n afterward. This is a pre-outcome runtime-planning choice, not a quality/precision criterion or change to scientific methods. Actual n remains computed once from freeze-time clock.",
    "Ruling: Stop the original protected collector at 2026-10-15T06:12:52UTC, at the first available safe generation/question boundary if the host is suspended, if it has not completed; preserve all480 assigned questions,8640 jobs and every attempt, and report an incomplete run rather than a smaller confirmation sample — repeated observed host suspensions invalidate the wall-time endpoint and make completion uncertain, while the authorized24h includes reproduction, reporting and review, so the final six hours must remain available — if wrong, this forgoes some potentially collectible quality evidence or a later full completion; no observed task outcome or significance informed the cutoff, and no battery stop or scientific-method/source change is authorized.",
    "Ruling: Preregister one separate clean timing replication on the exact same480-question sample, with unchanged selected A*/B*, reader, retriever, prompt, decoding, per-generation limits and statistical rules; use the unchanged scheduler with no family representatives, which necessarily retains FIXED10, random and FIXED2 plus two paired A/B repetitions (3360jobs). Preserve the original run and its invalid wall timings, allow it to finish or reach its existing06:12:52 cutoff, and open no quality outcomes until this replication closes or is explicitly unexecuted. Implement only a new manifest writer/config using frozen core APIs, with a fresh source review. Execute once only if awake conditions and report reserve make it feasible; no third timing attempt, sample enlargement or policy retuning — confirmed host suspension invalidated the original cost boundary before any protected quality peek, so an independently frozen same-sample measurement can test the intended endpoint without outcome-driven selection — if wrong, the replication wastes additional time or remains timing-invalid; its claim is limited to selected B* and quality anchor, all original artifacts remain visible, and no family-wide superiority or extra independent examples may be claimed. This requires explicit amendment A03/new protocol identity before execution, not a silent original-protocol repair.",
    "Ruling: Advance the original collector cutoff from06:12:52UTC to04:30:00UTC, at the first safe available generation/question boundary, preserving all480 assigned questions/8640jobs and every original attempt as incomplete if necessary; retain the one unchanged480-question/3360-job A03 comparison and its10:12:52 collection/12:12:52 project deadlines — the04:01 operational-only cost forecast now requires15227.676547s plus37.081556s final-inflight allowance, giving a latest feasible start about05:58:27UTC, so the former cutoff would make the intended replication infeasible; all source/reviews/802tests are complete and earlier stop preserves reporting capacity — if wrong, this forfeits a possible complete original full-family quality table and additional original compute, while A03 can still be invalid or unexecuted; no scored outcome, Gold, sample size, selected method, threshold, inference rule or scientific source changes. External amendmentA04 explicitly supersedes only the old operational cutoff; never rewrite A03/original registration bytes."
  ],
  "same_decision_summaries": [
    {
      "same_as_distinct_ruling": 3,
      "exact_paragraph": "Ruling Task13: total-batch forecast1.5×max(fresh27.6373,historical18-roster29.822mean)×highernative-envelopefactor; retain50.3149max as tail evidence, not every-querymean — root instruction beforefreeze — risk is unguaranteed tail/runtime allowance, with complete fixeddenominator and deadlines preserved. Stationarity remainsNone despite mostlycanceling common slowdown; actualrun validity assessment required."
    }
  ],
  "supersession": "Ruling6/A04 supersedes only Ruling4 operational cutoff from06:12:52 to04:30:00UTC. Immutable original/A03 registration bytes retain historical old cutoff.",
  "snapshot_utc": "2026-10-15T07:10:35.570943+00:00"
}
```

## Provenance

```json
{
  "protocol_verification": {
    "path": "artifacts/runs/task16-phase2b/protocol-verification.json",
    "sha256": "85df3dd7de4d281986706eedca2f60eb6a5a21d262cd8e7aaaadaaa1963c401f"
  },
  "original_stop": {
    "path": "artifacts/provenance/task14-original-incomplete.json",
    "sha256": "eff52ac360adac03b0fa9c1f083f44fb18ef6fad093be26c37c5595b17c56a37"
  },
  "development": {
    "development_parity": {
      "all_exact_scores_targets_selection_unchanged": true,
      "cache_disposition": "new source-bound equivalent score copies; original frozen score/cache records retained unchanged",
      "elapsed_seconds": 73.03529654099839,
      "fit_target_rows_unchanged": 256,
      "original_models_origins_selection_unchanged": true,
      "runs": [
        {
          "count": 163,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_unsealed",
          "new_scores_sha256": "48e19279f85ae6ed4ebd3dd7defb9eace93a8802c2e57a8d518c289b6ef53529",
          "old_scores_sha256": "48e19279f85ae6ed4ebd3dd7defb9eace93a8802c2e57a8d518c289b6ef53529",
          "prediction_closure_sha256": "93f2416086b8eb044f2d1f841d17ce3f297b38ae510a4d65a56f8eed2bf406b4",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task9-pilot32",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        },
        {
          "count": 163,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_unsealed",
          "new_scores_sha256": "9db903685c5f44d70549fa864196f1227fb02543e263423dbc46fc842e0d1eb0",
          "old_scores_sha256": "9db903685c5f44d70549fa864196f1227fb02543e263423dbc46fc842e0d1eb0",
          "prediction_closure_sha256": "4faec6c70f02e473db316bd4d80675c6b0a9d93ff55b30c5978177465dc09294",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task9-pilot64-extension",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        },
        {
          "count": 512,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_unsealed",
          "new_scores_sha256": "d074196c7b16e00c0417329541f686f7fee83e5f019b1edb992dd8ddc82c3bf5",
          "old_scores_sha256": "d074196c7b16e00c0417329541f686f7fee83e5f019b1edb992dd8ddc82c3bf5",
          "prediction_closure_sha256": "c3a162aabdbf8675a430fb084ca6b39bcd8ef0fa9bbf0cfff7c6226db56b7e84",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task10-fit256",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        },
        {
          "count": 12,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_unsealed",
          "new_scores_sha256": "4859b3f9db0d79f29cdb77e18f2d499c291948a8da01e038285f24e96ae8f849",
          "old_scores_sha256": "4859b3f9db0d79f29cdb77e18f2d499c291948a8da01e038285f24e96ae8f849",
          "prediction_closure_sha256": "f6d7dd759cbee147622b91eda76ac8456f0089a5cdd1ede0ffeb644acd3ac7b3",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task11-native",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        },
        {
          "count": 12,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_unsealed",
          "new_scores_sha256": "8028478a7569a27486f3bc5f4acaa8434364892924851ae4363854e48f2b548b",
          "old_scores_sha256": "8028478a7569a27486f3bc5f4acaa8434364892924851ae4363854e48f2b548b",
          "prediction_closure_sha256": "b6b3090e62697a4005fb10cf59f329671fcede0eacab87a04a934ece1cbf1ef9",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task11-native-repeat",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        },
        {
          "count": 1552,
          "exact_score_parity": true,
          "historical_receipt_coverage": "legacy_retrospective",
          "new_scores_sha256": "8e4612d3eb5e2082efb175dde39b84b28b5aab39955dab837b4c567e0f0078df",
          "old_scores_sha256": "8e4612d3eb5e2082efb175dde39b84b28b5aab39955dab837b4c567e0f0078df",
          "prediction_closure_sha256": "e7d6dd3967b3ae2e320253c2f294e5e468e6e3cd2aa4e00607716e170b14398c",
          "qualification": "mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten",
          "run_dir": "artifacts/runs/task12-tune128-retry",
          "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f"
        }
      ],
      "scorer_source_sha256": "912eb951565aeb6e71d8b215eedfa5b108c1a4332b5020460d80a6bb8ed6469f",
      "selected": {
        "A*": {
          "Q": 0.078125,
          "R": 19.1111308497,
          "answer_em": 0.453125,
          "config_id": "PRE-OUTCOME-GBM:17:numeric",
          "eligible": true,
          "family": "PRE-OUTCOME-GBM",
          "mean_time": 1.4930570976328126,
          "threshold": 0.0339522174316994,
          "threshold_mode": "numeric"
        },
        "B*": {
          "Q": 0.0859375,
          "R": 14.66098451109091,
          "answer_em": 0.46875,
          "config_id": "PROXY-LABEL:14:numeric",
          "eligible": true,
          "family": "PROXY-LABEL",
          "mean_time": 1.259928356421875,
          "threshold": 0.801315057689046,
          "threshold_mode": "numeric"
        }
      },
      "source_commit": "5181e5326eb7cc3f22c9ac52bfaacc56cf1b047b",
      "tuning_configuration_count": 246
    },
    "development_score_receipt": {
      "gold_projection_sha256": "637f8eb1e6864d10c54553e7fbcf17c776717ab16a8e67a4bd603c3e803fd2ee",
      "kind": "separate_closed_run_scorer",
      "paid_receipt_coverage": "legacy_retrospective",
      "prediction_closure_sha256": "e7d6dd3967b3ae2e320253c2f294e5e468e6e3cd2aa4e00607716e170b14398c",
      "prediction_sha256": "65525e3b4719b31f1eb9f477db99ad76f068d7acdb2a7feb4e9a33f32ebb7672",
      "record_count": 1552,
      "scorer_source_sha256": "bf090b997fc8a23904d8cfe6d4a12c03c9d7218759a311f26fae6b756275d603",
      "scores_sha256": "8e4612d3eb5e2082efb175dde39b84b28b5aab39955dab837b4c567e0f0078df",
      "scoring_seconds": 14.661938917008229,
      "timing_kind": "complete_ledger"
    },
    "execution_window": {
      "deadline_utc": "2026-10-15T12:12:52+00:00",
      "includes": [
        "implementation",
        "setup",
        "evaluation",
        "reporting"
      ],
      "start_reason": "first execution turn after user authorized implementation",
      "started_utc": "2026-10-14T12:12:52+00:00",
      "window_seconds": 86400
    },
    "process_archive_manifest": "artifacts/provenance/process-archive/2026-10-14/20261015T015117851969Z/process-manifest.json",
    "source_manifest": "artifacts/provenance/task16-development/20261015T015117851969Z/source-manifest.json",
    "initial_phase2a_input": {
      "path": "artifacts/provenance/task16-development/20261015T015117851969Z/report-inputs.json",
      "sha256": "e63596f8a54fdea17213948017dd9c26703c366dd0d298b73cd181a5b39f658e"
    },
    "A04": {
      "path": "docs/amendments/A04-earlier-operational-cutoff.json",
      "sha256": "35619ce1cd67508e437f6d42c2d6974b1bae8552bd421abd98ee789b0dc64111"
    },
    "initial_cost_inventory": {
      "path": "artifacts/provenance/task16-final/initial-physical-costs.json",
      "sha256": "9d01d3c5e4bc9da6c79060601d1b1474b6f086b9fbc5cce5046df3130ada7757"
    }
  }
}
```

## Reproduction

```json
{
  "receipt": {
    "assigned_jobs": 8640,
    "assigned_questions": 480,
    "gold_opened": false,
    "protocol_hash": "415c80344dc3609ee2600a20c63c2502e4fc100cf50c60daee73ebc8a721e100",
    "reason": "incomplete_run",
    "status": "unavailable"
  },
  "path": "artifacts/runs/task16-reproduce/original/receipt.json",
  "sha256": "ac0fbfe6edc98eb997e6b8096b2354ec72cd8f62aa35da6e0aa584179edeb7bb"
}
```

## Timing validation

```json
{
  "status": "invalid",
  "fresh_process_full_measurement_executed": true,
  "extra_fresh_small_block": "unexecuted; not automatically authorized",
  "evidence": {
    "path": "artifacts/provenance/task14-original-incomplete.json",
    "sha256": "eff52ac360adac03b0fa9c1f083f44fb18ef6fad093be26c37c5595b17c56a37"
  },
  "interpretation": "Fresh native process does not override proven clock failure; scoring reproduction is not timing validation."
}
```

## Regressions

```json
{
  "failure_clear": null,
  "latency_clear": null,
  "reason": "Descriptive status counts retained; no new statistical rule or valid wall-latency assessment invented."
}
```

## Remaining risks

```json
[
  "Both original and A03 wall-time endpoints are known invalid because performance clock excluded host suspension; active means/ratios are descriptive only.",
  "Original6510/8640 completion is not a smaller confirmation sample: all480assigned retained, no original subset scores or family table.",
  "A03 successes14/17 fall below frozen minimum30, so primary approximate CI is unavailable independently of clock invalidity.",
  "All four exact quality-guard intervals cross0; quality preservation and supported quality loss are not established.",
  "Stationarity and influence remainNone; no new thresholds or selective clock repair.",
  "Later user awake promise cannot repair earlier clock failure; transient pytest-argv candidates have unknown command origin/ownership/intensity.",
  "Unknown historical/outer costs and per-method adaptation stay null; global full project cost unavailable.",
  "Actual Task18/transfer/blind-review and final synthesis/archive refresh remain pending root terminal handoffs.",
  "Legacy v1 development paid-receipt sealing is retrospective, not historical completion-time attestation.",
  "Archived dataset source qualification, pretrained contamination, citation annotation limits, packet retrieval and single hardware remain."
]
```

Annotation agreement is not certified truth. Citation limitations, public pretraining contamination, packet-only retrieval and this hardware constrain interpretation. Unexecuted transfer does not establish generalization.

inconclusive

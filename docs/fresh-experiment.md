# Configure a separate fresh experiment

This is a **nonexecuting configuration guide**, not a launcher or authorization for another experiment. The examples have not been run. Supplied `configs/*.json` files are historical execution records. Preserve them and every retained protocol, index, attempt ledger and source seal.

Before relying on native reuse lineage in a new experiment, correct **both** `protected.py` and `transfer_runtime.py` in separately versioned source: they read top-level `reuse_sources`, while the real index producer writes `offline.reuse_sources`. The current native ancestry inventories are incomplete. A future correction needs fail-closed validation, recursive original physical identities and synthetic integration checks using real-producer manifests. Do not patch or rebind the completed experiment. Its external reconciliation qualifies the retained result; it is not a general native fix.

## Use a fresh checkout as the outer isolation boundary

Use a separate checkout with no copied historical `artifacts/`, `data/` or mutable index ledgers. Install using the [README setup commands](../README.md#native-setup-for-a-fresh-checkout). Within that checkout choose an unused root, here `experiments/example-001`, and make separately named editable copies of the base, development, calibration and freeze configs. For example, copy `configs/base.json` to `experiments/example-001/configs/base.json` and edit the copy; repeat for the other three configs. Do not execute any stage until the full configuration and new protocol have been reviewed.

A fresh checkout matters even after configuring output roots: pilot/collection and tuning read the **literal checkout-relative** `artifacts/provenance/execution-window.json`; tuning also writes some checkout-relative prelaunch provenance. The index CLI initially has a checkout-relative default ledger before loading its configuration. Config changes alone do not make those paths safe in the retained checkout.

## Base/preparation configuration fragment

This valid JSON is a **partial replacement fragment** to merge into the copied `base.json`; it is not a standalone config. Keep reviewed model revisions, data-source policy and other required fields from the copied config. The fresh checkout's `models/pinned` is a new writable cache, not the historical directory.

```json
{
  "output_dir": "experiments/example-001/provenance",
  "cache_dir": "models/pinned",
  "preparation": {
    "train_path": "models/pinned/data/hotpot_train_v1.1.json",
    "dev_path": "models/pinned/data/hotpot_dev_distractor_v1.json",
    "output_dir": "experiments/example-001/data/prepared",
    "asset_manifest": "experiments/example-001/provenance/asset-manifest.json"
  },
  "retrieval": {
    "output_dir": "experiments/example-001/data/index",
    "reuse_indexes": [],
    "reuse_indexes_by_split": {"fit": [], "tune": []}
  }
}
```

Preparation produces `tasks.jsonl`, `documents.jsonl`, `manifest.json` and `gold/gold.jsonl` beneath its new output root. Keep raw data, prepared Gold and score projections private; do not copy historical annotated outputs into a new run. Raw-source paths above also match current native denial probes. If changing those conventions or sharing asset paths, separately verify that the native OS denial profiles cover the actual new raw/Gold locations before execution.

Immutable pretrained model snapshots may be referenced read-only through newly verified asset-manifest `local_path` entries. Do not run acquisition against a shared historical cache, copy its mutable acquisition receipts as new work, or reuse mutable historical index ledgers. Leave reuse lists empty in this example; later within-experiment reuse requires the native lineage correction and its checks first.

## Move these development paths together

Apply the same base `output_dir`, `preparation` and `retrieval` settings to the copied development configuration. Its actual consumer fields are:

| Field | Example value inside the new checkout |
| --- | --- |
| `inputs.prepared_dir` | `experiments/example-001/data/prepared` |
| `inputs.asset_manifest` | `experiments/example-001/provenance/asset-manifest.json` |
| `inputs.index_dir` | `experiments/example-001/data/index/pilot` |
| `inputs.fit_index_dir` | `experiments/example-001/data/index/fit` |
| `pilot.run_dir` | `experiments/example-001/runs/pilot` |
| `collection.run_dir` | `experiments/example-001/runs/fit` |
| `collection.offline_attempts_paths` | `[]` initially; later only this experiment's actual index-attempt ledgers |
| `training.output_dir` | `experiments/example-001/runs/fit/training` |
| `training.gold_path` | `experiments/example-001/runs/fit/scores.gold.jsonl` after the new fit collection closes and is scored |
| `tuning.run_dir` | `experiments/example-001/runs/tune` |
| `tuning.prelaunch_dir` | `experiments/example-001/runs/tune-prelaunch` |
| `tuning.post_training_dir` | `experiments/example-001/runs/post-training` |
| `tuning.index_dir` | `experiments/example-001/data/index/tune` |
| `retrieval.reuse_indexes`, `retrieval.reuse_indexes_by_split` | Empty as above; never point at historical mutable ledgers |

Isolate **both** index outputs and ledger parents. The `index --config ... --split pilot|fit|tune` CLI writes configured `<retrieval.output_dir>/<split>` and `<output_dir>/index-attempts.jsonl`. Lower-level `build_index(output_dir=...)` writes `<output_dir.parent>/index-attempts.jsonl`. A new child under the historical `data/index/` parent can therefore mutate an old binding. The new protected index must have its own fresh parent as well, for example `experiments/example-001/data/protected-index/attempt-1`.

The copied calibration config must likewise move `inputs.prepared_dir`, `inputs.index_dir`, `inputs.fit_index_dir`, `inputs.asset_manifest`, `selection_path`, `training_dir`, `post_training_dir`, `index_dir`, `prelaunch_dir` and `run_dir` to this experiment's real new development outputs. Do not reuse old selection, capacity, fit-origin or scoring receipts as if produced by this experiment.

## New execution window and freeze inputs

Record a newly agreed start/deadline in the fresh checkout's `artifacts/provenance/execution-window.json`; there is no generic CLI `--deadline` flag. This example is syntax only: replace its illustrative dates with the actual authorized window, keeping all consumers consistent.

```json
{
  "started_utc": "2030-01-01T00:00:00+00:00",
  "deadline_utc": "2030-01-02T00:00:00+00:00",
  "window_seconds": 86400,
  "start_reason": "Illustrative only; replace with the new authorization record",
  "includes": ["implementation", "setup", "evaluation", "reporting"]
}
```

The copied freeze config uses these actual keys (paths are illustrative, required input files must be produced and checked first):

```json
{
  "selection_path": "experiments/example-001/provenance/task12-selection.json",
  "capacity_path": "experiments/example-001/runs/calibration/capacity.json",
  "development_path": "experiments/example-001/freeze-inputs/development.json",
  "artifact_manifest_path": "experiments/example-001/freeze-inputs/artifact-bindings.json",
  "artifact_files": ["experiments/example-001/freeze-inputs/development.json"],
  "prepared_dir": "experiments/example-001/data/prepared",
  "output_dir": "experiments/example-001/protocol",
  "run_dir": "experiments/example-001/runs/confirmation",
  "deadline_utc": "2030-01-02T00:00:00+00:00",
  "source_files": ["experiments/example-001/configs/frozen.json"],
  "fixture": false
}
```

This too is a partial fragment: set `n` through the new preregistration and measured feasibility check, not by inheriting 480 automatically. The `development_path` document supplies frozen `retrieval.prepared_dir`, `retrieval.index_dir`, `retrieval.reuse_indexes`, model paths and asset settings; those must agree with the new roots. Regenerate `artifact_manifest_path` hashes from actual new files, including any mutable attempt ledgers, before binding. `output_dir` receives new `methods.json`, `sample.json`, `schedule.json` and `protocol.json`; `run_dir` receives the new confirmation ledgers and score projections. Do not hand-edit these generated files after freezing.

## Optional diagnostic roots and preflight

The separate transfer tool's actual options are `--stage seal --primary-protocol PATH --root PATH`, then later stages use `--manifest PATH` (authorization uses `--forecast-seconds`). Choose a distinct root such as `experiments/example-001/runs/pooled-transfer`, outside the primary run. The generated manifest carries its own `root` and primary-derived `prepared_dir`, `deadline_utc` and `reuse_indexes`; its index attempts and parent ledger remain under that transfer root. Do not copy the retained transfer manifest or merely replace its paths. Its native fixed32/population assumptions also require review for a new protocol.

The action-replay tool takes `--protocol`, `--output` and `--release`; use new durable output/release locations such as `experiments/example-001/analysis/action-replay.json` and `experiments/example-001/releases/action-replay.json`, outside run/protocol roots. The current adapter specifically validates A03's parent/replication contract; it is not a generic fresh-experiment analysis launcher. Use it only if a separately reviewed new design satisfies its actual contract.

Before execution, check resolved paths against the retained checkout: no writable output or attempt-ledger parent may overlap it. Verify raw/Gold denial, source and asset hashes, available resources, the newly recorded deadline and reporting reserve, new selection/capacity inputs, and native lineage prerequisites. Standard stage syntax uses `python -m outcome_poc <stage> --config PATH`; `index` and `collect` also require `--split`, while `run` and protected `score` use `--protocol`. This guide executes none of them and makes no fresh-run readiness claim.

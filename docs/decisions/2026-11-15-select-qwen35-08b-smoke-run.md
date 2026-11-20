# Select a Smoke-Run Backbone and Remote Workflow

- **Status:** Accepted for the smoke experiment only
- **Date:** 2026-11-15
- **Scope:** First pretrained baseline and training-mechanics smoke run; not the final model selection.

## Decision

Use `unsloth/Qwen3.5-0.8B` for the first Unsloth decision-model smoke run. Pin repository revision `23c69c53358a07516b5827588b3fdb12ae78fd65` and license `Apache-2.0`. The model card identifies the 0.8B checkpoint and Apache-2.0 license. Unsloth's decision-model guide documents the Qwen3.5 family, 4-bit LoRA training, and a newly initialized decision head.

Use the already reviewed, training-only eight-row export at `data/training/exports/initial-training.jsonl`. This is a mechanics sample, not the complete training set and not a quality evaluation set. Do not mix in validation, calibration, or final-test rows. In particular, never use final-test labels in training, prompt development, threshold selection, or checkpoint selection.

Use the official Unsloth Colab decision-model notebook; use Kaggle as the fallback if a suitable Colab session cannot continue. A Colab NVIDIA Tesla T4 with 14.563 GiB VRAM is now provisioned. The installation cell completed with Python 3.13, PyTorch 2.8.0+cu128, CUDA Toolkit 12.8, Triton 3.4.0, Transformers 5.2.0, xFormers 0.0.32.post2, and Unsloth 2026.11.4. This macOS workspace still has neither PyTorch nor Unsloth installed, so it cannot execute the code-based smoke run locally.

The notebook's default `unsloth/Qwen3.5-4B` loaded without a pinned revision; the log reported 723/723 weights and 13 files loaded, with 10.07 GiB free of 14.563 GiB on the T4. One training-row inference returned valid original options with that 4B model. These observations do not verify the selected 0.8B revision or its memory usage. For the 4B load, Unsloth reported float32 fallback on the T4; a Torchaudio backend-dispatch deprecation warning also appeared and was non-fatal.

On 2026-11-18, the user ran the 0.8B load cell with the configured revision; it completed with 473/473 weights and 13 files fetched. Colab reported Unsloth 2026.11.6 and 13.08 GiB free of 14.56 GiB on the T4 after loading, with the same float32 fallback warning. The requested revision was passed to the loader; the encoder's commit metadata was checked later.

One training-row inference with the 0.8B model returned all six question IDs and valid original option keys. This verifies option compatibility for that row, not accuracy or full-dataset compatibility. The user also confirmed the eight uploaded rows' loaded questions matched the JSONL and its hash matched the pinned export.

Unsloth dataset preparation produced eight items from the eight training rows, reporting 48 decisions, zero skipped, and zero truncated. This is a preparation check, not a training or quality result.

LoRA setup completed with 37,147,588 trainable parameters, including 372 LoRA tensors; the listed trainable parameters also include the decision head. The T4 reported 13.04 GiB free of 14.56 GiB after setup.

On 2026-11-19, the three-step training run completed without a reported out-of-memory error. The trainer reported 137.2567 seconds, an epoch fraction of 0.375, and mean training loss of 1.0472546219825745; these are mechanics observations, not quality metrics. The trainer reported gradient offloading and double buffering.

The user saved a checkpoint to Google Drive and reported adapter, joint-head, tokenizer, and configuration files. The reported location and file hashes are recorded in the smoke configuration. Both the decision and adapter configuration identify the requested 0.8B repository and revision, and the loaded encoder's commit metadata reports the same revision.

The checkpoint reloaded on the T4 with Unsloth 2026.11.7, reporting the requested encoder commit and the same float32 fallback. Its head tensors and all 372 adapter tensors matched their saved files, and inference on one training row returned all six valid original option keys. This verifies the save/reload mechanics, not model quality.

The model repository's [license file at the pinned revision](https://huggingface.co/unsloth/Qwen3.5-0.8B/blob/23c69c53358a07516b5827588b3fdb12ae78fd65/LICENSE) was checked and contains the Apache License, Version 2.0.

## Smoke Configuration

The detailed settings are in [`configs/experiments/open-weight-smoke.yaml`](../../configs/experiments/open-weight-smoke.yaml). The run uses 4-bit loading, LoRA rank 16, learning rate `2e-4`, the Unsloth decision head, a fixed seed, and a three-step cap. These values follow Unsloth's current starter guidance where applicable; the short run is intended only to exercise loading, an update, checkpoint save/reload, and option-compatible inference.

A newly initialized decision head on the pretrained backbone is a sanity baseline only. Any measured score on eight training rows is not evidence of model quality and must not be reported as held-out performance.

## Preconditions and Acceptance

- Verify the pinned model revision resolves and the Apache-2.0 license file is present.
- Run a pretrained inference check on a training row and verify the runtime can run the configured 4-bit decision-head update without out-of-memory errors.
- Record training output, save the adapter/head, reload it, and obtain valid choices from a training example using the same options.
- Keep checkpoints, credentials, raw provider outputs, and run-local secrets out of Git. Record artifact location and hashes in experiment metadata.
- Do not use any final-test row or label during this smoke run.

The mechanics smoke run is complete: the 0.8B load, memory check, one-row option-compatibility check, dataset preparation, LoRA setup, three training steps, checkpoint save/reload, saved-weight comparisons, and post-reload option check completed with the configured revision reported by the encoder. The pinned model's license file was verified. Runtime-dependent settings may change only through a recorded experiment revision before touching the final test set.

## References

- [Unsloth decision-model guide](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Qwen3.5-0.8B model card](https://huggingface.co/unsloth/Qwen3.5-0.8B)
- [Open-weight smoke configuration](../../configs/experiments/open-weight-smoke.yaml)
- [Training plan](../training/plan.md)

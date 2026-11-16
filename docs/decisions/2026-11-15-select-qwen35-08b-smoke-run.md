# Select a Smoke-Run Backbone and Remote Workflow

- **Status:** Accepted for the smoke experiment only
- **Date:** 2026-11-15
- **Scope:** First pretrained baseline and training-mechanics smoke run; not the final model selection.

## Decision

Use `unsloth/Qwen3.5-0.8B` for the first Unsloth decision-model smoke run. Pin repository revision `23c69c53358a07516b5827588b3fdb12ae78fd65` and license `Apache-2.0`. The model card identifies the 0.8B checkpoint and Apache-2.0 license. Unsloth's decision-model guide documents the Qwen3.5 family, 4-bit LoRA training, and a newly initialized decision head.

Use the already reviewed, training-only eight-row export at `data/training/exports/initial-training.jsonl`. This is a mechanics sample, not the complete training set and not a quality evaluation set. Do not mix in validation, calibration, or final-test rows. In particular, never use final-test labels in training, prompt development, threshold selection, or checkpoint selection.

Use the official Unsloth Colab decision-model notebook; use Kaggle as the fallback if a suitable Colab session cannot continue. A Colab NVIDIA Tesla T4 with 14.563 GiB VRAM is now provisioned. The installation cell completed with Python 3.13, PyTorch 2.8.0+cu128, CUDA Toolkit 12.8, Triton 3.4.0, Transformers 5.2.0, xFormers 0.0.32.post2, and Unsloth 2026.11.4. This macOS workspace still has neither PyTorch nor Unsloth installed, so it cannot execute the code-based smoke run locally.

The Hugging Face model-setup cell has completed: the log reports 723/723 weights loaded and 13 model files fetched. After loading, Colab reported 10.07 GiB free of 14.563 GiB on the T4. Unsloth reported that fp16 is unsupported for Qwen3.5 on this runtime and selected float32 because bfloat16 is unavailable. This is enough headroom to attempt the planned inference and short smoke, but check for memory errors during both. A Torchaudio backend-dispatch deprecation warning also appeared during patching; it was non-fatal.

## Smoke Configuration

The detailed settings are in [`configs/experiments/open-weight-smoke.yaml`](../../configs/experiments/open-weight-smoke.yaml). The run uses 4-bit loading, LoRA rank 16, learning rate `2e-4`, the Unsloth decision head, a fixed seed, and a three-step cap. These values follow Unsloth's current starter guidance where applicable; the short run is intended only to exercise loading, an update, checkpoint save/reload, and option-compatible inference.

A newly initialized decision head on the pretrained backbone is a sanity baseline only. Any measured score on eight training rows is not evidence of model quality and must not be reported as held-out performance.

## Preconditions and Acceptance

- Verify the pinned model revision resolves and the Apache-2.0 license file is present.
- Run a pretrained inference check on a training row and verify the runtime can run the configured 4-bit decision-head update without out-of-memory errors.
- Record training output, save the adapter/head, reload it, and obtain valid choices from a training example using the same options.
- Keep checkpoints, credentials, raw provider outputs, and run-local secrets out of Git. Record artifact location and hashes in experiment metadata.
- Do not use any final-test row or label during this smoke run.

Model loading and the post-load memory check are complete. Pretrained inference, smoke training, save/reload, and post-reload inference are still pending. Runtime-dependent settings may change only through a recorded experiment revision before touching the final test set.

## References

- [Unsloth decision-model guide](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Qwen3.5-0.8B model card](https://huggingface.co/unsloth/Qwen3.5-0.8B)
- [Open-weight smoke configuration](../../configs/experiments/open-weight-smoke.yaml)
- [Training plan](../training/plan.md)

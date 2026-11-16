# Select a Smoke-Run Backbone and Remote Workflow

- **Status:** Accepted for the smoke experiment only
- **Date:** 2026-11-15
- **Scope:** First pretrained baseline and training-mechanics smoke run; not the final model selection.

## Decision

Use `unsloth/Qwen3.5-0.8B` for the first Unsloth decision-model smoke run. Pin repository revision `23c69c53358a07516b5827588b3fdb12ae78fd65` and license `Apache-2.0`. The model card identifies the 0.8B checkpoint and Apache-2.0 license. Unsloth's decision-model guide documents the Qwen3.5 family, 4-bit LoRA training, and a newly initialized decision head.

Use the already reviewed, training-only eight-row export at `data/training/exports/initial-training.jsonl`. This is a mechanics sample, not the complete training set and not a quality evaluation set. Do not mix in validation, calibration, or final-test rows. In particular, never use final-test labels in training, prompt development, threshold selection, or checkpoint selection.

Prepare execution for the official Unsloth Colab decision-model notebook; use Kaggle as the fallback if the Colab runtime cannot provide a suitable GPU. The user's account/runtime availability cannot be verified from this repository. Before starting, record the actual provider, GPU, VRAM, runtime image, Python version, and installed Unsloth/Transformers versions. This macOS workspace currently has neither PyTorch nor Unsloth installed, so it cannot execute the code-based smoke run locally.

## Smoke Configuration

The detailed settings are in [`configs/experiments/open-weight-smoke.yaml`](../../configs/experiments/open-weight-smoke.yaml). The run uses 4-bit loading, LoRA rank 16, learning rate `2e-4`, the Unsloth decision head, a fixed seed, and a three-step cap. These values follow Unsloth's current starter guidance where applicable; the short run is intended only to exercise loading, an update, checkpoint save/reload, and option-compatible inference.

A newly initialized decision head on the pretrained backbone is a sanity baseline only. Any measured score on eight training rows is not evidence of model quality and must not be reported as held-out performance.

## Preconditions and Acceptance

- Verify the pinned model revision resolves and the Apache-2.0 license file is present.
- Confirm the remote runtime can load the model and run the configured 4-bit decision-head update without out-of-memory errors.
- Record training output, save the adapter/head, reload it, and obtain valid choices from a training example using the same options.
- Keep checkpoints, credentials, raw provider outputs, and run-local secrets out of Git. Record artifact location and hashes in experiment metadata.
- Do not use any final-test row or label during this smoke run.

The smoke run has not yet been executed. Runtime-dependent settings may change only through a recorded experiment revision before touching the final test set.

## References

- [Unsloth decision-model guide](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Qwen3.5-0.8B model card](https://huggingface.co/unsloth/Qwen3.5-0.8B)
- [Open-weight smoke configuration](../../configs/experiments/open-weight-smoke.yaml)
- [Training plan](../training/plan.md)

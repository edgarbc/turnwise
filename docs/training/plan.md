# Open-Weight Decision Model Training Plan

## Purpose

Test whether a small open-weight decision model, fine-tuned for Turnwise's household repair-intake task, can approach the performance of Jev and a general LLM with schema-constrained output. This is an experiment, not an assumption that any one system will perform best. Conclusions will be limited to the task, data, and evaluation conditions described here.

The transcript-based experiment comes first. Audio transcription is a later stage and must be evaluated separately so ASR errors are not confused with decision errors.

## Research Questions

1. How does Jev compare with a general LLM on the six-field task?
2. Can an open-weight decision model be trained to make the same bounded decisions and approach those references?
3. Which changes to data, training, calibration, or model size improve local performance, and at what cost?
4. How do correctness, valid decisions, uncertainty handling, latency, operating cost, and local execution compare?

The completed 30-conversation Jev/OpenAI pilot is exploratory development evidence, not a held-out final evaluation. Both reference systems remain in the local-model comparison.

## Scope and Constraints

- **Task:** existing six-field household repair intake, defined in [`configs/tasks/repair-intake.yaml`](../../configs/tasks/repair-intake.yaml).
- **Initial model input:** transcript prefixes and shared candidate extraction; live audio is out of scope for this stage.
- **New data budget:** 50 synthetic conversations initially. Expand toward 100 only to address a documented data gap.
- **Existing pilot:** keep the original 30 conversations as a separate regression set, not as training data or a substitute for the new final test set.
- **Training environment:** begin by verifying the current Unsloth Colab workflow and available GPU/session limits. Kaggle or Modal are fallbacks if needed; verify current availability before committing to a platform.
- **Project tooling:** retain `uv` and Typer. Keep GPU-specific training dependencies separate from the core package and evaluation environment.
- **Generated artifacts:** do not commit credentials, private data, raw runs, or large checkpoints by default. Store provenance, hashes, model identity, and configuration in tracked metadata.

## Decision-Input and Label Contract

The exporter must represent the decisions the inference model actually receives, reusing Turnwise's transcript-prefix, candidate, evidence, and annotation rules.

- Candidate-backed fields target the selected candidate ID.
- Boolean fields target the available value-and-evidence option, such as `true::event-id` or `false::event-id`.
- Unsupported or unstated values target `__unknown__`.
- If a known expressed value is absent from the candidates, flag candidate-extraction failure. Do not convert it into an unknown training target.
- Preserve the exact option keys available for each example and require every gold target to be one of those keys.
- Share question construction between Jev inference and training export so the same task questions and criteria are used in both.
- Never include gold answers or events beyond the prefix cutoff in model input.

The Unsloth decision-model row format is `state`, `questions`, and `gold`. The Turnwise exporter should map to that format deterministically and retain enough metadata to trace each row back to its conversation and prefix without exposing evaluation labels to inference.

## Scenario, Split, and Review Plan

Create a versioned scenario catalogue before generating wording variations. Each scenario specifies intended facts and when they become available. Cover ordinary requests, missing information, explicit negatives, negation, corrections, conflicts, distractors, and useful combinations. Generator-produced answers are not ground truth: validate transcripts against scenario specifications, then annotate evidence and expected state at selected prefixes using Turnwise's rules.

The following allocation is the **initial proposal**. Confirm family assignments and split policy before generation; keep related scenarios, paraphrases, and every prefix from one conversation in one split.

| Split | Conversations | Use |
| --- | ---: | --- |
| Training | 30 | Fine-tuning |
| Validation | 5 | Diagnose errors and select settings/checkpoints |
| Calibration | 5 | Exploratory confidence and abstention calibration |
| Final test | 10 | Frozen evaluation after configuration selection |
| **Total** | **50** | |

These small partitions support workflow exploration, not precise population estimates. Report conversation-level counts and uncertainty; prefixes from one conversation are correlated and must not be counted as independent conversations.

Record review level and provenance for scenarios, conversations, annotations, and splits. Fully review the first 10 training/validation examples to refine the process, then generate the remaining data after split assignment. Apply automated schema, evidence-span, candidate-coverage, and consistency checks. Human-review a diverse sample and every flagged or ambiguous example. Fully review and lock every final-test conversation and annotation before evaluation; keep test labels unavailable during training and checkpoint selection.

## Work Sequence and Exit Criteria

### 1. Freeze task, labels, and split rules

Confirm the task and annotation rules, scenario metadata, review provenance, split membership policy, manifest changes, and validation requirements. Assign scenario families to splits before generating language variations.

**Exit:** versioned scenario and generation specification; documented split policy; validator requirements agreed.

### 2. Prove the data contract on a small reviewed batch

Generate and fully review an initial batch from development splits. Validate transcript facts, prefix labels, evidence spans, candidate coverage, and unknown handling. Record concrete defects and update the specification before generating the rest.

**Exit:** reviewed examples pass offline validation and demonstrate the required target shapes.

### 3. Complete and lock the 50-conversation corpus

Generate remaining examples after split assignment. Run automated checks and targeted review. Fully review the final test set and freeze its source hashes before any training or tuning.

**Exit:** split manifest, reviewed annotations, data-quality report, and frozen test hashes.

### 4. Extract shared questions and implement the exporter

Move Jev's task question and option construction into a reusable component. Export transcript-prefix inputs, exact options, and gold targets to Unsloth's `state`, `questions`, and `gold` format. Reject invalid targets, missing evidence, candidate extraction gaps, and split leakage. Provide a deterministic, inspectable sample.

**Exit:** unit tests cover option parity with Jev, target validity, evidence and candidate failures, and deterministic export.

### 5. Establish the pretrained baseline and smoke train

Select a small Unsloth-supported open-weight model only after checking model/license terms, GPU compatibility, decision-head support, and local inference/reload path. Measure a pretrained baseline where meaningful; document a newly initialized head as a sanity baseline, not a strong pretrained decision model. Run a short smoke experiment to verify loading, training, checkpoint save/reload, and Turnwise inference integration.

**Exit:** reproducible smoke configuration, logs, checkpoint reference, and inference check.

### 6. Train and compare

Evaluate the same frozen examples and task contract using Jev, the structured-output LLM, and the open-weight model before and after fine-tuning where applicable. Never provide gold labels to providers. Use the existing evaluation pipeline where possible.

Report field-level and conversation-level correctness, invalid or unsupported decisions, unknown/abstention behavior, evidence validity, latency, cost or compute, reviewed-conversation counts, and uncertainty. Separate candidate-extraction recall from candidate selection accuracy.

**Exit:** reproducible comparison report and error analysis, including remaining gaps to both references.

### 7. Improve only from diagnosed errors

Use training diagnostics and validation errors to propose targeted experiments. Change one main factor at a time. Preserve the frozen final test. Document a specific data gap before expanding beyond 50 conversations. Candidate interventions include scenario coverage, training settings, confidence calibration, or a larger backbone.

**Exit:** reproducible experiment sequence showing each change and its measured effect.

### 8. Integrate and communicate

Integrate the best validation-selected local checkpoint into Turnwise. Document comparison limits, model identity, dataset hashes, configuration, software versions, and compute. Add local audio transcription only after the transcript-based experiment is complete, and evaluate ASR separately.

**Exit:** reproducible demo, checkpoint notes or model card, evaluation report, and publishable evidence.

## Documentation and Sources of Truth

- This document is the living roadmap for the training stage.
- [`data-and-review.md`](data-and-review.md) defines the proposed training-row, split, provenance, and review contract; open decisions there must be resolved before corpus generation.
- [`../annotation-guide.md`](../annotation-guide.md) remains authoritative for annotation semantics.
- Task definitions and experiment settings belong in versioned files under `configs/`.
- Dataset membership, approval, provenance, and source hashes belong in a manifest under `data/manifests/`.
- Durable choices and rationale belong in [`../decisions/`](../decisions/); record choices there when they are made rather than treating proposals here as settled.
- Selected aggregate outcomes belong in `reports/`; generated predictions and large checkpoints remain excluded from ordinary Git history.

## References

- [Unsloth: Train your own Decision Model](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Turnwise evaluation protocol](../evaluation-protocol.md)
- [Turnwise project plan](../project-plan.md)

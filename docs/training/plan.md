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

The versioned development catalogue contains 40 reviewed non-test scenarios, with intended facts and their availability by turn. A separate final-test catalogue contains ten held-out scenarios across two families. All 50 conversations and their annotations are approved; the manifests and catalogues pin source hashes. The development dataset validates with 40 conversations and 49 snapshots, and the test dataset validates separately with 10 conversations and 27 snapshots. Generator-produced answers are not ground truth: transcripts were checked against scenario specifications, then annotated from customer evidence at selected prefixes. The final-test set is locked and excluded from development and model selection.

The working allocation is 30/5/5/10 conversations. Family assignments and split policy are recorded in the scenario catalogue; keep related scenarios, paraphrases, and every prefix from one conversation in one split.

| Split | Conversations | Use |
| --- | ---: | --- |
| Training | 30 | Fine-tuning |
| Validation | 5 | Diagnose errors and select settings/checkpoints |
| Calibration | 5 | Exploratory confidence and abstention calibration |
| Final test | 10 | Frozen evaluation after configuration selection |
| **Total** | **50** | |

These small partitions support workflow exploration, not precise population estimates. Report conversation-level counts and uncertainty; prefixes from one conversation are correlated and must not be counted as independent conversations.

Record review level and provenance for scenarios, conversations, annotations, and splits. The initial 10 development examples (six training, two validation, and two calibration) were fully reviewed first; the remaining development examples and the 10 final-test examples were then generated and reviewed in separate batches. All 50 examples are approved and their manifests record hashes and outcomes. Keep final-test labels unavailable during model, threshold, and checkpoint selection.

## Work Sequence and Exit Criteria

### 1. Freeze task, labels, and split rules

The initial task and label contract, 30/5/5/10 working split, family assignments, and all 40 development scenario specifications have been reviewed. The canonical task, scenario catalogue, review contract, and approved batch manifest record those decisions. The accepted workflow-freeze decision allows final-test specifications and labels to be prepared in a separate manifest, but not used in development, prompt or threshold selection, or checkpoint selection.

**Exit:** complete for the task, label, split, and 40 development-scenario specifications. Final-test cases are handled separately after the workflow freeze, and their labels remain unavailable to development and model selection.

### 2. Prove the data contract on a small reviewed batch

The first 10 development conversations (six training, two validation, and two calibration) and all 13 prefix annotations have been reviewed and approved. Their hashes and outcomes are recorded in `data/manifests/training-initial-drafts.json`. The exporter has been exercised against this batch, including checks for candidate coverage, exact options, evidence, and unknown handling.

**Exit:** complete for the initial development batch. Use any defects discovered while expanding the corpus to update the generation specification before further generation.

### 3. Complete and lock the 50-conversation corpus

The 50-conversation corpus is generated, annotated, and approved: 30 training, five validation, five calibration, and ten final-test conversations. `uv run turnwise validate --dataset data/training` passes with 40 conversations and 49 snapshots; `uv run turnwise validate --dataset data/test` passes with ten conversations and 27 snapshots. The final-test catalogue and manifest are locked as documented in [`../decisions/2026-11-15-freeze-training-data-workflow.md`](../decisions/2026-11-15-freeze-training-data-workflow.md). The corpus and hash audits are recorded in [`../../reports/final-test-data-quality-20261115.md`](../../reports/final-test-data-quality-20261115.md).

**Exit:** complete. All 50 approved conversations, split assignments, quality checks, and source hashes are recorded; final-test labels remain excluded from development and model selection.

### 4. Extract shared questions and implement the exporter

Move Jev's task question and option construction into a reusable component. Export transcript-prefix inputs, exact options, and gold targets to Unsloth's `state`, `questions`, and `gold` format. Reject invalid targets, missing evidence, candidate extraction gaps, and split leakage. Provide a deterministic, inspectable sample.

**Exit:** complete for the initial reviewed batch. Unit tests cover option parity with Jev, target validity, scenario-to-annotation agreement, evidence and candidate failures, and deterministic export. See [`export-format.md`](export-format.md) and the inspectable sample under `data/training/exports/`.

### 5. Establish the pretrained baseline and smoke train

The smoke-run candidate was `unsloth/Qwen3.5-0.8B` at pinned revision `23c69c53358a07516b5827588b3fdb12ae78fd65` (Apache-2.0), with a newly initialized decision head. The three-step, training-only smoke run completed on Colab's Tesla T4, including checkpoint save/reload, saved-weight checks, and option-compatible inference on one training row. The configuration, recorded observations, and checkpoint reference are in [`configs/experiments/open-weight-smoke.yaml`](../../configs/experiments/open-weight-smoke.yaml); the model choice and limits are in [`../decisions/2026-11-15-select-qwen35-08b-smoke-run.md`](../decisions/2026-11-15-select-qwen35-08b-smoke-run.md). The smoke run and newly initialized head do not establish model quality.

**Exit:** complete for the recorded smoke configuration, observations, checkpoint reference, and inference check. The full development exports are structurally audited in [`../../reports/development-export-audit-20261119.md`](../../reports/development-export-audit-20261119.md); review that audit before selecting a fresh training run.

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
- [`../decisions/2026-11-15-freeze-training-data-workflow.md`](../decisions/2026-11-15-freeze-training-data-workflow.md) records the accepted data and evaluation workflow freeze and its boundaries.
- [`approach.md`](approach.md) summarizes the research design and current corpus status for orientation.
- [`data-and-review.md`](data-and-review.md) defines the training-row, split, provenance, and review contract. All 50 conversations are approved; the final-test set is locked and kept out of development.
- [`generation-and-review.md`](generation-and-review.md) defines transcript generation and human review requirements for scenario-derived data.
- [`export-format.md`](export-format.md) documents the Unsloth row format, provenance sidecar, and export command.
- [`../annotation-guide.md`](../annotation-guide.md) remains authoritative for annotation semantics.
- Task definitions and experiment settings belong in versioned files under `configs/`.
- Dataset membership, approval, provenance, and source hashes belong in a manifest under `data/manifests/`.
- Durable choices and rationale belong in [`../decisions/`](../decisions/); record choices there when they are made rather than treating proposals here as settled.
- Selected aggregate outcomes belong in `reports/`; generated predictions and large checkpoints remain excluded from ordinary Git history.

## References

- [Unsloth: Train your own Decision Model](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Turnwise evaluation protocol](../evaluation-protocol.md)
- [Turnwise project plan](../project-plan.md)

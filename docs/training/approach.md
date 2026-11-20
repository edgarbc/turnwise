# Open-Weight Training Approach

**Status as of 2026-11-19:** all 50 conversations are reviewed and approved. The 40 development conversations are available for development; the 10 final-test cases are locked and excluded from model selection.

## Research Question

Turnwise is testing whether a small open-weight decision model can make bounded repair-intake decisions from transcript prefixes, and how it compares with Jev and a schema-constrained general LLM. This experiment evaluates a six-field task, not arbitrary conversation understanding. Audio transcription is out of scope until the transcript-based comparison is complete.

## Dataset Design

The initial budget is 50 new synthetic conversations. Scenario families are assigned to splits before dialogue generation so close variants and all prefixes from a conversation stay together.

| Split | Conversations | Status |
| --- | ---: | --- |
| Training | 30 | Reviewed and approved |
| Validation | 5 | Reviewed and approved |
| Calibration | 5 | Reviewed and approved |
| Final test | 10 | Reviewed and locked; excluded from development |

The 40 available development conversations pass the dataset validator: 40 conversations and 49 annotated snapshots. The original 30-conversation Jev/OpenAI pilot remains a separate regression set; it is not part of this allocation and is not training data.

## Generation and Annotation

Each conversation is derived from a confirmed scenario specification that defines the intended facts and when they become available. The specification guides coverage, but it does not replace transcript evidence: annotations are grounded only in customer statements visible at each prefix. Corrections produce new snapshots while earlier prefixes retain the earlier state. Unstated, ambiguous, or unresolved facts remain unknown rather than being inferred.

Candidate-backed values use Turnwise's shared lexical candidate extractor. Distractor candidates are retained as options, and candidate-mapping checks ensure the selected gold value is supported by the right source evidence. Human review checks transcripts and annotations separately; approvals, source hashes, and review outcomes are recorded in batch manifests.

## Model Input and Export

One model row represents one annotated transcript prefix. The Unsloth decision format contains `state`, `questions`, and `gold`: visible transcript and candidates, the six task questions with their exact available options, and a reviewed option key for each field. Candidate-backed labels select candidate IDs; boolean labels select a value with supporting customer-event evidence; unknown labels select `__unknown__`. Provenance stays in the export sidecar, not in model input.

Question construction is shared with the Jev path, and the exporter rejects invalid gold options, unsupported evidence, candidate gaps, source-hash changes, and split leakage. The complete contract and command are documented in the [data and review contract](data-and-review.md) and [export format](export-format.md).

## Leakage and Review Controls

All prefixes from a conversation and all related examples in a scenario family remain in one split. Test specifications and labels are not used to generate or review development data, and test labels must not influence model, threshold, or checkpoint selection. The final test set is created and locked only after the data-generation and evaluation workflow is frozen.

Automation checks structure, evidence spans, candidates, scenario consistency, and hashes; it does not establish semantic correctness. Human approval remains required. The small synthetic partitions support workflow exploration, not precise population estimates.

## Current State and Next Step

All 50 conversations are approved and locked: 30 training, five validation, five calibration, and ten final test. The development set validates at 40 conversations/49 snapshots; the isolated test set validates at 10 conversations/27 snapshots. The freeze decisions are recorded in [`../decisions/2026-11-15-freeze-training-data-workflow.md`](../decisions/2026-11-15-freeze-training-data-workflow.md) and [`../decisions/2026-11-15-select-qwen35-08b-smoke-run.md`](../decisions/2026-11-15-select-qwen35-08b-smoke-run.md). The Qwen3.5-0.8B three-step smoke completed, including checkpoint save/reload, weight checks, and one-row option compatibility; it provides no quality result. The full development splits are exported and structurally audited as described in the [export audit](../../reports/development-export-audit-20261119.md). The locked test labels remain outside development and model selection.

## Sources of Truth

- [Training plan](plan.md): milestones, prerequisites, and exit criteria.
- [Data and review contract](data-and-review.md): row labels, split policy, provenance, and acceptance checks.
- [Generation and review](generation-and-review.md): scenario-derived transcript workflow and human review.
- [Export format](export-format.md): deterministic Unsloth rows and provenance sidecar.
- [Annotation guide](../annotation-guide.md): authoritative field semantics and evidence rules.
- [Evaluation protocol](../evaluation-protocol.md): comparison design and metrics.
- [Scenario catalogue](../../data/scenarios/catalog.yaml): development families, assignments, and withheld-test reservations.

# Open-Weight Training Approach

**Status as of 2026-11-23:** the 40 development conversations are reviewed and approved. The original ten-case final-test set was exposed in public PR #5 and is no longer a blind test; it must not be used for final performance claims. See the [exposure decision](../decisions/2026-11-23-final-test-exposure.md).

## Research Question

Turnwise is testing whether a small open-weight decision model can make bounded repair-intake decisions from transcript prefixes, and how it compares with Jev and a schema-constrained general LLM. This experiment evaluates a six-field task, not arbitrary conversation understanding. Audio transcription is out of scope until the transcript-based comparison is complete.

## Dataset Design

The active experiment allocation is 50 synthetic conversations. Replacing the publicly exposed ten-case test requires a new private test set; retain the old set only as a separate regression set. Scenario families are assigned to splits before dialogue generation so close variants and all prefixes from a conversation stay together.

| Split | Conversations | Status |
| --- | ---: | --- |
| Training | 30 | Reviewed and approved |
| Validation | 5 | Reviewed and approved |
| Calibration | 5 | Reviewed and approved |
| Replacement test | 10 (planned) | Create privately after configuration freeze |
| **Active experiment total** | **50** | |

The ten-case original test is outside this active allocation and is only a known public regression set.

The 40 available development conversations pass the dataset validator: 40 conversations and 49 annotated snapshots. The original 30-conversation Jev/OpenAI pilot remains a separate regression set; it is not part of this allocation and is not training data.

## Generation and Annotation

Each conversation is derived from a confirmed scenario specification that defines the intended facts and when they become available. The specification guides coverage, but it does not replace transcript evidence: annotations are grounded only in customer statements visible at each prefix. Corrections produce new snapshots while earlier prefixes retain the earlier state. Unstated, ambiguous, or unresolved facts remain unknown rather than being inferred.

Candidate-backed values use Turnwise's shared lexical candidate extractor. Distractor candidates are retained as options, and candidate-mapping checks ensure the selected gold value is supported by the right source evidence. Human review checks transcripts and annotations separately; approvals, source hashes, and review outcomes are recorded in batch manifests.

## Model Input and Export

One model row represents one annotated transcript prefix. The Unsloth decision format contains `state`, `questions`, and `gold`: visible transcript and candidates, the six task questions with their exact available options, and a reviewed option key for each field. Candidate-backed labels select candidate IDs; boolean labels select a value with supporting customer-event evidence; unknown labels select `__unknown__`. Provenance stays in the export sidecar, not in model input.

Question construction is shared with the Jev path, and the exporter rejects invalid gold options, unsupported evidence, candidate gaps, source-hash changes, and split leakage. The complete contract and command are documented in the [data and review contract](data-and-review.md) and [export format](export-format.md).

## Leakage and Review Controls

All prefixes from a conversation and all related examples in a scenario family remain in one split. The original test set was published before configuration freeze and is compromised. Create a replacement privately after the workflow and configuration are frozen; do not use the exposed labels for model, threshold, checkpoint, or calibration decisions.

Automation checks structure, evidence spans, candidates, scenario consistency, and hashes; it does not establish semantic correctness. Human approval remains required. The small synthetic partitions support workflow exploration, not precise population estimates.

## Current State and Next Step

The 40 development conversations validate at 40 conversations/49 snapshots. The original ten-case test was structurally reviewed but is no longer a blind test because its labels were published; a fresh replacement remains pending. The freeze decisions are recorded in [`../decisions/2026-11-15-freeze-training-data-workflow.md`](../decisions/2026-11-15-freeze-training-data-workflow.md), [`../decisions/2026-11-15-select-qwen35-08b-smoke-run.md`](../decisions/2026-11-15-select-qwen35-08b-smoke-run.md), and [`../decisions/2026-11-23-final-test-exposure.md`](../decisions/2026-11-23-final-test-exposure.md). The Qwen3.5-0.8B three-step smoke completed but provides no quality result. Development exports are audited in the [export report](../../reports/development-export-audit-20261119.md).

## Sources of Truth

- [Training plan](plan.md): milestones, prerequisites, and exit criteria.
- [Data and review contract](data-and-review.md): row labels, split policy, provenance, and acceptance checks.
- [Generation and review](generation-and-review.md): scenario-derived transcript workflow and human review.
- [Export format](export-format.md): deterministic Unsloth rows and provenance sidecar.
- [Annotation guide](../annotation-guide.md): authoritative field semantics and evidence rules.
- [Evaluation protocol](../evaluation-protocol.md): comparison design and metrics.
- [Scenario catalogue](../../data/scenarios/catalog.yaml): development families, assignments, and withheld-test reservations.

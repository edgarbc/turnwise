# Training Conversation Generation and Review

This procedure applies to draft conversation data generated from [`data/scenarios/catalog.yaml`](../../data/scenarios/catalog.yaml). Scenario specifications define intended facts; generated dialogue and generator-suggested labels are never ground truth. Human reviewers determine whether each transcript supports its specification and create or approve prefix annotations.

## Generation Rules

1. Generate only scenarios with `specification_status: confirmed` and only for the assigned non-test split. Do not generate, inspect, or infer final-test scenario answers during development.
2. Keep the specified turn order, speaker, intended facts, unknown fields, and prefix cutoffs. Natural wording may vary, but do not add facts that change any field's state.
3. Use customer statements as the only evidence for values. Agent questions may request information but must not answer the questions. A customer's refusal or deferral must not imply a value.
4. Make temporal language unambiguous. Corrections change the value from their turn onward. For unresolved conflicts, do not add a correction marker, clarification, or later statement that resolves the conflict before the annotated cutoff.
5. For candidate-backed known values, phrase the source so the current shared candidate extractor produces a candidate for the intended value. Use detectable appliance terms, `in`/`at` place phrases, supported weekday/time patterns, and supported currency/amount patterns. Explicitly establish spending-limit semantics; a detected money candidate alone does not establish a spending limit.
6. Preserve distractor mentions required by a scenario. Make their role clear from context while ensuring they remain detectable candidates. The intended answer must be supported by its own source span, not merely by matching normalized text.
7. Keep the conversation natural and concise. Avoid repetitive template phrasing across scenarios. Do not add technical metadata, labels, or explanations to transcript text.
8. Use a unique conversation ID and event IDs derived from the scenario ID. Events are ordered, non-overlapping, and use the repository's event schema. One event corresponds to each specified turn in this initial batch.

## Validation Before Annotation

For every draft conversation:

- Confirm the event count, speaker, order, and IDs correspond to the scenario's turns.
- Assemble each specified prefix and verify that no later event is visible.
- Extract candidates with Turnwise's shared extractor. Confirm every known candidate-backed fact has a candidate with matching field, source text, and intended evidence; confirm distractors are present but not labeled as answers.
- Compare the transcript with every field in `available_facts`. Known values must be explicit and supported; null values must remain unstated, ambiguous, or conflicting as specified.
- Check that no agent statement supplies customer evidence and no unintended statement changes a label.
- Record validation results, source hashes, and any defects in the dataset manifest. Reject and regenerate a transcript when a required candidate is missing or the intended state is not unambiguous.

Structural validation is not semantic approval. After transcript validation, a human reviewer must inspect the full conversation and each selected prefix, then create or review annotations with precise customer evidence spans. Do not mark an annotation approved merely because it matches the scenario specification; resolve any transcript/spec mismatch first.

## Review Status

Track scenario-specification confirmation separately from generated-data review. Generated conversation drafts begin `unreviewed`; annotations do not exist until human review. Record targeted or full review, reviewer, date, outcome, and hashes in the batch manifest. Only mark a batch approved after all required transcript, label, and evidence checks have passed.

## Initial Batch Scope

The first development batch contains the ten confirmed non-test scenario specifications: six training, two validation, and two calibration conversations. They are intended to exercise the generation and annotation workflow, not to provide a statistically meaningful evaluation. The original 30-conversation pilot remains a separate regression set.
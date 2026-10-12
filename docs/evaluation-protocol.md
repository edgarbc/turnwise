# Evaluation Protocol

This protocol describes the planned comparison. Freeze the task, model versions, prompts, dataset, and measurement rules before the final evaluation. No benchmark results are available yet.

## Systems

The final comparison includes:

- A general LLM with schema-constrained output.
- Jev without task-specific fine-tuning.
- The local model before task-specific fine-tuning.
- The same local model after fine-tuning.

Record whether the initial local checkpoint is an existing decision model or a backbone with a newly initialized decision head. A random head is a sanity baseline only.

Use the same task semantics, transcript prefixes, and candidate values where applicable. Preserve each provider's native metadata and limitations. Do not treat agreement with Jev as correctness, or self-reported LLM confidence as calibrated probability.

## Data splits and leakage controls

- Use human-reviewed labels as ground truth.
- Keep source conversations, paraphrases, audio variants, and all prefixes from the same source in one split.
- Maintain distinct training, validation, calibration, and final-test partitions.
- Report held-out scenario families and unfamiliar phrasing.
- Never provide gold answers or future transcript turns as model input.
- Evaluate candidate extraction recall separately from candidate selection accuracy.
- Freeze final configurations before opening the final test set.

Evaluate clean transcripts, ASR transcripts of the same recordings, and the complete audio pipeline separately.

## Measures

| Dimension | Measures |
| --- | --- |
| Correctness | Per-field macro-F1, exact-value accuracy, and evidence validity |
| Output validity | Schema errors, invalid labels, missing fields, refusals, and failures |
| Streaming | Correction accuracy, unjustified changes, and stale-response commits |
| Responsiveness | p50/p95 latency, cold start, and end-to-end audio delay |
| Uncertainty | Error versus accepted coverage; calibration where probability outputs support it |
| Resources | Memory, total conversation cost, training effort, and annotation effort |

Include failures and retries in the report. Cached replay is not a latency measurement. Report per-field results and uncertainty intervals.

## Provisional local-model goals

The initial targets are macro-F1 within two percentage points of Jev and coverage within five points at the same accepted-error limit. Confirm these margins before local tuning; they are planning targets, not achieved results.

## Reporting

Publish selected reports only. Include model and dataset versions, configuration, environment, measurement policy, and any exclusions or retries so comparisons can be reproduced. Preserve an untouched final test set for the frozen comparison.
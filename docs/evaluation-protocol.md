# Evaluation Protocol

This protocol describes the comparison safeguards. Freeze the task, model versions, prompts, dataset, and measurement rules before each evaluation. An exploratory Jev/OpenAI pilot has been run on 30 synthetic conversations and 35 annotated prefixes; its aggregate results are summarized in [`reports/jev-vs-llm-pilot-20261014.json`](../reports/jev-vs-llm-pilot-20261014.json). This pilot is development evidence, not a final or held-out benchmark.

## Systems

The current hosted comparison includes:

- Jev without task-specific fine-tuning.
- OpenAI GPT-6.1 Sol with strict schema-constrained output.

The next modeling comparison will add an open-weight classifier measured both before and after task-specific training. Record the model/license, checkpoint revision, classifier head initialization, training data, hyperparameters, and compute. A smaller hosted LLM baseline is optional future work, not a prerequisite for classifier training.

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
| Resources | Input/output tokens, estimated API cost, memory, training effort, and annotation effort |

The pilot report estimates cost from actual SDK usage and the standard-tier, short-context per-million-token rates pinned in the experiment config. It accounts for cached input and cache writes when the OpenAI API reports those counts. It is an estimate, not a billing statement: retries are recorded in aggregate usage when available, and taxes, discounts, and non-standard service tiers are excluded.

Include failures and retries in the report. Cached replay is not a latency measurement. Report per-field results and uncertainty intervals.

The current evaluation runner scores each annotated prefix independently. Its evidence-validity measure checks that returned spans point to customer text inside the visible prefix; the pilot additionally records whether the evidence event matches the human annotation. Neither measure alone establishes semantic entailment. The 30-conversation pilot is larger than the initial workflow smoke test but remains synthetic, single-run development evidence; it does not support general performance claims or robust uncertainty intervals.

## Provisional local-model goals

The initial targets are macro-F1 within two percentage points of Jev and coverage within five points at the same accepted-error limit. Confirm these margins before local tuning; they are planning targets, not achieved results.

## Reporting

Publish selected reports only. Include model and dataset versions, configuration, environment, measurement policy, and any exclusions or retries so comparisons can be reproduced. Commit aggregate summaries rather than per-example predictions or gold labels. Preserve an untouched final test set for the frozen comparison.
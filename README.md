# Turnwise

*From conversation to structured decisions.*

Learning when to use decision models, then training a small local model for structured extraction from conversations.

**Status:** Planning. This README describes the intended repository and implementation milestones. Source modules, commands and benchmark results are not implemented yet.

## Research questions

1. When does a general decision model such as Jev offer an advantage over a general LLM with schema-constrained structured output?
2. Once the concept works, can a small local decision model approach Jev's task performance through fine-tuning?
3. Which improvements in data, training and calibration close the gap, and at what cost?

We investigate specialization twice: choosing a decision-oriented model, then training a local specialist for a defined task. Matching Jev on this task would not establish equivalent performance on arbitrary new tasks.

## Use case

A household repair intake conversation becomes a structured form that updates as new information arrives.

> “The washing machine is leaking in the laundry room. I turned it off, so it has stopped. Friday morning works … actually, Saturday afternoon. Please give me a quote before doing any work.”

| Field | Expected value |
| --- | --- |
| Appliance | Washing machine |
| Location | Laundry room |
| Active leak | Explicitly absent now |
| Preferred appointment | Saturday afternoon |
| Quote required | Yes |
| Spending limit | Unknown |

Initial scope: synthetic English conversations, one appliance per conversation, two known speaker roles and approximately two to five minutes of audio. The application drafts information for review; it does not book services or authorize spending.

## Why compare decision models with LLMs?

A general LLM can produce labels through structured output. Valid structure alone does not establish correct classification.

The experiment compares bounded decisions with schema-constrained generation using the same labels, transcript prefixes and candidate values. We measure correctness, output validity, latency, cost and uncertainty handling rather than assume either approach is better.

Exact dates and amounts require a shared candidate-extraction step. The model selects a candidate; code copies its source span and normalizes the value. Candidate recall and selection accuracy are evaluated separately.

## Experiment sequence

| Stage | Work | Exit condition |
| --- | --- | --- |
| 1. Define the task | Six fields, explicit unknown states and annotated transcript prefixes | Reviewed examples and annotation rules |
| 2. Prove and compare | Jev and a general LLM, followed by incremental replay and a small audio demo | Measured feasibility and evidence of where decision models help |
| 3. Freeze references | Pin task, prompts, models, dataset and evaluation protocol | Reproducible comparison |
| 4. Train locally | Train a small decision model with the Unsloth workflow | Saved checkpoint integrated into the same application |
| 5. Improve | Analyze validation errors, improve data and training, calibrate | Documented learning curves and performance gaps |
| 6. Evaluate | Compare frozen models on untouched data and demonstrate local audio processing | Final report and reproducible demo |

Training begins after the Jev concept is proved. Both reference models remain in the final comparison. If Jev does not outperform the general LLM, that is a result to report; local specialization can still be investigated.

## Development tooling

Application name: **Turnwise**. Repository, Python package and CLI command: `turnwise`.

- **uv** manages the Python environment, dependencies, lockfile and project command execution. Commit `pyproject.toml` and `uv.lock`; exclude the local `.venv/` directory from Git.
- **Typer** implements the `turnwise` CLI in `src/turnwise/cli.py`, with `validate`, `replay`, `benchmark` and `report` subcommands.
- Keep CLI handlers thin: parse arguments and invoke pipeline or evaluation functions. Model calls, data processing and metrics belong in their respective modules.
- Keep GPU training dependencies separate from the core CLI and evaluation environment.

These tooling choices are decided; package configuration and CLI implementation are part of the first milestone.

## Repository structure

The following paths are planned. Add modules as their milestones begin.

| Path | Purpose |
| --- | --- |
| `README.md` | Project goals, structure and workflow |
| `pyproject.toml`, `uv.lock` | uv project configuration, dependencies, CLI entry point and lockfile |
| `.env.example`, `.gitignore` | Credential placeholders and generated-file exclusions |
| `docs/project-plan.md` | Detailed roadmap |
| `docs/annotation-guide.md` | Field definitions, corrections, unknowns and evidence rules |
| `docs/evaluation-protocol.md` | Splits, metrics, latency measurement and comparison rules |
| `docs/decisions/` | Architecture and experiment decisions |
| `configs/tasks/repair-intake.yaml` | Canonical questions, labels and criteria |
| `configs/experiments/jev-vs-llm.yaml` | Initial comparison configuration |
| `configs/experiments/local-vs-references.yaml` | Later local-model comparison |
| `data/examples/conversations/` | Small synthetic transcript fixtures |
| `data/examples/annotations/` | Gold snapshots, stored separately from model inputs |
| `data/manifests/` | Dataset provenance, hashes and split membership |
| `src/turnwise/__init__.py` | Package entry |
| `src/turnwise/contracts.py` | Shared typed inputs and outputs |
| `src/turnwise/cli.py` | Typer application exposing validation, replay, benchmark and report commands |
| `src/turnwise/providers/base.py` | Provider interface |
| `src/turnwise/providers/fixture.py` | Scripted responses for offline pipeline checks |
| `src/turnwise/providers/jev.py` | Hosted decision-model adapter |
| `src/turnwise/providers/structured_llm.py` | General LLM with structured output |
| `src/turnwise/providers/local.py` | Local decision-model adapter, added after concept proof |
| `src/turnwise/pipeline/` | Prefix assembly, candidate extraction, normalization and form updates |
| `src/turnwise/evaluation/` | Metrics, run manifests, comparisons and error analysis |
| `src/turnwise/audio/` | ASR adapter and timestamped transcript events |
| `src/turnwise/training/` | Dataset conversion, fine-tuning, calibration and checkpoint loading |
| `src/turnwise/app/` | Later FastAPI service and minimal form interface |
| `tests/unit/` | State handling, metric and data-isolation checks |
| `tests/integration/` | Explicit opt-in provider smoke tests |
| `reports/` | Selected shareable results and error analyses |
| `runs/` | Generated predictions, logs and manifests; ignored by Git |
| `checkpoints/` | Local trained models; ignored by Git |

Keep the initial implementation in one Python package. Separate GPU training dependencies from the ordinary evaluation environment.

## Shared pipeline

Start with text fixtures, then feed speech recognition events into the same pipeline:

1. Assemble the transcript available at the current turn.
2. Find candidate values and preserve source offsets.
3. Evaluate the configured fields through the selected provider.
4. Validate and normalize the response.
5. Update the form with evidence and revision history.
6. Record outputs and measurements for evaluation.

The provider boundary is conceptually `decide(input) -> result`. Providers share task semantics while retaining their native metadata and limitations.

| Contract | Contents |
| --- | --- |
| `TranscriptEvent` | Conversation/event IDs, speaker, text, timestamps, revision and finalization status |
| `DecisionInput` | Available transcript prefix, task version, date/timezone and candidates |
| `DecisionResult` | Values, optional probabilities, evidence references, provider details, timing, usage and failures |
| `FormSnapshot` | Current values, acceptance status and superseded revisions |
| `GoldSnapshot` | Human-reviewed expected answers for a specific prefix |
| `RunManifest` | Dataset and code versions, configuration, environment and measurement policy |

Gold answers and future transcript turns must never enter provider inputs. Missing probability information remains null. A fixture provider verifies application behavior; it is not evidence of model quality.

## Evaluation

The final comparison includes:

- A general LLM with schema-constrained output.
- Jev without task-specific fine-tuning.
- The local model before task-specific fine-tuning.
- The same local model after fine-tuning.

Record whether the initial local checkpoint is an existing decision model or a backbone with a newly initialized decision head. A random head is only a sanity baseline.

| Dimension | Measures |
| --- | --- |
| Correctness | Per-field macro-F1, exact-value accuracy and evidence validity |
| Output validity | Schema errors, invalid labels, missing fields, refusals and failures |
| Streaming | Correction accuracy, unjustified changes and stale-response commits |
| Responsiveness | p50/p95 latency, cold start and end-to-end audio delay |
| Uncertainty | Error versus accepted coverage; calibration where probability outputs support it |
| Resources | Memory, total conversation cost, training and annotation effort |

Evaluate clean transcripts, ASR transcripts of the same recordings and the complete audio pipeline separately. Include failures and retries in the report. Cached replay is not a latency measurement.

Use human-reviewed labels as ground truth. Do not equate agreement with Jev with correctness, or self-reported LLM confidence with calibrated probabilities.

Keep source conversations, paraphrases, audio variants and all prefixes in the same split. Use distinct training, validation, calibration and final-test partitions. Report held-out scenario families and unfamiliar phrasing.

Provisional local-model goals are macro-F1 within two percentage points of Jev and coverage within five points at the same accepted-error limit. Confirm margins before local tuning, report uncertainty intervals and retain per-field results.

## First implementation milestone

- [ ] Initialize the Python package with uv and commit its lockfile.
- [ ] Add Typer and define the `turnwise` CLI entry point and subcommands.
- [ ] Define the six-field task and annotation rules.
- [ ] Create five conversations covering ordinary facts, missing facts, negation, corrections and irrelevant candidate values.
- [ ] Annotate the expected form after selected turns.
- [ ] Implement contracts, prefix assembly and fixture-based replay.
- [ ] Verify future-turn exclusion, explicit absence versus unknown, and stale-response rejection.
- [ ] Add Jev and structured-output LLM adapters.
- [ ] Produce the first side-by-side report, then expand to 30 conversations.

The first cloud LLM adapter is planned for OpenAI. Select and pin the actual model and SDK during implementation. Keep Jev credentials and other keys in environment variables, outside version control.

## Planned command interface

The CLI will use Typer, with commands executed through uv. These examples describe the intended interface; the project commands are not runnable yet.

```bash
uv run turnwise validate --dataset data/examples
uv run turnwise replay --case data/examples/conversations/correction.json --provider fixture
uv run turnwise benchmark --config configs/experiments/jev-vs-llm.yaml
uv run turnwise report --run runs/<run-id>
```

Setup instructions will be added once dependencies and adapters are implemented. Normal CI should run offline checks; paid provider tests should require explicit invocation and request limits.

## Local training and improvement

After concept proof, expand the reviewed dataset, train a small decision model and measure its gap against both references. Use validation errors to choose the next experiment:

- Add contrastive examples for negation and corrections.
- Improve coverage of unknown and conflicting states.
- Fix candidate recall or context loss before blaming model capacity.
- Calibrate probabilities separately for each model.
- Test a larger backbone only when persistent errors justify it.

If shared pipeline logic changes, rerun both references. Freeze the final configuration before opening the final test set. Verify checkpoint reload and inference support for the decision head. The final local demo must also use local transcription.

## Data and results policy

Commit only synthetic examples and selected publishable reports. Exclude secrets, personal audio, raw generated runs and checkpoints from ordinary Git history. Record dataset provenance and licenses before redistribution.

No benchmark results are available yet. The intended outcome is a working demo, trained local checkpoint, reproducible evaluation and a technical post explaining when each approach is useful.

## References

- [TypeSafe and Jev documentation](https://docs.typesafe.ai/introduction)
- [Language Models for Text Classification: From Bag-of-Words to Jev](https://magazine.sebastianraschka.com/p/classifier-history-and-jev)
- [Train your own decision model with Unsloth](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [TypeSafe candidate-based value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)


# Project Plan

This document tracks the planned work for Turnwise. The repository is currently in the planning stage; paths and commands below describe intended work and are not implemented unless stated otherwise.

## Research questions

1. When does a general decision model such as Jev offer an advantage over a general LLM with schema-constrained output?
2. Once the concept works, can a small local decision model approach Jev's task performance through fine-tuning?
3. Which improvements in data, training, and calibration close the gap, and at what cost?

The project investigates specialization twice: selecting a decision-oriented model, then training a local specialist for a defined task. A result on this task does not establish general-purpose equivalence.

## Experiment sequence

| Stage | Work | Exit condition |
| --- | --- | --- |
| 1. Define the task | Six fields, explicit unknown states, annotation rules, and transcript-prefix examples | Reviewed examples and annotation rules |
| 2. Prove and compare | Jev and a general LLM, followed by incremental replay and a small audio demo | Measured feasibility and evidence about where decision models help |
| 3. Freeze references | Pin task, prompts, models, dataset, and evaluation protocol | Reproducible comparison |
| 4. Train locally | Train a small decision model with the Unsloth workflow | Saved checkpoint integrated into the same application |
| 5. Improve | Analyze validation errors, improve data and training, and calibrate | Documented learning curves and performance gaps |
| 6. Evaluate | Compare frozen models on untouched data and demonstrate local audio processing | Final report and reproducible demo |

Training begins after the Jev concept is tested. Both reference models remain in the final comparison. If Jev does not outperform the general LLM, that is a result to report; local specialization can still be investigated.

## First implementation milestone

- [x] Initialize the Python package with uv and commit its lockfile.
- [x] Add Typer and define the `turnwise` CLI entry point and `validate`, `replay`, `benchmark`, and `report` subcommands.
- [x] Define the six-field task and annotation rules in `configs/tasks/repair-intake.yaml` and `docs/annotation-guide.md`.
- [ ] Create five conversations covering ordinary facts, missing facts, negation, corrections, and irrelevant candidate values.
- [ ] Annotate the expected form after selected turns.
- [ ] Implement shared contracts, prefix assembly, and fixture-based replay.
- [ ] Verify future-turn exclusion, explicit absence versus unknown, and stale-response rejection.
- [ ] Add Jev and structured-output LLM adapters.
- [ ] Produce the first side-by-side report, then expand to 30 conversations.

The first cloud LLM adapter is planned for OpenAI. Select and pin the actual model and SDK during implementation. Keep provider credentials in environment variables outside version control.

## Tooling decisions

- **uv** manages the Python environment, dependencies, lockfile, and project command execution. Commit `pyproject.toml` and `uv.lock`; exclude `.venv/` from Git.
- **Typer** provides the `turnwise` CLI, with thin handlers that delegate model calls, data processing, and metrics to their respective modules.
- Keep GPU training dependencies separate from the core CLI and evaluation environment.

## Intended pipeline

Start with text fixtures, then feed speech-recognition events into the same pipeline:

1. Assemble the transcript available at the current turn.
2. Find candidate values and preserve their source offsets.
3. Evaluate configured fields through the selected provider.
4. Validate and normalize the response.
5. Update the form with evidence and revision history.
6. Record outputs and measurements for evaluation.

The conceptual provider boundary is `decide(input) -> result`. Providers share task semantics while retaining their native metadata and limitations. Exact dates and amounts use a shared candidate-extraction step: the model selects a candidate, then code copies its source span and normalizes the value. Candidate recall and selection accuracy are evaluated separately.

Planned shared contracts:

| Contract | Contents |
| --- | --- |
| `TranscriptEvent` | Conversation and event IDs, speaker, text, timestamps, revision, and finalization status |
| `DecisionInput` | Available transcript prefix, task version, date/time zone, and candidates |
| `DecisionResult` | Values, optional probabilities, evidence references, provider details, timing, usage, and failures |
| `FormSnapshot` | Current values, acceptance status, and superseded revisions |
| `GoldSnapshot` | Human-reviewed expected answers for a specific prefix |
| `RunManifest` | Dataset and code versions, configuration, environment, and measurement policy |

Gold answers and future transcript turns must never enter provider inputs. Missing probability information remains null. A fixture provider verifies application behavior; it is not evidence of model quality.

## Intended repository layout

The directory scaffold is created up front; add implementation files as their corresponding milestones begin. Empty directories contain `.gitkeep` markers so Git preserves the planned layout.

| Path | Purpose |
| --- | --- |
| `pyproject.toml`, `uv.lock` | uv project configuration, dependencies, CLI entry point, and lockfile |
| `.env.example`, `.gitignore` | Credential placeholders and generated-file exclusions |
| `docs/decisions/` | Architecture and experiment decisions |
| `configs/tasks/repair-intake.yaml` | Canonical questions, labels, and criteria |
| `configs/experiments/` | Versioned experiment configurations |
| `data/examples/conversations/` | Small synthetic transcript fixtures |
| `data/examples/annotations/` | Gold snapshots, stored separately from model inputs |
| `data/manifests/` | Dataset provenance, hashes, and split membership |
| `src/turnwise/` | Python package, contracts, and CLI |
| `src/turnwise/settings.py` | Local environment loading and provider credentials/model settings |
| `src/turnwise/providers/` | Fixture, Jev, structured-LLM, and later local adapters |
| `src/turnwise/pipeline/` | Prefix assembly, candidate extraction, normalization, and form updates |
| `src/turnwise/evaluation/` | Metrics, run manifests, comparisons, and error analysis |
| `src/turnwise/audio/` | ASR adapter and timestamped transcript events |
| `src/turnwise/training/` | Dataset conversion, fine-tuning, calibration, and checkpoint loading |
| `src/turnwise/app/` | Later FastAPI service and minimal form interface |
| `tests/unit/`, `tests/integration/` | Offline behavior checks and opt-in provider smoke tests |
| `reports/` | Selected shareable results and error analyses |
| `runs/`, `checkpoints/` | Generated predictions and local models; ignored by Git |

Keep the initial implementation in one Python package. Separate GPU training dependencies from the ordinary evaluation environment.

## Planned command interface

These commands describe the intended interface; they are not runnable yet.

```bash
uv run turnwise validate --dataset data/examples
uv run turnwise replay --case data/examples/conversations/correction.json --provider fixture
uv run turnwise benchmark --config configs/experiments/jev-vs-llm.yaml
uv run turnwise report --run runs/<run-id>
```

Normal CI should run offline checks. Paid provider tests should require explicit invocation and request limits.

## Local training and iteration

After concept proof, expand the reviewed dataset, train a small decision model, and measure its gap against both references. Use validation errors to choose the next experiment:

- Add contrastive examples for negation and corrections.
- Improve coverage of unknown and conflicting states.
- Fix candidate recall or context loss before blaming model capacity.
- Calibrate probabilities separately for each model.
- Test a larger backbone only when persistent errors justify it.

If shared pipeline logic changes, rerun both references. Freeze the final configuration before opening the final test set. Verify checkpoint reload and inference support for the decision head. The final local demo must also use local transcription.

## Data and results policy

Commit only synthetic examples and selected publishable reports. Exclude secrets, personal audio, raw generated runs, and checkpoints from ordinary Git history. Record dataset provenance and licenses before redistribution.

No benchmark results are available yet. The intended outcome is a working demo, trained local checkpoint, reproducible evaluation, and a technical post explaining when each approach is useful.
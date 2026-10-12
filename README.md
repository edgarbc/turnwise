# Turnwise

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/package%20manager-uv-6E9F18)
![Status: Early implementation](https://img.shields.io/badge/status-early%20implementation-orange)

*From conversation to structured decisions.*

Turnwise is a research project about extracting reliable, reviewable information from conversations. It will compare decision models with schema-constrained LLMs, then explore whether a small local decision model can perform well on the same task.

**Status: Early implementation.** The uv-managed Python package and Typer CLI scaffold are in place. The CLI commands, datasets, provider integrations, and benchmark results are not implemented yet.

## Problem

A household repair intake conversation should become a structured form that updates as new information arrives. For example, the system should record that a washing machine leak has stopped, replace a Friday appointment preference with Saturday afternoon when the speaker corrects it, and note that a quote is required before work begins.

The initial experiment uses synthetic English conversations about one appliance, two known speaker roles, and approximately two to five minutes of audio. Turnwise drafts information for human review; it does not book services or authorize spending.

## Research approach

The first comparison is between Jev and a general LLM using schema-constrained output. Both receive the same task labels, transcript prefixes, and candidate values. If the concept is useful, a small local decision model will be trained and evaluated against both references. The experiment measures correctness, output validity, latency, cost, and uncertainty handling; valid output structure alone is not treated as evidence of correct answers.

The task and experimental limits matter: matching Jev on this defined task would not show equivalent performance on arbitrary tasks. See the [evaluation protocol](docs/evaluation-protocol.md) for the planned comparison and metrics.

## Project documents

- [Project plan](docs/project-plan.md): milestones, architecture, tooling, and intended repository layout.
- [Annotation guide](docs/annotation-guide.md): field meanings and proposed rules for evidence, unknowns, negation, and corrections.
- [Evaluation protocol](docs/evaluation-protocol.md): baselines, data splits, metrics, and comparison safeguards.

## Command-line interface

Install [uv](https://docs.astral.sh/uv/), then install the project and its dependencies from the repository root:

```bash
uv sync
uv run turnwise --help
uv run pytest
```

The CLI registers four commands. Offline dataset validation and fixture-based replay are implemented; `benchmark` and `report` remain scaffolds. Use each command's `--help` option to inspect its arguments:

```bash
uv run turnwise validate --help
uv run turnwise replay --help
uv run turnwise benchmark --help
uv run turnwise report --help
```

| Command | Arguments |
| --- | --- |
| `validate` | `--dataset PATH` (defaults to `data/examples`) |
| `replay` | `--case PATH`, `--provider fixture`, optional `--responses PATH` |
| `benchmark` | `--config PATH` |
| `report` | `--run PATH` |

Validate the conversation and annotation files in the example dataset with:

```bash
uv run turnwise validate --dataset data/examples
```

Validation checks task/version consistency, conversation/annotation pairing, event ordering and speaker roles, complete field maps, prefix ordering, and evidence references and spans. Invalid data is reported with file paths and causes a nonzero exit status.

Replay evaluates each transcript prefix in event order. The fixture provider is a deterministic offline test double; it does not infer values. Supply a separate response script to exercise form updates and corrections:

```bash
uv run turnwise replay \
  --case data/examples/conversations/repair-004-corrections.json \
  --provider fixture \
  --responses data/examples/provider-responses/repair-004-corrections.json
```

Without `--responses`, the fixture provider makes no field updates. Each run writes snapshots and metadata to a unique `runs/<run-id>/replay.json`; transcript text and gold annotations are not copied into the artifact. Scripted provider responses are for pipeline checks only, not benchmark predictions or evidence of model quality.

## Provider credentials

Copy `.env.example` to `.env` and add the credentials you use. `.env` is ignored by Git. Settings load `.env` without overriding variables already present in the process environment; secret values are excluded from settings representations.

```bash
cp .env.example .env
```

`TYPESAFE_API_KEY` is used for Jev, with `JEV_MODEL` defaulting to `jev-latest`. OpenAI uses `OPENAI_API_KEY`; set `OPENAI_MODEL` to the model selected for the comparison. Credentials are checked only when configuration for that provider is requested. The provider adapters and network calls are not implemented yet.

The settings API returns the selected model and credential for a provider without exposing the key in object representations:

```python
from turnwise.settings import Settings

settings = Settings.load()
jev = settings.for_provider("jev")
openai = settings.for_provider("openai")
```

## Repository structure

This is the current scaffold. Empty directories are retained with `.gitkeep`; implementation files will be added as the milestones progress. The local `.venv/` is excluded from version control.

```text
turnwise/
├── configs/
│   ├── experiments/
│   │   └── jev-vs-llm.yaml
│   └── tasks/
│       └── repair-intake.yaml
├── data/
│   ├── examples/
│   │   ├── annotations/
│   │   │   ├── repair-001-ordinary.json
│   │   │   ├── repair-002-missing.json
│   │   │   ├── repair-003-negation.json
│   │   │   ├── repair-004-corrections.json
│   │   │   └── repair-005-distractors.json
│   │   ├── conversations/
│   │   │   ├── repair-001-ordinary.json
│   │   │   ├── repair-002-missing.json
│   │   │   ├── repair-003-negation.json
│   │   │   ├── repair-004-corrections.json
│   │   │   └── repair-005-distractors.json
│   │   └── provider-responses/
│   │       └── repair-004-corrections.json
│   └── manifests/
├── docs/
│   ├── decisions/
│   ├── annotation-guide.md
│   ├── evaluation-protocol.md
│   └── project-plan.md
├── src/turnwise/
│   ├── app/
│   ├── audio/
│   ├── evaluation/
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── prefix.py
│   │   └── replay.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── fixture.py
│   ├── training/
│   ├── __init__.py
│   ├── cli.py
│   ├── contracts.py
│   └── settings.py
├── tests/
│   ├── integration/
│   └── unit/
│       ├── test_dataset_validation.py
│       ├── test_experiment_config.py
│       ├── test_prefix_assembly.py
│       ├── test_replay.py
│       ├── test_settings.py
│       ├── test_synthetic_conversations.py
│       └── test_task_definition.py
├── checkpoints/
├── reports/
├── runs/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── uv.lock
```

## References

- [TypeSafe and Jev documentation](https://docs.typesafe.ai/introduction)
- [Train your own decision model with Unsloth](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [TypeSafe candidate-based value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)
# Turnwise

*From conversation to structured decisions.*

Turnwise is a research project about extracting reliable, reviewable information from conversations. It will compare decision models with schema-constrained LLMs, then explore whether a small local decision model can perform well on the same task.

**Status: Planning.** The repository currently contains project documentation only. The application, CLI, datasets, and benchmark results are not implemented yet.

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

## References

- [TypeSafe and Jev documentation](https://docs.typesafe.ai/introduction)
- [Train your own decision model with Unsloth](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [TypeSafe candidate-based value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)
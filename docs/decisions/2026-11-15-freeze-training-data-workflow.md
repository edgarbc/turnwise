# Freeze the Data and Evaluation Workflow

- **Status:** Accepted
- **Date:** 2026-11-15
- **Scope:** Data generation, annotation, split, export, and evaluation procedure for the initial 50-conversation transcript experiment.

## Context

The 40 non-test development conversations are approved: 30 training, five validation, and five calibration conversations. They contain 49 annotated snapshots, and `uv run turnwise validate --dataset data/training` passes. A manifest audit confirms all 40 cases are approved and their conversation and annotation hashes match. The ten final-test case specifications and labels have not been generated or exposed.

## Decision

Freeze the following workflow before creating the final-test set:

1. **Task and labels:** use `repair_intake` version `0.1.0` and the six fields in `configs/tasks/repair-intake.yaml`. Apply the unknown, negation, correction, and evidence rules in `docs/annotation-guide.md`.
2. **Data unit:** one example is one annotated transcript prefix. Preserve the exact visible events and candidates through the prefix cutoff; do not include future events, gold labels, or annotations in model input.
3. **Candidates and options:** use Turnwise's shared candidate extractor, customer events only, preserving all detected candidates including distractors. Candidate-backed labels select a uniquely evidence-supported candidate ID; boolean labels select a value with a supporting customer event; unsupported or unresolved values use `__unknown__`.
4. **Generation and review:** generate only from confirmed scenario specifications after family assignment. Treat specifications as coverage guidance, not transcript ground truth. Validate schema, candidates, evidence, prefix cutoffs, and scenario consistency, then obtain separate human transcript and annotation approval. Record provenance, outcomes, and file hashes in manifests.
5. **Splits and leakage:** keep the family, conversation, and all its prefixes in one split. Use 30/5/5/10 conversations for training, validation, calibration, and final test. Keep the existing 30-conversation pilot separate as a regression set.
6. **Export and evaluation:** use the deterministic `state`, `questions`, `gold` export contract and shared Jev question construction. Follow `docs/evaluation-protocol.md` for leakage controls, metrics, failure reporting, and limitations. Version each concrete model/evaluation configuration before using the final test.

The canonical task hash is `2bcfeac17ccd30d85c640394b930bfd9db4a4dc7b1b67f049483ab79b9284db3`; the scenario-catalogue hash is `24733bfc371d679a96540574d7bd92cc313edc678d40de24fb727cf918a33572`. Per-case conversation and annotation hashes remain in the approved manifests rather than being duplicated here.

## Final-Test Boundary

This decision permits creating the ten held-out cases in a separate test manifest, with full transcript and annotation review and frozen hashes. Test labels must not enter training, validation, calibration, prompt development, threshold selection, or checkpoint selection. Keep the test manifest and labels out of development exports. After model and evaluation configuration are selected and frozen, run the final comparison against the locked test set and report the results once, including failures and limitations.

## Not Frozen

This workflow decision does not select an open-weight backbone, license, decision-head initialization, optimizer, hyperparameters, training duration, hardware, checkpoint, or calibration threshold. Those are subsequent experiment decisions using training, validation, and calibration data only. The provisional performance margins in the evaluation protocol remain targets, not results.

## References

- [Training plan](../training/plan.md)
- [Training approach](../training/approach.md)
- [Data and review contract](../training/data-and-review.md)
- [Generation and review procedure](../training/generation-and-review.md)
- [Export format](../training/export-format.md)
- [Evaluation protocol](../evaluation-protocol.md)

## Subsequent Status

On 2026-11-23, the final-test annotations, transcripts, manifest, and scenario catalogue were found in public PR #5 before model and evaluation configuration were frozen. The original set is therefore compromised as a blind final test; its `locked` metadata does not restore secrecy. See [`2026-11-23-final-test-exposure.md`](2026-11-23-final-test-exposure.md). Keep it only as a known public regression set and create a fresh, access-controlled replacement after configuration freeze.

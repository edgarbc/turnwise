# Unsloth Export Format

The exporter writes one JSONL row per approved transcript-prefix annotation. Each model row contains only:

- `state`: the visible transcript prefix and candidates produced by Turnwise's shared extractor;
- `questions`: the shared task questions and exact choices used by Jev;
- `gold`: one available option key for each task question.

Conversation, snapshot, split, source hashes, and row index are written to a separate metadata JSON sidecar. Gold values and annotation evidence are never added to `state`.

Export the reviewed training partition with:

```bash
uv run turnwise export-unsloth \
  --manifest data/manifests/training-initial-drafts.json \
  --task configs/tasks/repair-intake.yaml \
  --split training \
  --output data/training/exports/initial-training.jsonl \
  --metadata data/training/exports/initial-training.metadata.json
```

The command refuses unapproved transcripts or annotations, source-hash mismatches, scenario-catalogue mismatches, family leakage across splits, annotation values that differ from confirmed scenario facts, invalid prefix cutoffs, missing or ambiguous evidence-supported candidates, invalid boolean evidence, and gold choices absent from the per-row options. The sidecar includes the task and manifest hashes and exporter version. Re-running with unchanged inputs produces byte-identical JSONL and sidecar outputs.

Validation checks structure and mapping, not semantic correctness. The human-approved annotations remain the source of training labels.

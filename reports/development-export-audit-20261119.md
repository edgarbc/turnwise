# Development Export Audit

## Scope

The development exports cover the 40 reviewed development conversations and 49 annotated snapshots. No final-test case, annotation, or label was opened or exported during this audit. The original smoke export and checkpoint remain separate mechanics artifacts.

| Split | Conversations | Rows | JSONL SHA-256 | Sidecar SHA-256 |
| --- | ---: | ---: | --- | --- |
| Training | 30 | 36 | `047cd69b878e454bbba97ca6e4b93c1d58022622865c93cd607aeb9fc306b72b` | `d8324d5b253af8e80987e24105f964a28dd7d35cf27ac9bba7bee87940d11dca` |
| Validation | 5 | 8 | `d0216f37f996afed8ad73d823c71fcf1be498e5d8e7aaa71e4d8e543b5edab58` | `7c1da9921a8e47fbfc74c9f5d2f2c28f820c1a7c201b0a199c9eee3efaa606eb` |
| Calibration | 5 | 5 | `3275b94dc260edbea8f6ff934a06a1a1b1923416c2f7bc7276220e9c319159a8` | `9d2fafcacad0f83508d84ef5bc91a0f97272ce82ce0e91bc0973e4bf6bdeb964` |

The derived development manifest is `data/manifests/training-development.json` (SHA-256 `c9d2a788d91c6f888581230b0717890987d37a594dd5baef2efe57ba4aed5ba8`). Its task SHA-256 is `2bcfeac17ccd30d85c640394b930bfd9db4a4dc7b1b67f049483ab79b9284db3`; its development scenario catalogue SHA-256 is `24733bfc371d679a96540574d7bd92cc313edc678d40de24fb727cf918a33572`.

## Checks and Review Discrepancy

- All 19 development batch manifests share the pinned task and scenario catalogue. Their hashes and batch annotation statuses are recorded in the derived manifest.
- All 40 individual case records contain named, dated, approved transcript and annotation reviews. Sixteen batch annotation summaries previously reported review as not started; they were changed to approved to match their case-level records, and the derived manifest and sidecars were regenerated. The three JSONL files remained byte-identical.
- The same 16 batches still have pending or unreviewed transcript summaries despite approved case-level transcript reviews. Those separate summary fields were not changed; review this discrepancy before the exports are used for model selection.
- Each exporter run checked approved case statuses, source hashes, scenario consistency, prefix boundaries, evidence, candidate mapping, and gold option membership. The audit separately checked source-manifest hashes, row/sidecar alignment, six questions per row, gold option membership, and complete development case coverage.
- Conversation and scenario-family IDs do not cross splits. Re-export tests reproduce the JSONL and sidecar bytes for each split.
- These are structural and provenance checks, not independent semantic re-annotation or evidence of model quality. Validation and calibration labels remain evaluator-only; the final test remains locked.
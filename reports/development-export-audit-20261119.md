# Development Export Audit

## Scope

The development exports cover the 40 reviewed development conversations and 49 annotated snapshots. No final-test case, annotation, or label was opened or exported during this audit. The original smoke export and checkpoint remain separate mechanics artifacts.

| Split | Conversations | Rows | JSONL SHA-256 | Sidecar SHA-256 |
| --- | ---: | ---: | --- | --- |
| Training | 30 | 36 | `047cd69b878e454bbba97ca6e4b93c1d58022622865c93cd607aeb9fc306b72b` | `307f945e00934d2bfd54224e5d7ff7a071bcc9c2389579a060798f94844e27ad` |
| Validation | 5 | 8 | `d0216f37f996afed8ad73d823c71fcf1be498e5d8e7aaa71e4d8e543b5edab58` | `c177637ccb7fe8368a8b4eab9982bb59f5d5753f93c46664d53d606c5910cea9` |
| Calibration | 5 | 5 | `3275b94dc260edbea8f6ff934a06a1a1b1923416c2f7bc7276220e9c319159a8` | `6ead37b5afe80161e7f5cc1b556990d38c9b7b037112e62609fcccc83d5db897` |

The derived development manifest is `data/manifests/training-development.json` (SHA-256 `c4dffdd57556a06a62b692682f5c84c5a33ba0717142afcb9c36e16b14a0310a`). Its task SHA-256 is `2bcfeac17ccd30d85c640394b930bfd9db4a4dc7b1b67f049483ab79b9284db3`; its development scenario catalogue SHA-256 is `24733bfc371d679a96540574d7bd92cc313edc678d40de24fb727cf918a33572`.

## Checks and Review Reconciliation

- All 19 development batch manifests share the pinned task and scenario catalogue. Their hashes and batch transcript and annotation statuses are recorded in the derived manifest.
- All 40 individual case records contain named, dated, approved transcript and annotation reviews. Sixteen batch annotation summaries previously reported review as not started; they were changed to approved to match their case-level records, and the derived manifest and sidecars were regenerated. The three JSONL files remained byte-identical.
- The same 16 batches previously reported their transcript summaries as pending or unreviewed. Those summaries were also changed to approved to match their case-level records; the derived manifest and sidecars were refreshed, and the JSONL files remained byte-identical. The builder now requires approved batch summaries for both transcript and annotation reviews.
- Each exporter run checked approved case statuses, source hashes, scenario consistency, prefix boundaries, evidence, candidate mapping, and gold option membership. The audit separately checked source-manifest hashes, row/sidecar alignment, six questions per row, gold option membership, and complete development case coverage.
- Conversation and scenario-family IDs do not cross splits. Re-export tests reproduce the JSONL and sidecar bytes for each split.
- These are structural and provenance checks, not independent semantic re-annotation or evidence of model quality. Validation and calibration labels remain evaluator-only; the final test remains locked.
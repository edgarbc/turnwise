# Final-Test Data Quality Report

**Status date:** 2026-11-15  
**Purpose:** Record aggregate structure, approval, provenance, and leakage checks for the initial 50-conversation corpus. This report does not publish per-case labels or evidence.

## Subsequent Status (2026-11-23)

The final-test annotation and transcript files, manifest, and scenario catalogue were included in public PR #5 before model/evaluation configuration freeze. The original test set is therefore **compromised as a blind final test**. Do not use it for model, checkpoint, prompt, threshold, or calibration selection, and do not report its results as unseen held-out performance. Retain it only as a known public regression set. A fresh test set must be created privately after configuration freeze; see the [exposure decision](../docs/decisions/2026-11-23-final-test-exposure.md).

## Dataset Counts

| Split | Conversations | Annotated snapshots | Status |
| --- | ---: | ---: | --- |
| Training | 30 | 36 | Approved |
| Validation | 5 | 8 | Approved |
| Calibration | 5 | 5 | Approved |
| Original test | 10 | 27 | Approved, but publicly exposed; regression only |
| **Total** | **50** | **76** | |

## Validation and Review

- `uv run turnwise validate --dataset data/training`: passed, 40 conversations and 49 snapshots.
- `uv run turnwise validate --dataset data/test`: passed, 10 conversations and 27 snapshots.
- The 40 non-test conversations and annotations are approved in their batch manifests.
- All ten final-test scenario specifications, transcripts, and annotations are approved. The test allocation is five `test-heldout-corrections-conflicts` cases and five `test-heldout-combinations` cases.
- A manifest audit verified unique test case IDs, approvals, per-case scenario-specification hashes, transcript hashes, annotation hashes, and the 5/5 family allocation.

Validation establishes structural consistency, candidate/evidence validity under the implemented rules, and source integrity. It does not prove that the labels are semantically correct beyond the recorded human review or that this small synthetic set represents real-world performance.

## Pinned Sources

| Source | SHA-256 |
| --- | --- |
| Task: `configs/tasks/repair-intake.yaml` | `2bcfeac17ccd30d85c640394b930bfd9db4a4dc7b1b67f049483ab79b9284db3` |
| Original final-test catalogue (local-only, compromised) | `a39fad86b2c5848d1e2d9e794fbf1afce4081343d2b2cb4de5226ad1498cd0b8` |
| Original final-test manifest (local-only, compromised) | `cb96053ba8356188cc6344815c6190eea30cb00e3b9f1e2fc832c71d6b0bd1eb` |
| Workflow freeze decision: `docs/decisions/2026-11-15-freeze-training-data-workflow.md` | `110b0f072a3f4b7dfe103e51c28e35e9a5b20418d3a51587696f84bddb39b1cf` |

Per-case source hashes are retained in the manifests and are not duplicated here.

## Original Test-Set Boundary

At the time of this report, the final-test cases were stored separately under `data/test/` and excluded from development exports. They were later exposed publicly in PR #5 and no longer meet the blind-test boundary. The original set must not be used for final performance claims.

## Historical Next Experiment Stage

At the time this report was written, the dataset workflow was frozen and the original test set was considered locked. On 2026-11-23, its labels were identified in public PR #5 before configuration freeze; it is now compromised as a blind test. Keep it only as a known public regression set and create a private replacement after configuration freeze. See [`../docs/decisions/2026-11-23-final-test-exposure.md`](../docs/decisions/2026-11-23-final-test-exposure.md).

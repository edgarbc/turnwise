# Final-Test Data Quality Report

**Status date:** 2026-11-15  
**Purpose:** Record aggregate structure, approval, provenance, and leakage checks for the initial 50-conversation corpus. This report does not publish per-case labels or evidence.

## Dataset Counts

| Split | Conversations | Annotated snapshots | Status |
| --- | ---: | ---: | --- |
| Training | 30 | 36 | Approved |
| Validation | 5 | 8 | Approved |
| Calibration | 5 | 5 | Approved |
| Final test | 10 | 27 | Approved and locked |
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
| Final-test catalogue: `data/scenarios/final-test-catalog.yaml` | `a39fad86b2c5848d1e2d9e794fbf1afce4081343d2b2cb4de5226ad1498cd0b8` |
| Final-test manifest: `data/manifests/final-test.json` | `cb96053ba8356188cc6344815c6190eea30cb00e3b9f1e2fc832c71d6b0bd1eb` |
| Workflow freeze decision: `docs/decisions/2026-11-15-freeze-training-data-workflow.md` | `110b0f072a3f4b7dfe103e51c28e35e9a5b20418d3a51587696f84bddb39b1cf` |

Per-case source hashes are retained in the manifests and are not duplicated here.

## Test-Set Boundary

The final-test cases are stored separately under `data/test/` and are excluded from development exports. Do not use test labels for training, validation, calibration, prompt development, threshold selection, or checkpoint selection. Freeze the concrete model, checkpoint, and evaluation configuration before the final test comparison. Report the test result once with failures and limitations; do not iterate on the test labels.

## Next Experiment Stage

The dataset-generation and review workflow is frozen, and the final-test set is locked. The remaining pre-evaluation work is to select and document the open-weight model and training setup, verify the execution environment, establish the pretrained baseline, and smoke-test training and inference. Model and threshold selection must use training, validation, and calibration data only. Freeze that configuration before running the final held-out comparison.

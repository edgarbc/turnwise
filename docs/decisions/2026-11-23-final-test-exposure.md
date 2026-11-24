# Final-Test Exposure and Replacement

- **Status:** Confirmed exposure; the original set is no longer a blind final test
- **Date:** 2026-11-23
- **Scope:** Final-test annotations, transcripts, manifest, and scenario catalogue included in public PR #5

## Finding

PR #5 added the final-test annotations and their manifest/catalogue to the public `edgarbc/turnwise` repository before model and evaluation configuration were frozen. The files therefore cannot serve as an unseen final evaluation set, regardless of the notebook's runtime gate or the manifest's `locked` status. Removing them from the current branch does not remove them from the public PR's existing commit history.

The exposed manifest SHA-256 is `cb96053ba8356188cc6344815c6190eea30cb00e3b9f1e2fc832c71d6b0bd1eb`. Retain the old cases only as a known public regression set; do not report them as blind held-out performance or use their labels for model, checkpoint, prompt, threshold, or calibration decisions.

## Repository Handling

The test corpus, manifest, and scenario catalogue are removed from the current Git index but retained in the local worktree and ignored by `.gitignore`. This prevents their inclusion in future repository trees; it does not purge the already-published PR history.

## Replacement Requirement

Create a fresh, independent final-test set only after the model, checkpoint-selection rule, calibration procedure, metrics, and evaluation code are frozen. Keep its transcripts, annotations, manifest, and source hashes in access-controlled storage that is not part of the public repository. Export and evaluate it once, then publish only aggregate results and limitations. The development notebook's final-test cell requires a separately pinned replacement manifest hash and rejects the exposed hash.

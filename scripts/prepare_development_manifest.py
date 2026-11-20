"""Consolidate reviewed development cases without altering their batch manifests."""

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPLITS = {"training", "validation", "calibration"}


def build_manifest(root: Path) -> dict:
    manifest_dir = root / "data" / "manifests"
    paths = [manifest_dir / "training-initial-drafts.json"] + sorted(
        manifest_dir.glob("training-generation-batch-*.json")
    )
    if len(paths) != 19:
        raise ValueError(f"expected 19 development manifests, found {len(paths)}")

    cases = []
    sources = []
    seen_cases = set()
    family_splits = {}
    task = None
    catalog = None
    for path in paths:
        content = path.read_bytes()
        batch = json.loads(content)
        if task is None:
            task = batch["task"]
            catalog = batch["scenario_catalog"]
        elif batch["task"] != task or batch["scenario_catalog"] != catalog:
            raise ValueError(f"inconsistent task or scenario catalogue: {path.name}")
        if (batch["review_policy"]["conversation_review_status"] != "approved"
                or batch["validation"]["human_transcript_review"] != "approved"):
            raise ValueError(f"batch transcript review is not approved: {path.name}")
        if (batch["review_policy"]["annotation_status"] != "approved"
                or batch["validation"]["human_annotation_review"] != "approved"):
            raise ValueError(f"batch annotation review is not approved: {path.name}")
        source_path = path.relative_to(root).as_posix()
        sources.append({
            "path": source_path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "batch_conversation_review_status": batch["review_policy"]["conversation_review_status"],
            "batch_human_transcript_review": batch["validation"]["human_transcript_review"],
            "batch_annotation_status": batch["review_policy"]["annotation_status"],
            "batch_human_annotation_review": batch["validation"]["human_annotation_review"],
        })
        for case in batch["cases"]:
            case_id = case["case_id"]
            split = case["split"]
            if case_id in seen_cases:
                raise ValueError(f"duplicate case: {case_id}")
            if split not in SPLITS:
                raise ValueError(f"non-development split for {case_id}: {split}")
            if family_splits.setdefault(case["family_id"], split) != split:
                raise ValueError(f"family leaks across splits: {case['family_id']}")
            for kind in ("transcript", "annotation"):
                review = case.get(f"{kind}_review", {})
                if not all(review.get(key) for key in ("reviewer", "reviewed_at")) or review.get("outcome") != "approved":
                    raise ValueError(f"missing {kind} approval for {case_id}")
            if (case.get("human_review_status") != "approved"
                    or case.get("annotation_status") != "approved"
                    or case.get("annotation_review_status") != "approved"):
                raise ValueError(f"case status is not approved: {case_id}")
            for kind in ("conversation", "annotation"):
                expected_parent = f"data/training/{kind}s/"
                if not case[f"{kind}_path"].startswith(expected_parent):
                    raise ValueError(f"non-development {kind} path for {case_id}")
            seen_cases.add(case_id)
            cases.append({**case, "source_manifest": source_path})

    if catalog is None or task is None:
        raise ValueError("missing development task or catalogue")
    catalog_path = root / catalog["path"]
    if hashlib.sha256(catalog_path.read_bytes()).hexdigest() != catalog["sha256"]:
        raise ValueError("scenario catalogue hash mismatch")
    if hashlib.sha256((root / task["path"]).read_bytes()).hexdigest() != task["sha256"]:
        raise ValueError("task hash mismatch")
    scenarios = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))["scenarios"]
    expected_cases = {scenario["id"] for scenario in scenarios if scenario.get("split") in SPLITS}
    if seen_cases != expected_cases:
        raise ValueError("development cases do not match the scenario catalogue")

    return {
        "manifest_version": "0.1.0",
        "dataset_id": "repair-intake-reviewed-development",
        "purpose": "derived_development_export_manifest",
        "task": task,
        "scenario_catalog": catalog,
        "review_policy": {
            "annotation_status": "approved",
            "basis": "all individual cases have dated, named transcript and annotation approvals",
        },
        "validation": {
            "human_annotation_review": "approved",
            "basis": "case-level review records, with batch transcript and annotation summaries also required",
            "validation_is_not_semantic_approval": True,
        },
        "source_manifests": sources,
        "cases": cases,
    }


def main() -> None:
    output = ROOT / "data" / "manifests" / "training-development.json"
    content = json.dumps(build_manifest(ROOT), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != content:
        raise ValueError(f"refusing to overwrite differing manifest: {output}")
    output.write_text(content, encoding="utf-8")
    print(f"Prepared {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
"""Shared task configuration helpers for provider adapters."""

from pathlib import Path
from typing import Any, Mapping

import yaml

from turnwise.dataset_validation import DEFAULT_TASK_PATH


def load_task_definition(path: str | Path = DEFAULT_TASK_PATH) -> Mapping[str, Any]:
    """Load the canonical task object from YAML."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("task"), dict):
        raise ValueError(f"task definition at {path} must contain a task object")
    return data["task"]
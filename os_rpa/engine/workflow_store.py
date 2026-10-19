"""Locating and loading saved workflow JSON files (used by the API and flow.invoke_workflow)."""
import json
import os
from pathlib import Path
from typing import Optional

from os_rpa.models import Workflow


def workflows_dir() -> Path:
    """Folder holding saved workflows; relative to the working directory unless OS_RPA_WORKFLOWS_DIR is set."""
    return Path(os.environ.get("OS_RPA_WORKFLOWS_DIR") or "workflows")


def find_workflow_file(ref: str, base_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolves a workflow reference: a .json path, a saved workflow id (file stem or `id` field), or its name."""
    ref = (ref or "").strip()
    if not ref:
        return None
    base = Path(base_dir) if base_dir else workflows_dir()

    as_path = Path(ref)
    for candidate in (as_path, base / as_path):
        if candidate.suffix.lower() == ".json" and candidate.is_file():
            return candidate

    by_stem = base / f"{ref}.json"
    if by_stem.is_file():
        return by_stem

    by_name: Optional[Path] = None
    for f in sorted(base.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("id") == ref:
            return f
        if by_name is None and str(data.get("name", "")).strip().lower() == ref.lower():
            by_name = f
    return by_name


def load_workflow(ref: str, base_dir: Optional[Path] = None) -> Workflow:
    file_path = find_workflow_file(ref, base_dir)
    if not file_path:
        raise FileNotFoundError(
            f"Workflow '{ref}' not found (looked for a .json path, or an id/name in '{base_dir or workflows_dir()}')"
        )
    return Workflow(**json.loads(file_path.read_text(encoding="utf-8")))

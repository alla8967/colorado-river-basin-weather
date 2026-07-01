"""Write stable JSON artifacts for model-run and frontend handoff files.

Using one helper keeps generated JSON formatting predictable across scripts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


def write_json_file(file_path: Path, payload: Mapping[str, object]) -> None:
    """Write a stable, pretty JSON artifact and create its parent folder."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2) + "\n")

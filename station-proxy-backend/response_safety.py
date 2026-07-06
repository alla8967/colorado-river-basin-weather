"""Helpers for keeping public API responses free of local filesystem details."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PATH_KEY_MARKERS = ("file", "files", "path", "paths", "root", "executable")
DETAIL_KEYS = {"details", "enginedetails", "rawoutput"}
HOME_PATH_RE = re.compile(r"/(?:Users|home)/[^/\s,]+/")


def display_path(path: Path | str, project_dir: Path) -> str:
    """Return a project-relative path, or just the file name for outside paths."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return str(candidate)

    try:
        return str(candidate.resolve().relative_to(project_dir.resolve()))
    except (OSError, RuntimeError, ValueError):
        return candidate.name or "[redacted-path]"


def redact_project_paths(text: str, project_dir: Path) -> str:
    """Remove the absolute project prefix from text that may contain paths."""
    project = str(project_dir.resolve())
    redacted = text.replace(f"{project}/", "")
    redacted = "." if redacted == project else redacted.replace(project, ".")
    return HOME_PATH_RE.sub("~/", redacted)


def is_path_key(key: str | None) -> bool:
    if key is None:
        return False

    normalized = key.replace("_", "").replace("-", "").lower()
    return normalized in DETAIL_KEYS or any(marker in normalized for marker in PATH_KEY_MARKERS)


def sanitize_response_paths(value: Any, project_dir: Path, key: str | None = None) -> Any:
    """Recursively redact absolute paths from JSON-serializable payloads."""
    if isinstance(value, dict):
        return {
            item_key: sanitize_response_paths(item_value, project_dir, item_key)
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [sanitize_response_paths(item, project_dir, key) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_response_paths(item, project_dir, key) for item in value)

    if isinstance(value, Path):
        return display_path(value, project_dir)

    if isinstance(value, str):
        redacted = redact_project_paths(value, project_dir)
        if is_path_key(key) and Path(redacted).is_absolute():
            return display_path(redacted, project_dir)
        return redacted

    return value

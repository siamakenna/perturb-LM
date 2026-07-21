"""Artifact manifest helpers for local generated files."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "1.0"


def build_artifact_manifest(
    *,
    artifact_type: str,
    input_paths: Iterable[Path | str] = (),
    output_paths: Iterable[Path | str] = (),
    dataset: str | None = None,
    row_count: int | None = None,
    feature_count: int | None = None,
    embedding_dimension: int | None = None,
    index_type: str | None = None,
    distance_metric: str | None = None,
    warnings: Iterable[str] = (),
    notes: Iterable[str] = (),
    script_name: str | None = None,
    command: str | Sequence[str] | None = None,
    repo_root: Path | str | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a compact manifest that records artifact metadata, never row data."""

    input_path_strings = _path_strings(input_paths)
    output_path_strings = _path_strings(output_paths)
    git = git_metadata(repo_root=repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "created_at_utc": created_at_utc or _utc_now(),
        "script_name": script_name or current_script_name(),
        "command": normalize_command(command),
        "git_commit": git["git_commit"],
        "git_branch": git["git_branch"],
        "git_dirty": git["git_dirty"],
        "input_paths": input_path_strings,
        "input_file_sizes": file_size_map(input_path_strings),
        "output_paths": output_path_strings,
        "output_file_sizes": file_size_map(output_path_strings),
        "dataset": dataset,
        "row_count": _optional_int(row_count),
        "feature_count": _optional_int(feature_count),
        "embedding_dimension": _optional_int(embedding_dimension),
        "index_type": index_type,
        "distance_metric": distance_metric,
        "warnings": [str(warning) for warning in warnings],
        "notes": [str(note) for note in notes],
    }


def write_artifact_manifest(path: Path | str, manifest: dict[str, Any]) -> Path:
    """Write a manifest JSON file and return its path."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, manifest)
    output_file_sizes = manifest.get("output_file_sizes")
    path_key = str(path)
    if isinstance(output_file_sizes, dict) and path_key in output_file_sizes:
        for _ in range(3):
            current_size = path.stat().st_size
            if output_file_sizes[path_key] == current_size:
                break
            output_file_sizes[path_key] = current_size
            _write_json(path, manifest)
    return path


def file_size_map(paths: Iterable[Path | str]) -> dict[str, int | None]:
    """Return file sizes for paths that exist, with ``None`` for unavailable paths."""

    sizes: dict[str, int | None] = {}
    for path_value in paths:
        path = Path(path_value)
        try:
            sizes[str(path)] = path.stat().st_size if path.is_file() else None
        except OSError:
            sizes[str(path)] = None
    return sizes


def git_metadata(repo_root: Path | str | None = None) -> dict[str, str | bool | None]:
    """Return best-effort git metadata without failing outside a checkout."""

    cwd = Path(repo_root) if repo_root is not None else Path.cwd()
    commit = _git_output(["git", "rev-parse", "HEAD"], cwd)
    branch = _git_output(["git", "branch", "--show-current"], cwd)
    status = _git_output(["git", "status", "--short"], cwd)
    git_dirty: bool | None
    if status is None:
        git_dirty = None
    else:
        git_dirty = bool(status.strip())
    return {
        "git_commit": commit,
        "git_branch": branch or None,
        "git_dirty": git_dirty,
    }


def normalize_command(command: str | Sequence[str] | None = None) -> str | None:
    """Return a stable string form of a command or the current process command."""

    value: str | Sequence[str] | None = command
    if value is None:
        value = sys.argv if sys.argv else None
    if value is None:
        return None
    if isinstance(value, str):
        return value
    parts = [str(part) for part in value]
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def current_script_name() -> str | None:
    """Return the current script filename when available."""

    if not sys.argv:
        return None
    name = Path(sys.argv[0]).name
    return name or None


def _git_output(command: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _path_strings(paths: Iterable[Path | str]) -> list[str]:
    return [str(Path(path)) for path in paths]


def _optional_int(value: int | None) -> int | None:
    return None if value is None else int(value)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

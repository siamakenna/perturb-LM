"""Microscopy composite placeholders."""

from __future__ import annotations

from pathlib import Path


def validate_channel_paths(paths: list[Path]) -> list[Path]:
    """Validate that requested channel paths exist before future composite rendering."""

    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing channel image(s): {', '.join(str(path) for path in missing)}")
    return paths

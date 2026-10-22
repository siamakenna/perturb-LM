"""Bounded, root-confined snapshots of operator-selected audit JSON (#30, #52)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_JSON_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class JsonSnapshot:
    value: dict
    sha256: str


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _relative_parts(path, root_real):
    """Resolve aliases at the trusted root, never below it during the open."""
    absolute = Path(os.path.abspath(path))
    for ancestor in reversed(absolute.parents):
        if os.path.realpath(ancestor) == root_real:
            return absolute.relative_to(ancestor).parts
    raise ValueError("Audit JSON input is outside its trusted root")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Audit JSON contains duplicate object keys")
        value[key] = item
    return value


def _invalid_constant(_):
    raise ValueError("Audit JSON contains a non-finite constant")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Audit JSON contains a non-finite number")
    return value


def read_json_snapshot(path: Path, *, root: Path) -> JsonSnapshot:
    """Read once beneath an independently selected root; parse and hash those bytes.

    The root defaults at the CLI to the invocation directory. A caller may
    explicitly nominate another input directory whose ancestors are also trusted.
    This reader does not establish ownership or authenticate that root choice.
    Canonical containment excludes
    sibling prefixes and escaping aliases. Directory descriptors and O_NOFOLLOW
    then prevent a child path from being replaced with a symlink after checking.
    macOS aliases above the nominated root (for example /var) remain valid.
    """
    if ".." in Path(path).parts:
        raise ValueError("Audit JSON input must not contain parent traversal")
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(path)
    if not candidate.startswith(root_real.rstrip(os.sep) + os.sep):
        raise ValueError("Audit JSON input is outside its trusted root")
    parts = _relative_parts(path, root_real)
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Audit JSON input must name a file beneath its trusted root")
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if not all(hasattr(os, name) for name in required_flags) or os.open not in os.supports_dir_fd:
        raise ValueError("Safe audit JSON reads require descriptor-relative no-follow support")
    directory_fd = file_fd = None
    try:
        root_info = os.stat(root_real, follow_symlinks=False)
        if not stat.S_ISDIR(root_info.st_mode):
            raise ValueError("Audit JSON trusted root must be a directory")
        directory_fd = os.open(root_real, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if _identity(root_info) != _identity(os.fstat(directory_fd)):
            raise ValueError("Audit JSON trusted root changed while opening")
        for part in parts[:-1]:
            child_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            os.close(directory_fd)
            directory_fd = child_fd
        before = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Audit JSON input must be a regular file without symlinks")
        if before.st_size > MAX_JSON_BYTES:
            raise ValueError("Audit JSON input exceeds the 4 MiB limit")
        file_fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
        if _identity(before) != _identity(os.fstat(file_fd)):
            raise ValueError("Audit JSON input changed while opening")
        chunks, size = [], 0
        while True:
            chunk = os.read(file_fd, min(65536, MAX_JSON_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_JSON_BYTES:
                raise ValueError("Audit JSON input exceeds the 4 MiB limit")
        after = os.fstat(file_fd)
        named_after = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if _identity(before) != _identity(after) or _identity(after) != _identity(named_after):
            raise ValueError("Audit JSON input changed while reading")
        data = b"".join(chunks)
    except OSError as exc:
        raise ValueError("Audit JSON input is unavailable or contains a symlink") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
            parse_float=_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Audit JSON input must contain valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Audit JSON input must contain one object")
    return JsonSnapshot(value=value, sha256=hashlib.sha256(data).hexdigest())

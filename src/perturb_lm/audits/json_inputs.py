"""Bounded audit JSON/HGNC snapshots confined to the invocation directory (#30, #52)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_TSV_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class JsonSnapshot:
    value: dict
    sha256: str


@dataclass(frozen=True)
class TsvSnapshot:
    rows: list[dict]
    sha256: str


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _relative_parts(path, root_real):
    """Preserve descendant components; only aliases at/above the anchor are trusted."""
    absolute = Path(os.path.abspath(path))
    for ancestor in reversed((absolute, *absolute.parents)):
        if os.path.realpath(ancestor) == root_real:
            return absolute.relative_to(ancestor).parts
    raise ValueError("Audit input is outside its trusted root")


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


def _read_snapshot_bytes(path: Path, *, root: Path, byte_limit: int) -> bytes:
    """Confine input and a narrowing root to the independently chosen current directory."""
    if ".." in Path(path).parts or ".." in Path(root).parts:
        raise ValueError("Audit input/root must not contain parent traversal")
    anchor_real = os.path.realpath(Path.cwd())
    root_real = os.path.realpath(root)
    if root_real != anchor_real and not root_real.startswith(anchor_real.rstrip(os.sep) + os.sep):
        raise ValueError("Audit input root is outside the invocation directory")
    candidate = os.path.realpath(path)
    if not candidate.startswith(root_real.rstrip(os.sep) + os.sep):
        raise ValueError("Audit input is outside its trusted root")
    root_parts = _relative_parts(root, anchor_real)
    parts = _relative_parts(path, anchor_real)
    if parts[:len(root_parts)] != root_parts:
        raise ValueError("Audit input is outside its trusted root")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Audit input must name a file beneath its trusted root")
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if not all(hasattr(os, name) for name in required_flags) or os.open not in os.supports_dir_fd:
        raise ValueError("Safe audit reads require descriptor-relative no-follow support")
    directory_fd = file_fd = None
    try:
        root_info = os.stat(".", follow_symlinks=False)
        if not stat.S_ISDIR(root_info.st_mode):
            raise ValueError("Audit invocation directory must be a directory")
        directory_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if _identity(root_info) != _identity(os.fstat(directory_fd)):
            raise ValueError("Audit invocation directory changed while opening")
        for part in parts[:-1]:
            child_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            os.close(directory_fd)
            directory_fd = child_fd
        before = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Audit input must be a regular file without symlinks")
        if before.st_size > byte_limit:
            raise ValueError("Audit input exceeds its byte limit")
        file_fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
        if _identity(before) != _identity(os.fstat(file_fd)):
            raise ValueError("Audit input changed while opening")
        chunks, size = [], 0
        while True:
            chunk = os.read(file_fd, min(65536, byte_limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > byte_limit:
                raise ValueError("Audit input exceeds its byte limit")
        after = os.fstat(file_fd)
        named_after = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if _identity(before) != _identity(after) or _identity(after) != _identity(named_after):
            raise ValueError("Audit input changed while reading")
        data = b"".join(chunks)
    except OSError as exc:
        raise ValueError("Audit input is unavailable or contains a symlink") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    return data


def read_json_snapshot(path: Path, *, root: Path) -> JsonSnapshot:
    """Parse/hash one 4 MiB JSON snapshot beneath a root narrowing the current directory.

    The invocation directory is the independent trust anchor. A caller may select
    a narrower input directory; root arguments cannot authorize paths outside the
    invocation directory. Aliases above that anchor remain valid on macOS, while
    all descendants are opened descriptor-relatively with O_NOFOLLOW.
    """
    data = _read_snapshot_bytes(path, root=root, byte_limit=MAX_JSON_BYTES)
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


def read_tsv_snapshot(path: Path, *, root: Path) -> TsvSnapshot:
    """Parse/hash one bounded UTF-8 TSV snapshot using the same directory policy.

    The fixed 32 MiB cap accommodates the pinned 16,982,321-byte HGNC reference.
    This preserves csv.DictReader's existing tab-delimited field semantics.
    """
    data = _read_snapshot_bytes(path, root=root, byte_limit=MAX_TSV_BYTES)
    try:
        stream = io.StringIO(data.decode("utf-8"), newline="")
        rows = list(csv.DictReader(stream, delimiter="\t"))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Audit TSV input must contain valid UTF-8 tabular text") from exc
    return TsvSnapshot(rows=rows, sha256=hashlib.sha256(data).hexdigest())

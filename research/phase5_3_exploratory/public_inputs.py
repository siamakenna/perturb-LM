"""Bounded, pinned public inputs for one exploratory four-plate CPJUMP1 cohort.

This reconstructs four public plates. It does not verify or recreate the prior
private twelve-file cohort. Fetching never imports or executes downloaded code.
Call the loader only after the exploratory protocol has been frozen.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import re
import selectors
import shutil
import ssl
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.audits.cohort import (
    BATCH, CONDITIONS, KIND, REPO, REVISION, clean, join_cohort, source_tables,
)
from perturb_lm.audits.rotations import PLATES, _validate

MAX_PROFILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_PROFILE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 1024 * 1024
MAX_DECOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_POINTER_BYTES = 4096
MAX_MANIFEST_BYTES = 256 * 1024
FEATURE_PREFIXES = ("Cells_", "Cytoplasm_", "Nuclei_", "Image_")
ORIGIN = "public_reconstructed_four_plate_cohort_not_original_twelve_file_verification"
SOURCE_PATHS = (
    "benchmark/output/experiment-metadata.tsv",
    "README.md",
    "benchmark/0.create-experiment-metadata.ipynb",
    f"metadata/platemaps/{BATCH}/barcode_platemap.csv",
    *(
        path
        for modality in ("compound", "crispr", "orf")
        for path in (
            f"metadata/platemaps/{BATCH}/platemap/JUMP-Target-1_{modality}_platemap.txt",
            f"metadata/external_metadata/JUMP-Target-1_{modality}_metadata.tsv",
        )
    ),
    "metadata/external_metadata/JUMP-Target-1_compound_metadata_targets.tsv",
)
PROFILE_PATHS = tuple(
    f"profiles/{BATCH}/{plate}/{plate}_{KIND}.csv.gz" for plate in PLATES
)
METADATA_COLUMNS = (
    "row_id", "plate", "well", "gene", "reagent", "sequence", "condition",
    "treatment", "control", "pert_type", "control_type", "negcon_control_type",
)
BOUNDS = {
    "compressed_profile_bytes_per_file": MAX_PROFILE_BYTES,
    "compressed_profile_bytes_total": MAX_TOTAL_PROFILE_BYTES,
    "source_bytes_per_file": MAX_SOURCE_BYTES,
    "decompressed_profile_bytes_per_file": MAX_DECOMPRESSED_BYTES,
}
_HOSTS = {"raw.githubusercontent.com", "media.githubusercontent.com"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{REVISION}/{path}"


def _media_url(path: str) -> str:
    return f"https://media.githubusercontent.com/media/{REPO}/{REVISION}/{path}"


class _PinnedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (
            parsed.scheme != "https" or parsed.hostname not in _HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password
        ):
            raise ValueError("Refusing redirect outside the fixed public HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _urllib_url(url: str, limit: int) -> bytes:
    """Read at most limit+1 bytes, with normal certificate verification."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in _HOSTS:
        raise ValueError("Only the fixed public GitHub HTTPS hosts are allowed")
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), _PinnedRedirects()
    )
    request = urllib.request.Request(url, headers={"User-Agent": "phase53-bounded-public-inputs"})
    with opener.open(request, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and (not declared.isdecimal() or int(declared) > limit):
            raise ValueError("Public response exceeds its byte bound")
        output = bytearray()
        while True:
            chunk = response.read(min(65536, limit + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > limit:
                raise ValueError("Public response exceeds its byte bound")
        return bytes(output)


def _bounded_process(arguments: list[str], limit: int) -> bytes:
    """Bound subprocess stdout and duration; never echo credentials or response errors."""
    process = subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    output = bytearray()
    deadline = time.monotonic() + 40
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError("Bounded public-file request timed out")
                chunk = os.read(process.stdout.fileno(), min(65536, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > limit:
                    raise ValueError("Public subprocess response exceeds its byte bound")
        if process.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
            raise RuntimeError("Could not retrieve the fixed pinned public file with verified TLS")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()


def _download_url(url: str, limit: int) -> bytes:
    """Try verified urllib, then verified system curl (helpful on macOS)."""
    try:
        return _urllib_url(url, limit)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        curl = "/usr/bin/curl" if Path("/usr/bin/curl").is_file() else shutil.which("curl")
        if curl is None:
            raise RuntimeError("Verified-TLS public fetch failed; system curl is unavailable") from error
        # -q disables .curlrc. Redirects are disabled, so the fixed HTTPS URL
        # cannot silently become another host. Streaming enforces the hard cap.
        return _bounded_process([
            curl, "-q", "--fail", "--silent", "--show-error", "--proto", "=https",
            "--connect-timeout", "10", "--max-time", "35", "--max-filesize", str(limit),
            "--max-redirs", "0", url,
        ], limit)


def _gh_raw(gh: str, path: str, limit: int) -> bytes:
    """Resolve a pinned Git blob, then verify the raw Git object identity.

    The contents raw representation may expand LFS objects. The git/blobs API
    returns the actual committed object, so profile pointers stay small.
    """
    endpoint = f"repos/{REPO}/contents/{path}?ref={REVISION}"
    info_bytes = _bounded_process([
        gh, "api", "--hostname", "github.com", endpoint,
        "-H", "Accept: application/vnd.github+json",
    ], 2 * MAX_SOURCE_BYTES + 8192)
    info = json.loads(info_bytes)
    if (
        not isinstance(info, dict) or info.get("type") != "file" or info.get("path") != path
        or not isinstance(info.get("sha"), str) or re.fullmatch("[0-9a-f]{40}", info["sha"]) is None
    ):
        raise ValueError("GitHub did not resolve the exact pinned allowlisted Git blob")
    data = _bounded_process([
        gh, "api", "--hostname", "github.com", f"repos/{REPO}/git/blobs/{info['sha']}",
        "-H", "Accept: application/vnd.github.raw+json",
    ], limit)
    git_oid = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if git_oid != info["sha"]:
        raise ValueError("Raw public file differs from its pinned Git blob SHA-1")
    return data


def _get_raw(path: str, limit: int, gh: str | None) -> bytes:
    if gh is not None:
        return _gh_raw(gh, path, limit)
    try:
        return _download_url(_raw_url(path), limit)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as error:
        raise RuntimeError(
            "Pinned public metadata/pointer request failed; retry on the authorized "
            "Mac with its authenticated gh executable. No token is exported."
        ) from error


def _parse_pointer(data: bytes) -> tuple[str, int]:
    if len(data) > MAX_POINTER_BYTES:
        raise ValueError("Git LFS pointer exceeds its small-file bound")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("Expected a small Git LFS pointer, not profile contents") from error
    match = re.fullmatch(
        r"version https://git-lfs.github.com/spec/v1\r?\n"
        r"oid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)\r?\n?", text,
    )
    if match is None:
        raise ValueError("Pinned profile is not the expected Git LFS pointer; no fallback cohort")
    size = int(match.group(2))
    if not 0 < size <= MAX_PROFILE_BYTES:
        raise ValueError("LFS declared size exceeds the 16 MiB compressed per-file bound")
    return match.group(1), size


def _no_symlinks(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlink paths are not accepted for public input staging")


def _write_new(path: Path, data: bytes) -> None:
    _no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _no_symlinks(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def fetch_public_inputs(out: Path, gh: str | None = None) -> dict:
    """Capture only the fixed allowlist into a NEW private directory.

    Failure intentionally leaves an incomplete capture that the loader rejects.
    Existing directories, files and symlink paths are never overwritten.
    """
    out = Path(out).absolute()
    _no_symlinks(out)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(out, 0o700)
    marker = out / "CAPTURE_INCOMPLETE"
    _write_new(marker, b"Not loadable until all fixed public files are captured and verified.\n")
    source_receipts, profile_receipts = [], []
    for path in SOURCE_PATHS:
        data = _get_raw(path, MAX_SOURCE_BYTES, gh)
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("Public source file exceeds its 1 MiB bound")
        relative = f"source/{Path(path).name}"
        _write_new(out / relative, data)
        source_receipts.append({
            "path": relative, "source_path": path, "url": _raw_url(path),
            "bytes": len(data), "sha256": _sha(data),
        })
    total = 0
    for plate, path in zip(PLATES, PROFILE_PATHS, strict=True):
        pointer = _get_raw(path, MAX_POINTER_BYTES, gh)
        oid, declared_size = _parse_pointer(pointer)
        if total + declared_size > MAX_TOTAL_PROFILE_BYTES:
            raise ValueError("Selected profile capture exceeds the 64 MiB total bound")
        pointer_path = f"pointers/{plate}.lfs"
        _write_new(out / pointer_path, pointer)
        data = _download_url(_media_url(path), declared_size)
        if len(data) != declared_size or _sha(data) != oid:
            raise ValueError("Public profile does not match its pinned LFS size and SHA-256")
        _write_new(out / path, data)
        total += len(data)
        profile_receipts.append({
            "path": path, "source_path": path, "url": _media_url(path),
            "bytes": len(data), "sha256": oid, "lfs_oid_sha256": oid,
            "lfs_size": declared_size, "pointer_path": pointer_path,
            "pointer_url": _raw_url(path), "pointer_bytes": len(pointer),
            "pointer_sha256": _sha(pointer),
        })
    receipt = {
        "schema_version": 1, "status": "complete", "repository": REPO,
        "revision": REVISION, "batch": BATCH, "plates": list(PLATES),
        "cohort_origin": ORIGIN, "original_twelve_file_cohort_verified": False,
        "bounds": BOUNDS, "source_files": source_receipts, "profiles": profile_receipts,
    }
    _write_new(out / "manifest.json", _json_bytes(receipt))
    marker.unlink()
    return {
        "staging": str(out), "source": str(out / "source"),
        "profile_paths": [str(out / p) for p in PROFILE_PATHS],
        "manifest_path": str(out / "manifest.json"), "receipt": receipt,
    }


def _read_bounded(path: Path, limit: int) -> bytes:
    _no_symlinks(path)
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Input is not a bounded regular file")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Input exceeds its read bound")
        return data


def _verified_bytes(root: Path, entry: dict, limit: int) -> bytes:
    size, digest = entry.get("bytes"), entry.get("sha256")
    if type(size) is not int or not 0 <= size <= limit:
        raise ValueError("Invalid receipt byte count")
    if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
        raise ValueError("Invalid receipt SHA-256")
    data = _read_bounded(root / entry["path"], limit)
    if len(data) != size or _sha(data) != digest:
        raise ValueError("Captured bytes differ from their source receipt")
    return data


def _csv_frame(data: bytes, *, delimiter: str = ",", max_rows: int | None = None) -> pd.DataFrame:
    try:
        text = data.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        header = next(reader)
        if not header or any(not value for value in header) or len(set(header)) != len(header):
            raise ValueError("Duplicate or empty CSV/TSV header")
        records = []
        for row in reader:
            if max_rows is not None and len(records) >= max_rows:
                raise ValueError("Public profile exceeds the fixed 384-row plate bound")
            if len(row) != len(header):
                raise ValueError("CSV/TSV row does not match header width")
            records.append(row)
        return pd.DataFrame(records, columns=header)
    except (UnicodeDecodeError, csv.Error, StopIteration) as error:
        raise ValueError("Malformed public CSV/TSV") from error


def _decompress(data: bytes) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        result = stream.read(MAX_DECOMPRESSED_BYTES + 1)
    if len(result) > MAX_DECOMPRESSED_BYTES:
        raise ValueError("Profile exceeds the 32 MiB decompressed per-file bound")
    return result


def _capture_bytes(staging: Path) -> tuple[dict, dict[str, bytes], dict[str, bytes]]:
    """Verify every source and compressed profile BEFORE any feature parsing."""
    _no_symlinks(staging)
    if (staging / "CAPTURE_INCOMPLETE").exists():
        raise ValueError("Partial public capture cannot be loaded")
    receipt = json.loads(_read_bounded(staging / "manifest.json", MAX_MANIFEST_BYTES))
    expected = {
        "schema_version": 1, "status": "complete", "repository": REPO,
        "revision": REVISION, "batch": BATCH, "plates": list(PLATES),
        "cohort_origin": ORIGIN, "original_twelve_file_cohort_verified": False,
        "bounds": BOUNDS,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Capture is not the fixed pinned public four-plate cohort")
    sources, profiles = receipt.get("source_files"), receipt.get("profiles")
    if not isinstance(sources, list) or len(sources) != len(SOURCE_PATHS):
        raise ValueError("Incomplete or expanded source allowlist")
    if not isinstance(profiles, list) or len(profiles) != len(PROFILE_PATHS):
        raise ValueError("Exactly four prespecified profile receipts are required")
    source_bytes, profile_bytes = {}, {}
    expected_files = {"manifest.json"}
    for entry, path in zip(sources, SOURCE_PATHS, strict=True):
        relative = f"source/{Path(path).name}"
        if not isinstance(entry, dict) or (
            entry.get("path"), entry.get("source_path"), entry.get("url")
        ) != (relative, path, _raw_url(path)):
            raise ValueError("Source receipt is outside the pinned allowlist")
        source_bytes[Path(path).name] = _verified_bytes(staging, entry, MAX_SOURCE_BYTES)
        expected_files.add(relative)
    total = 0
    for entry, plate, path in zip(profiles, PLATES, PROFILE_PATHS, strict=True):
        pointer_path = f"pointers/{plate}.lfs"
        if not isinstance(entry, dict) or (
            entry.get("path"), entry.get("source_path"), entry.get("url"),
            entry.get("pointer_path"), entry.get("pointer_url")
        ) != (path, path, _media_url(path), pointer_path, _raw_url(path)):
            raise ValueError("Profile receipt is outside the fixed four-plate allowlist")
        pointer = _verified_bytes(staging, {
            "path": pointer_path, "bytes": entry.get("pointer_bytes"),
            "sha256": entry.get("pointer_sha256"),
        }, MAX_POINTER_BYTES)
        oid, size = _parse_pointer(pointer)
        if (entry.get("sha256"), entry.get("lfs_oid_sha256"), entry.get("bytes"),
            entry.get("lfs_size")) != (oid, oid, size, size):
            raise ValueError("Profile receipt contradicts the pinned LFS pointer")
        total += size
        if total > MAX_TOTAL_PROFILE_BYTES:
            raise ValueError("Compressed profile total exceeds its bound")
        profile_bytes[path] = _verified_bytes(staging, entry, MAX_PROFILE_BYTES)
        expected_files.update((path, pointer_path))
    actual_files = set()
    for path in staging.rglob("*"):
        _no_symlinks(path)
        if path.is_file():
            actual_files.add(path.relative_to(staging).as_posix())
    if actual_files != expected_files:
        raise ValueError("Capture contains missing or unreceipted files")
    return receipt, source_bytes, profile_bytes


def _source_from_bytes(staging: Path, sources: dict[str, bytes]):
    # source_tables is reused unchanged, but it sees private copies of the exact
    # bounded/hash-verified bytes rather than re-reading mutable staging paths.
    with tempfile.TemporaryDirectory(prefix=".verified-phase53-source-", dir=staging.parent) as temp:
        root = Path(temp)
        for name, data in sources.items():
            if Path(name).suffix in {".tsv", ".txt", ".csv"}:
                _csv_frame(data, delimiter="\t" if Path(name).suffix != ".csv" else ",")
            _write_new(root / name, data)
        return source_tables(root)


def _alignment_order(rows: pd.DataFrame, identities: dict[str, tuple[str, str]], keys: list) -> list[int]:
    positions = {key: i for i, key in enumerate(keys)}
    if len(positions) != len(keys) or len(rows) != len(keys):
        raise ValueError("Metadata/features have duplicate or missing physical row indices")
    order = []
    for row in rows.itertuples():
        key = (row.audit_file, row.audit_row)
        if identities.get(row.record_id) != key or key not in positions:
            raise ValueError("Metadata/features audit_file/audit_row alignment changed")
        order.append(positions[key])
    if len(set(order)) != len(keys):
        raise ValueError("Metadata/features row indices are not one-to-one")
    return order


def load_study_inputs(staging: Path) -> dict:
    """Load ALL 1536 selected rows, aligned to unchanged source feature values.

    Nonfinite feature values are retained for the analysis QC policy. Source
    annotations are exact metadata strings, never biological review labels.
    """
    staging = Path(staging).absolute()
    capture, sources, compressed = _capture_bytes(staging)
    experiments, barcodes, maps, annotations = _source_from_bytes(staging, sources)
    metadata_frames, feature_frames, keys, identities = [], [], [], {}
    feature_names = None
    for number, (plate, path) in enumerate(zip(PLATES, PROFILE_PATHS, strict=True)):
        frame = _csv_frame(_decompress(compressed[path]), max_rows=384)
        names = [name for name in frame if name.startswith(FEATURE_PREFIXES)]
        if not names or (feature_names is not None and names != feature_names):
            raise ValueError("Four plates must have the same nonempty ordered feature schema")
        feature_names = names
        metadata = frame[[name for name in frame if name.startswith("Metadata_")]].map(clean)
        if "Metadata_Plate" not in metadata or not metadata.Metadata_Plate.eq(plate).all():
            raise ValueError("Profile rows do not match their exact allowlisted plate file")
        if len(metadata) != 384:
            raise ValueError("Each public plate must contain exactly 384 rows")
        metadata["audit_file"] = path
        metadata["audit_row"] = np.arange(len(metadata)).astype(str)
        metadata["record_id"] = [f"file{number:03d}:row{i:06d}" for i in range(len(metadata))]
        metadata["path_batch"] = BATCH
        for row in metadata.itertuples():
            key = (path, row.audit_row)
            keys.append(key)
            identities[row.record_id] = key
        metadata_frames.append(metadata)
        feature_frames.append(frame[names])
    profiles = pd.concat(metadata_frames, ignore_index=True)
    joined = join_cohort(profiles, experiments, barcodes, maps, annotations)
    rows = _validate(joined)
    if len(rows) != 1536 or set(rows.Assay_Plate_Barcode) != set(PLATES):
        raise ValueError("The reconstructed cohort must contain all 1536 four-plate rows")
    if rows.annotation_conflict.map(lambda value: str(value).casefold() == "true").any():
        raise ValueError("Profile annotation contradicts its source annotation")
    if "target_sequence" not in rows:
        raise ValueError("Explicit pinned source target_sequence annotations are required")
    if "Metadata_target_sequence" in rows and not rows.Metadata_target_sequence.eq(rows.target_sequence).all():
        raise ValueError("Local and source target_sequence annotations disagree")
    order = _alignment_order(rows, identities, keys)
    # Conversion occurs only after all compressed/source receipts, joins and row
    # identities pass. Empty numeric fields are missing; bad text fails closed.
    raw_features = pd.concat(feature_frames, ignore_index=True)
    values = raw_features.to_numpy(dtype=str)
    values[np.char.strip(values) == ""] = "nan"
    try:
        features = values.astype(float)[order]
    except (TypeError, ValueError) as error:
        raise ValueError("Profile feature contains nonnumeric text") from error
    labeled = rows.broad_sample.ne("")
    pert_type = rows.Metadata_pert_type
    result = pd.DataFrame({
        "row_id": rows.record_id, "plate": rows.Assay_Plate_Barcode,
        "well": rows.well_position, "gene": rows.Metadata_gene,
        "reagent": rows.broad_sample, "sequence": rows.target_sequence,
        "condition": [json.dumps(tuple(row), separators=(",", ":")) for row in rows[CONDITIONS].itertuples(index=False, name=None)],
        "treatment": labeled & pert_type.eq("trt"),
        "control": labeled & pert_type.ne("trt"), "pert_type": pert_type,
        "control_type": rows.get("Metadata_control_type", rows.get("control_type", "")),
        "negcon_control_type": rows.get("Metadata_negcon_control_type", rows.get("negcon_control_type", "")),
    }, columns=METADATA_COLUMNS)
    ann = annotations[annotations.Perturbation.eq("crispr")].copy()
    if "target_sequence" not in ann or "gene" not in ann:
        raise ValueError("Pinned CRISPR annotations lack explicit sequence/gene fields")
    ann["canonical_sequence"] = ann.target_sequence.map(lambda value: clean(value).upper())
    valid = ann[ann.canonical_sequence.str.fullmatch("[ACGT]+")]
    receipt = {
        **capture, "selected_rows": len(result), "feature_count": len(feature_names),
        "feature_schema_sha256": _sha("\n".join(feature_names).encode()),
        "metadata_sha256": _sha(result.to_csv(index=False, lineterminator="\n").encode()),
        "missing_label_rows": int((~labeled).sum()),
        "labeled_treatment_rows": int(result.treatment.sum()),
        "labeled_control_rows": int(result.control.sum()),
        "nonfinite_feature_values_retained": int((~np.isfinite(features)).sum()),
        "source_sequences_shared_by_multiple_reagents": int(valid.groupby("canonical_sequence").broad_sample.nunique().gt(1).sum()),
        "source_sequences_with_multiple_gene_strings": int(valid.groupby("canonical_sequence").gene.nunique().gt(1).sum()),
        "annotation_semantics": "Exact source strings; no biological review, alias resolution or causal labels.",
        "upstream_normalization_scope": "source_batch_global",
        "normalization_note": "Public files already use batch-global normalization/feature selection; training-only preprocessing cannot undo it.",
    }
    return {"metadata": result, "features": features, "feature_names": list(feature_names), "receipt": receipt}

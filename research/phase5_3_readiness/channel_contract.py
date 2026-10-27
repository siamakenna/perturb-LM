"""Bounded five-channel inventory verification; no pixels, models or scoring.

The default digest binds the previously reviewed public two-site compound-image
inventory. A different digest must be explicitly supplied for another inventory.
This utility verifies bytes and declared grouping, not stain identity, image
registration, biological replication, or a suitable CRISPR study cohort.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

REVIEWED_SHA = "24f975b31929d3092f4f89a8f7f8e42445372e3245d207e98e75bfa38cb4cdc6"
CHANNELS = ("DNA", "ER", "RNA", "AGP", "Mito")
MAX_JSON_BYTES = 512 * 1024
MAX_FILES = 40
MAX_SITES = 8
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
SHA = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
WELL = re.compile(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])\Z")


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid declared " + label)
    return value


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid declared " + label)
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("Nonfinite JSON number")


def _relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Unsafe inventory-relative input path")
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or ".." in path.parts or len(path.parts) > 8
            or path.as_posix() != value or any(p in {"", ".", ".git"} for p in path.parts)):
        raise ValueError("Unsafe inventory-relative input path")
    return path.parts


@contextmanager
def _open_regular(root_fd, relative):
    """Walk below one canonical anchor using no-follow directory descriptors."""
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise ValueError("This platform lacks required no-follow file access")
    parts = _relative(relative)
    directory = os.dup(root_fd)
    descriptor = None
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                             dir_fd=directory)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Inventory inputs must be regular files")
        yield descriptor, before
        after = os.fstat(descriptor)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, k) != getattr(after, k) for k in fields):
            raise ValueError("An input changed during verification")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _bounded_bytes(descriptor, maximum):
    values, remaining = [], maximum + 1
    while remaining:
        value = os.read(descriptor, min(CHUNK_BYTES, remaining))
        if not value:
            break
        values.append(value)
        remaining -= len(value)
    result = b"".join(values)
    if len(result) > maximum:
        raise ValueError("Input byte limit exceeded")
    return result


def _verify(root_fd, inventory_name, expected_sha256):
    with _open_regular(root_fd, inventory_name) as (descriptor, info):
        if info.st_size > MAX_JSON_BYTES:
            raise ValueError("Inventory JSON exceeds its byte limit")
        raw = _bounded_bytes(descriptor, MAX_JSON_BYTES)
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha256:
        raise ValueError("Inventory checksum mismatch")
    data = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(data, dict) or data.get("status") != "raw_download_complete":
        raise ValueError("Expected a completed raw-download inventory")
    files = data.get("files")
    if not isinstance(files, list) or not 5 <= len(files) <= MAX_FILES:
        raise ValueError("Inventory file-count limit or schema mismatch")
    mapping = data.get("channel_mapping")
    if (not isinstance(mapping, dict) or set(mapping) != set(CHANNELS)
            or any(not isinstance(v, str) or not v or len(v) > 128 for v in mapping.values())
            or len(set(mapping.values())) != len(CHANNELS)):
        raise ValueError("The declared channel mapping must contain five unique channels")
    required = {"record_id", "batch", "plate", "well", "site", "channel", "path", "bytes",
                "sha256", "pixelWidth", "pixelHeight", "bitsPerSample", "samplesPerPixel"}
    groups, identities, paths, inodes, plates, batches, shapes = {}, {}, set(), set(), set(), set(), set()
    total = 0
    for row in files:
        if not isinstance(row, dict) or not required <= row.keys():
            raise ValueError("Missing image inventory fields")
        record = _identifier(row["record_id"], "record identity")
        batch = _identifier(row["batch"], "batch identity")
        plate = _identifier(row["plate"], "plate identity")
        well = row["well"]
        if not isinstance(well, str) or not WELL.fullmatch(well):
            raise ValueError("Expected canonical 384-well coordinates such as A01")
        site = _integer(row["site"], "field identity", 1, 999)
        identity = (batch, plate, well, site)
        if record in groups and groups[record]["identity"] != identity:
            raise ValueError("Conflicting identity metadata within an image field")
        if identity in identities and identities[identity] != record:
            raise ValueError("Duplicate image-field identity under different record IDs")
        identities[identity] = record
        if len(identities) > MAX_SITES:
            raise ValueError("Inventory image-field limit exceeded")
        channel = row["channel"]
        if channel not in CHANNELS:
            raise ValueError("Unrecognized fluorescence channel")
        if "mapping_column" in row and row["mapping_column"] != mapping[channel]:
            raise ValueError("Channel mapping contradicts an image entry")
        shape = (_integer(row["pixelHeight"], "height", 1, 100000),
                 _integer(row["pixelWidth"], "width", 1, 100000),
                 _integer(row["bitsPerSample"], "bit depth", 1, 64),
                 _integer(row["samplesPerPixel"], "samples per pixel", 1, 1))
        group = groups.setdefault(record, {"identity": identity, "shape": shape, "channels": set()})
        if group["shape"] != shape:
            raise ValueError("Declared image dimensions differ within a field")
        if channel in group["channels"]:
            raise ValueError("Duplicate fluorescence channel within a field")
        group["channels"].add(channel)
        relative = row["path"]
        _relative(relative)
        if relative in paths:
            raise ValueError("Duplicate image input path")
        paths.add(relative)
        declared_size = _integer(row["bytes"], "image bytes", 8, MAX_FILE_BYTES)
        expected_image_sha = row["sha256"]
        if not isinstance(expected_image_sha, str) or not SHA.fullmatch(expected_image_sha):
            raise ValueError("Malformed image checksum")
        total += declared_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Inventory total byte limit exceeded")
        with _open_regular(root_fd, relative) as (descriptor, info):
            if info.st_size != declared_size or info.st_size > MAX_FILE_BYTES:
                raise ValueError("Image byte size differs from the inventory")
            inode = (info.st_dev, info.st_ino)
            if inode in inodes:
                raise ValueError("Image files alias the same physical input")
            inodes.add(inode)
            digest, count, prefix = hashlib.sha256(), 0, b""
            while True:
                value = os.read(descriptor, CHUNK_BYTES)
                if not value:
                    break
                count += len(value)
                if count > declared_size or count > MAX_FILE_BYTES:
                    raise ValueError("Image byte limit exceeded during verification")
                if len(prefix) < 8:
                    prefix = (prefix + value)[:8]
                digest.update(value)
            if count != declared_size or digest.hexdigest() != expected_image_sha:
                raise ValueError("Image checksum mismatch")
            classic = prefix[:4] in {b"II*\x00", b"MM\x00*"}
            big = prefix in {b"II+\x00\x08\x00\x00\x00", b"MM\x00+\x00\x08\x00\x00"}
            if not (classic or big):
                raise ValueError("Image does not have a recognized TIFF signature")
        plates.add(plate); batches.add(batch); shapes.add(shape)
    if any(group["channels"] != set(CHANNELS) for group in groups.values()):
        raise ValueError("Every image field must have all five fluorescence channels")
    for key, expected in (("channel_files", len(files)), ("site_count", len(groups)), ("total_bytes", total)):
        if key in data and (type(data[key]) is not int or data[key] != expected):
            raise ValueError("Inventory aggregate count contradicts its image entries")
    return {
        "status": "VERIFIED_TECHNICAL_IMAGE_BYTES",
        "scope": "TECHNICAL_INPUT_ONLY_NOT_CRISPR_COHORT",
        "inventory_sha256": actual_sha,
        "image_fields": len(groups), "channel_files": len(files), "total_bytes": total,
        "channels": list(CHANNELS), "batches": sorted(batches), "plates": sorted(plates),
        "declared_image_shapes_yx_bits_samples": [list(v) for v in sorted(shapes)],
        "input_bytes_verified": True, "tiff_signatures_verified": True,
        "header_dimensions_verified": False, "channel_registration_verified": False,
        "pixels_decoded": False, "model_inference_performed": False,
        "study_cohort_established": False,
        "limitations": [
            "Dimensions, bit depth and stain identities remain inventory declarations; TIFF headers and pixels were not decoded.",
            "Byte integrity and complete channel groups do not establish registration, image quality, biological identity or replication.",
            "The reviewed two-site compound inventory does not establish a matched cross-guide CRISPR image cohort.",
        ],
    }


def inspect_inventory(path, expected_sha256=REVIEWED_SHA):
    """Verify a bounded local inventory and image bytes; return aggregates only."""
    if not isinstance(expected_sha256, str) or not SHA.fullmatch(expected_sha256):
        raise ValueError("Expected inventory SHA-256 must be explicit and valid")
    candidate = Path(path).expanduser()
    # Canonicalize ancestors above the confinement anchor, including /var aliases
    # on macOS. No symlinks are followed inside that anchor.
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    root_fd = None
    try:
        anchor = candidate.parent.resolve(strict=True)
        root_fd = os.open(anchor, flags)
        return _verify(root_fd, candidate.name, expected_sha256)
    except OSError as error:
        raise ValueError("Inventory inputs are unavailable, unsafe or not regular files") from error
    finally:
        if root_fd is not None:
            os.close(root_fd)

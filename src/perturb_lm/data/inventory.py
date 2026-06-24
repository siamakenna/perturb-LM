"""Local real-data inventory helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from perturb_lm.data.rxrx_common import find_metadata_files, normalize_dataset


EMBEDDING_EXTENSIONS = {".csv", ".parquet", ".npy", ".npz"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass(frozen=True)
class DataInventory:
    dataset: str
    data_root: str
    metadata_files: list[str]
    embedding_files: list[str]
    image_file_counts: dict[str, int]
    manifest_rows_checked: int
    manifest_image_paths_checked: int
    manifest_image_paths_found: int
    manifest_image_paths_missing: int
    missing_manifest_examples: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_local_dataset(
    dataset: str,
    data_root: Path,
    *,
    site_manifest: pd.DataFrame | None = None,
    image_check_limit: int = 200,
) -> DataInventory:
    """Inventory local metadata, embeddings, and optional manifest image paths."""

    dataset = normalize_dataset(dataset)
    data_root = Path(data_root)
    metadata_files = [str(path) for path in find_metadata_files(dataset, data_root)] if data_root.exists() else []
    embedding_files = [str(path) for path in find_embedding_files(data_root, dataset)] if data_root.exists() else []
    image_file_counts = count_image_files(data_root / dataset if (data_root / dataset).exists() else data_root)
    checked = found = missing = rows_checked = 0
    examples: list[str] = []
    if site_manifest is not None and len(site_manifest):
        rows_checked, checked, found, missing, examples = audit_manifest_image_paths(
            site_manifest,
            raw_root=data_root,
            limit=image_check_limit,
        )
    return DataInventory(
        dataset=dataset,
        data_root=str(data_root),
        metadata_files=metadata_files,
        embedding_files=embedding_files,
        image_file_counts=image_file_counts,
        manifest_rows_checked=rows_checked,
        manifest_image_paths_checked=checked,
        manifest_image_paths_found=found,
        manifest_image_paths_missing=missing,
        missing_manifest_examples=examples,
    )


def find_embedding_files(data_root: Path, dataset: str) -> list[Path]:
    """Find likely local embedding files without loading them."""

    roots = [data_root / dataset, data_root]
    found: list[Path] = []
    keywords = ("embed", "embedding", "feature", "features", "profile", "profiles")
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in EMBEDDING_EXTENSIONS:
                if any(keyword in path.name.lower() for keyword in keywords) and path not in found:
                    found.append(path)
    return found


def count_image_files(root: Path) -> dict[str, int]:
    """Count local image files by extension under a root."""

    counts = {extension: 0 for extension in sorted(IMAGE_EXTENSIONS)}
    if not root.exists():
        return counts
    for path in root.rglob("*"):
        suffix = path.suffix.lower()
        if path.is_file() and suffix in counts:
            counts[suffix] += 1
    return {extension: count for extension, count in counts.items() if count}


def audit_manifest_image_paths(
    site_manifest: pd.DataFrame,
    *,
    raw_root: Path,
    limit: int = 200,
) -> tuple[int, int, int, int, list[str]]:
    """Check whether image_path_ch* values in a manifest exist locally."""

    channel_columns = [column for column in site_manifest.columns if column.startswith("image_path_ch")]
    checked = found = missing = 0
    examples: list[str] = []
    frame = site_manifest.head(limit)
    for _, row in frame.iterrows():
        for column in channel_columns:
            value = row.get(column, "")
            if pd.isna(value) or str(value).strip() == "":
                continue
            checked += 1
            path = Path(str(value))
            if not path.is_absolute():
                path = raw_root / path
            if path.exists():
                found += 1
            else:
                missing += 1
                if len(examples) < 10:
                    examples.append(str(path))
    return len(frame), checked, found, missing, examples

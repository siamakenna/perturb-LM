"""Manifest-backed local datasets; loading is deliberately not estimator fitting."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

DATASETS = frozenset(
    {
        "synthetic",
        "CPJUMP1",
        "JUMP_cpg0016",
        "JUMP_cpg0000",
        "JUMP_cpg0002",
        "RxRx1",
        "RxRx19a",
        "PERISCOPE",
    }
)
RECORD_FIELDS = (
    "record_id",
    "dataset",
    "batch",
    "source",
    "plate",
    "well",
    "treatment",
    "perturbation",
    "gene",
    "compound",
    "replicate",
    "image_id",
    "profile_id",
    "split",
)


def present(value: object) -> bool:
    return (
        value is not None
        and not pd.isna(value)
        and str(value).strip().lower() not in {"", "nan", "none", "null", "<na>"}
    )


@dataclass(frozen=True)
class DatasetManifest:
    dataset: str
    version: str
    metadata_path: str
    metadata_sha256: str
    retrieval_unit: str = "well"
    representation_mode: str = "precomputed"
    access: str = "public"
    representation_path: str | None = None
    representation_sha256: str | None = None
    synthetic: bool = False

    def __post_init__(self):
        if self.dataset not in DATASETS or not self.version:
            raise ValueError("A supported dataset and nonempty data version are required")
        if self.retrieval_unit not in {"well", "treatment"}:
            raise ValueError("retrieval_unit must be well or treatment")
        if self.representation_mode not in {"computed", "precomputed"}:
            raise ValueError("representation_mode must be computed or precomputed")
        if self.access not in {"public", "restricted"}:
            raise ValueError("access must be public or restricted")
        for value in (self.metadata_path, self.representation_path):
            if value and (Path(value).is_absolute() or ".." in Path(value).parts or "://" in value):
                raise ValueError("Manifest paths must be relative to a caller-supplied local root")
        if not self.metadata_path:
            raise ValueError("metadata_path is required")
        if not isinstance(self.metadata_sha256, str):
            raise ValueError("metadata_sha256 must be a SHA-256 string")
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic must be a boolean")
        for value in (self.metadata_sha256, self.representation_sha256):
            if value is not None and (
                len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("Checksums must be lowercase SHA-256 hex")
        if bool(self.representation_path) != bool(self.representation_sha256):
            raise ValueError("Representation path and checksum must be supplied together")
        if self.dataset == "synthetic" and not self.synthetic:
            raise ValueError("Synthetic datasets must be labeled synthetic")

    def to_dict(self) -> dict:
        return asdict(self)


def validate_records(frame: pd.DataFrame, manifest: DatasetManifest) -> pd.DataFrame:
    missing = set(RECORD_FIELDS) - set(frame)
    if missing:
        raise ValueError(f"Missing record fields: {sorted(missing)}")
    if frame.empty or frame.record_id.duplicated().any() or not frame.record_id.map(present).all():
        raise ValueError("Records require unique nonempty record_id values")
    if set(frame.dataset) != {manifest.dataset}:
        raise ValueError("Record dataset differs from manifest")
    if not frame.split.isin(["train", "validation", "test", "unassigned"]).all():
        raise ValueError("Invalid split membership")
    if not (frame.image_id.map(present) | frame.profile_id.map(present)).all():
        raise ValueError("Every record requires an image_id or profile_id")
    # Missing biological/layout fields remain explicit and become evaluation exclusions.
    return frame.copy()


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ManifestDatasetAdapter:
    def __init__(self, manifest: DatasetManifest, root: Path | str, allow_restricted: bool = False):
        self.manifest = manifest
        self.root = Path(root)
        self.allow_restricted = allow_restricted

    def load(self) -> pd.DataFrame:
        if self.manifest.access == "restricted" and not self.allow_restricted:
            raise PermissionError("Restricted data requires allow_restricted=True and local access")
        path = (self.root / self.manifest.metadata_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Metadata symlink escapes the supplied data root")
        if file_checksum(path) != self.manifest.metadata_sha256:
            raise ValueError("Metadata checksum does not match manifest")
        return validate_records(pd.read_csv(path, dtype=str, keep_default_na=False), self.manifest)


class CPJUMP1MetadataAdapter(ManifestDatasetAdapter):
    """Normalize an existing local profile-metadata CSV, without reading feature matrices."""

    def load(self) -> pd.DataFrame:
        if self.manifest.dataset != "CPJUMP1":
            raise ValueError("CPJUMP1MetadataAdapter requires CPJUMP1")
        if self.manifest.access == "restricted" and not self.allow_restricted:
            raise PermissionError("Restricted data requires allow_restricted=True and local access")
        path = (self.root / self.manifest.metadata_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Metadata symlink escapes the supplied data root")
        if file_checksum(path) != self.manifest.metadata_sha256:
            raise ValueError("Metadata checksum does not match manifest")
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        aliases = {
            "batch": "Metadata_Batch",
            "plate": "Metadata_Plate",
            "well": "Metadata_Well",
            "treatment": "Metadata_broad_sample",
            "gene": "Metadata_gene",
            "compound": "Metadata_pert_iname",
            "perturbation": "Metadata_pert_id",
        }
        for key, alias in aliases.items():
            if key not in frame:
                frame[key] = frame[alias] if alias in frame else ""
        if "Metadata_Inferred_Batch" in frame:
            frame["batch"] = frame.batch.where(
                frame.batch.map(present), frame.Metadata_Inferred_Batch
            )
        for key in RECORD_FIELDS:
            if key not in frame:
                frame[key] = ""
        frame["dataset"] = "CPJUMP1"
        frame["split"] = frame.split.replace("", "unassigned")
        # File checksum + row offset is deterministic; no private path enters the ID.
        ids = [f"cpjump1:{self.manifest.metadata_sha256[:16]}:{i}" for i in range(len(frame))]
        frame["record_id"] = [v if present(v) else ids[i] for i, v in enumerate(frame.record_id)]
        frame["profile_id"] = frame.profile_id.where(frame.profile_id.map(present), frame.record_id)
        return validate_records(frame, self.manifest)

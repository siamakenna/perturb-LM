"""Schema-tested adapters for local user-supplied JUMP and RxRx files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.sklearn_api.contracts import canonical_well
from perturb_lm.sklearn_api.datasets import (
    RECORD_FIELDS,
    DatasetManifest,
    file_checksum,
    present,
    validate_records,
)

ADAPTERS = {
    "CPJUMP1": "jump",
    "JUMP_cpg0016": "jump",
    "JUMP_cpg0000": "jump",
    "JUMP_cpg0002": "jump",
    "RxRx1": "rxrx1",
    "RxRx19a": "rxrx19a",
    "synthetic": "normalized",
    "PERISCOPE": "normalized",
}
DEFAULT_COLUMNS = {
    "jump": {
        "record_id": "profile_id",
        "profile_id": "profile_id",
        "batch": "Metadata_Batch",
        "source": "Metadata_Source",
        "plate": "Metadata_Plate",
        "well": "Metadata_Well",
        "treatment": "Metadata_broad_sample",
        "gene": "Metadata_gene",
        "compound": "Metadata_compound_id",
        "perturbation": "Metadata_pert_id",
        "replicate": "Metadata_replicate",
        "split": "split",
        "perturbation_type": "Metadata_pert_type",
    },
    "rxrx1": {
        "record_id": "site_id",
        "image_id": "site_id",
        "batch": "experiment",
        "plate": "plate",
        "well": "well",
        "treatment": "sirna",
        "perturbation": "sirna",
        "gene": "gene",
        "replicate": "replicate",
        "split": "split",
        "source": "source",
    },
    "rxrx19a": {
        "record_id": "site_id",
        "image_id": "site_id",
        "batch": "experiment",
        "plate": "plate",
        "well": "well",
        "treatment": "treatment_id",
        "compound": "compound_id",
        "dose": "concentration",
        "timepoint": "timepoint",
        "replicate": "replicate",
        "split": "split",
        "source": "source",
    },
    "normalized": {key: key for key in RECORD_FIELDS},
}


@dataclass(frozen=True)
class AdapterConfig:
    columns: dict[str, str] = field(default_factory=dict)
    constants: dict[str, str] = field(default_factory=dict)
    record_unit: str = "profile"
    record_key_fields: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ("record_id", "treatment", "split")
    feature_columns: tuple[str, ...] = ()
    delimiter: str = ","

    def __post_init__(self):
        if self.record_unit not in {"treatment", "well", "profile", "image"}:
            raise ValueError("Unsupported record unit")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be one character")
        if set(self.constants) & {"record_id", "profile_id", "image_id", "representation_id"}:
            raise ValueError("Record identifiers cannot be supplied as shared constants")

    @classmethod
    def from_dict(cls, payload):
        payload = dict(payload)
        for key in ("record_key_fields", "required_fields", "feature_columns"):
            if key in payload:
                payload[key] = tuple(payload[key])
        return cls(**payload)


class LocalDatasetAdapter:
    """Column mappings are explicit; missing fields are reported, never inferred biologically."""

    def __init__(
        self,
        manifest: DatasetManifest,
        root: Path | str,
        config: AdapterConfig | None = None,
        allow_restricted: bool = False,
    ):
        self.manifest = manifest
        self.root = Path(root)
        self.config = config if config is not None else AdapterConfig()
        self.allow_restricted = allow_restricted

    def path(self, relative: str, digest: str | None = None) -> Path:
        if self.manifest.access == "restricted" and not self.allow_restricted:
            raise PermissionError("Restricted data requires explicit allow_restricted=True")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Data path escapes the authorized root")
        if not path.is_file():
            raise FileNotFoundError(f"needs_data: missing local manifest asset {relative}")
        if digest is not None and file_checksum(path) != digest:
            raise ValueError("Local asset checksum differs from dataset manifest")
        return path

    def load(self) -> pd.DataFrame:
        path = self.path(self.manifest.metadata_path, self.manifest.metadata_sha256)
        raw = pd.read_csv(path, sep=self.config.delimiter, dtype=str, keep_default_na=False)
        mapping = {**DEFAULT_COLUMNS[ADAPTERS[self.manifest.dataset]], **self.config.columns}
        for key, column in self.config.columns.items():
            if column not in raw:
                raise ValueError(f"Configured column missing: {key} <- {column}")
        frame = raw.copy()
        # Keep originals even if a target name overwrites a raw name.
        for column in raw:
            frame[f"original::{column}"] = raw[column]
        for target, source in mapping.items():
            if source in raw:
                frame[target] = raw[source]
        for key, value in self.config.constants.items():
            if key in frame and frame[key].map(present).any() and not frame[key].eq(value).all():
                raise ValueError(f"Constant conflicts with observed metadata: {key}")
            frame[key] = value
        frame["dataset"] = self.manifest.dataset
        if self.config.record_key_fields:
            keys = list(self.config.record_key_fields)
            if any(k not in frame or not frame[k].map(present).all() for k in keys):
                raise ValueError("Record key fields must be present and nonmissing")
            frame["record_id"] = [
                hashlib.sha256(json.dumps([self.manifest.dataset, *values]).encode()).hexdigest()[
                    :24
                ]
                for values in frame[keys].itertuples(index=False, name=None)
            ]
        for key in RECORD_FIELDS:
            if key not in frame:
                frame[key] = ""
        frame["split"] = frame.split.replace("", "unassigned")
        frame["well"] = frame.well.map(canonical_well)
        for key in ("gene", "compound", "treatment", "perturbation"):
            frame[key] = frame[key].str.normalize("NFKC").str.strip()
        if self.config.record_unit in {"profile", "image"}:
            field_name = self.config.record_unit + "_id"
            # This is a representation identifier, not a guessed biological label.
            frame[field_name] = frame[field_name].where(
                frame[field_name].map(present), frame.record_id
            )
        else:
            frame["profile_id"] = frame.profile_id.where(
                frame.profile_id.map(present), frame.record_id
            )
        if "representation_id" not in frame:
            frame["representation_id"] = frame.record_id
        for key in self.config.required_fields:
            if key not in frame or not frame[key].map(present).all():
                raise ValueError(f"Required metadata missing: {key}")
        if frame.representation_id.duplicated().any():
            raise ValueError("Duplicate representation identifiers")
        if self.config.record_unit == "well":
            keys = ["dataset", "source", "batch", "plate", "well"]
            if frame.duplicated(keys).any():
                raise ValueError("Duplicate physical well keys; aggregate explicitly")
        if self.config.record_unit == "treatment" and frame.treatment.duplicated().any():
            raise ValueError("Duplicate treatment records; aggregate explicitly")
        # Canonical fields used by query policies are never guessed from treatment IDs.
        for canonical, query_field in (
            ("gene", "Metadata_gene"),
            ("perturbation_type", "Metadata_pert_type"),
        ):
            if query_field not in frame and canonical in frame:
                frame[query_field] = frame[canonical]
        return validate_records(frame, self.manifest)

    def representations(self, frame: pd.DataFrame) -> np.ndarray:
        if self.manifest.representation_path:
            path = self.path(self.manifest.representation_path, self.manifest.representation_sha256)
            with np.load(path, allow_pickle=False) as saved:
                ids = saved["record_ids"].astype(str)
                matrix = saved["embeddings"]
            if ids.ndim != 1 or len(set(ids)) != len(ids):
                raise ValueError("Representation cache requires unique one-dimensional record_ids")
            if matrix.ndim != 2 or len(ids) != len(matrix):
                raise ValueError("Representation matrix/ID shape mismatch")
            expected = frame.representation_id.astype(str).tolist()
            if set(ids) != set(expected):
                raise ValueError("Representation IDs differ from metadata; no positional guessing")
            locations = {key: i for i, key in enumerate(ids)}
            matrix = matrix[[locations[key] for key in expected]]
        else:
            columns = list(self.config.feature_columns)
            if not columns or any(column not in frame for column in columns):
                raise ValueError(
                    "Provide explicit feature_columns or a checksummed representation NPZ"
                )
            matrix = frame[columns].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
        if matrix.ndim != 2 or not matrix.shape[1] or not np.isfinite(matrix).all():
            raise ValueError("Representations must be finite, nonempty two-dimensional arrays")
        return np.asarray(matrix, dtype=float)

    def validate(self, include_representations: bool = False) -> dict:
        frame = self.load()
        matrix = self.representations(frame) if include_representations else None
        # Synthetic fixtures establish schema behavior, never real-data validation.
        status = (
            "schema_tested"
            if self.manifest.synthetic
            else ("real_data_validated" if matrix is not None else "real_manifest_validated")
        )
        payload = {"manifest": self.manifest.to_dict(), "adapter": self.config.__dict__}
        return {
            "dataset": self.manifest.dataset,
            "status": status,
            "rows": len(frame),
            "record_unit": self.config.record_unit,
            "manifest_checksum": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
            "missing_fields": {key: int((~frame[key].map(present)).sum()) for key in RECORD_FIELDS},
            "unsupported_fields": [
                key for key in RECORD_FIELDS if not frame[key].map(present).any()
            ],
            "representation_shape": list(matrix.shape) if matrix is not None else None,
        }

"""Embedding loading and manifest alignment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EmbeddingLoadResult:
    ids: list[str]
    embeddings: np.ndarray
    manifest: pd.DataFrame
    matched: int
    unmatched: int

    @property
    def n_embeddings(self) -> int:
        return int(self.embeddings.shape[0])

    @property
    def dimension(self) -> int:
        return int(self.embeddings.shape[1]) if self.embeddings.ndim == 2 else 0

    def summary(self) -> dict[str, int]:
        return {
            "n_embeddings_loaded": self.n_embeddings,
            "embedding_dimension": self.dimension,
            "n_matched_to_manifest": self.matched,
            "n_unmatched": self.unmatched,
        }


def load_site_embeddings(
    path: Path,
    site_manifest: pd.DataFrame,
    *,
    id_column: str = "site_id",
    normalize: bool = True,
) -> EmbeddingLoadResult:
    ids, embeddings = _read_embeddings(Path(path), id_column=id_column)
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D matrix.")
    if normalize:
        embeddings = normalize_embeddings(embeddings)
    aligned_ids, aligned_embeddings, aligned_manifest, unmatched = align_embeddings_to_manifest(
        ids, embeddings, site_manifest, id_column=id_column
    )
    return EmbeddingLoadResult(
        ids=aligned_ids,
        embeddings=aligned_embeddings,
        manifest=aligned_manifest,
        matched=len(aligned_ids),
        unmatched=unmatched,
    )


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    matrix = np.asarray(embeddings, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def align_embeddings_to_manifest(
    ids: list[str],
    embeddings: np.ndarray,
    site_manifest: pd.DataFrame,
    *,
    id_column: str = "site_id",
) -> tuple[list[str], np.ndarray, pd.DataFrame, int]:
    if id_column not in site_manifest.columns:
        raise ValueError(f"Site manifest is missing ID column '{id_column}'.")
    if len(ids) != len(embeddings):
        raise ValueError("Embedding ID count does not match embedding row count.")

    by_id = {str(site_id): index for index, site_id in enumerate(ids)}
    keep_manifest_rows = []
    keep_embedding_rows = []
    keep_ids = []
    for manifest_index, site_id in site_manifest[id_column].astype(str).items():
        embedding_index = by_id.get(site_id)
        if embedding_index is None:
            continue
        keep_manifest_rows.append(manifest_index)
        keep_embedding_rows.append(embedding_index)
        keep_ids.append(site_id)
    unmatched = len(ids) - len(keep_ids)
    if not keep_ids:
        raise ValueError("No embeddings matched the site manifest.")
    aligned_manifest = site_manifest.loc[keep_manifest_rows].reset_index(drop=True)
    aligned_embeddings = embeddings[np.array(keep_embedding_rows)]
    return keep_ids, aligned_embeddings, aligned_manifest, unmatched


def _read_embeddings(path: Path, *, id_column: str) -> tuple[list[str], np.ndarray]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
        return _read_tabular_embeddings(frame, id_column)
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
        return _read_tabular_embeddings(frame, id_column)
    if suffix == ".npy":
        matrix = np.load(path)
        ids = [str(index) for index in range(len(matrix))]
        return ids, np.asarray(matrix, dtype=float)
    if suffix == ".npz":
        archive = np.load(path, allow_pickle=True)
        matrix_key = "embeddings" if "embeddings" in archive else archive.files[0]
        id_key = "ids" if "ids" in archive else id_column if id_column in archive else None
        matrix = np.asarray(archive[matrix_key], dtype=float)
        ids = [str(value) for value in archive[id_key]] if id_key else [str(index) for index in range(len(matrix))]
        return ids, matrix
    raise ValueError(f"Unsupported embedding format '{path.suffix}'. Expected CSV, parquet, npy, or npz.")


def _read_tabular_embeddings(frame: pd.DataFrame, id_column: str) -> tuple[list[str], np.ndarray]:
    if id_column not in frame.columns:
        raise ValueError(f"Embedding table is missing ID column '{id_column}'.")
    numeric = [
        column
        for column in frame.columns
        if column != id_column and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not numeric:
        raise ValueError("Embedding table does not contain numeric embedding columns.")
    return frame[id_column].astype(str).tolist(), frame[numeric].to_numpy(dtype=float)

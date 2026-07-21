"""Initial nearest-neighbor retrieval index."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from perturb_lm.retrieval.embeddings import EmbeddingLoadResult


@dataclass(frozen=True)
class SavedIndex:
    out_dir: Path
    metadata_path: Path
    embeddings_path: Path
    id_mapping_path: Path
    index_path: Path


@dataclass(frozen=True)
class LoadedSklearnIndex:
    index: NearestNeighbors
    embeddings: np.ndarray
    id_mapping: pd.DataFrame
    metadata: dict[str, object]


def nearest_neighbors(embeddings: np.ndarray, metadata: pd.DataFrame, top_k: int = 10) -> pd.DataFrame:
    """Return self-nearest neighbors for an embedding matrix and aligned metadata."""

    if len(embeddings) != len(metadata):
        raise ValueError("embeddings and metadata must have the same number of rows")
    model = NearestNeighbors(metric="cosine", n_neighbors=min(top_k + 1, len(metadata)))
    model.fit(embeddings)
    distances, indices = model.kneighbors(embeddings)
    rows = []
    for query_index, neighbors in enumerate(indices):
        rank = 0
        for distance, candidate_index in zip(distances[query_index], neighbors, strict=False):
            if candidate_index == query_index:
                continue
            rank += 1
            candidate = metadata.iloc[candidate_index]
            rows.append(
                {
                    "query_id": str(metadata.iloc[query_index].get("site_id", query_index)),
                    "rank": rank,
                    "site_id": candidate.get("site_id", candidate_index),
                    "score": 1.0 - float(distance),
                }
            )
            if rank == top_k:
                break
    return pd.DataFrame(rows)


def build_sklearn_index(embeddings: np.ndarray) -> NearestNeighbors:
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D matrix.")
    index = NearestNeighbors(metric="cosine", algorithm="brute")
    index.fit(embeddings)
    return index


def save_sklearn_index(
    result: EmbeddingLoadResult,
    out_dir: Path,
    *,
    dataset: str,
    id_column: str = "site_id",
) -> SavedIndex:
    """Save a simple sklearn index, normalized matrix, ID mapping, and metadata."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = build_sklearn_index(result.embeddings)

    embeddings_path = out_dir / "embeddings.npy"
    id_mapping_path = out_dir / "id_mapping.csv"
    metadata_path = out_dir / "index_metadata.json"
    index_path = out_dir / "sklearn_nearest_neighbors.pkl"

    np.save(embeddings_path, result.embeddings)
    pd.DataFrame({id_column: result.ids, "row_index": range(len(result.ids))}).to_csv(
        id_mapping_path, index=False
    )
    with index_path.open("wb") as handle:
        pickle.dump(index, handle)
    metadata = {
        "dataset": dataset,
        "backend": "sklearn-nearest-neighbors",
        "metric": "cosine",
        "id_column": id_column,
        **result.summary(),
        "faiss": "optional future backend; not required for Phase 1",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return SavedIndex(out_dir, metadata_path, embeddings_path, id_mapping_path, index_path)


def load_index_matrix(index_dir: Path) -> tuple[np.ndarray, pd.DataFrame, dict[str, object]]:
    index_dir = Path(index_dir)
    embeddings = np.load(index_dir / "embeddings.npy")
    id_mapping = pd.read_csv(index_dir / "id_mapping.csv")
    metadata = json.loads((index_dir / "index_metadata.json").read_text())
    return embeddings, id_mapping, metadata


def load_sklearn_index(index_dir: Path) -> LoadedSklearnIndex:
    """Load a saved sklearn index and its aligned matrix/metadata artifacts."""

    index_dir = Path(index_dir)
    embeddings, id_mapping, metadata = load_index_matrix(index_dir)
    with (index_dir / "sklearn_nearest_neighbors.pkl").open("rb") as handle:
        index = pickle.load(handle)
    return LoadedSklearnIndex(
        index=index,
        embeddings=embeddings,
        id_mapping=id_mapping,
        metadata=metadata,
    )

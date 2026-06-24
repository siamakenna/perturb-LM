"""Phase 1 text-to-image retrieval modes."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.data.rxrx_common import make_perturbation_key
from perturb_lm.retrieval.aggregate import aggregate_site_results
from perturb_lm.retrieval.embeddings import normalize_embeddings
from perturb_lm.retrieval.index import load_index_matrix
from perturb_lm.retrieval.text_embeddings import embed_query_text
from perturb_lm.schemas import validate_query_table, validate_site_manifest


LEXICAL_COLUMNS = [
    "perturbation_name",
    "perturbation_id",
    "condition_label",
    "cell_type",
    "perturbation_type",
]


def run_retrieval(
    queries: pd.DataFrame,
    site_manifest: pd.DataFrame,
    *,
    dataset: str,
    mode: str = "lexical",
    top_k: int = 50,
    seed: int = 0,
    index_dir: Path | None = None,
    text_embedding_mode: str = "hashing",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_query_table(queries)
    validate_site_manifest(site_manifest)
    candidates = prepare_candidates(site_manifest)
    mode = mode.lower()
    if mode == "lexical":
        site_results = lexical_retrieval(queries, candidates, dataset=dataset, top_k=top_k)
    elif mode == "random":
        site_results = random_site_retrieval(queries, candidates, dataset=dataset, top_k=top_k, seed=seed)
    elif mode in {"shuffled", "shuffled-label", "shuffled_label"}:
        site_results = shuffled_label_retrieval(queries, candidates, dataset=dataset, top_k=top_k, seed=seed)
    elif mode == "embedding":
        if index_dir is None:
            raise ValueError("--index is required for embedding retrieval mode.")
        site_results = embedding_retrieval(
            queries,
            candidates,
            dataset=dataset,
            index_dir=index_dir,
            text_embedding_mode=text_embedding_mode,
            top_k=top_k,
        )
    else:
        raise ValueError("mode must be lexical, random, shuffled, or embedding")
    perturbation_results = aggregate_site_results(site_results, method="max")
    return site_results, perturbation_results


def prepare_candidates(site_manifest: pd.DataFrame) -> pd.DataFrame:
    candidates = site_manifest.copy()
    if "perturbation_key" not in candidates.columns:
        candidates["perturbation_key"] = [
            make_perturbation_key(
                row.dataset,
                row.perturbation_id,
                row.perturbation_name,
                row.cell_type,
                row.condition_label,
                row.concentration,
            )
            for row in candidates.itertuples(index=False)
        ]
    return candidates


def lexical_retrieval(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    dataset: str,
    top_k: int,
) -> pd.DataFrame:
    candidate_text = candidates[LEXICAL_COLUMNS].fillna("").astype(str).agg(" ".join, axis=1)
    candidate_tokens = [set(_tokens(text)) for text in candidate_text]
    rows: list[dict[str, object]] = []
    for _, query in queries.iterrows():
        query_tokens = set(_tokens(query["query_text"]))
        scores = np.array([_lexical_score(query_tokens, tokens) for tokens in candidate_tokens])
        order = np.lexsort((candidates["site_id"].astype(str).to_numpy(), -scores))
        for rank, candidate_index in enumerate(order[:top_k], start=1):
            rows.append(_site_result_row(query, candidates.iloc[candidate_index], dataset, rank, scores[candidate_index]))
    return pd.DataFrame(rows)


def random_site_retrieval(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    dataset: str,
    top_k: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for _, query in queries.iterrows():
        order = rng.permutation(len(candidates))[:top_k]
        for rank, candidate_index in enumerate(order, start=1):
            rows.append(_site_result_row(query, candidates.iloc[candidate_index], dataset, rank, 1.0 / rank))
    return pd.DataFrame(rows)


def shuffled_label_retrieval(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    dataset: str,
    top_k: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shuffled = candidates.copy().reset_index(drop=True)
    shuffled["perturbation_key"] = rng.permutation(shuffled["perturbation_key"].astype(str).to_numpy())
    shuffled["perturbation_id"] = rng.permutation(shuffled["perturbation_id"].astype(str).to_numpy())
    return random_site_retrieval(queries, shuffled, dataset=dataset, top_k=top_k, seed=seed)


def embedding_retrieval(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    dataset: str,
    index_dir: Path,
    text_embedding_mode: str,
    top_k: int,
) -> pd.DataFrame:
    image_embeddings, id_mapping, metadata = load_index_matrix(index_dir)
    text_embeddings = normalize_embeddings(embed_query_text(queries, mode=text_embedding_mode, n_features=image_embeddings.shape[1]))
    if text_embeddings.shape[1] != image_embeddings.shape[1]:
        raise ValueError("Text and image embeddings must have the same dimensionality for embedding mode.")
    id_column = str(metadata.get("id_column", "site_id"))
    candidates_by_id = candidates.set_index(candidates[id_column].astype(str), drop=False)
    image_ids = id_mapping[id_column].astype(str).tolist()
    scores = text_embeddings @ image_embeddings.T
    rows: list[dict[str, object]] = []
    for query_index, (_, query) in enumerate(queries.iterrows()):
        order = np.argsort(scores[query_index])[::-1][:top_k]
        for rank, embedding_index in enumerate(order, start=1):
            site_id = image_ids[embedding_index]
            candidate = candidates_by_id.loc[site_id]
            rows.append(_site_result_row(query, candidate, dataset, rank, float(scores[query_index, embedding_index])))
    return pd.DataFrame(rows)


def write_retrieval_outputs(
    dataset: str,
    site_results: pd.DataFrame,
    perturbation_results: pd.DataFrame,
    out_dir: Path,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "site_csv": out_dir / f"{dataset}_site_retrieval_results.csv",
        "site_parquet": out_dir / f"{dataset}_site_retrieval_results.parquet",
        "perturbation_csv": out_dir / f"{dataset}_perturbation_retrieval_results.csv",
        "perturbation_parquet": out_dir / f"{dataset}_perturbation_retrieval_results.parquet",
    }
    site_results.to_csv(paths["site_csv"], index=False)
    site_results.to_parquet(paths["site_parquet"], index=False)
    perturbation_results.to_csv(paths["perturbation_csv"], index=False)
    perturbation_results.to_parquet(paths["perturbation_parquet"], index=False)
    return paths


def _tokens(text: object) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _lexical_score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = len(query_tokens & candidate_tokens)
    return overlap / len(query_tokens | candidate_tokens)


def _site_result_row(
    query: pd.Series,
    candidate: pd.Series,
    dataset: str,
    rank: int,
    score: float,
) -> dict[str, object]:
    return {
        "query_id": query["query_id"],
        "dataset": dataset,
        "rank": int(rank),
        "site_id": candidate["site_id"],
        "perturbation_key": candidate["perturbation_key"],
        "perturbation_id": candidate["perturbation_id"],
        "score": float(score),
        "experiment": candidate.get("experiment", ""),
        "plate": candidate.get("plate", ""),
        "well": candidate.get("well", ""),
        "site": candidate.get("site", ""),
        "cell_type": candidate.get("cell_type", ""),
        "condition_label": candidate.get("condition_label", ""),
    }

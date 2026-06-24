#!/usr/bin/env python3
"""Run perturbation/profile-level cosine retrieval on JUMP pilot profiles."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.metrics.pairwise import cosine_similarity


NULL_LABELS = {"", "nan", "none", "null", "<na>"}


def clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def valid_label_mask(labels: np.ndarray) -> np.ndarray:
    return np.array([label.lower() not in NULL_LABELS for label in labels], dtype=bool)


def load_profiles(manifest_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    frames = []
    for path in manifest["path"]:
        frame = pd.read_csv(path)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [col for col in frame.columns if not col.startswith("Metadata_") and pd.api.types.is_numeric_dtype(frame[col])]


def aggregate_profiles(frame: pd.DataFrame, label_column: str, feature_cols: list[str]) -> pd.DataFrame:
    work = frame.copy()
    work[label_column] = work[label_column].map(clean_label)
    work = work[valid_label_mask(work[label_column].to_numpy())]
    grouped = work.groupby(label_column, dropna=True)[feature_cols].mean()
    counts = work.groupby(label_column).size().rename("n_wells")
    meta = counts.to_frame()
    return grouped.join(meta)


def retrieval_metrics(labels: list[str], matrix: np.ndarray, top_k: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_query_rows = []
    top_hit_rows = []
    n = len(labels)

    for i, label in enumerate(labels):
        scores = matrix[i].copy()
        scores[i] = -np.inf

        # At the aggregated perturbation level each label appears once, so there is
        # no same-label positive after self-removal. We therefore use nearest-neighbor
        # inspection here and reserve AP for well-level retrieval below if needed.
        order = np.argsort(scores)[::-1]
        for rank, j in enumerate(order[: max(top_k)], start=1):
            top_hit_rows.append(
                {
                    "query_label": label,
                    "rank": rank,
                    "hit_label": labels[j],
                    "cosine_similarity": float(scores[j]),
                }
            )

        per_query_rows.append(
            {
                "query_label": label,
                "top1_label": labels[order[0]] if len(order) else "",
                "top1_cosine_similarity": float(scores[order[0]]) if len(order) else np.nan,
            }
        )

    return pd.DataFrame(per_query_rows), pd.DataFrame(top_hit_rows)


def random_hit_probability(num_candidates: int, num_positives: int, k: int) -> float:
    if num_candidates <= 0 or num_positives <= 0 or k <= 0:
        return 0.0
    k = min(k, num_candidates)
    num_negatives = num_candidates - num_positives
    if k > num_negatives:
        return 1.0
    log_no_hit = (
        math.lgamma(num_negatives + 1)
        - math.lgamma(k + 1)
        - math.lgamma(num_negatives - k + 1)
        - math.lgamma(num_candidates + 1)
        + math.lgamma(k + 1)
        + math.lgamma(num_candidates - k + 1)
    )
    return float(1.0 - math.exp(log_no_hit))


def well_level_replicate_metrics(frame: pd.DataFrame, label_column: str, feature_cols: list[str], top_k: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = frame[label_column].map(clean_label).to_numpy(dtype=str)
    valid = valid_label_mask(labels)
    x = frame.loc[valid, feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=float)
    labels = labels[valid]

    if len(labels) < 3:
        return pd.DataFrame(), pd.DataFrame()

    sim = cosine_similarity(x)
    np.fill_diagonal(sim, -np.inf)

    rows = []
    hits = []
    for i, label in enumerate(labels):
        positives = labels == label
        positives[i] = False
        if positives.sum() == 0:
            continue
        scores = sim[i]
        y_true = positives.astype(int)
        finite_scores = np.where(np.isfinite(scores), scores, -1e9)
        ap = average_precision_score(y_true, finite_scores)
        order = np.argsort(scores)[::-1]
        row = {
            "query_index": i,
            "query_label": label,
            "average_precision": float(ap),
            "n_positives": int(positives.sum()),
            "random_average_precision_approx": float(positives.sum() / max(len(labels) - 1, 1)),
        }
        for k in top_k:
            top = order[:k]
            row[f"recall_at_{k}"] = float(positives[top].sum() / positives.sum())
            row[f"hit_at_{k}"] = float(positives[top].any())
            row[f"random_hit_at_{k}"] = random_hit_probability(len(labels) - 1, int(positives.sum()), k)
        rows.append(row)
        for rank, j in enumerate(order[: max(top_k)], start=1):
            hits.append(
                {
                    "query_index": i,
                    "query_label": label,
                    "rank": rank,
                    "hit_label": labels[j],
                    "is_positive": bool(positives[j]),
                    "cosine_similarity": float(scores[j]),
                }
            )

    return pd.DataFrame(rows), pd.DataFrame(hits)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("data/interim/jump_pilot_profile_files.csv"))
    parser.add_argument("--label-column", default="Metadata_broad_sample")
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--out-dir", type=Path, default=Path("results/week1"))
    args = parser.parse_args()

    profiles = load_profiles(args.manifest)
    if args.label_column not in profiles.columns:
        raise ValueError(f"{args.label_column} not found in profile columns")

    features = feature_columns(profiles)
    if not features:
        raise ValueError("No numeric feature columns found")

    profiles[features] = profiles[features].replace([np.inf, -np.inf], np.nan).fillna(0)

    aggregated = aggregate_profiles(profiles, args.label_column, features)
    x = aggregated[features].to_numpy(dtype=float)
    labels = list(aggregated.index.astype(str))
    sim = cosine_similarity(x)
    per_perturbation, perturbation_hits = retrieval_metrics(labels, sim, args.top_k)
    well_metrics, well_hits = well_level_replicate_metrics(profiles, args.label_column, features, args.top_k)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    per_perturbation.to_csv(args.out_dir / "profile_retrieval_per_perturbation.csv", index=False)
    perturbation_hits.to_csv(args.out_dir / "profile_retrieval_top_hits.csv", index=False)
    well_metrics.to_csv(args.out_dir / "well_replicate_retrieval_per_query.csv", index=False)
    well_hits.to_csv(args.out_dir / "well_replicate_retrieval_top_hits.csv", index=False)

    summary_rows = [
        {
            "level": "perturbation_profile",
            "n_profiles": len(labels),
            "metric": "top1_cosine_similarity_mean",
            "value": float(per_perturbation["top1_cosine_similarity"].mean()) if len(per_perturbation) else np.nan,
        }
    ]
    if len(well_metrics):
        summary_rows.append(
            {
                "level": "well_replicate",
                "n_profiles": len(profiles),
                "metric": "mean_average_precision",
                "value": float(well_metrics["average_precision"].mean()),
                }
            )
        summary_rows.append(
            {
                "level": "well_replicate",
                "n_profiles": len(profiles),
                "metric": "random_mean_average_precision_approx",
                "value": float(well_metrics["random_average_precision_approx"].mean()),
            }
        )
        for k in args.top_k:
            observed_hit = float(well_metrics[f"hit_at_{k}"].mean())
            random_hit = float(well_metrics[f"random_hit_at_{k}"].mean())
            summary_rows.append(
                {
                    "level": "well_replicate",
                    "n_profiles": len(profiles),
                    "metric": f"mean_hit_at_{k}",
                    "value": observed_hit,
                }
            )
            summary_rows.append(
                {
                    "level": "well_replicate",
                    "n_profiles": len(profiles),
                    "metric": f"random_mean_hit_at_{k}",
                    "value": random_hit,
                }
            )
            summary_rows.append(
                {
                    "level": "well_replicate",
                    "n_profiles": len(profiles),
                    "metric": f"hit_at_{k}_enrichment_over_random",
                    "value": observed_hit / random_hit if random_hit else np.nan,
                }
            )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(args.out_dir / "profile_retrieval_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote outputs to {args.out_dir}")


if __name__ == "__main__":
    main()

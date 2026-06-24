"""Batch-aware split helpers for Phase 1 validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from perturb_lm.data.rxrx_common import make_perturbation_key


def assign_held_out_well_split(
    site_manifest: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign splits by whole wells, keeping all sites from a well together."""

    return assign_group_split(
        site_manifest,
        ["experiment", "plate", "well"],
        test_fraction=test_fraction,
        val_fraction=val_fraction,
        seed=seed,
        split_column=split_column,
    )


def assign_held_out_image_split(
    site_manifest: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign splits by individual site/image IDs."""

    return assign_group_split(
        site_manifest,
        ["site_id"],
        test_fraction=test_fraction,
        val_fraction=val_fraction,
        seed=seed,
        split_column=split_column,
    )


def assign_held_out_plate_split(
    site_manifest: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign splits by whole experiment/plate groups."""

    return assign_group_split(
        site_manifest,
        ["experiment", "plate"],
        test_fraction=test_fraction,
        val_fraction=val_fraction,
        seed=seed,
        split_column=split_column,
    )


def assign_held_out_batch_split(
    site_manifest: pd.DataFrame,
    *,
    batch_columns: list[str] | None = None,
    test_fraction: float = 0.2,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign splits by whole acquisition batches."""

    columns = batch_columns or ["experiment"]
    return assign_group_split(
        site_manifest,
        columns,
        test_fraction=test_fraction,
        val_fraction=val_fraction,
        seed=seed,
        split_column=split_column,
    )


def assign_held_out_perturbation_split(
    site_manifest: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign splits by perturbation labels when perturbation IDs are available."""

    work = site_manifest.copy()
    if "perturbation_key" not in work.columns:
        required = [
            "dataset",
            "perturbation_id",
            "perturbation_name",
            "cell_type",
            "condition_label",
            "concentration",
        ]
        missing = [column for column in required if column not in work.columns]
        if missing:
            raise ValueError(
                "Cannot assign perturbation splits without perturbation_key or columns: "
                + ", ".join(missing)
            )
        work["perturbation_key"] = [
            make_perturbation_key(
                row.dataset,
                row.perturbation_id,
                row.perturbation_name,
                row.cell_type,
                row.condition_label,
                row.concentration,
            )
            for row in work.itertuples(index=False)
        ]
    if (work["perturbation_key"].astype(str).str.strip() == "").all():
        raise ValueError("Cannot assign perturbation splits because perturbation labels are empty.")
    return assign_group_split(
        work,
        ["perturbation_key"],
        test_fraction=test_fraction,
        val_fraction=val_fraction,
        seed=seed,
        split_column=split_column,
    )


def assign_group_split(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    test_fraction: float,
    val_fraction: float = 0.0,
    seed: int = 0,
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign train/val/test labels by group without splitting a group across labels."""

    _validate_fractions(test_fraction, val_fraction)
    missing = [column for column in group_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Cannot split by missing column(s): {', '.join(missing)}")

    work = frame.copy()
    group_key = _group_key(work, group_columns)
    groups = np.array(sorted(group_key.unique().astype(str)))
    rng = np.random.default_rng(seed)
    groups = rng.permutation(groups)

    n_groups = len(groups)
    n_test = _fraction_count(n_groups, test_fraction)
    n_val = _fraction_count(n_groups - n_test, val_fraction)
    test_groups = set(groups[:n_test])
    val_groups = set(groups[n_test : n_test + n_val])

    work[split_column] = "train"
    work.loc[group_key.isin(val_groups), split_column] = "val"
    work.loc[group_key.isin(test_groups), split_column] = "test"
    return work


def _group_key(frame: pd.DataFrame, group_columns: list[str]) -> pd.Series:
    return frame[group_columns].fillna("").astype(str).agg("::".join, axis=1)


def _validate_fractions(test_fraction: float, val_fraction: float) -> None:
    if not 0 <= test_fraction < 1:
        raise ValueError("test_fraction must be >= 0 and < 1.")
    if not 0 <= val_fraction < 1:
        raise ValueError("val_fraction must be >= 0 and < 1.")
    if test_fraction + val_fraction >= 1:
        raise ValueError("test_fraction + val_fraction must be < 1.")


def _fraction_count(n_items: int, fraction: float) -> int:
    if n_items <= 1 or fraction <= 0:
        return 0
    return max(1, int(round(n_items * fraction)))
